"""Tests básicos del app — sin stack arriba (mocks vendrán en Sprint 2)."""

from src.main import create_app


def test_app_factory_creates_app():
    app = create_app()
    assert app.title == "RAG SBS Multiagente"


def test_openapi_includes_endpoints():
    app = create_app()
    schema = app.openapi()
    paths = schema["paths"]
    assert "/v1/health" in paths
    assert "/v1/query" in paths
    assert "/v1/ingest" in paths
