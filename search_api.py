from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from openai import OpenAI
from dotenv import load_dotenv
from typing import List, Optional, Literal
import os, uuid, json, redis, numpy as np, time, re

load_dotenv()

redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", 6379))
redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

router = APIRouter(tags=["search"])

# ------------------ MODELS ------------------

class QuestionRequest(BaseModel):
    question: str
    chat_id: Optional[str] = None
    chat_type: Literal["question", "insight"] = "question"

class SearchResponse(BaseModel):
    question: str
    answer: str
    follow_up_questions: List[str]
    chat_id: str
    chat_type: Literal["question", "insight"]
    title: Optional[str] = None   # NEW (returned only when created)

class HistoryItem(BaseModel):
    question: str
    answer: str
    ts: Optional[int] = None  # unix timestamp (user_id removed from each item)

class HistoryResponse(BaseModel):
    chat_id: str
    chat_type: Literal["question", "insight"]
    user_id: str
    chat_title: Optional[str] = None          # NEW: title outside the list
    history: List[HistoryItem]

class ChatSummary(BaseModel):
    chat_id: str
    chat_type: Literal["question", "insight"]
    title: Optional[str] = None
    created: Optional[int] = None
    message_count: int

class ChatListItem(BaseModel):
    chat_id: str
    title: str

# ------------------ HELPERS ------------------

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

def redis_key(chat_id: str, chat_type: str) -> str:
    return f"chat:{chat_type}:{chat_id}"

def chat_meta_key(chat_id: str, chat_type: str) -> str:
    return f"chatmeta:{chat_type}:{chat_id}"

def build_chat_context(chat_id: str, chat_type: str | None = None) -> str:
    keys = []
    if chat_type:
        keys.append(redis_key(chat_id, chat_type))
    else:
        keys.append(redis_key(chat_id, "question"))
        keys.append(redis_key(chat_id, "insight"))

    parts = []
    for k in keys:
        history = redis_client.lrange(k, 0, -1)
        for item in history:
            entry = json.loads(item)
            parts.append(f"User: {entry['question']}\nAssistant: {entry['answer']}")
    return "\n".join(parts)

def generate_chat_title(client: OpenAI, question: str) -> str:
    prompt = f"""
Generate a short (max 7 words) clear, professional title summarizing this chat based ONLY on the first user question below.

Question: {question}

Return only the title, no quotes, no punctuation at end.
"""
    try:
        resp = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role":"system","content":"You create concise, descriptive chat titles."},
                {"role":"user","content": prompt.strip()}
            ],
            temperature=0.4,
            max_tokens=30
        )
        title = resp.choices[0].message.content.strip()
        title = title.strip('"').strip("'")
        # Collapse whitespace
        title = re.sub(r"\s+", " ", title)
        # Enforce hard limit
        if len(title) > 60:
            title = title[:57].rstrip() + "..."
        return title
    except Exception:
        return "Conversation"

# ------------------ ENDPOINTS ------------------

@router.post("/search", response_model=SearchResponse)
async def search_question(request: QuestionRequest):
    chat_id = request.chat_id or str(uuid.uuid4())
    chat_type = request.chat_type
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    mongo_client, collection = connect_to_mongodb()
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

        list_key = redis_key(chat_id, chat_type)
        is_first_message = redis_client.llen(list_key) == 0

        # Store item WITHOUT user_id now
        item = {
            "question": request.question,
            "answer": final_answer,
            "ts": int(time.time())
        }
        redis_client.rpush(list_key, json.dumps(item))

        # ALWAYS provide a title in the response
        title = None
        meta_key = chat_meta_key(chat_id, chat_type)

        if is_first_message:
            title = generate_chat_title(openai_client, request.question)
            meta = {"title": title, "created": int(time.time()), "user_id": "admin"}
            redis_client.set(meta_key, json.dumps(meta))
        else:
            meta_raw = redis_client.get(meta_key)
            meta = {}
            if meta_raw:
                try:
                    meta = json.loads(meta_raw)
                    title = meta.get("title")
                except Exception:
                    meta = {}
            if not title:
                # Fallback derive from first message
                first_raw = redis_client.lindex(list_key, 0)
                if first_raw:
                    try:
                        first = json.loads(first_raw)
                        q = first.get("question", "").strip()
                        title = (q[:60] + "...") if len(q) > 60 else q or "Conversation"
                    except Exception:
                        title = "Conversation"
                else:
                    title = "Conversation"
                # Persist missing meta
                meta.setdefault("user_id", "admin")
                meta["title"] = title
                meta.setdefault("created", int(time.time()))
                redis_client.set(meta_key, json.dumps(meta))
            else:
                # Ensure user_id exists for backward compatibility
                if "user_id" not in meta:
                    meta["user_id"] = "admin"
                    redis_client.set(meta_key, json.dumps(meta))

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

@router.get("/chats/{chat_id}", response_model=HistoryResponse)
async def get_history(chat_id: str, chat_type: Literal["question", "insight"]):
    key = redis_key(chat_id, chat_type)
    raw = redis_client.lrange(key, 0, -1)

    user_id = "admin"
    chat_title: Optional[str] = None

    # Read meta
    meta_raw = redis_client.get(chat_meta_key(chat_id, chat_type))
    if meta_raw:
        try:
            meta = json.loads(meta_raw)
            user_id = meta.get("user_id", user_id)
            chat_title = meta.get("title")
        except Exception:
            pass

    # If no title in meta, derive from first message (fallback)
    if not chat_title and raw:
        try:
            first = json.loads(raw[0])
            q = first.get("question", "").strip()
            chat_title = (q[:60] + "...") if len(q) > 60 else q or "Conversation"
        except Exception:
            chat_title = "Conversation"

    history_items: List[HistoryItem] = []
    for r in raw:
        try:
            data = json.loads(r)
            if "user_id" in data and user_id == "admin":
                user_id = data["user_id"]
            data.pop("user_id", None)
            history_items.append(HistoryItem(**data))
        except Exception:
            continue

    # Persist back filled title/user_id if meta missing
    if not meta_raw:
        meta_save = {
            "title": chat_title or "Conversation",
            "created": int(time.time()),
            "user_id": user_id
        }
        redis_client.set(chat_meta_key(chat_id, chat_type), json.dumps(meta_save))

    return HistoryResponse(
        chat_id=chat_id,
        chat_type=chat_type,
        user_id=user_id,
        chat_title=chat_title,
        history=history_items
    )

@router.get("/chats", response_model=List[ChatListItem])
async def list_chats(include_insight: bool = True, include_question: bool = True):
    items: List[ChatListItem] = []
    types: List[str] = []
    if include_question:
        types.append("question")
    if include_insight:
        types.append("insight")

    for t in types:
        for key in redis_client.keys(f"chat:{t}:*"):
            chat_id = key.split(f"chat:{t}:")[1]
            # Try meta title
            meta_raw = redis_client.get(chat_meta_key(chat_id, t))
            title = None
            if meta_raw:
                try:
                    meta = json.loads(meta_raw)
                    title = meta.get("title")
                except Exception:
                    pass
            # Fallback: derive from first message question
            if not title:
                first_raw = redis_client.lindex(key, 0)
                if first_raw:
                    try:
                        first = json.loads(first_raw)
                        q = first.get("question", "").strip()
                        title = (q[:60] + "...") if len(q) > 60 else q
                    except Exception:
                        pass
            items.append(ChatListItem(chat_id=chat_id, title=title or "Conversation"))
    # Optional: sort alphabetically by title
    items.sort(key=lambda x: x.title.lower())
    return items


@router.delete("/chats/{chat_id}")
async def delete_session(chat_id: str, chat_type: Optional[Literal["question","insight"]] = None):
    deleted = 0
    if chat_type in (None, "question"):
        deleted += redis_client.delete(redis_key(chat_id, "question"))
    if chat_type in (None, "insight"):
        deleted += redis_client.delete(redis_key(chat_id, "insight"))
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"detail": "Deleted", "chat_id": chat_id, "segments_deleted": deleted}