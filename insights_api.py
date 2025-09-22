from fastapi import FastAPI, HTTPException, APIRouter
from pydantic import BaseModel
from pymongo import MongoClient
from typing import List
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()
router = APIRouter(prefix="/insights", tags=["insights"])

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

# List insights  (GET /insights)
@router.get("/", response_model=List[InsightResponse])
async def get_insights():
    mongo_client, collection = connect_to_mongodb()
    if mongo_client is None or collection is None:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        insights = []
        # Sort descending so newest (by insertion) appears first
        cursor = collection.find({}, {"Insight ID": 1, "insight": 1}).sort([("_id", -1)])
        for doc in cursor:
            insights.append(
                InsightResponse(
                    id=doc.get("Insight ID", ""),
                    insight=doc.get("insight", "")
                )
            )
        return insights
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        mongo_client.close()



# Get one (GET /insights/{insight_id})
@router.get("/{insight_id}", response_model=DetailedInsightResponse)
async def get_insight_by_id(insight_id: str):
    # Connect to MongoDB
    mongo_client, collection = connect_to_mongodb()
    if mongo_client is None or collection is None:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        # Find document by Insight ID
        doc = collection.find_one({"Insight ID": insight_id})
        
        if not doc:
            raise HTTPException(status_code=404, detail="Not found")
        
        # Collect follow-up questions
        follow_ups = []
        for i in range(1, 4):
            key = f"follow_up_question_{i}"
            if doc.get(key):
                follow_ups.append(doc[key])
        
        # Return detailed insight response
        return DetailedInsightResponse(
            id=doc.get("Insight ID", ""),
            insight=doc.get("insight", ""),
            detailed_answer=doc.get("detailed_answer", ""),
            follow_up_questions=follow_ups
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        mongo_client.close()

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)