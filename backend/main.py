"""
Main FastAPI entry point for Bhaav backend.

Design decision: We assemble routes modularly and mount static frontend assets
last so API and WebSocket routes take strict precedence.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.bus import broadcast_all_jobs
from backend.config import logger, settings
from backend.llm import add_health_listener
from backend.speech import add_speech_health_listener
from backend.routes_http import router as http_router
from backend.routes_ws import router as ws_router
from backend import store


from fastapi.responses import FileResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    # Ensure SQLite tables exist
    store.init_db()
    # Pipe LLM provider and speech health events into the broadcast event bus
    add_health_listener(broadcast_all_jobs)
    add_speech_health_listener(broadcast_all_jobs)
    
    # Startup: log key names only (never print secret values)
    configured_keys = []
    if settings.groq_api_key:
        configured_keys.append("GROQ_API_KEY")
    if settings.nvidia_api_key:
        configured_keys.append("NVIDIA_API_KEY")
    if settings.sarvam_api_key:
        configured_keys.append("SARVAM_API_KEY")
    logger.info("Configured API keys present: %s", ", ".join(configured_keys) if configured_keys else "None")
    logger.info("Bhaav backend initialized successfully")
    yield


app = FastAPI(
    title="Bhaav API",
    description="Backend for Bhaav: AI-powered negotiation agent for repair shops.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS setup configured from environment
origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint required by deployment runners and contract."""
    return {"ok": True}


# Register HTTP and WebSocket API routers
app.include_router(http_router)
app.include_router(ws_router)

# Mount frontend dist if it exists (mounted last so it doesn't intercept API routes)
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
if os.path.isdir(frontend_dist):
    index_file = os.path.join(frontend_dist, "index.html")

    @app.get("/dashboard")
    @app.get("/shop/{shop_id}")
    @app.get("/report/{job_id}")
    @app.get("/check")
    async def serve_spa_page(shop_id: str = "", job_id: str = ""):
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"ok": True}

    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
    logger.info("Mounted frontend distribution from %s", frontend_dist)
