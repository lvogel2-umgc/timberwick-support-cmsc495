"""
Authors: Jacob Wills-Brennan, Luke Vogel

Creates the FastAPI application and connects every module: settings, database, error
handling, authentication, the AI orchestrator, chat, and agent tickets.

Run locally with:  uvicorn app.main:create_app --factory --reload
"""

import logging
from contextlib import asynccontextmanager
from dataclasses import replace

from fastapi import FastAPI

from app import auth, conversations, tickets
from app.config import Settings, load_settings
from app.database import init_db, make_engine, make_session_factory
from app.errors import register_error_handling, remove_unused_validation_docs
from app.orchestrator import AIOrchestrator
from app.retriever import KnowledgeRetriever

logging.basicConfig(level=logging.INFO)


def create_app(settings: Settings | None = None, database_url: str | None = None) -> FastAPI:
    settings = settings or load_settings()
    if database_url is not None:
        settings = replace(settings, database_url=database_url)

    engine = make_engine(settings.database_url)
    init_db(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        # Close pooled database connections when the app shuts down.
        engine.dispose()

    app = FastAPI(
        title="Timberwick Outfitters Support API",
        version="0.1.0-alpha",
        description="AI customer service platform. Alpha release.",
        lifespan=lifespan,
    )

    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)

    retriever = KnowledgeRetriever.from_json(settings.knowledge_base_path)
    app.state.orchestrator = AIOrchestrator(retriever, settings.confidence_threshold)

    register_error_handling(app)
    remove_unused_validation_docs(app)
    app.include_router(auth.router)
    app.include_router(conversations.router)
    app.include_router(tickets.router)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
