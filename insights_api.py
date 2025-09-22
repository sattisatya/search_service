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

# Response model for listing insights
class InsightResponse(BaseModel):
    id: str
    insight: str
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
        cursor = collection.find({}, {"Insight ID": 1, "insight": 1, "tags": 1}).sort([("_id", -1)])

        for doc in cursor:
            raw_tags = doc.get("tags", "")
            # If tags is a string that looks like a list, e.g. "['tag1', 'tag2']"
            if isinstance(raw_tags, str) and raw_tags.startswith("[") and raw_tags.endswith("]"):
                # Remove brackets and split by comma
                tags = [t.strip(" '\"") for t in raw_tags[1:-1].split(",") if t.strip(" '\"")]
            else:
                # Otherwise, split by comma as usual
                tags = [t.strip() for t in str(raw_tags).split(",") if t.strip()]
            insights.append(
                InsightResponse(
                    id=doc.get("Insight ID", ""),
                    insight=doc.get("insight", ""),
                    tags=tags
                )
            )
        return insights
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        mongo_client.close()



app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)