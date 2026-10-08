"""
FastAPI application entry point.

Start with:
    uvicorn backend.main:app --reload          # development
    docker-compose up                          # full stack
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router as collection_router
from backend.api.processing_routes import router as processing_router
from backend.config.settings import get_settings

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Review Data Pipeline — Phase 1 + 2",
    description=(
        "Domain-agnostic review collection and NLP processing pipeline.\n\n"
        "**Phase 1**: data collection (Reddit, YouTube, Demo).\n"
        "**Phase 2**: language detection, cleaning, quality filtering, "
        "deduplication, entity extraction, aspect extraction, sentiment analysis."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Phase 1 routes (collection) ───────────────────────────────────────────────
app.include_router(collection_router, prefix="/api")

# ── Phase 2 routes (processing + analytics) ──────────────────────────────────
app.include_router(processing_router, prefix="/api")


@app.on_event("startup")
async def _startup() -> None:
    logger.info("Review pipeline API starting (env=%s, version=2.0.0)", settings.app_env)


@app.on_event("shutdown")
async def _shutdown() -> None:
    logger.info("Review pipeline API shutting down")
