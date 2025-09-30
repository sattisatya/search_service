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
    """Process uploaded document and store its content (avoid re-inserting duplicates in MongoDB)"""
    try:
        content = await file.read()

        # Generate unique document ID (hash of bytes)
        doc_id = hashlib.md5(content).hexdigest()

        # Extract text based on file type
        text = ""
        fname = file.filename or ""
        lname = fname.lower()
        if lname.endswith('.pdf'):
            text = extract_pdf_text(io.BytesIO(content))
        elif lname.endswith('.docx'):
            doc = Document(io.BytesIO(content))
            text = '\n'.join([p.text for p in doc.paragraphs])
        elif lname.endswith('.txt'):
            text = content.decode('utf-8')
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format")

        created_date = datetime.utcnow().isoformat()
        document_store[doc_id] = {
            'filename': fname,
            'upload_time': created_date,
            'content': text
        }

        # Persist document into MongoDB collection "upload" only if not already present
        mongo_client, collection = connect_to_mongodb("upload")
        if mongo_client is not None and collection is not None:
            try:
                existing = collection.find_one({"id": doc_id})
                if existing:
                    # already stored
                    document_store[doc_id]["saved_to_mongo"] = True
                else:
                    doc_record = {
                        "file_name": fname,
                        "text": text,
                        "id": doc_id,
                        "created_date": created_date
                    }
                    collection.insert_one(doc_record)
                    document_store[doc_id]["saved_to_mongo"] = True
            except Exception:
                # on failure, keep in-memory copy but mark not saved
                document_store[doc_id]["saved_to_mongo"] = False
            finally:
                try:
                    mongo_client.close()
                except Exception:
                    pass
        return doc_id

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")

@router.post("/")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    doc_id = await process_document(file)

    # create a new chat session for this document with "ask" chat type
    chat_id = chat_id or str(uuid.uuid4())

    # Persist document id into chat meta for quick rehydration (chat_type = "upload")
    try:
        # title is optional; store filename for quick UI hint
        update_chat_meta_on_message(chat_id, "documentqna", title=f"Upload: {file.filename}", document_ids=[doc_id])
        update_chat_order("documentqna", chat_id)
    except Exception:
        pass

    return {"document_id": doc_id, "chat_id": chat_id}

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

    chat_id_final = request.chat_id or str(uuid.uuid4())
    chat_type_final = "documentqna"
    # allow 'upload' as a valid chat_type so we can store/retrieve doc meta there
    # if chat_type_final not in ("documentqna", "question", "insight"):
    #     chat_type_final = "documentqna"

    list_key = redis_key(chat_id_final, chat_type_final)

    # --- NEW: if caller did not supply ids, try to recover from Redis meta or recent history ---
    if not ids:
        try:
            meta_raw = redis_client.get(chat_meta_key(chat_id_final, chat_type_final))
            if meta_raw:
                meta = json.loads(meta_raw)
                meta_ids = meta.get("document_ids", [])
                if isinstance(meta_ids, list) and meta_ids:
                    ids = meta_ids
        except Exception:
            pass

    # also scan last N history entries for document_ids as a last-resort
    if not ids:
        try:
            history_raw = redis_client.lrange(list_key, -10, -1)  # last 10 entries
            found = []
            for h in history_raw:
                try:
                    obj = json.loads(h)
                    if isinstance(obj.get("document_ids"), list):
                        for d in obj.get("document_ids", []):
                            if d and d not in found:
                                found.append(d)
                except Exception:
                    continue
            if found:
                ids = found
        except Exception:
            pass
    # --- end new block ---

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
        # pass document ids so meta stays in sync with this chat activity
        update_chat_meta_on_message(chat_id_final, chat_type_final, title, document_ids=ids)
        update_chat_order(chat_type_final, chat_id_final)
    except Exception:
        pass

    return FileUploadQuestionResponse(
        question=q_text,
        answer=answer,
        processing_time=processing_time,
        follow_up_questions=follow_ups
    )
