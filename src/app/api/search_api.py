from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv
import os, uuid, json, time, re
from datetime import datetime, timezone
from ..models.model import QuestionRequest, SearchResponse

# Use service modules
from ..services.redis_service import (
    redis_client,
    redis_key,
    chat_meta_key,
    build_chat_context,
    update_chat_meta_on_message,
    update_chat_order
)
from ..services.mongo_service import connect_to_mongodb
from ..services.openai_service import get_client, get_embedding, chat_completion, generate_chat_title

load_dotenv()

router = APIRouter(tags=["search"])

def iso_utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------ ENDPOINTS ------------------


@router.post("/search", response_model=SearchResponse)
async def search_question(request: QuestionRequest):
    chat_id = request.chat_id or str(uuid.uuid4())
    chat_type = request.chat_type
    openai_client = get_client()

    chat_context = build_chat_context(chat_id, chat_type)

    # Transient document ids (not stored)
    doc_ids = request.document_ids or []

    mongo_client, collection = connect_to_mongodb(os.getenv("questions_collection_name", "knowledge_bank"))
    if mongo_client is None or collection is None:
        raise HTTPException(status_code=500, detail="DB connection failed")

    try:
        # ----------------- If doc_ids provided: bypass vector search -----------------
        if doc_ids:
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

            prompt = f"""You are an AI assistant answering ONLY from the provided documents.

Rules:
- Use only the reference documents below; do not invent facts.
- If the answer is not in the documents say: "I cannot answer based on the provided documents."
- Provide a concise, professional bulleted answer.
- Then produce exactly three relevant follow-up questions.

Previous conversation (for style only):
{chat_context or 'None'}

Reference documents (truncated if long):
{doc_context_block}

User question:
{request.question}

Format EXACTLY:
ANSWER:
<bulleted answer>

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

        else:
            # ----------------- Original vector search flow -----------------
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
        # ------------------------------------------------------------------

        list_key = redis_key(chat_id, chat_type)
        is_first = redis_client.llen(list_key) == 0
        redis_client.rpush(list_key, json.dumps({
            "question": request.question,
            "answer": final_answer,
            "ts": iso_utc_now()
        }))

        meta_key = chat_meta_key(chat_id, chat_type)
        title = None
        if is_first:
            try:
                title = generate_chat_title(openai_client, request.question)
            except Exception:
                title = (request.question[:60] + "...") if len(request.question) > 60 else request.question
        else:
            existing = redis_client.get(meta_key)
            if existing:
                try:
                    em = json.loads(existing)
                    title = em.get("title")
                except Exception:
                    pass
            if not title:
                first_raw = redis_client.lindex(list_key, 0)
                if first_raw:
                    try:
                        first = json.loads(first_raw)
                        fq = first.get("question", "").strip()
                        title = (fq[:60] + "...") if fq and len(fq) > 60 else (fq or "Conversation")
                    except Exception:
                        title = "Conversation"
                else:
                    title = "Conversation"

        update_chat_meta_on_message(chat_id, chat_type, title)
        update_chat_order(chat_type, chat_id)

        return SearchResponse(
            question=request.question,
            answer=final_answer,
            follow_up_questions=follow_up_questions,
            chat_id=chat_id,
            chat_type=chat_type,
            title=title,
            tags=tags
        )
    finally:
        if mongo_client:
            mongo_client.close()
