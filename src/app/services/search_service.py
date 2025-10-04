import os
import json
import re
from typing import List, Tuple

from click import prompt
from ..services.mongo_service import connect_to_mongodb
from ..models.model import QuestionRequest
from ..services.openai_service import get_embedding,chat_completion,generate_chat_title
from ..services.redis_service import redis_client, redis_key, chat_meta_key, iso_utc_now, update_chat_meta_on_message, update_chat_order
from dotenv import load_dotenv
from fastapi import HTTPException

# Add: limit previous conversation included in LLM prompts
CHAT_CONTEXT_MAX_TURNS = int(os.getenv("CHAT_CONTEXT_MAX_TURNS", "3"))
CHAT_CONTEXT_MAX_CHARS = int(os.getenv("CHAT_CONTEXT_MAX_CHARS", "3000"))

def _limit_chat_context(chat_context: str, max_turns: int = CHAT_CONTEXT_MAX_TURNS, max_chars: int = CHAT_CONTEXT_MAX_CHARS) -> str:
    """
    Keep only the most recent max_turns (User/Assistant pairs) and cap total chars.
    Expects chat_context formatted as "User: ...\\nAssistant: ...\\nUser: ..." etc.
    """
    if not chat_context:
        return ""
    # Split into turn blocks on lines that start with "User:"
    lines = chat_context.splitlines()
    blocks = []
    current = []
    for line in lines:
        if line.startswith("User:"):
            if current:
                blocks.append("\n".join(current))
                current = []
        current.append(line)
    if current:
        blocks.append("\n".join(current))
    recent = blocks[-max_turns:]
    limited = "\n".join(recent).strip()
    if len(limited) > max_chars:
        # keep trailing chars up to max_chars, try not to cut mid-line
        limited = limited[-max_chars:]
        nl = limited.find("\n")
        if 0 < nl < 120:
            limited = limited[nl+1:]
    return limited

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

    # LIMIT previous conversation included in prompt
    chat_context_limited = _limit_chat_context(chat_context)
    prev_conv = (chat_context_limited or 'None').replace('"', '\\"')

    prompt = f"""
You are an AI assistant that MUST rely ONLY on the provided reference documents below.
They are presented as blocks beginning with lines like:
[DOC <id> | <filename>]

QUESTION TYPES YOU MUST HANDLE:

Type A: Content Question
 - User asks for facts explicitly present inside the document texts.
 - Respond only if the facts are explicitly stated (no outside inference).
 - If any required fact is missing -> HAS_ANSWER = false.

Type B: Document Metadata / Introspection Question
 - User asks ABOUT the uploaded documents themselves (e.g. "what did I upload", "list the documents", "how many documents", "what is the new document I uploaded", "what files do you have").
 - Treat these as answerable IF there is at least one document.
 - Derive answers ONLY from the [DOC id | filename] headers you see.
 - Provide counts and file names. DO NOT invent upload times, ordering, or 'newest' unless the question explicitly implies latest and you will then ONLY state the last file name in the sequence shown.
 - If there are no documents (empty block), HAS_ANSWER = false.

HAS_ANSWER must be True ONLY when:
  (Type A) All needed facts are explicitly present in document text, OR
  (Type B) At least one document exists and the question is metadata-oriented.

Output MUST be STRICT JSON. NO extra text.

If HAS_ANSWER is False:
{{
  "HAS_ANSWER": false,
  "ANSWER": "I cannot answer based on the provided documents.",
  "FOLLOW_UP_QUESTIONS": [],
  "PREVIOUS_CONVERSATION": "{prev_conv}"
}}

If HAS_ANSWER is True (Type A content):
{{
  "HAS_ANSWER": true,
  "ANSWER": [
    "1. First strictly evidence-grounded point",
    "2. Second strictly evidence-grounded point",
    "3. Third strictly evidence-grounded point"
  ],
  "FOLLOW_UP_QUESTIONS": [
    "Question 1",
    "Question 2",
    "Question 3"
  ],
  "PREVIOUS_CONVERSATION": "{prev_conv}"
}}

If HAS_ANSWER is True (Type B metadata):
{{
  "HAS_ANSWER": true,
  "ANSWER": [
    "1. You have X uploaded document(s).",
    "2. Document names: <comma-separated file names>",
    "3. <Optional: The latest document (by list order) is: NAME. (ONLY if user asked)>"
  ],
  "FOLLOW_UP_QUESTIONS": [
    "Ask a question about one document's contents",
    "Request a summary of a specific document",
    "Compare two documents"
  ],
  "PREVIOUS_CONVERSATION": "{prev_conv}"
}}

REFERENCE DOCUMENTS (may be truncated):
{doc_context_block}

USER QUESTION:
{request.question}
"""
    # print(prompt)
    llm_resp = chat_completion(
        openai_client,
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Return ONLY valid JSON matching the required schema."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.4,
        max_tokens=900
    )
    raw_content = llm_resp.choices[0].message.content.strip()

    # ---------- JSON extraction / normalization ----------
    def extract_json(txt: str) -> str:
        # Strip code fences if present
        if txt.startswith("```"):
            # remove first and last fence
            lines = [l for l in txt.splitlines() if not l.strip().startswith("```")]
            txt = "\n".join(lines).strip()
        # Heuristic: grab from first { to last }
        if "{" in txt and "}" in txt:
            start = txt.find("{")
            end = txt.rfind("}")
            return txt[start:end+1]
        return txt

    parsed = {}
    json_str = extract_json(raw_content)
    try:
        parsed = json.loads(json_str)
    except Exception:
        # Fallback: attempt to fix common trailing commas
        try:
            json_str_fixed = re.sub(r",(\s*[}\]])", r"\1", json_str)
            parsed = json.loads(json_str_fixed)
        except Exception:
            parsed = {}

    has_answer = bool(parsed.get("HAS_ANSWER") is True)
    follow_up_questions = []
    answer_text = ""

    # ANSWER field: if list, join; if string, use directly
    ans_field = parsed.get("ANSWER")
    if isinstance(ans_field, list):
        answer_text = "\n".join([str(x).strip() for x in ans_field if str(x).strip()])
    elif isinstance(ans_field, str):
        answer_text = ans_field.strip()
    else:
        answer_text = ""

    fq_field = parsed.get("FOLLOW_UP_QUESTIONS")
    if isinstance(fq_field, list):
        follow_up_questions = [str(x).strip() for x in fq_field if str(x).strip()][:3]

    # Fallbacks if JSON failed
    if not parsed:
        has_answer = False
        answer_text = "I cannot answer based on the provided documents."
        follow_up_questions = []

    # Enforce no follow-ups when HAS_ANSWER is False
    if not has_answer:
        follow_up_questions = []

    tags = doc_tags
    return answer_text, follow_up_questions, tags, has_answer

def vector_search(request: QuestionRequest, chat_context: str, openai_client, collection) -> Tuple[str, List[str], List[str]]:
    query_embedding = get_embedding(request.question, openai_client)
    vector_index = os.getenv("VECTOR_INDEX_NAME", "questions_index")

    # Use limited chat context for tone only
    chat_context_limited = _limit_chat_context(chat_context)
    if not chat_context_limited:
        prev_conv_block = "None"
    else:
        prev_conv_block = chat_context_limited
        # Add explicit truncation notice if we actually trimmed
        if chat_context and chat_context_limited != chat_context:
            prev_conv_block += "\n[... truncated ...]"

    pipeline = [
        {"$vectorSearch": {
            "index": vector_index,
            "path": "question_embedding",
            "queryVector": query_embedding,
            "numCandidates": 10000,
            "limit": 1
        }},
        {"$addFields": {"similarity_score": {"$meta": "vectorSearchScore"}}},
        {"$match": {"similarity_score": {"$gt": 0.75}}},
        {"$project": {
            "user_question": 1,
            "detailed_answer": 1,
            "follow_up_question_1": 1,
            "follow_up_question_2": 1,
            "follow_up_question_3": 1,
            "tags": 1,
            "file_url": 1,
            "similarity_score": 1
        }}
    ]
    results = list(collection.aggregate(pipeline))

    if not results:
        # No hits: deterministic fallback (NO extra LLM call optional; if you keep, still use limited context)
        fallback = "I cannot answer based on stored knowledge: no relevant indexed documents were found. You may upload a document related to your question."
        return fallback, [], []

    best = results[0]

    raw_tags = best.get("tags", "")
    if isinstance(raw_tags, str) and raw_tags.startswith("[") and raw_tags.endswith("]"):
        tags = [t.strip(" '\"") for t in raw_tags[1:-1].split(",") if t.strip(" '\"")]
    else:
        tags = [t.strip() for t in str(raw_tags).split(",") if t.strip()]

    follow_up_questions: List[str] = []
    for i in range(1, 4):
        k = f"follow_up_question_{i}"
        if best.get(k):
            follow_up_questions.append(best[k])

    # IMPORTANT: use the LIMITED previous conversation (prev_conv_block) not the full chat_context
    prompt = f"""
You are acting as a conversational agent for a high-value client demonstration. 
Your goal is to synthesize the provided context into a detailed and professional answer.

### Instructions:
1. **Content Source Priority:** 
   - The response MUST be generated directly and entirely from the 'Retrieved answer (context)' provided below. 
   - Treat this as the sole authoritative source. Do NOT use outside knowledge or inference.
2. **Formatting Requirement:** 
   - The final answer MUST be structured as a comprehensive numbered list. 
   - Each distinct fact, step, or component of the answer MUST be its own numbered point.
   - Use professional, precise wording; avoid fluff or repetition.
3. **Previous Conversation Usage:** 
   - Use the 'Previous conversation' only to maintain conversational continuity or flow. 
   - Do NOT add new content from it; only minor adjustments for tone or context.

---

**Previous conversation:**
{chat_context}

**Current user question:** 
{request.question}

**Retrieved answer (context):**
{best.get('detailed_answer','')}

---

**Your detailed, numbered answer:**
"""
    # print(prompt)

    llm_resp = chat_completion(
        openai_client,
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Helpful, precise, no hallucinations."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=600
    )
    final_answer = llm_resp.choices[0].message.content.strip()
    return final_answer, follow_up_questions, tags , best.get("file_url", "")