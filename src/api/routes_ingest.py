"""POST /v1/ingest — ingesta de un archivo (PDF/TXT/MD).

Sprint 1: ingesta puntual de un archivo subido. Sprint 2 añade el scheduler
con detección incremental y endpoint /v1/ingest/scan.
"""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

logger = logging.getLogger(__name__)
from psycopg_pool import AsyncConnectionPool

from src.core.deps import get_llm, get_pool
from src.llm import LLMProvider
from src.rag.chunker_estructural import chunk_estructural
from src.rag.parser import parse_by_filename
from src.schemas.query import IngestResponse
from src.storage import PgVectorStore
from src.storage.pgvector_store import hash_content

router = APIRouter(tags=["ingest"])


def _slug_desde_nombre(filename: str) -> str:
    """Genera document_id estable a partir del nombre."""
    base = filename.rsplit(".", 1)[0]
    base = re.sub(r"[^A-Za-z0-9_-]+", "_", base)
    return base.strip("_").lower() or "doc"


@router.post("/v1/ingest", response_model=IngestResponse)
async def ingest(
    file: UploadFile = File(...),
    pool: AsyncConnectionPool = Depends(get_pool),
    llm: LLMProvider = Depends(get_llm),
) -> IngestResponse:
    """Recibe un archivo, lo parsea, chunkea, embebe y persiste."""
    if not file.filename:
        raise HTTPException(400, "Archivo sin nombre")

    contenido = await file.read()
    if not contenido:
        raise HTTPException(400, "Archivo vacío")

    # 0. Persistir el binario original en object storage (S3/GCS/local)
    # Esto permite re-procesar el documento en el futuro sin re-descargar
    # del portal SBS (que puede cambiar URLs). Falla suave: si el storage
    # no está disponible, seguimos con la ingesta y solo logueamos.
    try:
        from src.storage.object_store import get_object_store
        store_obj = get_object_store()
        key = f"pdfs/{_slug_desde_nombre(file.filename)}.pdf"
        store_obj.put(key, contenido, content_type="application/pdf")
        logger.info("PDF persistido en object store: %s", key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo persistir el PDF en object store: %s", exc)

    # 1. Parse
    try:
        texto = parse_by_filename(file.filename, contenido)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    if not texto.strip():
        raise HTTPException(422, "No se pudo extraer texto del archivo")

    # 2. Chunk estructural (respeta Capítulos / Artículos / Anexos SBS)
    fragmentos_con_meta = chunk_estructural(texto)
    if not fragmentos_con_meta:
        raise HTTPException(422, "El documento no produjo chunks viables")
    textos_fragmentos = [t for t, _ in fragmentos_con_meta]
    metas_fragmentos = [m for _, m in fragmentos_con_meta]

    # 3. Embed (batch)
    try:
        vectores = await llm.embed(textos_fragmentos)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, f"LLM provider error en embedding: {exc}") from exc

    # 4. Persist
    document_id = _slug_desde_nombre(file.filename)
    hash_contenido = hash_content(contenido)

    async with pool.connection() as conn:
        store = PgVectorStore(conn)
        doc_uuid = await store.upsert_document(
            document_id=document_id,
            title=file.filename,
            content_hash=hash_contenido,
            metadata={"original_filename": file.filename, "size_bytes": len(contenido)},
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

    return IngestResponse(
        document_id=document_id,
        title=file.filename,
        chunks_indexed=indexados,
        content_hash=hash_contenido,
    )
