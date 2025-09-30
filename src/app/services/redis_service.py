import os
import json
import time
import redis
from datetime import datetime, timezone
from typing import Optional, List

redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", 6379))
redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

CHAT_ORDER_ZSET = "chat:order"  # member format: "<chat_type>:<chat_id>"
# add the additional chat types you want handled when aggregating context/order
ADDITIONAL_CHAT_TYPES = ["documentqna"]
DEFAULT_CHAT_TYPES = ["question", "insight"] + ADDITIONAL_CHAT_TYPES

def iso_utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def redis_key(chat_id: str, chat_type: str) -> str:
    return f"chat:{chat_type}:{chat_id}"

def chat_meta_key(chat_id: str, chat_type: str) -> str:
    return f"chatmeta:{chat_type}:{chat_id}"

def chat_order_member(chat_type: str, chat_id: str) -> str:
    return f"{chat_type}:{chat_id}"

def update_chat_order(chat_type: str, chat_id: str):
    try:
        redis_client.zadd(CHAT_ORDER_ZSET, {chat_order_member(chat_type, chat_id): time.time()})
    except Exception:
        pass

def remove_chat_order_member(chat_id: str, chat_type: Optional[str] = None):
    try:
        if chat_type:
            redis_client.zrem(CHAT_ORDER_ZSET, chat_order_member(chat_type, chat_id))
        else:
            # remove for default set of chat types (includes the new 'upload' type)
            members = [chat_order_member(t, chat_id) for t in DEFAULT_CHAT_TYPES]
            redis_client.zrem(CHAT_ORDER_ZSET, *members)
    except Exception:
        pass

def is_orphan(chat_type: str, chat_id: str) -> bool:
    return (
        not redis_client.exists(redis_key(chat_id, chat_type))
        and not redis_client.exists(chat_meta_key(chat_id, chat_type))
    )

def build_chat_context(chat_id: str, chat_type: Optional[str] = None) -> str:
    keys = []
    if chat_type:
        keys.append(redis_key(chat_id, chat_type))
    else:
        # include the additional chat type(s) when no specific type requested
        for t in DEFAULT_CHAT_TYPES:
            keys.append(redis_key(chat_id, t))

    parts = []
    for k in keys:
        history = redis_client.lrange(k, 0, -1)
        for item in history:
            try:
                entry = json.loads(item)
                parts.append(f"User: {entry.get('question','')}\nAssistant: {entry.get('answer','')}")
            except Exception:
                continue
    return "\n".join(parts)

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

def update_chat_meta_on_message(chat_id: str, chat_type: str, title: Optional[str] = None, document_ids: Optional[List[str]] = None):
    """
    Update chat meta and optionally merge document_ids into the meta.
    Backwards-compatible: callers that don't pass document_ids are unaffected.
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
    if "created" not in meta:
        meta["created"] = now_iso
    meta["last_activity"] = now_iso
    if title:
        meta["title"] = title
    else:
        meta.setdefault("title", "Conversation")
    meta.setdefault("user_id", "admin")

    # Merge document_ids if provided
    if document_ids:
        try:
            prev_ids = meta.get("document_ids", [])
            if not isinstance(prev_ids, list):
                prev_ids = []
            merged = list(dict.fromkeys(prev_ids + document_ids))  # preserve order, dedupe
            meta["document_ids"] = merged
        except Exception:
            # fallback to provided ids
            meta["document_ids"] = document_ids

    redis_client.set(key, json.dumps(meta))
    return meta

def add_document_ids_to_meta(chat_id: str, chat_type: str, document_ids: List[str]):
    """
    Helper to add/merge document ids into chat meta without altering other fields.
    """
    return update_chat_meta_on_message(chat_id, chat_type, title=None, document_ids=document_ids)


def delete_all_sessions(batch_size: int = 500) -> dict:
    """
    Delete all chat lists (chat:<type>:<id>), meta keys (chatmeta:<type>:<id>)
    and the CHAT_ORDER_ZSET. Returns counts of deleted keys.
    """
    deleted_lists = 0
    deleted_meta = 0

    try:
        # delete chat lists
        keys_iter = redis_client.scan_iter(match="chat:*:*", count=1000)
        batch = []
        for k in keys_iter:
            batch.append(k)
            if len(batch) >= batch_size:
                deleted_lists += redis_client.delete(*batch)
                batch = []
        if batch:
            deleted_lists += redis_client.delete(*batch)

        # delete chat meta keys
        keys_iter = redis_client.scan_iter(match="chatmeta:*:*", count=1000)
        batch = []
        for k in keys_iter:
            batch.append(k)
            if len(batch) >= batch_size:
                deleted_meta += redis_client.delete(*batch)
                batch = []
        if batch:
            deleted_meta += redis_client.delete(*batch)

        # remove ordering zset if present
        removed_order = False
        if redis_client.exists(CHAT_ORDER_ZSET):
            redis_client.delete(CHAT_ORDER_ZSET)
            removed_order = True

        return {
            "deleted_lists": int(deleted_lists),
            "deleted_meta": int(deleted_meta),
            "removed_order_zset": removed_order
        }
    except Exception:
        return {
            "deleted_lists": int(deleted_lists),
            "deleted_meta": int(deleted_meta),
            "removed_order_zset": False
        }