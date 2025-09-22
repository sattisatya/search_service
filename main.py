from fastapi import FastAPI
from search_api import router as search_router
from insights_api import router as insights_router

app = FastAPI(title="Unified Service")

app.include_router(search_router)
app.include_router(insights_router)

# Now /docs shows all endpoints