from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from openai import OpenAI
import os
from dotenv import load_dotenv
import numpy as np
from typing import List, Optional

# Load environment variables
load_dotenv()

app = FastAPI()

# Pydantic models for request and response
class QuestionRequest(BaseModel):
    question: str

class FollowUpQuestion(BaseModel):
    question: str

class SearchResponse(BaseModel):
    question: str
    answer: str
    follow_up_questions: List[str]

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

@app.post("/search", response_model=SearchResponse)
async def search_question(request: QuestionRequest):
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

        # Prepare response with follow-up questions
        response = SearchResponse(
            question=best_match['user_question'],
            answer=best_match['detailed_answer'],
            follow_up_questions=follow_up_questions
        )

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        if mongo_client:
            mongo_client.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)