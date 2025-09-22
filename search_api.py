from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from openai import OpenAI
from dotenv import load_dotenv
from typing import List, Optional
import os, uuid, json, redis, numpy as np

load_dotenv()

redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", 6379))
redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

router = APIRouter(tags=["search"])

class QuestionRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    # top_k: Optional[int] = 1          # optional: how many results to consider (we still answer with best one)
    # candidates: Optional[int] = 1000  # optional: numCandidates for vector search

class SearchResponse(BaseModel):
    question: str
    answer: str
    follow_up_questions: List[str]
    session_id: str

class HistoryItem(BaseModel):
    session_id: str
    question: str
    answer: str

class HistoryResponse(BaseModel):
    history: List[HistoryItem]

def connect_to_mongodb():
    try:
        mongo_uri = os.getenv('mongo_connection_string')
        client = MongoClient(mongo_uri)
        db = client['crda']
        collection = db['knowledge_bank']
        return client, collection
    except Exception as e:
        print(f"Mongo error: {e}")
        return None, None

def get_embedding(text: str, client: OpenAI):
    try:
        resp = client.embeddings.create(model="text-embedding-ada-002", input=text)
        return resp.data[0].embedding
    except Exception:
        raise HTTPException(status_code=500, detail="Embedding failed")


def build_chat_context(session_id: str) -> str:
    history = redis_client.lrange(f"chat_history:{session_id}", 0, -1)
    parts = []
    for item in history:
        entry = json.loads(item)
        parts.append(f"User: {entry['question']}\nAssistant: {entry['answer']}")
    return "\n".join(parts)

@router.post("/search", response_model=SearchResponse)
async def search_question(request: QuestionRequest):
    session_id = request.session_id or str(uuid.uuid4())
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    mongo_client, collection = connect_to_mongodb()
    if mongo_client is None or collection is None:
        raise HTTPException(status_code=500, detail="DB connection failed")
    try:
        # 1. Get embedding
        query_embedding = get_embedding(request.question, openai_client)

        # 2. Vector search pipeline (MongoDB Atlas)
        limit = request.top_k or 1
        num_candidates = request.candidates or 1000
        vector_index = os.getenv("VECTOR_INDEX_NAME", "questions_index")

        pipeline = [
            {
                "$vectorSearch": {
                    "index": vector_index,
                    "path": "question_embedding",
                    "queryVector": query_embedding,
                    "numCandidates": num_candidates,
                    "limit": limit
                }
            },
            {
                "$addFields": {
                    "similarity_score": {"$meta": "vectorSearchScore"}
                }
            },
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

        # 3. Build context
        chat_context = build_chat_context(session_id)

        # 4. LLM formatting with context + retrieved doc answer
        prompt = f"""Previous conversation:
{chat_context}

Current user question: {request.question}

Retrieved answer (context):
{best.get('detailed_answer','')}

Provide the best possible answer to the current user question using prior context if helpful. Be concise and accurate."""
        llm_resp = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Helpful technical assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        final_answer = llm_resp.choices[0].message.content.strip()

        # 5. Store in Redis history (user question + final answer)
        history_item = {
            "session_id": session_id,
            "question": request.question,
            "answer": final_answer
        }
        redis_client.rpush(f"chat_history:{session_id}", json.dumps(history_item))

        return SearchResponse(
            question=request.question,
            answer=final_answer,
            follow_up_questions=follow_up_questions,
            session_id=session_id
        )
    finally:
        if mongo_client:
            mongo_client.close()

@router.get("/sessions/{session_id}", response_model=HistoryResponse)
async def get_history(session_id: str):
    try:
        history = redis_client.lrange(f"chat_history:{session_id}", 0, -1)
        items = [HistoryItem(**json.loads(h)) for h in history]
        return HistoryResponse(history=items)
    except Exception:
        raise HTTPException(status_code=500, detail="History fetch failed")

@router.get("/sessions", response_model=List[str])
async def list_sessions():
    keys = redis_client.keys("chat_history:*")
    return [k.split("chat_history:")[1] for k in keys]

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    deleted = redis_client.delete(f"chat_history:{session_id}")
    if not deleted:
        raise HTTPException(status_code=404, detail="Not found")
    return {"detail": "Deleted"}