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


def document_search(doc_ids: List[str], request: QuestionRequest, chat_context: str, openai_client) -> Tuple[str, List[str], List[str]]:
            # ----------------- If doc_ids provided: bypass vector search -----------------
        # Build document context
        doc_context_block = "No referenced documents."
        snippets = []
        doc_tags = []  # NEW: collect document names for tags
        up_client, up_coll = connect_to_mongodb("upload")
        if up_client is not None and up_coll is not None:
            try:
                cur = up_coll.find({"id": {"$in": doc_ids}}, {"id": 1, "file_name": 1, "text": 1})
                for d in cur:
                    file_name = d.get("file_name") or "Unnamed"
                    # collect tag (dedupe later)
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

        prompt = f"""You are an AI assistant. Answer STRICTLY from the reference documents below.
If the answer (or any part of it) is not explicitly supported by the documents, respond exactly:
"I cannot answer based on the provided documents."

Instructions:
1. Use ONLY facts explicitly present in the documents. No unstated assumptions, no outside knowledge.
2. Be concise, professional, and use bullet points.
3. Do NOT summarize beyond what is present—stay faithful to wording where critical.
4. If documents conflict, state the conflict briefly.
5. Never fabricate numbers, dates, or entities.

Follow-up questions:
- Generate exactly three.
- Each must be directly grounded in gaps, unresolved details, or natural next steps from the document content and (if relevant) prior conversation context.
- Do NOT repeat the user question or prior follow-ups.
- Avoid near-duplicates; each must explore a distinct angle.
- If insufficient material for three meaningful follow-ups, still output three, but label uncertain ones with a prefix "(Exploratory)".

Previous conversation (style only; do NOT invent new facts from it):
{chat_context or 'None'}

Reference documents (authoritative scope; truncated if long):
{doc_context_block}

User question:
{request.question}

Output format EXACTLY:
ANSWER:
<bulleted answer or "I cannot answer based on the provided documents.">

FOLLOW_UP_QUESTIONS:
1. ...
2. ...
3. ...
"""
        llm_resp = chat_completion(
            openai_client,
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Helpful technical assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=700
        )
        raw_content = llm_resp.choices[0].message.content.strip()

        # Parse follow-up questions
        follow_ups = []
        if "FOLLOW_UP_QUESTIONS:" in raw_content:
            ans_part, fu_part = raw_content.split("FOLLOW_UP_QUESTIONS:", 1)
            answer_text = ans_part.replace("ANSWER:", "").strip()
            for line in fu_part.strip().splitlines():
                line = line.strip()
                if not line:
                    continue
                if line[0].isdigit():
                    line = re.sub(r"^\d+[\).]?\s*", "", line)
                if line:
                    follow_ups.append(line)
            follow_up_questions = follow_ups[:3]
        else:
            answer_text = raw_content
            follow_up_questions = []

        final_answer = answer_text
        # Use document names as tags in doc-only flow
        tags = doc_tags

        return final_answer, follow_up_questions, tags

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