from datetime import datetime
import hashlib
import io
from typing import Dict
from dotenv import load_dotenv
from fastapi import HTTPException, UploadFile
from pdfminer.high_level import extract_text as extract_pdf_text
from docx import Document
from ..services.openai_service import get_client
from ..services.mongo_service import connect_to_mongodb

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