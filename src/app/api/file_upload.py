import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import Optional

from ..services.upload_service import process_document
from ..services.redis_service import (
    update_chat_meta_on_message,
    add_doc_ids_to_chat_meta,
    update_chat_order
)

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("/")
async def upload_file(
    file: UploadFile = File(...),
    chat_id: Optional[str] = None
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    chat_id = chat_id or str(uuid.uuid4())
    chat_type = "question"  # Fixed chat type for uploads

    # Process and get stored document id
    doc_id = await process_document(file)

    # Do NOT set or modify title here
    update_chat_meta_on_message(chat_id, chat_type)
    add_doc_ids_to_chat_meta(chat_id, chat_type, [doc_id])
    update_chat_order(chat_type, chat_id)

    return {
        "document_id": doc_id,
        "chat_id": chat_id
    }
