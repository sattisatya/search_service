from pydantic import BaseModel
from typing import List, Optional, Literal


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
    title: Optional[str] = None

class HistoryItem(BaseModel):
    question: str
    answer: str
    ts: Optional[str] = None

class HistoryResponse(BaseModel):
    chat_id: str
    chat_type: Literal["question", "insight"]
    user_id: str
    chat_title: Optional[str] = None
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
    last_answer: Optional[str] = None
    timestamp: Optional[str] = None


# Updated Response model
class InsightResponse(BaseModel):
    id: str
    title: str
    updatedAt: str
    summary: str
    type: str
    tags: list[str]
