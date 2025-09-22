from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from typing import List
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()

class InsightRequest(BaseModel):
    id: str
    insight: str
    detailed_answer: str
    follow_up_question_1: str
    follow_up_question_2: str
    follow_up_question_3: str
    tags: str

class InsightResponse(BaseModel):
    id: str
    insight: str

# Add new response model for detailed insights
class DetailedInsightResponse(BaseModel):
    id: str
    insight: str
    detailed_answer: str
    follow_up_questions: List[str]

def connect_to_mongodb():
    """Connect to MongoDB and return database collection"""
    try:
        mongo_uri = os.getenv('mongo_connection_string')
        client = MongoClient(mongo_uri)
        db = client['crda']
        collection = db['insights']
        return client, collection
    except Exception as e:
        print(f"Error connecting to MongoDB: {str(e)}")
        return None, None

@app.get("/insights", response_model=List[InsightResponse])
async def get_insights():
    # Connect to MongoDB
    mongo_client, collection = connect_to_mongodb()
    if mongo_client is None or collection is None:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        # Get all insights from collection
        insights = []
        cursor = collection.find({}, {"Insight ID": 1, "insight": 1})
        
        for doc in cursor:
            insights.append(InsightResponse(
                id=doc.get("Insight ID", ""),
                insight=doc.get("insight", "")
            ))
        
        return insights

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        if mongo_client:
            mongo_client.close()

@app.get("/insights", response_model=InsightResponse)
async def create_insight(insight: InsightRequest):
    # Connect to MongoDB
    mongo_client, collection = connect_to_mongodb()
    if mongo_client is None or collection is None:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        # Convert insight to dictionary
        insight_dict = insight.dict()
        insight_dict["Insight ID"] = insight_dict.pop("id")  # Rename id field to match schema
        
        # Insert the document
        result = collection.insert_one(insight_dict)
        
        if result.inserted_id:
            return InsightResponse(
                id=insight.id,
                insight=insight.insight
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to insert insight")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        if mongo_client:
            mongo_client.close()

@app.get("/insights/{insight_id}", response_model=DetailedInsightResponse)
async def get_insight_by_id(insight_id: str):
    # Connect to MongoDB
    mongo_client, collection = connect_to_mongodb()
    if mongo_client is None or collection is None:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        # Find document by Insight ID
        doc = collection.find_one({"Insight ID": insight_id})
        
        if not doc:
            raise HTTPException(status_code=404, detail=f"Insight with ID {insight_id} not found")
        
        # Collect follow-up questions
        follow_ups = []
        for i in range(1, 4):
            question_key = f"follow_up_question_{i}"
            if question_key in doc and doc[question_key]:
                follow_ups.append(doc[question_key])
        
        # Return detailed insight response
        return DetailedInsightResponse(
            id=doc["Insight ID"],
            insight=doc["insight"],
            detailed_answer=doc["detailed_answer"],
            follow_up_questions=follow_ups
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        if mongo_client:
            mongo_client.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)