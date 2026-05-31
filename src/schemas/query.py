"""Schemas de /v1/query — versión Sprint 1 simplificada.

NOTA: el schema completo del documento de arquitectura (sec 4.2) incluye agentes,
filtros avanzados, graph-augmented retrieval, function calling. Aquí implementamos
la versión mínima funcional para validar el pipeline RAG end-to-end.
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class QueryFilters(BaseModel):
    """Filtros opcionales sobre metadata de documentos."""

    domain: str | None = None
    entity_type: str | None = None
    validity_status: Literal["vigente", "derogada", "modificada", "vigencia_futura"] | None = None


class QueryOptions(BaseModel):
    """Opciones del pipeline."""

    expansion_enabled: bool = False  # graph-augmented retrieval
    max_hops: int = Field(default=0, ge=0, le=2)
    rerank_enabled: bool = True       # rerank LLM post-fusión
    report_mode: bool = False         # respuesta estructurada por dimensiones
    stream: bool = False              # streaming — Sprint posterior


class ChatMessage(BaseModel):
    """Turno del historial conversacional para memoria multi-turno."""

    role: Literal["user", "assistant"]
    content: str


class QueryRequest(BaseModel):
    """POST /v1/query."""

    query: str = Field(..., min_length=3, max_length=8192)
    session_id: UUID | None = None
    filters: QueryFilters = Field(default_factory=QueryFilters)
    options: QueryOptions = Field(default_factory=QueryOptions)
    history: list[ChatMessage] = Field(
        default_factory=list,
        description="Últimos turnos (user/assistant) para memoria conversacional",
    )
    alias: str | None = Field(
        default=None,
        max_length=60,
        description="Alias del usuario para analytics y memoria persistente",
    )


class Source(BaseModel):
    """Cita de fuente en la respuesta."""

    doc_id: str
    title: str
    url: str | None = None
    page: int | None = None
    score: float
    via: Literal["vector", "graph_expansion", "both"] = "vector"
    section_path: str | None = None     # "Capítulo VII > Artículo 45" si chunker estructural
    content_snippet: str | None = None  # texto exacto del chunk citado (~500 chars)
    issuer: str | None = None           # SBS / BCRP / Congreso / MEF / SMV / INDECOPI / SUNAT


class QueryResponse(BaseModel):
    """Respuesta de /v1/query."""

    trace_id: UUID
    answer: str
    sources: list[Source]
    confidence: Literal["alta", "media", "baja"]
    cache_hit: bool = False
    tokens_used: dict[str, int] = Field(default_factory=lambda: {"input": 0, "output": 0})
    latency_ms: float
    warnings: list[str] = Field(default_factory=list)
    graph_expansion: dict | None = None
    calculations: list[dict] = Field(default_factory=list)
    query_rewrite: dict | None = None    # telemetría de reescritura por memoria


class IngestResponse(BaseModel):
    """Respuesta de /v1/ingest cuando se sube un archivo."""

    document_id: str
    title: str
    chunks_indexed: int
    content_hash: str


# ---------------------------------------------------------------------------
# Planner agent
# ---------------------------------------------------------------------------

class PlanQuestion(BaseModel):
    """Una pregunta de clarificación que el planner le hace al usuario."""

    id: str
    label: str
    type: Literal["text", "select", "multiselect"] = "text"
    options: list[str] | None = None
    rationale: str | None = None


class PlanRequest(BaseModel):
    """POST /v1/plan."""

    query: str = Field(..., min_length=3, max_length=8192)


class PlanResponse(BaseModel):
    """Decisión del agente planner."""

    action: Literal["answer_directly", "ask_clarifications"]
    reason: str | None = None
    questions: list[PlanQuestion] = Field(default_factory=list)
