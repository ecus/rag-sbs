"""FastAPI app entry point.

uvicorn src.main:app --host 0.0.0.0 --port 8000
"""

import logging
import os
import time
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from src import __version__
from src.api import (
    routes_analytics,
    routes_background,
    routes_conversations,
    routes_graph,
    routes_health,
    routes_ingest,
    routes_ingest_scan,
    routes_query,
    routes_users,
)
from src.core.deps import lifespan
from src.core.logging_setup import configurar_logging, request_id_var
from src.core.security import verificar_admin

configurar_logging()
_acceso_log = logging.getLogger("app.access")


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

    # Correlation ID + access log estructurado JSON por request (RNF-016)
    @app.middleware("http")
    async def correlation_middleware(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid4().hex[:16]
        token = request_id_var.set(rid)
        inicio = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            latencia_ms = round((time.perf_counter() - inicio) * 1000, 1)
            _acceso_log.info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status,
                    "latency_ms": latencia_ms,
                    "client_ip": (
                        request.headers.get("x-real-ip")
                        or (request.client.host if request.client else "")
                    ),
                },
            )
            request_id_var.reset(token)

    # Routes públicas (rate-limited donde corresponde)
    app.include_router(routes_health.router)
    app.include_router(routes_query.router)
    app.include_router(routes_graph.router)
    app.include_router(routes_users.router)
    app.include_router(routes_conversations.router)

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
