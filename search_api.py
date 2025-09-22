from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from pymongo import MongoClient
from openai import OpenAI
import os
from dotenv import load_dotenv
import numpy as np
from typing import List, Optional
import redis
import json
import uuid
from datetime import timedelta

# Load environment variables
load_dotenv()

app = FastAPI()

# Initialize Redis
redis_client = redis.Redis(
    host='localhost',
    port=6379,
    db=0,
    decode_responses=True
)

# Update Pydantic models
class QuestionRequest(BaseModel):
    question: str
    session_id: Optional[str] = None

class ChatHistory(BaseModel):
    session_id: str
    messages: List[dict]

class SearchResponse(BaseModel):
    session_id: str
    question: str
    answer: str
    follow_up_questions: List[str]
    chat_history: List[dict]

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

def get_or_create_session(session_id: Optional[str] = None) -> str:
    """Get existing session or create new one"""
    if not session_id:
        session_id = str(uuid.uuid4())
    return session_id

def update_chat_history(session_id: str, question: str, answer: str):
    """Update chat history in Redis"""
    try:
        # Get existing history or create new
        history = redis_client.get(f"chat_history:{session_id}")
        if history:
            messages = json.loads(history)
        else:
            messages = []

        # Add new message pair
        messages.append({
            "question": question,
            "answer": answer,
            "timestamp": str(datetime.now())
        })

        # Store updated history
        redis_client.setex(
            f"chat_history:{session_id}",
            timedelta(hours=24),  # Expire after 24 hours
            json.dumps(messages)
        )
        return messages
    except Exception as e:
        print(f"Error updating chat history: {str(e)}")
        return []

def get_chat_history(session_id: str) -> List[dict]:
    """Retrieve chat history from Redis"""
    try:
        history = redis_client.get(f"chat_history:{session_id}")
        if history:
            return json.loads(history)
        return []
    except Exception as e:
        print(f"Error getting chat history: {str(e)}")
        return []

@app.post("/search", response_model=SearchResponse)
async def search_question(request: QuestionRequest):
    # Get or create session
    session_id = get_or_create_session(request.session_id)
    
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

        # Format the answer using LLM with context from chat history
        chat_history = get_chat_history(session_id)
        context = "\n".join([
            f"Q: {msg['question']}\nA: {msg['answer']}"
            for msg in chat_history[-3:]  # Use last 3 messages for context
        ])

        formatted_answer = format_response_with_llm(
            question=request.question,
            answer=best_match['detailed_answer'],
            context=context,
            client=openai_client
        )

        # Update chat history
        updated_history = update_chat_history(
            session_id,
            request.question,
            formatted_answer
        )

        # Prepare response
        response = SearchResponse(
            session_id=session_id,
            question=best_match['user_question'],
            answer=formatted_answer,
            follow_up_questions=follow_up_questions,
            chat_history=updated_history
        )

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        if mongo_client:
            mongo_client.close()

# Update the format_response_with_llm function to include context
def format_response_with_llm(question: str, answer: str, context: str, client: OpenAI) -> str:
    """Format the answer using OpenAI's LLM with conversation context"""
    try:
        prompt = f"""
        Previous Conversation:
        {context}

        Current Question: {question}
        Raw Answer: {answer}
        
        Please provide a response that:
        1. Is clear and well-structured
        2. Maintains technical accuracy
        3. Considers the context of previous messages
        4. Is engaging and easy to understand
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides consistent and contextual responses while maintaining technical accuracy."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error formatting response: {str(e)}")
        return answer