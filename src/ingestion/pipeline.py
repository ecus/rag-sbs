"""Pipeline de ingesta: orquesta download → diff → parse → chunk → embed → upsert.

Idempotente: si el hash es igual al último indexado, no hace nada.
Versionado: mantiene historial; never delete (regla inviolable Sec 11.2 #4).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from psycopg_pool import AsyncConnectionPool

from src.ingestion.differ import classify_change, hash_bytes, has_changed
from src.ingestion.downloader import Downloader
from src.ingestion.repository import IngestionRepository
from src.llm import LLMProvider
from src.rag.chunker_estructural import chunk_estructural
from src.rag.parser import parse_pdf, parse_text
from src.storage import PgVectorStore

logger = logging.getLogger(__name__)


@dataclass
class SourceResult:
    """Resultado de procesar una fuente."""

    source_name: str
    status: str  # 'new' | 'modified' | 'derogatorio' | 'unchanged' | 'error'
    document_id: UUID | None = None
    chunks_indexed: int = 0
    error: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


def _normalizar_nombre(nombre: str) -> str:
    norm = re.sub(r"[^A-Za-z0-9_-]+", "_", nombre)
    return norm.strip("_").lower() or "source"


def _parsear_bytes_a_texto(content: bytes, *, content_type: str | None) -> str:
    """Decide parser según content-type."""
    tipo = (content_type or "").lower()
    if "application/pdf" in tipo or content[:4] == b"%PDF":
        return parse_pdf(content)
    return parse_text(content)


async def process_source(
    source: dict,
    *,
    pool: AsyncConnectionPool,
    llm: LLMProvider,
    downloader: Downloader,
    run_id: UUID | None,
    force: bool = False,
    dry_run: bool = False,
) -> SourceResult:
    """Procesa UNA fuente del registro.

    Pasos:
    1. fetch (con ETag/Last-Modified si aplica) → 304 short-circuit
    2. hash bytes → comparar con last_hash
    3. parse → text
    4. classify (new | modified | derogatorio)
    5. chunk + embed
    6. upsert atómico (transacción)
    7. update doc_sources cache + log change_event

    Cumple: RF-010 .. RF-012, RF-021, RF-022, RF-024.
    """
    nombre = source["name"]
    url = source["url"]
    source_id = source["id"]

    # 1. Fetch
    res = await downloader.fetch(
        url,
        prev_etag=None if force else source.get("last_etag"),
        prev_last_modified=None if force else source.get("last_modified"),
    )

    # Update check state, decide flow
    if res.status == "error":
        async with pool.connection() as conn:
            repo = IngestionRepository(conn)
            await repo.update_check_state(
                source_id=source_id,
                etag=source.get("last_etag"),
                last_modified=source.get("last_modified"),
                content_hash=None,
                status="error",
                changed=False,
            )
        return SourceResult(
            source_name=nombre,
            status="error",
            error=res.error,
            detail={"http_status": res.http_status},
        )

    if res.status == "not_modified":
        async with pool.connection() as conn:
            repo = IngestionRepository(conn)
            await repo.update_check_state(
                source_id=source_id,
                etag=res.etag or source.get("last_etag"),
                last_modified=res.last_modified or source.get("last_modified"),
                content_hash=None,
                status="not_modified",
                changed=False,
            )
        return SourceResult(source_name=nombre, status="unchanged")

    # res.status == "changed"
    assert res.content is not None
    hash_nuevo = hash_bytes(res.content)
    hash_anterior = source.get("last_hash")
    es_nuevo = hash_anterior is None
    if not has_changed(hash_anterior, hash_nuevo):
        # Hash idéntico al indexado → unchanged (force solo bypassea cache HTTP,
        # no la igualdad de hash; si hash coincide, no hay cambio real).
        async with pool.connection() as conn:
            repo = IngestionRepository(conn)
            await repo.update_check_state(
                source_id=source_id,
                etag=res.etag,
                last_modified=res.last_modified,
                content_hash=hash_nuevo,
                status="unchanged",
                changed=False,
            )
        return SourceResult(source_name=nombre, status="unchanged")

    # 3. Parse
    try:
        texto = _parsear_bytes_a_texto(res.content, content_type=res.content_type)
    except Exception as exc:  # noqa: BLE001
        async with pool.connection() as conn:
            repo = IngestionRepository(conn)
            await repo.update_check_state(
                source_id=source_id,
                etag=res.etag,
                last_modified=res.last_modified,
                content_hash=hash_nuevo,
                status="error",
                changed=False,
            )
            await repo.insert_change_event(
                source_id=source_id,
                run_id=run_id,
                event_type="parse_failed",
                summary=f"No se pudo parsear contenido de {nombre}: {exc}",
                details={"error": str(exc), "url": url},
            )
        return SourceResult(source_name=nombre, status="error", error=f"parse: {exc}")

    if not texto.strip():
        return SourceResult(
            source_name=nombre, status="error", error="texto extraído vacío"
        )

    # 4. Classify
    titulo = source.get("metadata", {}).get("title") or nombre
    tipo_cambio = classify_change(
        is_new=es_nuevo, title=titulo, text_head=texto[:2000]
    )

    if dry_run:
        # No upsert; solo registra cambio detectado
        return SourceResult(
            source_name=nombre,
            status=tipo_cambio,
            detail={
                "would_index": True,
                "new_hash": hash_nuevo,
                "text_chars": len(texto),
            },
        )

    # 5. Chunk estructural (respeta Capítulo > Artículo > Anexo)
    fragmentos_con_meta = chunk_estructural(texto)
    if not fragmentos_con_meta:
        return SourceResult(
            source_name=nombre, status="error", error="chunker no produjo chunks"
        )
    textos_fragmentos = [t for t, _ in fragmentos_con_meta]
    metas_fragmentos = [m for _, m in fragmentos_con_meta]

    # 6. Embed
    try:
        vectores = await llm.embed(textos_fragmentos)
    except Exception as exc:  # noqa: BLE001
        return SourceResult(
            source_name=nombre, status="error", error=f"embed: {exc}"
        )

    # 7. Upsert atómico
    document_id_slug = _normalizar_nombre(nombre)
    async with pool.connection() as conn:
        async with conn.transaction():
            store = PgVectorStore(conn)
            doc_uuid = await store.upsert_document(
                document_id=document_id_slug,
                title=source.get("metadata", {}).get("title") or nombre,
                content_hash=hash_nuevo,
                source_url=url,
                document_type=source.get("document_type"),
                domain=source.get("domain"),
                metadata={
                    **source.get("metadata", {}),
                    "fetched_url": url,
                    "fetched_via": "scheduler",
                    "content_type": res.content_type,
                },
            )
            indexados = await store.insert_chunks(
                doc_uuid,
                [
                    (i, frag, vec, meta)
                    for i, (frag, vec, meta) in enumerate(
                        zip(textos_fragmentos, vectores, metas_fragmentos)
                    )
                ],
            )

            repo = IngestionRepository(conn)
            await repo.update_check_state(
                source_id=source_id,
                etag=res.etag,
                last_modified=res.last_modified,
                content_hash=hash_nuevo,
                status=tipo_cambio,
                changed=True,
            )
            await repo.insert_change_event(
                source_id=source_id,
                run_id=run_id,
                event_type=tipo_cambio,
                document_id=doc_uuid,
                summary=f"{tipo_cambio.upper()}: {nombre} ({indexados} chunks)",
                details={
                    "url": url,
                    "new_hash": hash_nuevo,
                    "prev_hash": hash_anterior,
                    "chunks_indexed": indexados,
                    "text_chars": len(texto),
                },
            )

    return SourceResult(
        source_name=nombre,
        status=tipo_cambio,
        document_id=doc_uuid,
        chunks_indexed=indexados,
        detail={"new_hash": hash_nuevo, "text_chars": len(texto)},
    )


async def run_scan(
    *,
    pool: AsyncConnectionPool,
    llm: LLMProvider,
    source_filter: list[str],
    force: bool,
    dry_run: bool,
    triggered_by: str,
    external_run_id: UUID | None = None,
) -> dict:
    """Ejecuta un scan completo. Retorna resumen del run.

    Si se pasa ``external_run_id``, se reutiliza ese ID en vez de crear uno
    nuevo. Esto permite que el endpoint /v1/ingest/scan retorne un run_id
    ANTES de procesar, y el frontend pueda hacer polling del MISMO run_id
    para la barra de progreso.
    """
    async with pool.connection() as conn:
        repo = IngestionRepository(conn)
        if external_run_id is None:
            run_id = await repo.create_run(
                triggered_by=triggered_by,
                source_filter=source_filter,
                dry_run=dry_run,
            )
        else:
            run_id = external_run_id
        fuentes = await repo.list_sources(
            only_enabled=True, names=source_filter or None
        )

    resultados: list[SourceResult] = []
    errores: list[dict] = []

    async with Downloader() as descargador:
        for fuente in fuentes:
            try:
                resultado = await process_source(
                    fuente,
                    pool=pool,
                    llm=llm,
                    downloader=descargador,
                    run_id=run_id,
                    force=force,
                    dry_run=dry_run,
                )
                resultados.append(resultado)
                if resultado.error:
                    errores.append({"source": resultado.source_name, "error": resultado.error})
            except Exception as exc:  # noqa: BLE001
                logger.exception("Error procesando fuente %s", fuente["name"])
                errores.append({"source": fuente["name"], "error": str(exc)})

    docs_nuevos = sum(1 for r in resultados if r.status == "new")
    docs_modificados = sum(1 for r in resultados if r.status in ("modified", "derogatorio"))
    docs_sin_cambios = sum(1 for r in resultados if r.status == "unchanged")
    estado_final = (
        "completed"
        if not errores
        else ("partial" if docs_nuevos + docs_modificados > 0 else "failed")
    )

    async with pool.connection() as conn:
        repo = IngestionRepository(conn)
        await repo.update_run(
            run_id,
            status=estado_final,
            finished_at="now()",  # type: ignore[arg-type]  # special handled below
            sources_scanned=len(resultados),
            docs_new=docs_nuevos,
            docs_modified=docs_modificados,
            docs_unchanged=docs_sin_cambios,
            errors=errores,
        )
        # finished_at workaround — psycopg necesita expresión SQL real
        async with conn.cursor() as cursor:
            await cursor.execute(
                "UPDATE ingestion_runs SET finished_at = now() WHERE id = %s",
                (run_id,),
            )

    return {
        "run_id": str(run_id),
        "status": estado_final,
        "sources_scanned": len(resultados),
        "docs_new": docs_nuevos,
        "docs_modified": docs_modificados,
        "docs_unchanged": docs_sin_cambios,
        "errors": errores,
        "results": [
            {
                "source": r.source_name,
                "status": r.status,
                "chunks_indexed": r.chunks_indexed,
                "error": r.error,
            }
            for r in resultados
        ],
    }
