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

    def set_admin_key(self, key: str | None) -> None:
        """Activa/desactiva el header X-Admin-Key para endpoints de admin."""
        if key:
            self._client.headers["X-Admin-Key"] = key
        else:
            self._client.headers.pop("X-Admin-Key", None)

    def verificar_admin_key(self, key: str) -> bool:
        """Prueba la clave contra un endpoint admin liviano."""
        try:
            r = self._client.get(
                f"{self.base_url}/v1/analytics/users?limit=1",
                headers={"X-Admin-Key": key},
                timeout=5,
            )
            return r.status_code == 200
        except Exception:  # noqa: BLE001
            return False

    # ------ Analytics ---------------------------------------------------------

    def analytics_users(self, limit: int = 50) -> list[dict]:
        r = self._client.get(f"{self.base_url}/v1/analytics/users?limit={limit}")
        r.raise_for_status()
        return r.json()

    def analytics_user_queries(self, alias: str, limit: int = 50) -> list[dict]:
        r = self._client.get(
            f"{self.base_url}/v1/analytics/user/{alias}/queries?limit={limit}"
        )
        r.raise_for_status()
        return r.json()

    # ------ Genéricos ---------------------------------------------------------

    def _get(self, path: str) -> dict:
        r = self._client.get(f"{self.base_url}{path}")
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, *, json: dict | None = None) -> dict:
        r = self._client.post(f"{self.base_url}{path}", json=json or {})
        r.raise_for_status()
        return r.json()

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
        alias: str | None = None,
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
                "alias": alias,
            },
        )
        r.raise_for_status()
        return r.json()

    def plan(self, q: str) -> dict:
        """Pide al planner que decida si responder directo o clarificar."""
        r = self._client.post(f"{self.base_url}/v1/plan", json={"query": q})
        r.raise_for_status()
        return r.json()

    # ------ Conversaciones ----------------------------------------------------

    def conv_listar(self, email: str, limit: int = 50) -> list[dict]:
        try:
            r = self._client.get(
                f"{self.base_url}/v1/conversations",
                params={"email": email, "limit": limit},
                timeout=8,
            )
            r.raise_for_status()
            return r.json()
        except Exception:  # noqa: BLE001
            return []

    def conv_crear(self, email: str, user_id: str | None = None,
                   title: str | None = None) -> dict | None:
        try:
            r = self._client.post(
                f"{self.base_url}/v1/conversations",
                json={"email": email, "user_id": user_id, "title": title},
                timeout=8,
            )
            r.raise_for_status()
            return r.json()
        except Exception:  # noqa: BLE001
            return None

    def conv_mensajes(self, conversation_id: str, limit: int = 100) -> list[dict]:
        try:
            r = self._client.get(
                f"{self.base_url}/v1/conversations/{conversation_id}/messages",
                params={"limit": limit},
                timeout=8,
            )
            r.raise_for_status()
            return r.json()
        except Exception:  # noqa: BLE001
            return []

    def conv_renombrar(self, conversation_id: str, email: str, title: str) -> bool:
        try:
            r = self._client.patch(
                f"{self.base_url}/v1/conversations/{conversation_id}",
                json={"email": email, "title": title},
                timeout=8,
            )
            return r.status_code == 200
        except Exception:  # noqa: BLE001
            return False

    def conv_borrar(self, conversation_id: str, email: str) -> bool:
        try:
            r = self._client.request(
                "DELETE",
                f"{self.base_url}/v1/conversations/{conversation_id}",
                json={"email": email},
                timeout=8,
            )
            return r.status_code == 200
        except Exception:  # noqa: BLE001
            return False

    def query_stream(
        self,
        q: str,
        *,
        expansion: bool = False,
        max_hops: int = 1,
        report_mode: bool = False,
        history: list[dict] | None = None,
        alias: str | None = None,
        conversation_id: str | None = None,
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
                "alias": alias,
                "conversation_id": conversation_id,
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

    def stats_by_issuer(self) -> dict:
        """Breakdown del corpus por institución emisora (SBS, BCRP, etc.)."""
        r = self._client.get(f"{self.base_url}/v1/stats/by-issuer", timeout=15)
        r.raise_for_status()
        return r.json()

    def graph_topics_details(
        self,
        sample_chunks_per_topic: int = 3,
        max_docs_per_topic: int = 8,
    ) -> dict:
        """Devuelve cada tópico L2 con docs principales y chunks representativos."""
        r = self._client.get(
            f"{self.base_url}/v1/graph/topics/details",
            params={
                "sample_chunks_per_topic": sample_chunks_per_topic,
                "max_docs_per_topic": max_docs_per_topic,
            },
            timeout=30,
        )
        r.raise_for_status()
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

    def get_run(self, run_id: str) -> dict:
        """Obtiene el estado actual de un run de ingesta (para polling de progreso)."""
        r = self._client.get(f"{self.base_url}/v1/ingest/runs/{run_id}", timeout=10)
        r.raise_for_status()
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

        Estrategia (en orden):
        1. Si está set ``API_URL_PUBLIC`` con esquema completo → usarla.
        2. Si no, derivar del ``request_host`` que el browser usó para llegar
           a Streamlit. Si el puerto es ``443`` o ``API_PUBLIC_SCHEME=https``,
           usar HTTPS sin puerto explícito (proxy Caddy maneja).
        3. Último recurso: ``http://localhost:8000``.

        Args:
            request_host: opcional. Host con el que el navegador llegó a la UI
                (ej. ``3.220.87.49.nip.io`` o ``192.168.0.133:8501``).
        """
        # Caso 1: explícita por env
        url_explicita = os.getenv("API_URL_PUBLIC", "").strip()
        if url_explicita and url_explicita not in ("http://_", "https://_"):
            return url_explicita.rstrip("/") + "/graph"

        # Caso 2: derivar del request del browser
        if request_host:
            host_only = request_host.split(":")[0]
            api_port = os.getenv("API_PUBLIC_PORT", "8000")
            scheme = os.getenv("API_PUBLIC_SCHEME", "")

            if not scheme:
                # Autodetectar HTTPS si puerto 443 o si no hay puerto en host
                scheme = "https" if api_port in ("443", "") else "http"

            # Si esquema https y puerto 443, omitir puerto explícito
            if scheme == "https" and api_port in ("443", ""):
                return f"https://{host_only}/graph"
            if scheme == "http" and api_port == "80":
                return f"http://{host_only}/graph"
            return f"{scheme}://{host_only}:{api_port}/graph"

        # Caso 3: fallback dev local
        return "http://localhost:8000/graph"
