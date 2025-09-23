from fastapi import FastAPI, HTTPException, APIRouter
from pydantic import BaseModel
from pymongo import MongoClient
from typing import List
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()
router = APIRouter(prefix="/insights", tags=["insights"])

# Updated Response model
class InsightResponse(BaseModel):
    id: str
    title: str
    updatedAt: str
    summary: str
    type: str
    tags: list[str]


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
        cursor = collection.find({}, {
            "Insight ID": 1,
            "insight": 1,
            "tags": 1,
            "type": 1,
            "updatedAt": 1,
            "title": 1
        }).sort([("_id", -1)])

        for doc in cursor:
            # Process tags
            raw_tags = doc.get("tags", "")
            if isinstance(raw_tags, str) and raw_tags.startswith("[") and raw_tags.endswith("]"):
                tags = [t.strip(" '\"") for t in raw_tags[1:-1].split(",") if t.strip(" '\"")]
            else:
                tags = [t.strip() for t in str(raw_tags).split(",") if t.strip()]
            
            # Get or generate timestamp
            updated_at = doc.get("updatedAt", datetime.utcnow().isoformat())
            
            # Create insight response
            insights.append(
                InsightResponse(
                    id=doc.get("Insight ID", ""),
                    title=doc.get("title", doc.get("insight", "")[:50] + "..."),
                    updatedAt=updated_at,
                    summary=doc.get("insight", ""),
                    type=doc.get("type", "DOCUMENT"),
                    tags=tags[:4]  # Limit to 4 tags
                )
            )
        return insights
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if mongo_client:
            mongo_client.close()



app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)