"""Endpoints del Knowledge Graph (L1).

  GET    /v1/graph                          — estadísticas + nodos top
  GET    /v1/graph/data                     — JSON de nodes/edges (para vis-network)
  GET    /graph                             — UI HTML interactiva estilo Obsidian
  GET    /v1/graph/document/{document_id}/related  — docs relacionados
  GET    /v1/graph/topics                   — top labels más citados (proxy de tópicos en L1)
  POST   /v1/graph/rebuild                  — reconstruye desde chunks
  POST   /v1/export/obsidian                — genera vault
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from psycopg_pool import AsyncConnectionPool

from src.core.deps import get_llm, get_pool
from src.graph.builder import construir_para_documento, reconstruir_completo
from src.graph.classifier import reclasificar_aristas_cites
from src.graph.exporter import exportar_a_vault
from src.graph.repository import GraphRepository
from src.graph.topics import descubrir_topicos
from src.llm import LLMProvider

router = APIRouter(tags=["graph"])


# -------------------------------------------------------------------------
# Schemas
# -------------------------------------------------------------------------

class GraphStats(BaseModel):
    nodos_total: int
    aristas_total: int
    nodos_por_tipo: dict[str, int] | None = None
    aristas_por_tipo: dict[str, int] | None = None


class RelatedDocument(BaseModel):
    document_id: UUID
    label: str
    document_title: str | None
    source_url: str | None
    citas_compartidas: int


class TopicEntry(BaseModel):
    """En L1 'topic' = etiqueta más citada (resolución, ley, circular)."""
    kind: str
    label: str
    citaciones: int


class RebuildResult(BaseModel):
    documentos_procesados: int
    operaciones_nodo: int
    operaciones_arista: int
    estado_final: dict[str, Any]


class ExportResult(BaseModel):
    ruta_vault: str
    documentos_exportados: int
    notas_referencia_creadas: int


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------

@router.get("/v1/graph", response_model=GraphStats)
async def get_graph_stats(
    pool: AsyncConnectionPool = Depends(get_pool),
) -> GraphStats:
    """Estadísticas globales del grafo.

    El conteo de ``document`` se sobreescribe con la tabla ``documents``
    para mostrar valor LIVE (sin esperar al rebuild horario del grafo).
    """
    async with pool.connection() as conn:
        repo = GraphRepository(conn)
        stats = await repo.estadisticas()
        # Override live: contar documentos reales en BD
        async with conn.cursor() as cur:
            await cur.execute("SELECT COUNT(*) FROM documents")
            row = await cur.fetchone()
            if row and stats.get("nodos_por_tipo") is not None:
                stats["nodos_por_tipo"]["document"] = int(row[0])
    return GraphStats(**stats)


@router.get(
    "/v1/graph/document/{document_id}/related",
    response_model=list[RelatedDocument],
)
async def get_related_documents(
    document_id: UUID,
    limit: int = 10,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> list[RelatedDocument]:
    """Documentos que comparten citas con el documento dado."""
    async with pool.connection() as conn:
        repo = GraphRepository(conn)
        filas = await repo.documentos_relacionados(document_id, limit=limit)
    return [
        RelatedDocument(
            document_id=f["document_id"],
            label=f["label"],
            document_title=f.get("document_title"),
            source_url=f.get("source_url"),
            citas_compartidas=f["citas_compartidas"],
        )
        for f in filas
    ]


@router.get("/v1/graph/topics", response_model=list[TopicEntry])
async def get_topics(
    limit: int = 20,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> list[TopicEntry]:
    """En L1, los 'tópicos' son las entidades más citadas (resoluciones, leyes, circulares)."""
    async with pool.connection() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                """
                SELECT n.kind, n.label, COUNT(e.id) AS citaciones
                FROM graph_nodes n
                LEFT JOIN graph_edges e ON e.dst_node = n.id
                WHERE n.kind IN ('resolution', 'ley', 'circular')
                GROUP BY n.kind, n.label
                HAVING COUNT(e.id) > 0
                ORDER BY citaciones DESC
                LIMIT %s
                """,
                (limit,),
            )
            filas = await cursor.fetchall()
    return [TopicEntry(kind=k, label=l, citaciones=c) for k, l, c in filas]


@router.post("/v1/graph/rebuild", response_model=RebuildResult, status_code=202)
async def post_rebuild_graph(
    background: BackgroundTasks,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> RebuildResult:
    """Reconstruye el grafo completo desde los chunks indexados.

    Síncrono (rápido para volúmenes MVP). Sprint 3: pasarlo a background con
    estado consultable. Por ahora ejecuta y retorna el resumen final.
    """
    resultado = await reconstruir_completo(pool)
    return RebuildResult(**resultado)


class IncrementalRequest(BaseModel):
    document_id: UUID


@router.post("/v1/graph/incremental", status_code=202)
async def post_incremental(
    payload: IncrementalRequest,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> dict:
    """Construye el subgrafo de UN documento (uso post-ingesta puntual)."""
    return await construir_para_documento(pool, document_id=payload.document_id)


@router.post("/v1/export/obsidian", response_model=ExportResult)
async def post_export_obsidian(
    output_dir: str = "vault",
    pool: AsyncConnectionPool = Depends(get_pool),
) -> ExportResult:
    """Genera vault Obsidian desde el grafo + documentos."""
    resultado = await exportar_a_vault(pool, output_dir=output_dir)
    return ExportResult(**resultado)


# ---------------------------------------------------------------------------
# L2 — Topic Modeling
# ---------------------------------------------------------------------------

@router.post("/v1/graph/topics/build")
async def post_construir_topicos(
    n_topicos: int = 8,
    pool: AsyncConnectionPool = Depends(get_pool),
    llm: LLMProvider = Depends(get_llm),
) -> dict:
    """K-means sobre embeddings + LLM nombra cada cluster.

    Produce nodos `kind='topic'` y aristas `relation='same_topic'` documento↔tópico.
    """
    return await descubrir_topicos(pool, llm, n_topicos=n_topicos)


@router.get("/v1/stats/by-issuer")
async def get_stats_by_issuer(
    pool: AsyncConnectionPool = Depends(get_pool),
) -> dict:
    """Breakdown del corpus por institución emisora (SBS, BCRP, Congreso, etc.).

    Retorna por cada issuer: docs, chunks, top documentos por chunks.
    """
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                  COALESCE(metadata->>'issuer', '(s/d)') AS issuer,
                  COUNT(*) AS docs,
                  SUM((SELECT COUNT(*) FROM chunks WHERE document_id=d.id))::int AS chunks
                FROM documents d
                GROUP BY 1
                ORDER BY docs DESC
                """
            )
            por_issuer = []
            for issuer, docs_count, chunks_count in await cur.fetchall():
                # Top 3 docs por chunks de este issuer
                await cur.execute(
                    """
                    SELECT d.title,
                           (SELECT COUNT(*) FROM chunks WHERE document_id=d.id)::int AS ch
                    FROM documents d
                    WHERE COALESCE(d.metadata->>'issuer', '(s/d)') = %s
                    ORDER BY ch DESC
                    LIMIT 3
                    """,
                    (issuer,),
                )
                top_docs = [
                    {"title": (t or "")[:80], "chunks": ch}
                    for t, ch in await cur.fetchall()
                ]
                por_issuer.append({
                    "issuer": issuer,
                    "docs": int(docs_count or 0),
                    "chunks": int(chunks_count or 0),
                    "top_docs": top_docs,
                })

    return {"por_issuer": por_issuer, "total_issuers": len(por_issuer)}


@router.get("/v1/graph/topics/details")
async def get_topics_details(
    sample_chunks_per_topic: int = 2,
    max_docs_per_topic: int = 6,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> dict:
    """Devuelve cada tópico L2 con sus docs principales y chunks representativos.

    Usa la estructura del grafo: nodos ``kind='topic'`` con aristas
    ``relation='same_topic'`` apuntando a documentos. El metadata.indice
    del nodo topic da el índice del cluster; el peso de la arista es el
    número de chunks del documento que cayeron en ese tópico.

    Args:
        sample_chunks_per_topic: cuántos chunks ejemplo devolver por tópico
        max_docs_per_topic: máximo de docs en el top
    """
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            # 1. Listar tópicos (nodos kind='topic') con su metadata
            await cur.execute(
                """
                SELECT id, label, metadata
                FROM graph_nodes
                WHERE kind = 'topic'
                ORDER BY (metadata->>'indice')::int NULLS LAST
                """
            )
            topicos_raw = await cur.fetchall()

            if not topicos_raw:
                return {
                    "topicos": [],
                    "warning": (
                        "No hay topicos construidos. POST "
                        "/v1/graph/topics/build primero."
                    ),
                }

            topicos = []
            for topic_node_id, topic_label, topic_metadata in topicos_raw:
                meta = topic_metadata or {}
                indice = meta.get("indice")
                snippets_repr = meta.get("snippets", []) or []
                tamano = meta.get("tamano", 0) or 0

                # 2. Top docs del tópico via aristas same_topic
                # Columnas reales en graph_edges: src_node, dst_node, weight
                # Las aristas same_topic van DOCUMENT → TOPIC
                # No tenemos columna weight — usamos COUNT de aristas como proxy
                await cur.execute(
                    """
                    SELECT
                        d.id, d.title,
                        COALESCE((ge.metadata->>'peso')::int, 1) AS chunks_del_topico,
                        (SELECT COUNT(*) FROM chunks WHERE document_id = d.id)
                            AS chunks_totales
                    FROM graph_edges ge
                    JOIN graph_nodes gd ON gd.id = ge.src_node AND gd.kind = 'document'
                    JOIN documents d ON d.id = gd.document_id
                    WHERE ge.dst_node = %s
                      AND ge.relation = 'same_topic'
                    ORDER BY chunks_del_topico DESC NULLS LAST
                    LIMIT %s
                    """,
                    (topic_node_id, max_docs_per_topic),
                )
                docs = []
                for did, title, ch_topico, ch_total in await cur.fetchall():
                    docs.append({
                        "id": str(did),
                        "title": (title or "")[:120],
                        "chunks_del_topico": int(ch_topico or 0),
                        "chunks_totales": int(ch_total or 0),
                    })

                # 3. Sample chunks
                samples = []
                for snippet in snippets_repr[:sample_chunks_per_topic]:
                    if not snippet:
                        continue
                    samples.append({
                        "doc_title": "Fragmento representativo",
                        "snippet": snippet[:400] + (
                            "…" if len(snippet) > 400 else ""
                        ),
                    })

                # 4. Breakdown por institución (Mejora #1)
                # Para cada tópico, cuántos documentos pertenecen a cada issuer
                await cur.execute(
                    """
                    SELECT
                      COALESCE(d.metadata->>'issuer', '(s/d)') AS issuer,
                      COUNT(DISTINCT d.id) AS docs_count
                    FROM graph_edges ge
                    JOIN graph_nodes gd ON gd.id = ge.src_node AND gd.kind = 'document'
                    JOIN documents d ON d.id = gd.document_id
                    WHERE ge.dst_node = %s
                      AND ge.relation = 'same_topic'
                    GROUP BY issuer
                    ORDER BY docs_count DESC
                    """,
                    (topic_node_id,),
                )
                por_issuer = [
                    {"issuer": iss, "docs": int(cnt or 0)}
                    for iss, cnt in await cur.fetchall()
                ]

                topicos.append({
                    "indice": indice,
                    "label": meta.get("label_llm") or topic_label or "Sin nombre",
                    "miembros": tamano,
                    "documentos_unicos": len(docs),
                    "docs_top": docs,
                    "samples": samples,
                    "por_issuer": por_issuer,
                })

    return {"topicos": topicos, "total_topicos": len(topicos)}


# ---------------------------------------------------------------------------
# Reclasificación de citas: cites → modifies / derogates
# ---------------------------------------------------------------------------

@router.post("/v1/graph/citations/classify")
async def post_clasificar_citaciones(
    pool: AsyncConnectionPool = Depends(get_pool),
) -> dict:
    """Recorre aristas `cites`, examina ventana de contexto del chunk evidencia,
    y promueve a `modifies` o `derogates` cuando regex detecta vocabulario clave.

    No usa LLM — instantáneo, determinista, basado en regex de differ.py.
    """
    return await reclasificar_aristas_cites(pool)


# ---------------------------------------------------------------------------
# Visualización web (estilo Obsidian con vis-network)
# ---------------------------------------------------------------------------

# Paleta por tipo de nodo — institucional SBS (legible sobre fondo claro)
# Documento = azul SBS profundo (autoridad central)
# Resolución = azul medio, Ley = verde institucional, etc.
COLORES_NODO = {
    "document":   "#003d7a",   # azul SBS — documento (autoridad central)
    "resolution": "#0073cf",   # azul medio — resolución SBS
    "ley":        "#059669",   # verde institucional — ley
    "circular":   "#d97706",   # ámbar oscuro — circular
    "articulo":   "#475569",   # slate-700 — artículo
    "anexo":      "#7c3aed",   # violeta — anexo
    "topic":      "#db2777",   # rosa fuerte — tópico (L2)
}

# Paleta por tipo de arista (legible sobre fondo blanco/claro)
COLORES_ARISTA = {
    "cites":          "#94a3b8",   # slate-400 — cita simple
    "self_reference": "#cbd5e1",   # slate-300 — referencia interna
    "canonical_form": "#003d7a",   # azul SBS — forma canónica
    "modifies":       "#d97706",   # ámbar — modificación
    "derogates":      "#dc0014",   # ROJO SBS/PERÚ — derogación
    "same_topic":     "#db2777",   # rosa — mismo tópico
}

ANCHOS_ARISTA = {
    "cites":          0.6,
    "self_reference": 0.4,
    "canonical_form": 0.8,
    "modifies":       1.5,
    "derogates":      2.0,
    "same_topic":     0.4,
}


@router.get("/v1/graph/data")
async def get_graph_data(
    limit_nodes: int = 500,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> dict:
    """JSON con nodos y aristas en formato vis-network.

    Usado por la UI `/graph`. También sirve para integraciones externas.
    """
    async with pool.connection() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                """
                SELECT n.id, n.kind, n.label, n.document_id,
                       d.title AS doc_title,
                       COALESCE(d.metadata->>'issuer', '(s/d)') AS issuer,
                       (SELECT COUNT(*) FROM graph_edges WHERE dst_node = n.id) AS in_deg,
                       (SELECT COUNT(*) FROM graph_edges WHERE src_node = n.id) AS out_deg
                FROM graph_nodes n
                LEFT JOIN documents d ON d.id = n.document_id
                ORDER BY (
                    (SELECT COUNT(*) FROM graph_edges WHERE dst_node = n.id) +
                    (SELECT COUNT(*) FROM graph_edges WHERE src_node = n.id)
                ) DESC
                LIMIT %s
                """,
                (limit_nodes,),
            )
            filas_nodos = await cursor.fetchall()

            ids_visibles = {f[0] for f in filas_nodos}

            await cursor.execute(
                """
                SELECT src_node, dst_node, relation, score
                FROM graph_edges
                WHERE src_node = ANY(%s) AND dst_node = ANY(%s)
                """,
                (list(ids_visibles), list(ids_visibles)),
            )
            filas_aristas = await cursor.fetchall()

    # Paleta de colores por institución emisora (Mejora #2)
    COLORES_ISSUER = {
        "SBS": "#003d7a",        # azul institucional SBS
        "BCRP": "#b91c1c",       # rojo BCRP
        "Congreso": "#7c3aed",   # morado leyes
        "MEF": "#15803d",        # verde MEF
        "SMV": "#0891b2",        # cyan
        "INDECOPI": "#ca8a04",   # ámbar
        "SUNAT": "#be185d",      # rosa
        "(s/d)": "#94a3b8",      # gris cuando falta
    }

    # Map de nid → grado (para luego calcular longitudes de aristas)
    grados: dict[str, int] = {}
    nodos = []
    for nid, kind, label, doc_id, doc_title, issuer, in_deg, out_deg in filas_nodos:
        grado = (in_deg or 0) + (out_deg or 0)
        grados[str(nid)] = grado
        # tamaño según grado (escala log para que no domine el más conectado)
        tamano = 10 + min(grado * 1.5, 40)

        # Masa: hubs son más pesados → actúan como anclas; las hojas orbitan
        masa = 1.0 + min(grado / 8.0, 3.0)

        # Label visible: para documentos usamos el título (acortado)
        if kind == "document" and doc_title:
            etiqueta_visible = doc_title if len(doc_title) <= 50 else doc_title[:47] + "…"
        else:
            etiqueta_visible = label

        # Tooltip incluye issuer
        partes_tooltip = [
            etiqueta_visible,
            f"tipo: {kind}",
            f"institución: {issuer or '?'}",
            f"conexiones: in={in_deg or 0}  out={out_deg or 0}",
        ]
        if doc_title and kind != "document":
            partes_tooltip.append(f"doc: {doc_title}")
        tooltip = "\n".join(partes_tooltip)

        # Color: para documentos usar institución; para otros tipos el color por tipo
        if kind == "document":
            color = COLORES_ISSUER.get(issuer or "(s/d)", "#94a3b8")
        else:
            color = COLORES_NODO.get(kind, "#cbd5e1")

        nodos.append({
            "id": str(nid),
            "label": etiqueta_visible,
            "title": tooltip,
            "color": color,
            "shape": "dot" if kind != "document" else "diamond",
            "size": tamano,
            "mass": round(masa, 2),
            "kind": kind,
            "issuer": issuer or "(s/d)",
            "grado": grado,
            "doc_title": doc_title or label,
            "doc_id": str(doc_id) if doc_id else None,
        })

    aristas = []
    for src, dst, relation, score in filas_aristas:
        sid, did = str(src), str(dst)
        # peso 0..1 según grado combinado de los dos extremos
        grado_max = max(grados.get(sid, 0), grados.get(did, 0))
        peso = min(grado_max / 60.0, 1.0)
        color_base = COLORES_ARISTA.get(relation, "#cbd5e1")
        ancho = ANCHOS_ARISTA.get(relation, 0.6)
        aristas.append({
            "from": sid,
            "to": did,
            "title": f"{relation}  (score={score:.2f})",
            "label": "",
            "relation": relation,
            "peso_hub": round(peso, 3),
            "arrows": "to",
            "width": ancho,
            "color": {
                "color": color_base,
                "highlight": "#0ea5e9",
                "hover": "#0ea5e9",
            },
            "smooth": {"type": "continuous"},
        })

    return {
        "nodes": nodos,
        "edges": aristas,
        "stats": {
            "nodes_returned": len(nodos),
            "edges_returned": len(aristas),
        },
    }


PAGINA_GRAFO_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <title>RAG SBS · Cerebro Regulatorio</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
  <style>
    :root {
      /* Paleta institucional SBS Perú — azul + rojo + blanco */
      --bg: #f5f7fa;             /* fondo claro casi blanco */
      --bg-elev: #ffffff;        /* superficies elevadas */
      --bg-panel: #ffffff;       /* panel lateral */
      --bg-hover: #eef2f8;       /* hover suave */
      --bg-graph: #fafbfd;       /* canvas del grafo */
      --border: #d8dee8;         /* borde estándar */
      --border-strong: #b8c2d1;  /* borde énfasis */
      --fg: #0d1b2a;             /* texto principal */
      --fg-muted: #4a5568;       /* texto secundario */
      --fg-dim: #8a96a8;         /* texto terciario */
      --accent: #003d7a;         /* azul institucional SBS */
      --accent-hover: #00529b;   /* azul claro */
      --accent-soft: rgba(0, 61, 122, 0.08);
      --accent-bg: #003d7a;      /* fondo del header */
      --info: #00629b;
      --success: #059669;
      --warn: #d97706;
      --danger: #dc0014;         /* rojo SBS / Perú */
      --shadow-sm: 0 1px 2px rgba(13, 27, 42, 0.04);
      --shadow-md: 0 4px 12px rgba(13, 27, 42, 0.08);
      --shadow-lg: 0 8px 24px rgba(13, 27, 42, 0.12);
    }
    * { box-sizing: border-box; }
    html, body { margin: 0; padding: 0; height: 100%; overflow: hidden; }
    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg); color: var(--fg);
      -webkit-font-smoothing: antialiased;
      font-feature-settings: "cv02", "cv03", "cv04", "cv11";
    }
    code, .mono { font-family: 'JetBrains Mono', 'SF Mono', Menlo, monospace; }

    /* ── Header — barra azul institucional SBS ─── */
    header {
      padding: 14px 24px;
      background: linear-gradient(180deg, #003d7a 0%, #002d5a 100%);
      border-bottom: 3px solid var(--danger);   /* línea roja SBS/Perú */
      display: flex; gap: 20px; align-items: center; flex-wrap: wrap;
      position: relative; z-index: 50;
      box-shadow: var(--shadow-md);
    }
    .brand { display: flex; align-items: center; gap: 14px; }
    .brand .logo {
      width: 38px; height: 38px; border-radius: 4px;
      background: #ffffff;
      display: flex; align-items: center; justify-content: center;
      color: #003d7a; font-weight: 700; font-size: 13px;
      letter-spacing: 0.02em;
      box-shadow: 0 1px 3px rgba(0,0,0,0.2);
    }
    .brand .titulo { display: flex; flex-direction: column; line-height: 1.15; color: #fff; }
    .brand .titulo h1 {
      margin: 0; font-size: 14px; font-weight: 600;
      letter-spacing: -0.005em; color: #ffffff;
    }
    .brand .titulo .subtitulo {
      font-size: 10.5px; color: rgba(255, 255, 255, 0.7);
      text-transform: uppercase; letter-spacing: 0.1em;
      font-weight: 500; margin-top: 2px;
    }
    .stats-pill {
      padding: 6px 14px; background: rgba(255, 255, 255, 0.12);
      border: 1px solid rgba(255, 255, 255, 0.2);
      border-radius: 999px; font-size: 11px; font-weight: 500;
      color: rgba(255, 255, 255, 0.85); white-space: nowrap;
    }
    .stats-pill .num {
      color: #ffffff; font-weight: 700;
      font-family: 'JetBrains Mono', monospace;
    }

    .controls { display: flex; gap: 10px; flex-wrap: wrap; align-items: center;
                margin-left: auto; }
    .controls input[type="search"] {
      background: rgba(255, 255, 255, 0.95); color: var(--fg);
      border: 1px solid rgba(255, 255, 255, 0.3);
      border-radius: 6px;
      padding: 7px 10px 7px 32px; width: 240px; font-size: 12px;
      font-family: inherit;
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='%23003d7a' stroke-width='2'%3E%3Ccircle cx='11' cy='11' r='8'/%3E%3Cpath d='m21 21-4.3-4.3'/%3E%3C/svg%3E");
      background-repeat: no-repeat;
      background-position: 10px center;
      transition: all 0.15s;
    }
    .controls input[type="search"]:focus {
      outline: none; border-color: #ffffff;
      background-color: #ffffff;
      box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.15);
    }
    .filtros { display: flex; gap: 4px; flex-wrap: wrap; align-items: center; }
    .filtros label {
      font-size: 11px; padding: 5px 10px;
      border-radius: 6px;
      border: 1px solid rgba(255, 255, 255, 0.18);
      background: rgba(255, 255, 255, 0.08);
      color: rgba(255, 255, 255, 0.78);
      cursor: pointer; user-select: none;
      display: inline-flex; align-items: center; gap: 5px;
      transition: all 0.15s;
    }
    .filtros label:hover {
      background: rgba(255, 255, 255, 0.15);
      border-color: rgba(255, 255, 255, 0.3);
    }
    .filtros label:has(input:checked) {
      background: #ffffff;
      border-color: #ffffff;
      color: var(--accent);
      font-weight: 600;
    }
    .filtros input[type="checkbox"] { display: none; }
    .filtros .marca {
      width: 8px; height: 8px; border-radius: 50%;
      background: rgba(255, 255, 255, 0.4);
      transition: background 0.15s;
    }
    .filtros label:has(input:checked) .marca { background: var(--accent); }

    .btn {
      background: rgba(255, 255, 255, 0.1);
      color: #ffffff;
      border: 1px solid rgba(255, 255, 255, 0.25);
      border-radius: 6px;
      padding: 7px 14px; cursor: pointer; font-size: 12px;
      font-family: inherit; font-weight: 500;
      transition: all 0.15s;
      display: inline-flex; align-items: center; gap: 6px;
    }
    .btn:hover {
      background: rgba(255, 255, 255, 0.18);
      border-color: rgba(255, 255, 255, 0.4);
    }
    .btn-primary {
      background: #ffffff; border-color: #ffffff;
      color: var(--accent); font-weight: 600;
    }
    .btn-primary:hover {
      background: #f0f5ff; border-color: #ffffff;
      color: var(--accent-hover);
    }

    /* ── Main + grafo ─────────────────────────── */
    main { display: flex; height: calc(100vh - 68px); }
    #grafo {
      flex: 1; background: var(--bg-graph);
      background-image:
        radial-gradient(circle at 20% 30%, rgba(0, 61, 122, 0.04) 0%, transparent 50%),
        radial-gradient(circle at 80% 70%, rgba(220, 0, 20, 0.03) 0%, transparent 50%);
    }

    /* ── Panel lateral ────────────────────────── */
    aside {
      width: 340px; background: var(--bg-panel);
      border-left: 1px solid var(--border);
      padding: 24px; overflow-y: auto; font-size: 13px;
      box-shadow: var(--shadow-md);
    }
    aside h2 {
      margin: 0 0 12px; font-size: 10.5px; font-weight: 600;
      color: var(--accent); text-transform: uppercase;
      letter-spacing: 0.1em;
      padding-bottom: 8px; border-bottom: 1px solid var(--border);
    }
    aside h2:not(:first-child) { margin-top: 24px; }
    aside p { color: var(--fg-muted); line-height: 1.55; margin: 0 0 12px; }
    aside .kv {
      display: grid; grid-template-columns: max-content 1fr;
      gap: 8px 14px; font-size: 12px;
    }
    aside .kv dt {
      font-weight: 500; color: var(--fg-dim);
      text-transform: uppercase; font-size: 10.5px;
      letter-spacing: 0.04em;
    }
    aside .kv dd { margin: 0; word-break: break-word; color: var(--fg); }
    aside .kv code {
      background: var(--bg-hover); padding: 2px 6px;
      border-radius: 3px; font-size: 11px; color: var(--accent);
    }
    aside ul { padding: 0; margin: 6px 0 0; list-style: none; }
    aside li {
      padding: 8px 10px; margin-bottom: 2px;
      border-radius: 4px; cursor: pointer; font-size: 12px;
      transition: all 0.12s;
      border-left: 2px solid transparent;
      color: var(--fg);
    }
    aside li:hover {
      background: var(--bg-hover); border-left-color: var(--accent);
      color: var(--accent); padding-left: 12px;
    }
    aside li small { color: var(--fg-dim); margin-left: 4px; font-weight: 400; }

    /* ── Leyenda ──────────────────────────────── */
    .leyenda { display: flex; flex-wrap: wrap; gap: 10px; }
    .leyenda span {
      display: inline-flex; align-items: center; gap: 6px;
      font-size: 11px; color: var(--fg-muted);
    }
    .leyenda .dot {
      width: 9px; height: 9px; border-radius: 50%;
      display: inline-block;
    }

    /* ── Loader ───────────────────────────────── */
    #loader {
      position: absolute; top: 50%; left: 50%;
      transform: translate(-50%, -50%);
      display: flex; flex-direction: column; align-items: center; gap: 18px;
    }
    #loader .spinner {
      width: 36px; height: 36px;
      border: 2.5px solid var(--border);
      border-top-color: var(--accent);
      border-radius: 50%;
      animation: spin 0.7s linear infinite;
    }
    #loader .texto {
      color: var(--fg-muted); font-size: 11px;
      text-transform: uppercase; letter-spacing: 0.12em; font-weight: 500;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* ── Panel config (overlay) ───────────────── */
    #panel-config {
      position: absolute; top: 80px; right: 360px; z-index: 100;
      background: #ffffff; border: 1px solid var(--border);
      border-radius: 10px; padding: 20px; min-width: 280px;
      box-shadow: var(--shadow-lg);
      display: none;
    }
    #panel-config.visible { display: block; }
    #panel-config h3 {
      margin: 0 0 16px; font-size: 10.5px; font-weight: 600;
      color: var(--accent); text-transform: uppercase;
      letter-spacing: 0.1em;
      padding-bottom: 10px; border-bottom: 1px solid var(--border);
    }
    #panel-config .grupo { margin-bottom: 16px; }
    #panel-config label {
      display: block; font-size: 12px; margin-bottom: 6px;
      color: var(--fg); font-weight: 500;
    }
    #panel-config .valor {
      float: right; color: var(--accent);
      font-family: 'JetBrains Mono', monospace; font-size: 11px;
      font-weight: 600;
    }
    /* Slider custom — azul SBS */
    #panel-config input[type=range] {
      -webkit-appearance: none; appearance: none;
      width: 100%; height: 4px; background: var(--bg-hover);
      border-radius: 2px; outline: none; cursor: pointer;
    }
    #panel-config input[type=range]::-webkit-slider-thumb {
      -webkit-appearance: none; appearance: none;
      width: 16px; height: 16px; border-radius: 50%;
      background: var(--accent); cursor: pointer; border: 2px solid #fff;
      box-shadow: 0 1px 4px rgba(0, 61, 122, 0.4);
      transition: transform 0.1s;
    }
    #panel-config input[type=range]::-webkit-slider-thumb:hover { transform: scale(1.15); }
    #panel-config input[type=range]::-moz-range-thumb {
      width: 14px; height: 14px; border-radius: 50%;
      background: var(--accent); cursor: pointer; border: 2px solid #fff;
    }
    #panel-config .botones { display: flex; gap: 8px; margin-top: 18px; }
    /* Botones DENTRO del panel: usan estilo sólido (no ghost del header) */
    #panel-config .btn {
      background: var(--bg-hover); color: var(--fg);
      border-color: var(--border);
      flex: 1; justify-content: center;
    }
    #panel-config .btn:hover {
      background: var(--accent-soft); border-color: var(--accent);
      color: var(--accent);
    }
    #panel-config .btn-primary {
      background: var(--accent); color: #ffffff; border-color: var(--accent);
    }
    #panel-config .btn-primary:hover {
      background: var(--accent-hover); color: #ffffff;
      border-color: var(--accent-hover);
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="logo">SBS</div>
      <div class="titulo">
        <h1>Cerebro Regulatorio</h1>
        <span class="subtitulo">Mesa Experta · Sistema Financiero</span>
      </div>
    </div>
    <div class="stats-pill" id="stats">Cargando…</div>

    <div class="controls">
      <input type="search" id="busqueda" placeholder="Buscar (ej. 11356, ciberseguridad)" />
      <div class="filtros">
        <label><input type="checkbox" data-kind="document" checked /><span class="marca"></span>Documentos</label>
        <label><input type="checkbox" data-kind="resolution" checked /><span class="marca"></span>Resoluciones</label>
        <label><input type="checkbox" data-kind="ley" checked /><span class="marca"></span>Leyes</label>
        <label><input type="checkbox" data-kind="circular" checked /><span class="marca"></span>Circulares</label>
        <label><input type="checkbox" data-kind="articulo" checked /><span class="marca"></span>Artículos</label>
        <label><input type="checkbox" data-kind="anexo" checked /><span class="marca"></span>Anexos</label>
        <label><input type="checkbox" data-kind="topic" checked /><span class="marca"></span>Tópicos</label>
      </div>
      <button class="btn" onclick="ajustarVista()">Centrar</button>
      <button class="btn btn-primary" onclick="togglePanel()">Config</button>
    </div>
  </header>

  <div id="panel-config">
    <h3>Configuración del grafo</h3>

    <div class="grupo">
      <label>Duración entrada<span class="valor" id="v-duracion">1200 ms</span></label>
      <input type="range" id="s-duracion" min="0" max="4000" step="100" value="1200" />
    </div>

    <div class="grupo">
      <label>Intensidad (vueltas)<span class="valor" id="v-intensidad">2</span></label>
      <input type="range" id="s-intensidad" min="1" max="5" step="1" value="2" />
    </div>

    <div class="grupo">
      <label>Espaciado entre nodos<span class="valor" id="v-espaciado">250</span></label>
      <input type="range" id="s-espaciado" min="60" max="500" step="10" value="250" />
    </div>

    <div class="grupo">
      <label>Repulsión<span class="valor" id="v-repulsion">9000</span></label>
      <input type="range" id="s-repulsion" min="500" max="20000" step="250" value="9000" />
    </div>

    <div class="grupo">
      <label>Gravedad central<span class="valor" id="v-gravedad">0.30</span></label>
      <input type="range" id="s-gravedad" min="0" max="1" step="0.05" value="0.30" />
    </div>

    <div class="botones">
      <button class="btn btn-primary" onclick="replayAnimacion()">Replay</button>
      <button class="btn" onclick="resetConfig()">Reset</button>
    </div>
  </div>
  <main>
    <div id="grafo">
      <div id="loader">
        <div class="spinner"></div>
        <div class="texto">Cargando red regulatoria</div>
      </div>
    </div>
    <aside>
      <h2>Acerca del corpus</h2>
      <p>
        Cada <b style="color:var(--fg)">nodo</b> es un documento de la SBS o una entidad
        citada (resolución, ley, circular, artículo, anexo). Cada <b style="color:var(--fg)">arista</b>
        es una cita detectada en el texto del corpus. El tamaño del nodo crece con su
        número de conexiones.
      </p>
      <h2>Documento por institución</h2>
      <p style="font-size: 11px; color: var(--fg-muted); margin: 0 0 6px 0;">
        Los nodos de documento (rombos) se colorean según la entidad emisora.
      </p>
      <div class="leyenda">
        <span><span class="dot" style="background:#003d7a"></span>SBS</span>
        <span><span class="dot" style="background:#b91c1c"></span>BCRP</span>
        <span><span class="dot" style="background:#7c3aed"></span>Congreso</span>
        <span><span class="dot" style="background:#15803d"></span>MEF</span>
        <span><span class="dot" style="background:#0891b2"></span>SMV</span>
        <span><span class="dot" style="background:#ca8a04"></span>INDECOPI</span>
      </div>
      <h2>Tipo de nodo (entidades citadas)</h2>
      <div class="leyenda">
        <span><span class="dot" style="background:#0073cf"></span>Resolución</span>
        <span><span class="dot" style="background:#059669"></span>Ley</span>
        <span><span class="dot" style="background:#d97706"></span>Circular</span>
        <span><span class="dot" style="background:#475569"></span>Artículo</span>
        <span><span class="dot" style="background:#7c3aed"></span>Anexo</span>
        <span><span class="dot" style="background:#db2777"></span>Tópico</span>
      </div>
      <h2>Relación</h2>
      <div class="leyenda">
        <span><span class="dot" style="background:#94a3b8;width:14px;height:2px;border-radius:0"></span>Cita</span>
        <span><span class="dot" style="background:#d97706;width:14px;height:2px;border-radius:0"></span>Modifica</span>
        <span><span class="dot" style="background:#dc0014;width:14px;height:2px;border-radius:0"></span>Deroga</span>
        <span><span class="dot" style="background:#db2777;width:14px;height:2px;border-radius:0"></span>Tópico</span>
      </div>
      <h2>Selección</h2>
      <div id="info">
        <p>Selecciona un nodo del grafo para ver sus detalles.</p>
      </div>
    </aside>
  </main>
  <script>
    // ----- Estado top-level (visible para todas las funciones del script) -----
    let red, datasetNodos, datasetAristas, todosNodos = [], todasAristas = [];
    let timeoutTransicion = null;

    const CONFIG_DEFAULT = {
      duracion: 1500,    // ms de la fase de entrada
      intensidad: 2,     // 1 (poca) — 5 (mucha): controla damping en entrada
      espaciado: 250,    // springLength base (era 130 → ahora más aire)
      repulsion: 9000,   // |gravitationalConstant| (era 3500 → más separación)
      gravedad: 0.15,    // centralGravity (era 0.30 → menos aglomeración central)
    };
    let config = { ...CONFIG_DEFAULT };

    // Mapeo intensidad → damping: 1=0.70 (poca rotación), 5=0.30 (mucha)
    function dampingEntrada() {
      const tabla = { 1: 0.70, 2: 0.55, 3: 0.45, 4: 0.38, 5: 0.30 };
      return tabla[config.intensidad] || 0.55;
    }
    function maxVelEntrada() {
      const tabla = { 1: 30, 2: 50, 3: 70, 4: 90, 5: 120 };
      return tabla[config.intensidad] || 50;
    }

    function fisicaEntrada() {
      return {
        enabled: true,
        solver: 'forceAtlas2Based',
        forceAtlas2Based: {
          gravitationalConstant: -45,
          centralGravity: 0.02,
          springLength: config.espaciado,
          springConstant: 0.04,
          damping: dampingEntrada(),
          avoidOverlap: 0.3,
        },
        maxVelocity: maxVelEntrada(),
        minVelocity: 1,
        timestep: 0.5,
        stabilization: { enabled: false },
      };
    }

    // Modo asentado: damping bajado a 0.78 para que los cambios de
    // espaciado/repulsion se propaguen visiblemente.
    function fisicaAsentada() {
      return {
        enabled: true,
        solver: 'barnesHut',
        barnesHut: {
          gravitationalConstant: -config.repulsion,
          centralGravity: config.gravedad,
          springLength: config.espaciado,
          springConstant: 0.05,
          damping: 0.78,
          avoidOverlap: 0.5,
        },
        maxVelocity: 25,
        minVelocity: 0.3,
        timestep: 0.3,
        stabilization: {
          enabled: true,
          iterations: 300,
          updateInterval: 25,
          fit: false,
        },
      };
    }

    // Frenado breve post-entrada: damping muy alto durante 250 ms
    // para matar la inercia antes del modo asentado.
    function fisicaFrenado() {
      return {
        enabled: true,
        solver: 'forceAtlas2Based',
        forceAtlas2Based: {
          gravitationalConstant: -45,
          centralGravity: 0.05,
          springLength: config.espaciado,
          springConstant: 0.04,
          damping: 0.95,
          avoidOverlap: 0.3,
        },
        maxVelocity: 15,
        minVelocity: 0.2,
        timestep: 0.3,
        stabilization: { enabled: false },
      };
    }

    async function cargar() {
      const resp = await fetch('/v1/graph/data?limit_nodes=500');
      const datos = await resp.json();
      todosNodos = datos.nodes;
      todasAristas = datos.edges;
      document.getElementById('stats').innerHTML =
        '<span class="num">' + datos.stats.nodes_returned + '</span> nodos &middot; ' +
        '<span class="num">' + datos.stats.edges_returned + '</span> aristas';

      // Calcula length por arista: hub-a-hub queda 2.5× más larga que hoja-a-hoja
      todasAristas.forEach(a => {
        a.length = config.espaciado * (1 + 1.5 * (a.peso_hub || 0));
      });

      datasetNodos = new vis.DataSet(todosNodos);
      datasetAristas = new vis.DataSet(todasAristas);

      const opciones = {
        nodes: {
          font: {
            color: '#0d1b2a', size: 11, face: 'Inter, sans-serif',
            strokeWidth: 3, strokeColor: '#ffffffee',  // halo blanco para legibilidad
          },
          borderWidth: 1.5,
          borderWidthSelected: 3,
          color: { border: '#ffffffaa', highlight: { border: '#003d7a' } },
        },
        edges: {
          width: 0.6,
          arrows: { to: { enabled: true, scaleFactor: 0.4 } },
          smooth: false,
          color: { color: '#94a3b8', highlight: '#003d7a', hover: '#003d7a' },
        },
        physics: fisicaEntrada(),
        interaction: { hover: true, tooltipDelay: 200, dragNodes: true },
      };

      const contenedor = document.getElementById('grafo');
      document.getElementById('loader').remove();
      red = new vis.Network(contenedor, { nodes: datasetNodos, edges: datasetAristas }, opciones);

      programarTransicion();

      // Cuando termine la estabilización del modo asentado, apagamos la física
      red.on('stabilizationIterationsDone', () => {
        red.setOptions({ physics: { enabled: false } });
        red.fit({ animation: { duration: 600, easingFunction: 'easeInOutQuad' } });
      });

      // Drag temporal: re-enciende física brevemente para reacomodar
      red.on('dragStart', () => red.setOptions({ physics: { enabled: true } }));
      red.on('dragEnd', () => {
        setTimeout(() => red.setOptions({ physics: { enabled: false } }), 800);
      });

      red.on('click', evento => {
        if (evento.nodes.length > 0) mostrarInfo(evento.nodes[0]);
        else document.getElementById('info').innerHTML =
          '<p style="opacity:0.6;">Click un nodo para ver detalles.</p>';
      });
    }

    function mostrarInfo(idNodo) {
      const nodo = datasetNodos.get(idNodo);
      const conectados = red.getConnectedNodes(idNodo);
      const vecinos = conectados.map(id => datasetNodos.get(id))
                                .sort((a, b) => b.size - a.size);

      let html = '<div class="kv">';
      html += '<dt>Tipo</dt><dd>' + nodo.kind + '</dd>';
      html += '<dt>Etiqueta</dt><dd><code>' + nodo.label + '</code></dd>';
      if (nodo.doc_title && nodo.kind === 'document')
        html += '<dt>Título</dt><dd>' + nodo.doc_title + '</dd>';
      html += '<dt>Conexiones</dt><dd>' + vecinos.length + '</dd>';
      html += '</div>';

      if (vecinos.length > 0) {
        html += '<h2 style="margin-top:14px;">Conectado con</h2><ul>';
        vecinos.slice(0, 30).forEach(v => {
          html += '<li onclick="red.focus(\\'' + v.id + '\\', {scale:1.2,animation:true});'
               + 'red.selectNodes([\\''+v.id+'\\']);mostrarInfo(\\''+v.id+'\\')">'
               + v.label + ' <small style="opacity:0.5">(' + v.kind + ')</small></li>';
        });
        if (vecinos.length > 30) html += '<li>+ ' + (vecinos.length - 30) + ' más…</li>';
        html += '</ul>';
      }
      document.getElementById('info').innerHTML = html;
    }

    function ajustarVista() { red.fit({ animation: true }); }

    function aplicarFiltros() {
      const tiposActivos = new Set(
        Array.from(document.querySelectorAll('[data-kind]:checked'))
             .map(c => c.dataset.kind)
      );
      const consulta = document.getElementById('busqueda').value.toLowerCase();
      const idsVisibles = new Set(
        todosNodos.filter(n =>
          tiposActivos.has(n.kind) &&
          (consulta === '' || n.label.toLowerCase().includes(consulta))
        ).map(n => n.id)
      );
      datasetNodos.clear();
      datasetNodos.add(todosNodos.filter(n => idsVisibles.has(n.id)));
      datasetAristas.clear();
      datasetAristas.add(todasAristas.filter(e =>
        idsVisibles.has(e.from) && idsVisibles.has(e.to)));
    }

    document.querySelectorAll('[data-kind]').forEach(c =>
      c.addEventListener('change', aplicarFiltros));
    document.getElementById('busqueda').addEventListener('input', aplicarFiltros);

    // ===== Panel de configuración =====
    function togglePanel() {
      document.getElementById('panel-config').classList.toggle('visible');
    }

    function recalcularLongitudesAristas() {
      // Reaplica length por arista usando config.espaciado actual.
      // Hub→hub queda hasta 2.5× más larga que hoja→hoja.
      const updates = todasAristas.map(a => ({
        id: a.id !== undefined ? a.id : a.from + '-' + a.to,
        length: config.espaciado * (1 + 1.5 * (a.peso_hub || 0)),
      }));
      // datasetAristas no asigna IDs explícitos; mejor reemplazar con clear+add
      const aristasActualizadas = todasAristas.map(a => ({
        ...a,
        length: config.espaciado * (1 + 1.5 * (a.peso_hub || 0)),
      }));
      datasetAristas.clear();
      datasetAristas.add(aristasActualizadas);
      todasAristas = aristasActualizadas;
    }

    function programarTransicion() {
      // Limpia timeouts pendientes (si el usuario hace replay rápido)
      if (timeoutTransicion) clearTimeout(timeoutTransicion);

      // Si el usuario eligió duración 0 → arranca directamente asentado
      if (config.duracion <= 50) {
        red.setOptions({ physics: fisicaAsentada() });
        return;
      }
      // Fase 1: entrada con física libre durante config.duracion ms
      timeoutTransicion = setTimeout(() => {
        // Fase 2 (corta): frenado fuerte para matar la inercia
        red.setOptions({ physics: fisicaFrenado() });
        timeoutTransicion = setTimeout(() => {
          // Fase 3: asentamiento (stabilizationIterationsDone apaga física)
          red.setOptions({ physics: fisicaAsentada() });
        }, 250);
      }, config.duracion);
    }

    function replayAnimacion() {
      if (!red) return;
      // 1. Reposiciona nodos aleatoriamente para forzar re-layout
      datasetNodos.forEach(n => {
        datasetNodos.update({ id: n.id, x: (Math.random() - 0.5) * 400,
                                          y: (Math.random() - 0.5) * 400 });
      });
      // 2. Reaplica física de entrada y reprograma transición
      red.setOptions({ physics: fisicaEntrada() });
      programarTransicion();
    }

    function resetConfig() {
      config = { ...CONFIG_DEFAULT };
      sincronizarSliders();
      replayAnimacion();
    }

    function sincronizarSliders() {
      document.getElementById('s-duracion').value = config.duracion;
      document.getElementById('s-intensidad').value = config.intensidad;
      document.getElementById('s-espaciado').value = config.espaciado;
      document.getElementById('s-repulsion').value = config.repulsion;
      document.getElementById('s-gravedad').value = config.gravedad;
      document.getElementById('v-duracion').textContent = config.duracion + ' ms';
      document.getElementById('v-intensidad').textContent = config.intensidad;
      document.getElementById('v-espaciado').textContent = config.espaciado;
      document.getElementById('v-repulsion').textContent = config.repulsion;
      document.getElementById('v-gravedad').textContent = config.gravedad.toFixed(2);
    }

    function vincularSlider(idSlider, idValor, clave, sufijo, formato, afectaLayout) {
      const slider = document.getElementById(idSlider);
      const valor = document.getElementById(idValor);
      slider.addEventListener('input', e => {
        const v = parseFloat(e.target.value);
        config[clave] = v;
        valor.textContent = (formato ? formato(v) : v) + (sufijo || '');
      });
      slider.addEventListener('change', () => {
        // Solo los sliders que afectan layout disparan re-stabilize.
        // duracion / intensidad solo aplican en próximo replay.
        if (red && afectaLayout) {
          // Si cambió 'espaciado', recalcula length por arista (hub→hub más largas)
          if (clave === 'espaciado') {
            recalcularLongitudesAristas();
          }
          red.setOptions({ physics: fisicaAsentada() });
          red.stabilize(150);   // fuerza recálculo; al terminar dispara
                                 // stabilizationIterationsDone → física off
        }
      });
    }
    vincularSlider('s-duracion', 'v-duracion', 'duracion', ' ms', null, false);
    vincularSlider('s-intensidad', 'v-intensidad', 'intensidad', '', null, false);
    vincularSlider('s-espaciado', 'v-espaciado', 'espaciado', '', null, true);
    vincularSlider('s-repulsion', 'v-repulsion', 'repulsion', '', null, true);
    vincularSlider('s-gravedad', 'v-gravedad', 'gravedad', '', v => v.toFixed(2), true);

    // Tecla 'r' = replay rápido
    document.addEventListener('keydown', e => {
      if (e.key === 'r' && !e.metaKey && !e.ctrlKey
          && document.activeElement.tagName !== 'INPUT') replayAnimacion();
    });

    cargar();
  </script>
</body>
</html>
"""


@router.get("/graph", response_class=HTMLResponse, include_in_schema=False)
async def graph_view() -> str:
    """UI HTML interactiva del grafo (vis-network desde CDN)."""
    return PAGINA_GRAFO_HTML
