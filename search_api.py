from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from openai import OpenAI
from dotenv import load_dotenv
from typing import List, Optional, Literal
import os, uuid, json, redis, numpy as np, time, re
from datetime import datetime, timezone

load_dotenv()

redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", 6379))
redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

router = APIRouter(tags=["search"])

def iso_utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

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
    ts: Optional[str] = None  # CHANGED: store UTC ISO string

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
    last_answer: Optional[str] = None        # NEW: latest answer text
    timestamp: Optional[str] = None          # NEW: ISO UTC timestamp of latest message (or meta created)

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

# ------------------ ORDERING (NEW: Redis Sorted Set) ------------------
CHAT_ORDER_ZSET = "chat:order"  # member format: "<chat_type>:<chat_id>"

def chat_order_member(chat_type: str, chat_id: str) -> str:
    return f"{chat_type}:{chat_id}"

def update_chat_order(chat_type: str, chat_id: str):
    """
    Store/update chat recency using a Redis sorted set scored by epoch seconds.
    Guarantees deterministic newest-first ordering.
    """
    try:
        redis_client.zadd(CHAT_ORDER_ZSET, {chat_order_member(chat_type, chat_id): time.time()})
    except Exception:
        # Fallback: ignore ordering failure
        pass

def remove_chat_order_member(chat_id: str, chat_type: Optional[str] = None):
    """
    Remove one or both members from the chat:order sorted set.
    If chat_type is None, remove both possible variants.
    """
    try:
        if chat_type:
            redis_client.zrem(CHAT_ORDER_ZSET, chat_order_member(chat_type, chat_id))
        else:
            redis_client.zrem(
                CHAT_ORDER_ZSET,
                chat_order_member("question", chat_id),
                chat_order_member("insight", chat_id),
            )
    except Exception:
        pass

# (Optional) prune orphaned zset members (used inside list endpoint)
def is_orphan(chat_type: str, chat_id: str) -> bool:
    return (
        not redis_client.exists(redis_key(chat_id, chat_type))
        and not redis_client.exists(chat_meta_key(chat_id, chat_type))
    )

def get_last_answer(chat_type: str, chat_id: str) -> Optional[str]:
    try:
        last_raw = redis_client.lindex(redis_key(chat_id, chat_type), -1)
        if last_raw:
            obj = json.loads(last_raw)
            return obj.get("answer")
    except Exception:
        pass
    return None

def to_iso(val) -> str:
    if isinstance(val, (int, float)):
        return datetime.fromtimestamp(val, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(val, str):
        try:
            datetime.strptime(val, "%Y-%m-%dT%H:%M:%SZ")
            return val
        except Exception:
            return iso_utc_now()
    return iso_utc_now()

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
            # Try existing title
            existing = redis_client.get(meta_key)
            if existing:
                try:
                    existing_meta = json.loads(existing)
                    title = existing_meta.get("title")
                except Exception:
                    pass
            if not title:
                # Fallback derive from first message
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
        update_chat_order(chat_type, chat_id)   # NEW: recency tracking

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

            # Normalize legacy numeric ts -> ISO
            if isinstance(data.get("ts"), (int, float)):
                data["ts"] = iso_utc_now()
            history_items.append(HistoryItem(**data))
        except Exception:
            continue

    if not meta_raw:
        meta_save = {
            "title": chat_title or "Conversation",
            "created": iso_utc_now(),  # CHANGED: ensure ISO string
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


def update_chat_meta_on_message(chat_id: str, chat_type: str, title: Optional[str] = None):
    """
    Update (or create) chat meta:
      - created: first creation time (kept immutable)
      - last_activity: updated every message
      - title: only set/updated if provided (else preserved)
      - user_id: fixed 'admin' for now
    """
    key = chat_meta_key(chat_id, chat_type)
    now_iso = iso_utc_now()
    meta = {}
    raw = redis_client.get(key)
    if raw:
        try:
            meta = json.loads(raw)
        except Exception:
            meta = {}
    # Keep original created
    if "created" not in meta:
        meta["created"] = now_iso
    # Always update last_activity
    meta["last_activity"] = now_iso
    # Title logic
    if title:
        meta["title"] = title
    else:
        meta.setdefault("title", "Conversation")
    meta.setdefault("user_id", "admin")
    redis_client.set(key, json.dumps(meta))
    return meta


@router.get("/chats", response_model=List[ChatListItem])
async def list_chats(
    include_insight: bool = True,
    include_question: bool = True
):
    """
    Deterministic newest-first list using a Redis sorted set.
    Only top 'answer_expose_limit' items include last_answer.
    """
    answer_expose_limit = 1
    if answer_expose_limit < 0:
        answer_expose_limit = 0

    allowed_types = set()
    if include_question:
        allowed_types.add("question")
    if include_insight:
        allowed_types.add("insight")

    try:
        members = redis_client.zrevrange(CHAT_ORDER_ZSET, 0, -1, withscores=True)
    except Exception:
        members = []

    results: List[ChatListItem] = []
    seen = set()

    for member, score in members:
        # member format chat_type:chat_id
        if ":" not in member:
            continue
        chat_type, chat_id = member.split(":", 1)
        if chat_type not in allowed_types:
            continue
        # Avoid duplicates
        uniq = f"{chat_type}:{chat_id}"
        if uniq in seen:
            continue
        # SKIP & CLEAN ORPHANS (no list + no meta)
        if is_orphan(chat_type, chat_id):
            remove_chat_order_member(chat_id, chat_type)
            continue
        seen.add(uniq)

        meta_raw = redis_client.get(chat_meta_key(chat_id, chat_type))
        title = None
        last_activity_iso = to_iso(score)

        if meta_raw:
            try:
                meta = json.loads(meta_raw)
                title = meta.get("title") or title
                # Prefer stored last_activity if exists
                la = meta.get("last_activity")
                if la is not None:
                    last_activity_iso = to_iso(la)
            except Exception:
                pass

        if not title:
            # Fallback from first message
            first_raw = redis_client.lindex(redis_key(chat_id, chat_type), 0)
            if first_raw:
                try:
                    first = json.loads(first_raw)
                    q = first.get("question", "").strip()
                    title = (q[:60] + "...") if q and len(q) > 60 else (q or None)
                except Exception:
                    pass
        if not title:
            title = "Conversation"

        results.append(
            ChatListItem(
                chat_id=chat_id,
                title=title,
                last_answer=None,   # fill later for top N
                timestamp=last_activity_iso
            )
        )

    # Migration support: include chats not yet in ZSET
    for t in allowed_types:
        pattern = f"chat:{t}:*"
        for key in redis_client.keys(pattern):
            chat_id = key.split(f"chat:{t}:")[1]
            uniq = f"{t}:{chat_id}"
            if uniq in seen:
                continue
            # Skip orphans (should not happen here)
            if is_orphan(t, chat_id):
                continue
            last_raw = redis_client.lindex(key, -1)
            score_time = time.time()
            if last_raw:
                try:
                    last = json.loads(last_raw)
                    ts = last.get("ts")
                    if isinstance(ts, str):
                        try:
                            score_time = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").timestamp()
                        except Exception:
                            pass
                except Exception:
                    pass
            redis_client.zadd(CHAT_ORDER_ZSET, {f"{t}:{chat_id}": score_time})

    for item in results:
        # Determine chat type efficiently by checking meta keys first
        if redis_client.exists(chat_meta_key(item.chat_id, "question")):
            item.last_answer = get_last_answer("question", item.chat_id)
        elif redis_client.exists(chat_meta_key(item.chat_id, "insight")):
            item.last_answer = get_last_answer("insight", item.chat_id)

    return results

# ------------------ PATCH delete endpoint: also remove from sorted set ------------------
@router.delete("/chats/{chat_id}")
async def delete_session(chat_id: str, chat_type: Optional[Literal["question","insight"]] = None):
    deleted_lists = 0
    deleted_meta = 0

    if chat_type in (None, "question"):
        deleted_lists += redis_client.delete(redis_key(chat_id, "question"))
        deleted_meta += redis_client.delete(chat_meta_key(chat_id, "question"))
        remove_chat_order_member(chat_id, "question")

    if chat_type in (None, "insight"):
        deleted_lists += redis_client.delete(redis_key(chat_id, "insight"))
        deleted_meta += redis_client.delete(chat_meta_key(chat_id, "insight"))
        remove_chat_order_member(chat_id, "insight")

    if (deleted_lists + deleted_meta) == 0:
        # Ensure also no stale ordering member
        if chat_type:
            remove_chat_order_member(chat_id, chat_type)
        else:
            remove_chat_order_member(chat_id, None)
        raise HTTPException(status_code=404, detail="Not found")

    return {
        "detail": "Deleted",
        "chat_id": chat_id,
        "chat_type": chat_type,
        "message_lists_deleted": deleted_lists,
        "meta_keys_deleted": deleted_meta
    }
