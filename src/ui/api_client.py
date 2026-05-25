"""Cliente HTTP minimalista sobre la API REST del RAG SBS."""

from __future__ import annotations

import os
from typing import Any

import httpx


class APIClient:
    """Wrapper sobre los endpoints que la UI consume."""

    def __init__(self, base_url: str | None = None, timeout_sec: float = 300.0) -> None:
        self.base_url = (base_url or os.getenv("API_URL", "http://api:8000")).rstrip("/")
        self._client = httpx.Client(timeout=timeout_sec)

    # ------ Health & meta -----------------------------------------------------

    def health(self) -> dict:
        try:
            r = self._client.get(f"{self.base_url}/v1/health")
            return r.json()
        except Exception as exc:  # noqa: BLE001
            return {"status": "unreachable", "error": str(exc)}

    # ------ Query -------------------------------------------------------------

    def query(
        self,
        q: str,
        *,
        expansion: bool = False,
        max_hops: int = 1,
        report_mode: bool = False,
        history: list[dict] | None = None,
    ) -> dict:
        r = self._client.post(
            f"{self.base_url}/v1/query",
            json={
                "query": q,
                "options": {
                    "expansion_enabled": expansion,
                    "max_hops": max_hops,
                    "report_mode": report_mode,
                },
                "history": history or [],
            },
        )
        r.raise_for_status()
        return r.json()

    def plan(self, q: str) -> dict:
        """Pide al planner que decida si responder directo o clarificar."""
        r = self._client.post(f"{self.base_url}/v1/plan", json={"query": q})
        r.raise_for_status()
        return r.json()

    def query_stream(
        self,
        q: str,
        *,
        expansion: bool = False,
        max_hops: int = 1,
        report_mode: bool = False,
        history: list[dict] | None = None,
    ):
        """Generator: yields (event_type, data) parseando SSE.

        Eventos posibles: status, sources, calculations, graph, token,
        metadata, done, error.
        """
        import json as _json

        with self._client.stream(
            "POST",
            f"{self.base_url}/v1/query/stream",
            json={
                "query": q,
                "options": {
                    "expansion_enabled": expansion,
                    "max_hops": max_hops,
                    "report_mode": report_mode,
                },
                "history": history or [],
            },
        ) as resp:
            resp.raise_for_status()
            event_actual = "message"
            for linea in resp.iter_lines():
                if not linea:
                    continue
                if linea.startswith("event:"):
                    event_actual = linea[6:].strip()
                elif linea.startswith("data:"):
                    raw = linea[5:].strip()
                    try:
                        data = _json.loads(raw)
                    except _json.JSONDecodeError:
                        data = raw
                    yield event_actual, data
                    event_actual = "message"

    # ------ Graph -------------------------------------------------------------

    def graph_stats(self) -> dict:
        r = self._client.get(f"{self.base_url}/v1/graph")
        return r.json()

    def graph_topics(self, limit: int = 20) -> list[dict]:
        r = self._client.get(f"{self.base_url}/v1/graph/topics", params={"limit": limit})
        return r.json()

    # ------ Ingest ------------------------------------------------------------

    def list_sources(self) -> list[dict]:
        r = self._client.get(f"{self.base_url}/v1/ingest/sources")
        return r.json()

    def list_runs(self, limit: int = 10) -> list[dict]:
        r = self._client.get(f"{self.base_url}/v1/ingest/runs", params={"limit": limit})
        return r.json()

    def trigger_scan(self, *, force: bool = False, dry_run: bool = False) -> dict:
        r = self._client.post(
            f"{self.base_url}/v1/ingest/scan",
            json={"force": force, "dry_run": dry_run},
        )
        return r.json()

    def list_events(self, limit: int = 50) -> list[dict]:
        r = self._client.get(f"{self.base_url}/v1/ingest/events", params={"limit": limit})
        return r.json()

    def get_catalog(self) -> dict:
        """Catálogo curado de fuentes regulatorias (no requiere DB)."""
        r = self._client.get(f"{self.base_url}/v1/ingest/catalog")
        r.raise_for_status()
        return r.json()

    def seed_catalog(self, only_issuer: str | None = None) -> dict:
        """Pobla doc_sources con el catálogo curado.

        Args:
            only_issuer: opcional, filtra por institución (SBS, BCRP, etc.).
        """
        params = {"only_issuer": only_issuer} if only_issuer else {}
        r = self._client.post(
            f"{self.base_url}/v1/ingest/seed",
            params=params,
            timeout=60,
        )
        r.raise_for_status()
        return r.json()

    def graph_url(self, request_host: str | None = None) -> str:
        """URL pública del grafo (vista desde el navegador del usuario).

        Args:
            request_host: opcional. Host que el navegador usó para llegar a Streamlit
                (p. ej. ``192.168.0.133:8501``). Si se provee, se reusa ese hostname
                con el puerto de la API — así la UI funciona desde cualquier máquina
                en la LAN sin hardcodear IPs. Si no se provee, cae al env
                ``API_URL_PUBLIC`` o, en último caso, ``localhost:8000``.
        """
        if request_host:
            # Quitar puerto si viene incluido y usar el de la API
            host_only = request_host.split(":")[0]
            api_port = os.getenv("API_PUBLIC_PORT", "8000")
            return f"http://{host_only}:{api_port}/graph"
        return os.getenv("API_URL_PUBLIC", "http://localhost:8000") + "/graph"
