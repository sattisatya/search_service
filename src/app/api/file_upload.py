import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from typing import Dict, List, Optional
import os, io, asyncio, hashlib, json
from datetime import datetime

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
    chat_id: str = Form(None),
    chat_type: str = Form("default"),
    title: str = Form(None)
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Generate chat_id if not provided
    chat_id = chat_id or str(uuid.uuid4())

    # Process and get stored document id
    doc_id = await process_document(file)

    # Derive a title if not provided
    if not title:
        base = file.filename.rsplit(".", 1)[0]
        title = (base[:60] + "...") if len(base) > 60 else base or "Uploads"

    # Update chat meta and attach document id
    update_chat_meta_on_message(chat_id, chat_type, title)
    add_doc_ids_to_chat_meta(chat_id, chat_type, [doc_id])
    update_chat_order(chat_type, chat_id)

    return {
        "document_id": doc_id,
        "chat_id": chat_id,
        "chat_type": chat_type,
        "title": title
    }
