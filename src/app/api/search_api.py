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
                    "similarity_score": 1
                }
            }
        ]
        results = list(collection.aggregate(pipeline))
        if not results:
            raise HTTPException(status_code=404, detail="No matches")
        best = results[0]

        follow_up_questions = []
        for i in range(1, 4):
            k = f"follow_up_question_{i}"
            if best.get(k):
                follow_up_questions.append(best[k])

        chat_context = build_chat_context(chat_id, chat_type)

        prompt = f"""Previous conversation:
{chat_context}

Current user question: {request.question}

Retrieved answer (context):
{best.get('detailed_answer','')}

Provide the best possible answer using prior context if helpful. Be concise and accurate."""
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
            "ts": iso_utc_now()
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

        update_chat_meta_on_message(chat_id, chat_type, title)
        update_chat_order(chat_type, chat_id)

        return SearchResponse(
            question=request.question,
            answer=final_answer,
            follow_up_questions=follow_up_questions,
            chat_id=chat_id,
            chat_type=chat_type,
            title=title
        )
    finally:
        if mongo_client:
            mongo_client.close()
