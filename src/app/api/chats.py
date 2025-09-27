from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import List, Optional, Literal
import json, time
from datetime import datetime, timezone
from fastapi import FastAPI
from ..models.model import HistoryResponse, HistoryItem, ChatListItem
# Use service modules
from ..services.redis_service import (
    iso_utc_now,
    redis_client,
    redis_key,
    chat_meta_key,
    is_orphan,
    get_last_answer,
    to_iso,
    CHAT_ORDER_ZSET,
    remove_chat_order_member,
    delete_all_sessions as redis_delete_all_sessions
)


router = APIRouter(prefix="/chats", tags=["chats"])

@router.get("/{chat_id}", response_model=HistoryResponse)
async def get_history(chat_id: str, chat_type: Literal["question", "insight"]):
    key = redis_key(chat_id, chat_type)
    raw = redis_client.lrange(key, 0, -1)

    user_id = "admin"
    chat_title: Optional[str] = None

    meta_raw = redis_client.get(chat_meta_key(chat_id, chat_type))
    if meta_raw:
        try:
            meta = json.loads(meta_raw)
            user_id = meta.get("user_id", user_id)
            chat_title = meta.get("title")
        except Exception:
            pass

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
            if isinstance(data.get("ts"), (int, float)):
                data["ts"] = iso_utc_now()
            history_items.append(HistoryItem(**data))
        except Exception:
            continue

    if not meta_raw:
        meta_save = {
            "title": chat_title or "Conversation",
            "created": iso_utc_now(),
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

# update_chat_meta_on_message imported from redis_service
# list_chats and delete_session unchanged but now use redis_service helpers
@router.get("/", response_model=List[ChatListItem])
async def list_chats(include_insight: bool = True, include_question: bool = True):
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
        if ":" not in member:
            continue
        chat_type, chat_id = member.split(":", 1)
        if chat_type not in allowed_types:
            continue
        uniq = f"{chat_type}:{chat_id}"
        if uniq in seen:
            continue
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
                la = meta.get("last_activity")
                if la is not None:
                    last_activity_iso = to_iso(la)
            except Exception:
                pass

        if not title:
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
                last_answer=None,
                timestamp=last_activity_iso
            )
        )

    for t in allowed_types:
        pattern = f"chat:{t}:*"
        for key in redis_client.keys(pattern):
            chat_id = key.split(f"chat:{t}:")[1]
            uniq = f"{t}:{chat_id}"
            if uniq in seen:
                continue
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
        if redis_client.exists(chat_meta_key(item.chat_id, "question")):
            item.last_answer = get_last_answer("question", item.chat_id)
        elif redis_client.exists(chat_meta_key(item.chat_id, "insight")):
            item.last_answer = get_last_answer("insight", item.chat_id)

    return results

@router.delete("/{chat_id}")
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


@router.delete("/")
async def delete_all_sessions_endpoint():
    """
    Delete all sessions in Redis using the redis service helper.
    """
    result = redis_delete_all_sessions()
    return {
        "detail": "All sessions deleted",
        "result": result
    }
