from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv
import os, uuid, json, time, re
from datetime import datetime, timezone
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

    mongo_client, collection = connect_to_mongodb(os.getenv("questions_collection_name", "knowledge_bank"))
    if mongo_client is None or collection is None:
        raise HTTPException(status_code=500, detail="DB connection failed")

    try:
        # Build prior conversation + collect any document ids from previous documentqna / upload interactions
        chat_context, prior_doc_ids = build_chat_context(chat_id, chat_type, return_doc_ids=True)

        # (Optional) fetch document contents to enrich prompt (pulled from 'upload' collection)
        doc_context_block = "No prior documents referenced."
        if prior_doc_ids:
            doc_snippets = []
            up_client, up_coll = connect_to_mongodb("upload")
            # Must compare explicitly with None; pymongo Collection forbids truthiness checks
            if up_client is not None and up_coll is not None:
                 try:
                     cursor_docs = up_coll.find({"id": {"$in": prior_doc_ids}}, {"id": 1, "file_name": 1, "text": 1})
                     for d in cursor_docs:
                         text = (d.get("text", "") or "").strip()
                         snippet = text
                         doc_snippets.append(
                             f"[DOC {d.get('id')} | {d.get('file_name','Unnamed')}]\n{snippet}"
                         )
                 except Exception:
                     pass
                 finally:
                     try:
                         up_client.close()
                     except Exception:
                         pass
            if doc_snippets:
                doc_context_block = "\n\n".join(doc_snippets)

        query_embedding = get_embedding(request.question, openai_client)
        vector_index = os.getenv("VECTOR_INDEX_NAME", "questions_index")

        pipeline = [
            {
                "$vectorSearch": {
                    "index": vector_index,
                    "path": "question_embedding",
                    "queryVector": query_embedding,
                    "numCandidates": 10000,
                    "limit": 1
                }
            },
            {"$addFields": {"similarity_score": {"$meta": "vectorSearchScore"}}},
            {
                "$project": {
                    "user_question": 1,
                    "detailed_answer": 1,
                    "follow_up_question_1": 1,
                    "follow_up_question_2": 1,
                    "follow_up_question_3": 1,
                    "tags": 1,
                    "similarity_score": 1
                }
            }
        ]
        results = list(collection.aggregate(pipeline))
        if not results:
            raise HTTPException(status_code=404, detail="No matches")
        best = results[0]
        raw_tags = best.get("tags", "")
        if isinstance(raw_tags, str) and raw_tags.startswith("[") and raw_tags.endswith("]"):
            tags = [t.strip(" '\"") for t in raw_tags[1:-1].split(",") if t.strip(" '\"")]
        else:
            tags = [t.strip() for t in str(raw_tags).split(",") if t.strip()]

        follow_up_questions = []
        for i in range(1, 4):
            k = f"follow_up_question_{i}"
            if best.get(k):
                follow_up_questions.append(best[k])

        prompt = f"""You are acting as a conversational agent for a high-value client demonstration.

Instructions:
1.  **Content Source Priority:** The response MUST be generated directly and entirely from the 'Retrieved answer (context)' provided below. Assume this context is the definitive information provided by the UI's RAG system.
2.  **Formatting Requirement:** The final answer MUST be delivered in a comprehensive, detailed **bulleted list** format. Each distinct piece of information (e.g., each component of a multi-part answer, or each fact) should be its own bullet point for maximum clarity.
3.  **Prior Conversation Use:** Use the 'Previous conversation' only for essential contextual reference or minor conversational flow adjustments. For the content of the answer, strictly adhere to the 'Retrieved answer (context)'.

Previous conversation:
{chat_context or 'None'}

Referenced documents (may be truncated):
{doc_context_block}

Current user question: {request.question}

Retrieved answer (context):
{best.get('detailed_answer','')}

Your detailed, bulleted answer:
"""
        print(prompt)
        llm_resp = chat_completion(
            openai_client,
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Helpful technical assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        final_answer = llm_resp.choices[0].message.content.strip()

        list_key = redis_key(chat_id, chat_type)
        is_first_message = redis_client.llen(list_key) == 0

        item = {
            "question": request.question,
            "answer": final_answer,
            "ts": iso_utc_now(),
            "document_ids": prior_doc_ids  # propagate any collected doc references
        }
        redis_client.rpush(list_key, json.dumps(item))

        meta_key = chat_meta_key(chat_id, chat_type)
        title = None
        if is_first_message:
            title = generate_chat_title(openai_client, request.question)
        else:
            existing = redis_client.get(meta_key)
            if existing:
                try:
                    existing_meta = json.loads(existing)
                    title = existing_meta.get("title")
                except Exception:
                    pass
            if not title:
                first_raw = redis_client.lindex(list_key, 0)
                if first_raw:
                    try:
                        first = json.loads(first_raw)
                        q = first.get("question", "").strip()
                        title = (q[:60] + "...") if q and len(q) > 60 else (q or "Conversation")
                    except Exception:
                        title = "Conversation"
                else:
                    title = "Conversation"

        # Merge prior_doc_ids into meta so they persist
        update_chat_meta_on_message(chat_id, chat_type, title, document_ids=prior_doc_ids)
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
