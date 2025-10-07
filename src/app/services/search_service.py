import os
import json
import re
import ast
from typing import List, Tuple

from click import prompt
from ..services.mongo_service import connect_to_mongodb
from ..models.model import QuestionRequest
from ..services.openai_service import get_embedding,chat_completion



json_path = 'config.json'
if not os.path.exists(json_path):
    print(f"File not found: {json_path}")
else:
    with open(json_path, 'r', encoding='utf-8') as f:
        data1 = json.load(f)


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

def document_search(doc_ids: List[str], request: QuestionRequest, chat_context: str, openai_client) -> Tuple[str, List[str], List[dict], bool]:
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
                snippets.append(f"[DOC {file_name}]\n{text}")
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
    You are an assistant that answers ONLY from provided REFERENCE DOCUMENTS below.
    Documents start with: [DOC <filename>]

    Rules:
    1) Metadata questions (what files uploaded, how many, list names): Answer from headers only
    2) Content questions (facts, dates, numbers): Answer only if explicitly stated, cite [DOC <filename>]
    3) Missing facts = HAS_ANSWER: false

    Return strict JSON:
    - HAS_ANSWER: boolean
    - ANSWER: either a string or a list of strings (do NOT add numeric ordering)
    - FOLLOW_UP_QUESTIONS: max 3 short user-style QUESTIONS (e.g. "Can you summarize KAG1.pdf?")
    - PREVIOUS_CONVERSATION: "{prev_conv}"
    - SOURCES: list of {{"id":"<id>","filename":"<name>"}}

    Examples:
    No answer: {{ "HAS_ANSWER": false, "ANSWER": "I cannot answer based on the provided documents.", "FOLLOW_UP_QUESTIONS": [], "PREVIOUS_CONVERSATION": "{prev_conv}", "SOURCES": [] }}

    Content: {{ "HAS_ANSWER": true, "ANSWER": ["Fact with evidence [DOC 42]"], "FOLLOW_UP_QUESTIONS": ["Can you summarize the supporting document?"], "PREVIOUS_CONVERSATION": "{prev_conv}", "SOURCES": [{{ "id": "42", "filename": "file.pdf" }}] }}

    Metadata: {{ "HAS_ANSWER": true, "ANSWER": "You have 2 documents: file1.pdf, file2.docx.", "FOLLOW_UP_QUESTIONS": ["Can you summarize file1.pdf?"], "PREVIOUS_CONVERSATION": "{prev_conv}", "SOURCES": [{{ "id": "1", "filename": "file1.pdf" }}] }}

    DOCUMENTS: {doc_context_block}
    QUESTION: {request.question}
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

    # Store tags as list of objects: [{name, file_url}]
    tags = [{"name": str(n).strip(), "file_url": ""} for n in doc_tags if str(n).strip()]
    return answer_text, follow_up_questions, tags, has_answer

def vector_search(request: QuestionRequest, chat_context: str, openai_client, collection) -> Tuple[str, List[str], List[str], str]:
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
            # "user_question": 1,
            "detailed_answer": 1,
            "follow_up_question_1": 1,
            "follow_up_question_2": 1,
            "follow_up_question_3": 1,
            "tags": 1,
            "file_url": 1,
            "similarity_score": 1,
            "user_question_short": 1
        }}
    ]
    results = list(collection.aggregate(pipeline))

    if not results:
        # Always return a 4‑tuple
        fallback = "I cannot answer based on stored knowledge: no relevant indexed documents were found. You may upload a document related to your question."
        return fallback, [], [], ""

    best = results[0]

    raw_tags = best.get("tags", [])
    names: List[str] = []

    # Normalize tags to a list of names
    if isinstance(raw_tags, list):
        for t in raw_tags:
            if isinstance(t, dict):
                v = t.get("name") or t.get("filename") or t.get("file_name") or t.get("tag")
                if isinstance(v, list):
                    names.extend(str(x).strip() for x in v if str(x).strip())
                elif v:
                    names.append(str(v).strip())
            else:
                s = str(t).strip()
                if s:
                    names.append(s)
    elif isinstance(raw_tags, str):
        s = raw_tags.strip()
        if s.startswith("[") and s.endswith("]"):
            try:
                parsed = ast.literal_eval(s)
                if isinstance(parsed, (list, tuple)):
                    for x in parsed:
                        names.append(str(x).strip())
            except Exception:
                pass
        else:
            names.extend([p.strip() for p in s.split(",") if p.strip()])

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

    # Build tags as list of objects and return file_url separately
    file_url = best.get("file_url", "") or ""
    tags = best.get("tags", [])
    final_tags: List[dict] = []
    names = tags[0].get("names",[])
    for name in names:
        if name.endswith(".pdf"):
            final_tags.append({"name":name, "file_url": data1["filenames"].get(name, "")})
        else:
            final_tags.append({"name":name, "file_url":""})
    # print(final_tags)

    return final_answer, follow_up_questions, final_tags, file_url