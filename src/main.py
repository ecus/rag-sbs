"""FastAPI app entry point.

uvicorn src.main:app --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src import __version__
from src.api import (
    routes_analytics,
    routes_background,
    routes_graph,
    routes_health,
    routes_ingest,
    routes_ingest_scan,
    routes_query,
)
from src.core.deps import lifespan


def create_app() -> FastAPI:
    """Application factory — facilita testing."""
    app = FastAPI(
        title="RAG SBS Multiagente",
        description=(
            "Mesa experta regulatoria sobre el corpus público SBS Perú. "
            "RAG agéntico + function calling + ingesta automática + cerebro digital."
        ),
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS — para Streamlit UI en otro puerto. Endurecer en cloud.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Sprint 2: restringir según APP_ENV
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes
    app.include_router(routes_health.router)
    app.include_router(routes_query.router)
    app.include_router(routes_ingest.router)
    app.include_router(routes_ingest_scan.router)
    app.include_router(routes_graph.router)
    app.include_router(routes_background.router)
    app.include_router(routes_analytics.router)

    return app


app = create_app()


@app.get("/")
async def root() -> dict:
    """Raíz: redirige al docs."""
    return {
        "service": "rag-sbs",
        "version": __version__,
        "docs": "/docs",
        "health": "/v1/health",
    }
