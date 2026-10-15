"""
Main FastAPI entry point for Bhaav backend.

Design decision: We assemble routes modularly and mount static frontend assets
last so API routes take strict precedence.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings, logger

app = FastAPI(
    title="Bhaav API",
    description="Backend for Bhaav: AI-powered negotiation agent for repair shops.",
    version="1.0.0",
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


# Mount frontend dist if it exists (mounted last so it doesn't intercept API routes)
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
if os.path.isdir(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
    logger.info("Mounted frontend distribution from %s", frontend_dist)
