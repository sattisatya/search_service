from fastapi import APIRouter, FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
import os
import io
import asyncio
from datetime import datetime
import hashlib
from dotenv import load_dotenv
import uuid
import json

# Document processing
from pdfminer.high_level import extract_text as extract_pdf_text
from docx import Document
from ..services.openai_service import get_client, generate_chat_title
from ..models.model import FileUploadQuestionRequest, FileUploadQuestionResponse

# add mongo service import
from ..services.mongo_service import connect_to_mongodb

# Redis chat helpers
from ..services.redis_service import (
    redis_client,
    redis_key,
    chat_meta_key,
    update_chat_meta_on_message,
    update_chat_order,
    iso_utc_now
)

router = APIRouter(prefix="/upload", tags=["upload"])

# Load environment variables
load_dotenv()

# Initialize OpenAI client once
openai_client = get_client()

# In-memory document storage
document_store: Dict[str, Dict] = {}

async def process_document(file: UploadFile) -> str:
    """Process uploaded document and store its content"""
    try:
        content = await file.read()
        
        # Generate unique document ID
        doc_id = hashlib.md5(content).hexdigest()
        
        # Extract text based on file type
        text = ""
        if file.filename.lower().endswith('.pdf'):
            text = extract_pdf_text(io.BytesIO(content))
        elif file.filename.lower().endswith('.docx'):
            doc = Document(io.BytesIO(content))
            text = '\n'.join([paragraph.text for paragraph in doc.paragraphs])
        elif file.filename.lower().endswith('.txt'):
            text = content.decode('utf-8')
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format")

        # Store document info in memory
        created_date = datetime.utcnow().isoformat()
        document_store[doc_id] = {
            'filename': file.filename,
            'upload_time': created_date,
            'content': text
        }

        # Persist document into MongoDB collection "upload"
        mongo_client, collection = connect_to_mongodb("upload")
        if mongo_client is not None and collection is not None:
            try:
                doc_record = {
                    "file_name": file.filename,
                    "text": text,
                    "id": doc_id,
                    "created_date": created_date
                }
                collection.insert_one(doc_record)
                # optional flag in memory store
                document_store[doc_id]["saved_to_mongo"] = True
            except Exception:
                # on failure, keep in-memory copy but do not block upload
                document_store[doc_id]["saved_to_mongo"] = False
            finally:
                try:
                    mongo_client.close()
                except Exception:
                    pass

        return doc_id

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")

@router.post("/")
async def upload_file(file: UploadFile = File(...), chat_id: Optional[str] = None):
    """Upload and process a document and create a chat session for it"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
        
    doc_id = await process_document(file)

    # create a new chat session for this document with "ask" chat type
    chat_id = chat_id or str(uuid.uuid4())
    chat_type = "ask"  # changed to "ask" for uploaded documents
    list_key = redis_key(chat_id, chat_type)

    initial_item = {
        "question": f"[Document uploaded] {file.filename}",
        "answer": f"Document stored with id {doc_id}",
        "ts": iso_utc_now(),
        "document_id": doc_id
    }
    try:
        redis_client.rpush(list_key, json.dumps(initial_item))
        # set metadata (use filename as title)
        update_chat_meta_on_message(chat_id, chat_type, title=file.filename)
        update_chat_order(chat_type, chat_id)
    except Exception:
        # do not fail upload if Redis is down — the document itself was stored in memory
        pass

    return {"document_id": doc_id, "chat_id": chat_id}

# Update the ask_question endpoint to accept multiple document ids via body OR query params
@router.post("/ask", response_model=FileUploadQuestionResponse)
async def ask_question(request: FileUploadQuestionRequest):
    """
    Answer questions about uploaded documents.
    If request.document_ids is provided and non-empty -> fetch those docs.
    If omitted or empty -> skip Mongo lookup (no error) and proceed without document context.
    """
    start_time = asyncio.get_event_loop().time()

    ids = request.document_ids or []          # optional now
    q_text = (request.question or "").strip()
    if not q_text:
        raise HTTPException(status_code=400, detail="Question text is required")

    chat_id_final = request.chat_id or str(uuid.uuid4())
    chat_type_final = request.chat_type or "ask"
    if chat_type_final not in ("ask", "question", "insight"):
        chat_type_final = "ask"

    list_key = redis_key(chat_id_final, chat_type_final)

    documents_content: List[str] = []
    documents_found = 0

    if ids:  # only hit Mongo if we actually got IDs
        mongo_client, collection = connect_to_mongodb("upload")
        if mongo_client is None or collection is None:
            raise HTTPException(status_code=500, detail="Database connection failed")
        try:
            cursor = collection.find({"id": {"$in": ids}})
            for doc in cursor:
                documents_found += 1
                file_name = doc.get("file_name", "Unknown")
                text_content = doc.get("text", "")
                documents_content.append(
                    f"Document: {file_name}\nContent:\n{text_content}\n{'='*50}\n"
                )
        finally:
            try:
                mongo_client.close()
            except Exception:
                pass

    combined_content = "".join(documents_content) if documents_content else "(No documents provided or found; answer based only on prior chat context if any.)"

    # (Optional) include prior chat context from Redis for continuity
    prior_messages = []
    try:
        history_raw = redis_client.lrange(list_key, 0, -1)
        for h in history_raw[-5:]:  # last 5 entries
            try:
                obj = json.loads(h)
                prior_q = obj.get("question")
                prior_a = obj.get("answer")
                if prior_q and prior_a:
                    prior_messages.append(f"Q: {prior_q}\nA: {prior_a}")
            except Exception:
                continue
    except Exception:
        pass
    prior_context_block = "\n".join(prior_messages) if prior_messages else "None"

    prompt = f"""You are an AI assistant answering user questions about uploaded documents.

Provided Documents Content:
{combined_content}

Recent Chat Context (may be empty):
{prior_context_block}

Task:
1. Answer the new user question strictly using the document content above if any; if no documents were provided, rely only on explicit prior Q&A context.
2. If the answer cannot be derived from provided documents/context, reply: "I cannot answer based on the provided documents."
3. Then produce three follow-up questions.

Format exactly:
ANSWER: <answer>
FOLLOW_UP_QUESTIONS:
1. ...
2. ...
3. ...

User Question: {q_text}
"""

    response = openai_client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
        messages=[
            {"role": "system", "content": "Be concise, factual, cite only provided content."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=1500
    )

    content = response.choices[0].message.content
    parts = content.split("FOLLOW_UP_QUESTIONS:")

    answer = parts[0].replace("ANSWER:", "").strip()
    follow_ups: List[str] = []
    if len(parts) > 1:
        for line in parts[1].strip().splitlines():
            ls = line.strip()
            if ls and ls[0].isdigit():
                cleaned = ls.lstrip("1234567890. )").strip()
                if cleaned:
                    follow_ups.append(cleaned)

    processing_time = asyncio.get_event_loop().time() - start_time

    ts_val = iso_utc_now()
    item = {
        "question": q_text,
        "answer": answer,
        "follow_up_questions": follow_ups,
        "ts": ts_val,
        "document_ids": ids,                # may be empty list
        "documents_found": documents_found, # 0 if none / not searched
        "chat_type": chat_type_final
    }
    try:
        is_first = redis_client.llen(list_key) == 0
        redis_client.rpush(list_key, json.dumps(item))
        title = None
        if is_first:
            try:
                title = generate_chat_title(openai_client, q_text)
            except Exception:
                title = (q_text[:60] + "...") if len(q_text) > 60 else (q_text or "Document Q&A")
        else:
            existing = redis_client.get(chat_meta_key(chat_id_final, chat_type_final))
            if existing:
                try:
                    meta = json.loads(existing)
                    title = meta.get("title")
                except Exception:
                    title = None
        update_chat_meta_on_message(chat_id_final, chat_type_final, title)
        update_chat_order(chat_type_final, chat_id_final)
    except Exception:
        pass

    return FileUploadQuestionResponse(
        question=q_text,
        answer=answer,
        follow_up_questions=follow_ups,
        chat_id=chat_id_final,
        chat_type=chat_type_final,
        document_ids=ids,
        documents_found=documents_found,
        ts=ts_val,
        processing_time=processing_time
    )

# Add endpoint to list uploaded documents
@router.get("/documents")
async def list_uploaded_documents():
    """List all uploaded documents from MongoDB"""
    mongo_client, collection = connect_to_mongodb("upload")
    if mongo_client is None or collection is None:
        raise HTTPException(status_code=500, detail="Database connection failed")
    
    try:
        documents = []
        cursor = collection.find({}, {"id": 1, "file_name": 1, "created_date": 1, "_id": 0})
        
        for doc in cursor:
            documents.append({
                "document_id": doc.get("id"),
                "file_name": doc.get("file_name"),
                "created_date": doc.get("created_date")
            })
        
        return {"documents": documents, "count": len(documents)}
        
    finally:
        mongo_client.close()

