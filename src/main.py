"""FastAPI app entry point.

uvicorn src.main:app --host 0.0.0.0 --port 8000
"""

import os

from fastapi import Depends, FastAPI
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
    routes_users,
)
from src.core.deps import lifespan
from src.core.security import verificar_admin


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

    # CORS — restringido por ALLOWED_ORIGINS (coma-separado). En dev local
    # (sin la variable) se permite todo para no romper el flujo de desarrollo.
    origins_env = os.environ.get("ALLOWED_ORIGINS", "").strip()
    if origins_env:
        allow_origins = [o.strip() for o in origins_env.split(",") if o.strip()]
        allow_credentials = True
    else:
        allow_origins = ["*"]
        allow_credentials = False  # "*" + credentials es inválido según spec
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes públicas (rate-limited donde corresponde)
    app.include_router(routes_health.router)
    app.include_router(routes_query.router)
    app.include_router(routes_graph.router)
    app.include_router(routes_users.router)

    # Routes de administración — requieren header X-Admin-Key
    admin_dep = [Depends(verificar_admin)]
    app.include_router(routes_ingest.router, dependencies=admin_dep)
    app.include_router(routes_ingest_scan.router, dependencies=admin_dep)
    app.include_router(routes_background.router, dependencies=admin_dep)
    app.include_router(routes_analytics.router, dependencies=admin_dep)

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
