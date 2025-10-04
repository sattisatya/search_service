from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv
from datetime import datetime, timezone
import os, uuid, json  # added

from ..services.search_service import document_search, vector_search
from ..models.model import QuestionRequest, SearchResponse

from ..services.redis_service import (
    redis_client,
    redis_key,
    chat_meta_key,
    build_chat_context,
    update_chat_meta_on_message,
    update_chat_order,
    add_doc_ids_to_chat_meta)
from ..services.mongo_service import connect_to_mongodb
from ..services.openai_service import get_client, generate_chat_title

load_dotenv()
router = APIRouter(tags=["search"])

def iso_utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

FALLBACK_PHRASES = [
    "i cannot answer based on stored knowledge",
    "i cannot answer based on the provided documents",
    "no relevant indexed documents were found",
    "i'm sorry, but the provided context does not contain",
    "i do not have that specific information",              # <— added
    "do not have that specific information"                 # <— added (broader match)
]

def is_fallback_answer(answer: str) -> bool:
    if not answer:
        return True
    low = answer.lower()
    return any(p in low for p in FALLBACK_PHRASES)

@router.post("/search", response_model=SearchResponse)
async def search_question(request: QuestionRequest):
    chat_id = request.chat_id or str(uuid.uuid4())
    chat_type = request.chat_type
    openai_client = get_client()
    chat_context = build_chat_context(chat_id, chat_type)

    # --- Initialize to avoid UnboundLocalError ---
    has_answer: bool = False
    used_vector: bool = False
    final_answer: str = ""
    follow_up_questions: list[str] = []
    tags: list[str] = []
    doc_ids: list[str] = []
    file_url = ""

    # Load prior doc ids if stored
    try:
        meta_raw = redis_client.get(chat_meta_key(chat_id, chat_type))
        if meta_raw:
            meta_obj = json.loads(meta_raw)
            if isinstance(meta_obj.get("document_ids"), list):
                doc_ids = meta_obj["document_ids"]
    except Exception:
        doc_ids = []

    mongo_client, collection = connect_to_mongodb(os.getenv("questions_collection_name", "knowledge_bank"))
    if mongo_client is None or collection is None:
        raise HTTPException(status_code=500, detail="DB connection failed")

    try:
        # 1. Try document-grounded path
        if doc_ids:
            doc_answer, doc_follow, doc_tags, doc_has = document_search(doc_ids, request, chat_context, openai_client)
            final_answer = doc_answer
            follow_up_questions = doc_follow
            tags = doc_tags
            has_answer = doc_has

            # If doc path failed, fall back to vector
            if not has_answer:
                vec_answer, vec_follow, vec_tags , vec_file_url = vector_search(request, chat_context, openai_client, collection)
                final_answer = vec_answer
                follow_up_questions = vec_follow
                tags = vec_tags
                file_url = vec_file_url
                used_vector = True
                has_answer = not is_fallback_answer(final_answer)
        else:
            # Direct vector
            vec_answer, vec_follow, vec_tags , vec_file_url = vector_search(request, chat_context, openai_client, collection)
            final_answer = vec_answer
            follow_up_questions = vec_follow
            tags = vec_tags
            file_url = vec_file_url
            used_vector = True
            has_answer = not is_fallback_answer(final_answer)

        # Sanitize tags if no grounded answer
        if not has_answer:
            tags = []
            grounded_doc_ids = []
        else:
            grounded_doc_ids = doc_ids if doc_ids else []

        # Persist turn
        list_key = redis_key(chat_id, chat_type)
        is_first = redis_client.llen(list_key) == 0
        redis_client.rpush(list_key, json.dumps({
            "question": request.question,
            "answer": final_answer,
            "ts": iso_utc_now(),
            "tags": tags,
            "document_ids": grounded_doc_ids
        }))

        # Title logic
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
        if has_answer and grounded_doc_ids:
            add_doc_ids_to_chat_meta(chat_id, chat_type, grounded_doc_ids)
        update_chat_order(chat_type, chat_id)

        return SearchResponse(
            question=request.question,
            answer=final_answer,
            follow_up_questions=follow_up_questions,
            chat_id=chat_id,
            chat_type=chat_type,
            title=title,
            tags=tags,
            file_url=file_url
        )
    finally:
        if mongo_client:
            mongo_client.close()
