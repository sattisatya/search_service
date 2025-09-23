from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from search_api import router as search_router
from insights_api import router as insights_router

app = FastAPI(title="Unified Service")

# CORS: allow all origins (adjust later for security)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # or specify domains ["https://yourdomain.com"]
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search_router)
app.include_router(insights_router)

# Now /docs shows all endpoints