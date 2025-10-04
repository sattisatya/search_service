import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import Optional
import os
from ..services.upload_service import process_document
from ..services.redis_service import (
    update_chat_meta_on_message,
    add_doc_ids_to_chat_meta,
    update_chat_order,
    redis_client,
    chat_meta_key
)

router = APIRouter(prefix="/upload", tags=["upload"])

MAX_DOCS_PER_CHAT = int(os.getenv("MAX_DOCS_PER_CHAT", "2"))


@router.post("/")
async def upload_file(
    file: UploadFile = File(...),
    chat_id: Optional[str] = None
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    chat_id = chat_id or str(uuid.uuid4())
    chat_type = "question"

    # Fetch existing document ids for this chat
    existing_ids = []
    try:
        meta_raw = redis_client.get(chat_meta_key(chat_id, chat_type))
        if meta_raw:
            import json
            meta_obj = json.loads(meta_raw)
            if isinstance(meta_obj.get("document_ids"), list):
                existing_ids = meta_obj["document_ids"]
    except Exception:
        existing_ids = []

    # Enforce max documents (allow re-upload of an already attached doc silently)
    if len(existing_ids) >= MAX_DOCS_PER_CHAT:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum of {MAX_DOCS_PER_CHAT} documents allowed per chat. Remove one or start a new chat."
        )

    # Process and get stored document id
    doc_id = await process_document(file)

    # If doc already present, just acknowledge (do not count twice)
    if doc_id in existing_ids:
        return {
            "document_id": doc_id,
            "chat_id": chat_id,
            "message": "Document already associated with this chat."
        }

    # Attach new doc id (now guaranteed we are below limit)
    update_chat_meta_on_message(chat_id, chat_type)
    add_doc_ids_to_chat_meta(chat_id, chat_type, [doc_id])
    update_chat_order(chat_type, chat_id)

    return {
        "document_id": doc_id,
        "chat_id": chat_id,
        "message": f"Document added. {len(existing_ids)+1}/{MAX_DOCS_PER_CHAT} used."
    }
