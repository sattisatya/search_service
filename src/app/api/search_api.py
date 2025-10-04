from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv
from datetime import datetime, timezone
import os, uuid, json  # added
from typing import Any

from ..services.search_service import document_search, vector_search
from ..models.model import QuestionRequest, SearchResponse

from ..services.redis_service import (
    redis_client,
    redis_key,
    chat_meta_key,
    build_chat_context,
    update_chat_meta_on_message,
    update_chat_order,
    add_doc_ids_to_chat_meta,
    push_history_item,  # added
)
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

# Helper to ensure tags are list[dict] before storing/returning
def ensure_tag_objects(raw: Any, default_file_url: str = "") -> list[dict]:
    out: list[dict] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                name = item.get("name") or item.get("file_name") or item.get("filename") or item.get("tag")
                furl = item.get("file_url", default_file_url)
                if name:
                    out.append({"name": str(name).strip(), "file_url": str(furl or "")})
            else:
                s = str(item).strip()
                if s:
                    out.append({"name": s, "file_url": default_file_url if s.lower().endswith(".pdf") else ""})
    elif isinstance(raw, str):
        s = raw.strip()
        if s:
            out.append({"name": s, "file_url": default_file_url if s.lower().endswith(".pdf") else ""})
    return out

@router.post("/search", response_model=SearchResponse)
async def search_question(request: QuestionRequest):
    chat_id = request.chat_id or str(uuid.uuid4())
    chat_type = request.chat_type
    openai_client = get_client()
    chat_context = build_chat_context(chat_id, chat_type)

    # Determine if this is the first message in this chat
    list_key = redis_key(chat_id, chat_type)
    try:
        is_first = (redis_client.llen(list_key) == 0)
    except Exception:
        is_first = True

    # --- Initialize to avoid UnboundLocalError ---
    has_answer: bool = False
    used_vector: bool = False
    final_answer: str = ""
    follow_up_questions: list[str] = []
    tags: list[dict] = []   # store exactly as produced
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
        # 1) Document-grounded ONLY if doc_ids exist (no vector fallback)
        if doc_ids:
            doc_answer, doc_follow, doc_tags, doc_has = document_search(doc_ids, request, chat_context, openai_client)
            final_answer = doc_answer
            follow_up_questions = doc_follow
            tags = doc_tags  # already list[dict] from document_search
            has_answer = doc_has
            file_url = ""  # document_search does not provide file_url

            # Do NOT run vector search when docs are attached.
            if not has_answer:
                # Deterministic document-only fallback
                final_answer = "I cannot answer based on the provided documents."
                follow_up_questions = []
                tags = []
                file_url = ""
        else:
            # 2) No docs -> use vector search
            vec_answer, vec_follow, vec_tags, vec_file_url = vector_search(request, chat_context, openai_client, collection)
            final_answer = vec_answer
            follow_up_questions = vec_follow
            tags = vec_tags  # list[dict] from vector_search
            file_url = vec_file_url
            has_answer = not is_fallback_answer(final_answer)

        # Sanitize on fallback
        if not has_answer or is_fallback_answer(final_answer):
            tags = []
            grounded_doc_ids = []
        else:
            grounded_doc_ids = doc_ids if doc_ids else []

        # Normalize tags shape for Redis/API (list of dicts)
        tags_to_store = tags

        # Persist turn with tags as-is
        push_history_item(
            chat_id=chat_id,
            chat_type=chat_type,
            question=request.question,
            answer=final_answer,
            tags=tags,
            document_ids=grounded_doc_ids,
            extra=None
        )

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
            tags=tags_to_store,
            file_url=file_url
        )
    finally:
        if mongo_client:
            mongo_client.close()
