from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv
import os, uuid, json, time, re
from datetime import datetime, timezone

from ..services.search_service import document_search, vector_search
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
            final_answer, follow_up_questions, tags = document_search(doc_ids, request, chat_context, openai_client)

        else:
            # ----------------- Original vector search flow -----------------
            final_answer, follow_up_questions, tags = vector_search(request, chat_context, openai_client, collection)
        # ------------------------------------------------------------------

        list_key = redis_key(chat_id, chat_type)
        is_first = redis_client.llen(list_key) == 0
        redis_client.rpush(list_key, json.dumps({
            "question": request.question,
            "answer": final_answer,
            "ts": iso_utc_now(),
            "tags": tags              # NEW
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
