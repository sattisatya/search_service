from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.app.api.search_api import router as search_router
from src.app.api.insights_api import router as insights_router
from src.app.api.chats import router as chats_router
from src.app.api.file_upload import router as upload_router
from fastapi import APIRouter

app = FastAPI(title="Unified Service")

# CORS: allow all origins (adjust later for security)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # or specify domains ["https://yourdomain.com"]
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
# wrap existing routers so they are exposed under the /api prefix
_orig_search_router = search_router
_orig_insights_router = insights_router
_orig_chats_router = chats_router
_orig_upload_router = upload_router

search_router = APIRouter(prefix="/api")
search_router.include_router(_orig_search_router)

insights_router = APIRouter(prefix="/api")
insights_router.include_router(_orig_insights_router)

chats_router = APIRouter(prefix="/api")
chats_router.include_router(_orig_chats_router)

upload_router = APIRouter(prefix="/api")
upload_router.include_router(_orig_upload_router)
app.include_router(search_router)
app.include_router(insights_router)
app.include_router(chats_router)
app.include_router(upload_router)

@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}
