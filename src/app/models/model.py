from typing_extensions import Literal
from pydantic import BaseModel
from typing import List, Optional


class QuestionRequest(BaseModel):
    question: str
    chat_id: Optional[str] = None
    chat_type: str = "question"

class SearchResponse(BaseModel):
    question: str
    answer: str
    follow_up_questions: List[str] = []
    chat_id: str
    chat_type: Literal["question", "insight"]
    title: Optional[str] = None
    tags: List[str] = []
    file_url: Optional[str] = None  # NEW

class HistoryItem(BaseModel):
    question: str
    answer: str
    ts: Optional[str] = None
    tags: List[str] = []          # NEW

class HistoryResponse(BaseModel):
    chat_id: str
    chat_type: str
    user_id: str
    chat_title: Optional[str]
    history: List[HistoryItem]
    document_ids: List[str] = []   # <-- added

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

class InsightResponse(BaseModel):
    id: str
    title: str
    updatedAt: str
    insight: str
    user_question: str
    summary: str
    tags: list[str]

