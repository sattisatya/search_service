from fastapi import FastAPI, HTTPException, APIRouter
from typing import List
import os
from datetime import datetime
from dotenv import load_dotenv
from ..services.mongo_service import connect_to_mongodb
from ..models.model import InsightResponse

# Load environment variables
load_dotenv()

app = FastAPI()
router = APIRouter(prefix="/insights", tags=["insights"])

# List insights  (GET /insights)
@router.get("/", response_model=List[InsightResponse])
async def get_insights():
    mongo_client, collection = connect_to_mongodb(os.getenv("insights_collection_name", "insights"))
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

            # Only convert the retrieved time to a string; don't set or update it here
            updated_at_raw = doc.get("updatedAt")
            if isinstance(updated_at_raw, datetime):
                updated_at_str = updated_at_raw.isoformat()
            elif isinstance(updated_at_raw, str):
                try:
                    updated_at_str = datetime.fromisoformat(updated_at_raw).isoformat()
                except Exception:
                    updated_at_str = updated_at_raw  # Keep as-is if not ISO
            else:
                updated_at_str = ""

            insights.append(
            InsightResponse(
                id=doc.get("Insight ID", ""),
                title=doc.get("title", doc.get("insight", "")[:50] + "..."),
                updatedAt=updated_at_str,
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
