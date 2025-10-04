import os
import json
import time
import redis
from datetime import datetime, timezone
from typing import Optional, List

redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", 6379))
redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

CHAT_ORDER_ZSET = "chat:order"
DEFAULT_CHAT_TYPES = ["question", "insight"]

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
            members = [chat_order_member(t, chat_id) for t in DEFAULT_CHAT_TYPES]
            redis_client.zrem(CHAT_ORDER_ZSET, *members)
    except Exception:
        pass

def is_orphan(chat_type: str, chat_id: str) -> bool:
    return (
        not redis_client.exists(redis_key(chat_id, chat_type))
        and not redis_client.exists(chat_meta_key(chat_id, chat_type))
    )

def build_chat_context(
    chat_id: str,
    chat_type: Optional[str] = None,
    max_messages_per_type: int = 50
) -> str:
    """
    Build a plain-text conversation context from last N messages.
    (No document id handling.)
    """
    keys = []
    if chat_type:
        keys.append(redis_key(chat_id, chat_type))
    else:
        for t in DEFAULT_CHAT_TYPES:
            keys.append(redis_key(chat_id, t))

    parts = []
    for k in keys:
        history = redis_client.lrange(k, -max_messages_per_type, -1)
        for item in history:
            try:
                entry = json.loads(item)
                q = entry.get("question", "")
                a = entry.get("answer", "")
                parts.append(f"User: {q}\nAssistant: {a}")
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

def update_chat_meta_on_message(chat_id: str, chat_type: str, title: Optional[str] = None):
    """
    Update chat meta (preserves existing document_ids).
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
    # DO NOT remove document_ids anymore (preserve if present)
    redis_client.set(key, json.dumps(meta))
    return meta

def add_doc_ids_to_chat_meta(chat_id: str, chat_type: str, doc_ids):
    if not doc_ids:
        return
    key = chat_meta_key(chat_id, chat_type)
    try:
        existing_raw = redis_client.get(key)
        if existing_raw:
            try:
                meta = json.loads(existing_raw)
            except Exception:
                meta = {}
        else:
            meta = {}
        existing_ids = set(meta.get("document_ids", []))
        # Preserve original order where possible, append new ones
        new_ids = [d for d in doc_ids if d not in existing_ids]
        if not new_ids:
            return
        meta["document_ids"] = meta.get("document_ids", []) + new_ids
        redis_client.set(key, json.dumps(meta))
    except Exception:
        pass

def delete_session(
    chat_id: str,
    chat_type: Optional[str] = None,
    delete_history: bool = True,
    delete_meta: bool = True,
    remove_order: bool = True
) -> dict:
    """
    Delete a single chat (history + meta + order entry).
    If chat_type is None, applies to all DEFAULT_CHAT_TYPES.
    """
    types = [chat_type] if chat_type else DEFAULT_CHAT_TYPES
    deleted_history = 0
    deleted_meta = 0
    removed_order_entries = 0

    for t in types:
        if delete_history:
            k_hist = redis_key(chat_id, t)
            try:
                if redis_client.exists(k_hist):
                    deleted_history += redis_client.delete(k_hist)
            except Exception:
                pass
        if delete_meta:
            k_meta = chat_meta_key(chat_id, t)
            try:
                if redis_client.exists(k_meta):
                    deleted_meta += redis_client.delete(k_meta)
            except Exception:
                pass
        if remove_order:
            try:
                rem = redis_client.zrem(CHAT_ORDER_ZSET, chat_order_member(t, chat_id))
                removed_order_entries += rem
            except Exception:
                pass

    return {
        "chat_id": chat_id,
        "types_processed": types,
        "deleted_history": deleted_history,
        "deleted_meta": deleted_meta,
        "removed_order_entries": removed_order_entries
    }


def delete_all_sessions(
    batch_size: int = 500,
    only_types: Optional[List[str]] = None,
    include_order_zset: bool = True
) -> dict:
    """
    Delete all chats (optionally restricted to only_types).
    - only_types: if provided, only keys for those chat types are removed.
    - include_order_zset: control whether CHAT_ORDER_ZSET is deleted.
    """
    type_filter = set(only_types) if only_types else None

    def type_allowed(key: str) -> bool:
        # key formats: chat:<type>:<id> or chatmeta:<type>:<id>
        try:
            parts = key.split(":")
            if len(parts) >= 3:
                t = parts[1]
                if type_filter is None:
                    return True
                return t in type_filter
        except Exception:
            return False
        return False

    deleted_lists = 0
    deleted_meta = 0

    try:
        # chat histories
        keys_iter = redis_client.scan_iter(match="chat:*:*", count=1000)
        batch = []
        for k in keys_iter:
            if not k.startswith("chatmeta:") and type_allowed(k):
                batch.append(k)
                if len(batch) >= batch_size:
                    try:
                        deleted_lists += redis_client.delete(*batch)
                    except Exception:
                        pass
                    batch = []
        if batch:
            try:
                deleted_lists += redis_client.delete(*batch)
            except Exception:
                pass

        # chat meta
        keys_iter = redis_client.scan_iter(match="chatmeta:*:*", count=1000)
        batch = []
        for k in keys_iter:
            if type_allowed(k):
                batch.append(k)
                if len(batch) >= batch_size:
                    try:
                        deleted_meta += redis_client.delete(*batch)
                    except Exception:
                        pass
                    batch = []
        if batch:
            try:
                deleted_meta += redis_client.delete(*batch)
            except Exception:
                pass

        removed_order = False
        if include_order_zset and redis_client.exists(CHAT_ORDER_ZSET):
            try:
                if type_filter:
                    # Remove only members whose prefix matches allowed types
                    members = redis_client.zrange(CHAT_ORDER_ZSET, 0, -1)
                    to_remove = [
                        m for m in members
                        if m.split(":", 1)[0] in type_filter
                    ]
                    if to_remove:
                        redis_client.zrem(CHAT_ORDER_ZSET, *to_remove)
                        removed_order = True
                else:
                    redis_client.delete(CHAT_ORDER_ZSET)
                    removed_order = True
            except Exception:
                pass

        return {
            "deleted_lists": int(deleted_lists),
            "deleted_meta": int(deleted_meta),
            "removed_order_zset": removed_order,
            "filtered_types": list(type_filter) if type_filter else None
        }
    except Exception:
        return {
            "deleted_lists": int(deleted_lists),
            "deleted_meta": int(deleted_meta),
            "removed_order_zset": False,
            "filtered_types": list(type_filter) if type_filter else None
        }

def push_history_item(
    chat_id: str,
    chat_type: str,
    question: str,
    answer: str,
    tags: List[dict],
    document_ids: Optional[List[str]] = None,
    extra: Optional[dict] = None,
    ts: Optional[str] = None
) -> int:
    """
    Append a history item to Redis. Tags are stored as-is (list of dicts).
    Optionally include follow_up_questions via 'extra'.
    """
    entry = {
        "question": question,
        "answer": answer,
        "ts": ts or iso_utc_now(),
        "tags": tags or [],
        "document_ids": document_ids or []
    }
    if extra:
        entry.update(extra)
    try:
        return redis_client.rpush(redis_key(chat_id, chat_type), json.dumps(entry))
    except Exception:
        return 0