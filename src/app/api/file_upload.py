import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import Dict, List, Optional
import os, io, asyncio, hashlib, json
from datetime import datetime

from ..services.upload_service import process_document

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("/")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    doc_id = await process_document(file)
    return {"document_id": doc_id}
