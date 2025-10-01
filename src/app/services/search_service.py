import os
import json
import re
from typing import List, Tuple
from ..services.mongo_service import connect_to_mongodb
from ..models.model import QuestionRequest
from ..services.openai_service import get_embedding,chat_completion,generate_chat_title
from ..services.redis_service import redis_client, redis_key, chat_meta_key, iso_utc_now, update_chat_meta_on_message, update_chat_order
from dotenv import load_dotenv
from fastapi import HTTPException


def document_search(doc_ids: List[str], request: QuestionRequest, chat_context: str, openai_client) -> Tuple[str, List[str], List[str], bool]:
    # ----------------- If doc_ids provided: build document context -----------------
    doc_context_block = "No referenced documents."
    snippets = []
    doc_tags = []
    up_client, up_coll = connect_to_mongodb("upload")
    if up_client is not None and up_coll is not None:
        try:
            cur = up_coll.find({"id": {"$in": doc_ids}}, {"id": 1, "file_name": 1, "text": 1})
            for d in cur:
                file_name = d.get("file_name") or "Unnamed"
                if file_name not in doc_tags:
                    doc_tags.append(file_name)
                text = (d.get("text", "") or "").strip()
                snippets.append(f"[DOC {d.get('id')} | {file_name}]\n{text}")
        except Exception:
            pass
        finally:
            try:
                up_client.close()
            except Exception:
                pass
    if snippets:
        doc_context_block = "\n\n".join(snippets)

    prompt = f"""You are an AI assistant constrained to ONLY the provided reference documents.

Your first task: Determine if the documents contain sufficient explicit information to answer the user's question accurately (not partially, not by guess, not by outside knowledge).

HAS_ANSWER criteria (must be True ONLY if ALL are satisfied):
1. The documents explicitly contain the key facts needed.
2. No required fact must be inferred from outside knowledge.
3. No critical ambiguity remains that would materially change the answer.

If any of the above are not met, set HAS_ANSWER: False.

If HAS_ANSWER is False you MUST:
- Output: HAS_ANSWER: False
- For ANSWER section output EXACTLY: "I cannot answer based on the provided documents."
- Still produce 3 exploratory follow-up questions (label uncertain ones with (Exploratory)).

If HAS_ANSWER is True:
- Output: HAS_ANSWER: True
- Provide a concise, professional, strictly evidence-grounded bulleted answer.
- Do NOT invent or embellish.
- If documents conflict, note the conflict briefly.

ALWAYS follow this exact output template:

HAS_ANSWER: True or False
ANSWER:
<bulleted answer OR "I cannot answer based on the provided documents.">
FOLLOW_UP_QUESTIONS:
1. ...
2. ...
3. ...

Previous conversation (style only; never a source of new facts):
{chat_context or 'None'}

Reference documents (authoritative scope; may be truncated):
{doc_context_block}

User question:
{request.question}
"""

    llm_resp = chat_completion(
        openai_client,
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Helpful technical assistant that never fabricates unsupported facts."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=750
    )
    raw_content = llm_resp.choices[0].message.content.strip()

    # Default parsing
    has_answer = False
    answer_text = raw_content
    follow_up_questions: List[str] = []

    # Extract HAS_ANSWER
    m = re.search(r"HAS_ANSWER:\s*(True|False)", raw_content, re.IGNORECASE)
    if m:
        has_answer = m.group(1).lower() == "true"

    # Split sections
    if "ANSWER:" in raw_content:
        after_answer = raw_content.split("ANSWER:", 1)[1]
        if "FOLLOW_UP_QUESTIONS:" in after_answer:
            ans_part, fu_part = after_answer.split("FOLLOW_UP_QUESTIONS:", 1)
            answer_text = ans_part.strip()
            # Parse follow-ups
            for line in fu_part.strip().splitlines():
                line = line.strip()
                if not line:
                    continue
                if line[0].isdigit():
                    line = re.sub(r"^\d+[\).]?\s*", "", line)
                if line:
                    follow_up_questions.append(line)
            follow_up_questions = follow_up_questions[:3]

    # Clean answer_text if it still has HAS_ANSWER line
    answer_text = re.sub(r"^HAS_ANSWER:\s*(True|False)\s*", "", answer_text, flags=re.IGNORECASE).strip()

    # If model failed format and we have no follow-ups, set empty list
    if not follow_up_questions:
        follow_up_questions = []

    tags = doc_tags
    return answer_text, follow_up_questions, tags, has_answer

def vector_search(request: QuestionRequest, chat_context: str, openai_client, collection) -> Tuple[str, List[str], List[str]]:
    doc_context_block = "No referenced documents."
    query_embedding = get_embedding(request.question, openai_client)
    vector_index = os.getenv("VECTOR_INDEX_NAME", "questions_index")
    pipeline = [
        {"$vectorSearch": {
            "index": vector_index,
            "path": "question_embedding",
            "queryVector": query_embedding,
            "numCandidates": 10000,
            "limit": 1
        }},
        {"$addFields": {"similarity_score": {"$meta": "vectorSearchScore"}}},
        {"$project": {
            "user_question": 1,
            "detailed_answer": 1,
            "follow_up_question_1": 1,
            "follow_up_question_2": 1,
            "follow_up_question_3": 1,
            "tags": 1,
            "similarity_score": 1
        }}
    ]
    results = list(collection.aggregate(pipeline))
    if not results:
        raise HTTPException(status_code=404, detail="No matches")
    best = results[0]

    raw_tags = best.get("tags", "")
    if isinstance(raw_tags, str) and raw_tags.startswith("[") and raw_tags.endswith("]"):
        tags = [t.strip(" '\"") for t in raw_tags[1:-1].split(",") if t.strip(" '\"")]
    else:
        tags = [t.strip() for t in str(raw_tags).split(",") if t.strip()]

    follow_up_questions = []
    for i in range(1, 4):
        k = f"follow_up_question_{i}"
        if best.get(k):
            follow_up_questions.append(best[k])

    prompt = f"""You are acting as a conversational agent for a high-value client demonstration.

Instructions:
1. Use ONLY the 'Retrieved answer (context)' for factual content.
2. Provide a detailed bulleted list.
3. Prior conversation is for style continuity only.

Previous conversation:
{chat_context or 'None'}

Referenced documents:
(No documents supplied)

Current user question: {request.question}

Retrieved answer (context):
{best.get('detailed_answer','')}

Your detailed, bulleted answer:
"""
    llm_resp = chat_completion(
        openai_client,
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Helpful technical assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=500
    )
    final_answer = llm_resp.choices[0].message.content.strip()
    return final_answer, follow_up_questions, tags