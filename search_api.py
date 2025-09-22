from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from openai import OpenAI
import os
from dotenv import load_dotenv
import numpy as np
from typing import List, Optional
import redis
import json
import uuid  # Added for session id generation
from fastapi.responses import JSONResponse

# Load environment variables
load_dotenv()

app = FastAPI()

# Redis connection
redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", 6379))
redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

# Pydantic models for request and response
class QuestionRequest(BaseModel):
    question: str
    session_id: Optional[str] = None  # Made optional

class SearchResponse(BaseModel):
    question: str
    answer: str
    follow_up_questions: List[str]
    session_id: str  # Added to response

class HistoryItem(BaseModel):
    session_id: str
    question: str
    answer: str

class HistoryResponse(BaseModel):
    history: List[HistoryItem]

def connect_to_mongodb():
    """Connect to MongoDB and return database collection"""
    try:
        mongo_uri = os.getenv('mongo_connection_string')
        client = MongoClient(mongo_uri)
        db = client['crda']
        collection = db['knowledge_bank']
        return client, collection
    except Exception as e:
        print(f"Error connecting to MongoDB: {str(e)}")
        return None, None

def get_embedding(text: str, client: OpenAI) -> List[float]:
    """Get embedding for the input text using OpenAI API"""
    try:
        response = client.embeddings.create(
            model="text-embedding-ada-002",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error getting embedding: {str(e)}")
        raise HTTPException(status_code=500, detail="Error generating embedding")

def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def build_chat_context(session_id: str) -> str:
    """Builds a context string from previous chat history for the LLM prompt."""
    history = redis_client.lrange(f"chat_history:{session_id}", 0, -1)
    context = ""
    for item in history:
        entry = json.loads(item)
        context += f"User: {entry['question']}\nAssistant: {entry['answer']}\n"
    return context

@app.post("/search", response_model=SearchResponse)
async def search_question(request: QuestionRequest):
    # Generate session_id if not provided
    session_id = request.session_id or str(uuid.uuid4())

    # Initialize OpenAI client
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    # Connect to MongoDB
    mongo_client, collection = connect_to_mongodb()
    if mongo_client is None or collection is None:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        # Get embedding for the input question
        query_embedding = get_embedding(request.question, openai_client)

        # Get all documents and calculate similarity
        documents = list(collection.find({}))
        similarities = []

        for doc in documents:
            if 'question_embedding' in doc:
                similarity = cosine_similarity(query_embedding, doc['question_embedding'])
                similarities.append((similarity, doc))

        # Sort by similarity and get the top result
        if not similarities:
            raise HTTPException(status_code=404, detail="No matching documents found")

        similarities.sort(key=lambda x: x[0], reverse=True)
        best_match = similarities[0][1]

        # Extract follow-up questions from the document
        follow_up_questions = []
        for i in range(1, 4):  # Get all three follow-up questions
            follow_up_key = f'follow_up_question_{i}'
            if follow_up_key in best_match:
                follow_up_questions.append(best_match[follow_up_key])

        # Build chat context from previous history
        chat_context = build_chat_context(session_id)

        # Format the answer using LLM, including previous chat context
        prompt = f"""
        Previous conversation:
        {chat_context}
        Current question: {request.question}
        Raw Answer: {best_match['detailed_answer']}
        
        Please answer the current question, considering the previous conversation for context. 
        Make the answer clear, concise, and well-structured. Keep technical accuracy and make it engaging.
        """

        response_llm = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that uses previous conversation context to answer technical questions accurately and accessibly."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        formatted_answer = response_llm.choices[0].message.content.strip()

        # Prepare response with formatted answer
        response = SearchResponse(
            question=best_match['user_question'],
            answer=formatted_answer,
            follow_up_questions=follow_up_questions,
            session_id=session_id
        )

        # Save only user's question and answer to Redis for chat history
        history_item = {
            "session_id": session_id,
            "question": request.question,
            "answer": formatted_answer
        }
        redis_client.rpush(f"chat_history:{session_id}", json.dumps(history_item))

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        if mongo_client:
            mongo_client.close()

@app.get("/history/{session_id}", response_model=HistoryResponse)
async def get_history(session_id: str):
    try:
        history = redis_client.lrange(f"chat_history:{session_id}", 0, -1)
        history_list = [HistoryItem(**json.loads(item)) for item in history]
        return HistoryResponse(history=history_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching history")

@app.get("/sessions", response_model=List[str])
async def list_sessions():
    """List all session IDs with chat history."""
    keys = redis_client.keys("chat_history:*")
    session_ids = [key.split("chat_history:")[1] for key in keys]
    return session_ids

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete chat history for a session."""
    deleted = redis_client.delete(f"chat_history:{session_id}")
    if deleted:
        return JSONResponse(content={"detail": f"Session {session_id} deleted."})
    else:
        raise HTTPException(status_code=404, detail="Session not found.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)