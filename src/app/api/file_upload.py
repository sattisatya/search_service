from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import Dict, List, Optional
import os, io, asyncio, hashlib, json
from datetime import datetime
from dotenv import load_dotenv
from pdfminer.high_level import extract_text as extract_pdf_text
from docx import Document

from ..services.openai_service import get_client
from ..models.model import FileUploadQuestionRequest, FileUploadQuestionResponse

from ..services.mongo_service import connect_to_mongodb

router = APIRouter(prefix="/upload", tags=["upload"])
load_dotenv()
openai_client = get_client()

document_store: Dict[str, Dict] = {}

async def process_document(file: UploadFile) -> str:
    try:
        content = await file.read()
        doc_id = hashlib.md5(content).hexdigest()
        if file.filename.lower().endswith('.pdf'):
            text = extract_pdf_text(io.BytesIO(content))
        elif file.filename.lower().endswith('.docx'):
            doc = Document(io.BytesIO(content))
            text = '\n'.join(p.text for p in doc.paragraphs)
        elif file.filename.lower().endswith('.txt'):
            text = content.decode('utf-8')
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format")

        created_date = datetime.utcnow().isoformat()
        document_store[doc_id] = {
            "filename": file.filename,
            "upload_time": created_date,
            "content": text
        }

        mongo_client, collection = connect_to_mongodb("upload")
        if mongo_client is not None and collection is not None:
            try:
                collection.insert_one({
                    "file_name": file.filename,
                    "text": text,
                    "id": doc_id,
                    "created_date": created_date
                })
                document_store[doc_id]["saved_to_mongo"] = True
            except Exception:
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
async def upload_file(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    doc_id = await process_document(file)
    return {"document_id": doc_id}

@router.post("/ask", response_model=FileUploadQuestionResponse)
async def ask_question(request: FileUploadQuestionRequest):
    """
    Stateless document Q&A.
    Client can supply prior_history (list of {question, answer}) for lightweight context.
    """
    start_time = asyncio.get_event_loop().time()

    ids = request.document_ids or []
    q_text = (request.question or "").strip()
    if not q_text:
        raise HTTPException(status_code=400, detail="Question text is required")

    # Load documents
    documents_content: List[str] = []
    if ids:
        mongo_client, collection = connect_to_mongodb("upload")
        if mongo_client is None or collection is None:
            raise HTTPException(status_code=500, detail="Database connection failed")
        try:
            cursor = collection.find({"id": {"$in": ids}})
            for doc in cursor:
                file_name = doc.get("file_name", "Unknown")
                text_content = doc.get("text", "")
                documents_content.append(
                    f"Document: {file_name}\nContent:\n{text_content}\n{'='*40}\n"
                )
        finally:
            try:
                mongo_client.close()
            except Exception:
                pass

    combined_docs = "".join(documents_content) if documents_content else "(No documents provided.)"

    # Build lightweight prior context (last N kept client-side; re-sent each call)
    prior_block = "None"
    if request.prior_history:
        lines = []
        for qa in request.prior_history[-5:]:
            lines.append(f"Q: {qa.question}\nA: {qa.answer}")
        if lines:
            prior_block = "\n".join(lines)

    prompt = f"""You are an AI assistant answering questions about uploaded documents.

Provided Documents:
{combined_docs}

Prior Chat Context (client-supplied; may be empty):
{prior_block}

Task:
1. Answer the new user question using ONLY the above document content and provided prior context.
2. If the answer cannot be derived, reply exactly: "I cannot answer based on the provided documents."
3. Provide three follow-up questions.

Format exactly:
ANSWER: <answer>
FOLLOW_UP_QUESTIONS:
1. ...
2. ...
3. ...

User Question: {q_text}
"""

    ai_resp = openai_client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
        messages=[
            {"role": "system", "content": "Be concise, factual; only use provided content."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=1000
    )

    content = ai_resp.choices[0].message.content
    parts = content.split("FOLLOW_UP_QUESTIONS:")
    answer = parts[0].replace("ANSWER:", "").strip()

    follow_ups: List[str] = []
    if len(parts) > 1:
        for line in parts[1].strip().splitlines():
            t = line.strip()
            if not t:
                continue
            if t[0].isdigit():
                cleaned = t.lstrip("1234567890. )").strip()
                if cleaned:
                    follow_ups.append(cleaned)

    processing_time = asyncio.get_event_loop().time() - start_time

    return FileUploadQuestionResponse(
        question=q_text,
        answer=answer,
        processing_time=processing_time,
        follow_up_questions=follow_ups
    )
