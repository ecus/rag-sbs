"""pgvector store — búsqueda híbrida (vector + BM25) con RRF.

ADR-002: pgvector sobre Postgres. HNSW para vectores, GIN+tsvector para texto.
RRF (Reciprocal Rank Fusion) combina los dos rankings en código.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from uuid import UUID

from pgvector.psycopg import register_vector_async
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


@dataclass
class RetrievedChunk:
    """Resultado de retrieval: chunk con metadatos y score combinado."""

    chunk_id: UUID
    document_id: UUID
    document_title: str
    document_url: str | None
    content: str
    score: float                # RRF combinado
    vector_score: float = 0.0   # cosine similarity
    text_score: float = 0.0     # ts_rank
    page: int | None = None
    metadata: dict = field(default_factory=dict)   # section_path, structural_level, etc.
    document_issuer: str | None = None  # SBS / BCRP / Congreso / etc.
    document_publication_date: str | None = None   # ISO 'AAAA-MM-DD'
    document_date_precision: str | None = None      # 'dia' | 'anio'


class PgVectorStore:
    """Acceso a documentos y chunks con búsqueda híbrida."""

    def __init__(self, conn: AsyncConnection) -> None:
        self.conn = conn

    @classmethod
    async def setup_connection(cls, conn: AsyncConnection) -> None:
        """Registra el tipo `vector` con psycopg. Llamar una vez por conexión."""
        await register_vector_async(conn)

    # -------------------------------------------------------------------------
    # Ingesta
    # -------------------------------------------------------------------------

    async def upsert_document(
        self,
        *,
        document_id: str,
        title: str,
        content_hash: str,
        source_url: str | None = None,
        document_type: str | None = None,
        domain: str | None = None,
        metadata: dict | None = None,
        publication_date=None,
    ) -> UUID:
        """Inserta documento (versión 1 si nuevo). Retorna UUID interno.

        `publication_date` (date | None): fecha de publicación detectada en la
        ingesta; la precisión ('dia'/'anio') va en metadata['date_precision'].
        """
        async with self.conn.cursor(row_factory=dict_row) as cursor:
            # Si existe documento con mismo hash → reutilizar (idempotente)
            await cursor.execute(
                "SELECT id FROM documents WHERE document_id = %s AND content_hash = %s",
                (document_id, content_hash),
            )
            fila = await cursor.fetchone()
            if fila:
                return fila["id"]

            # Calcular siguiente version_id si ya existe el slug con otro hash
            await cursor.execute(
                "SELECT COALESCE(MAX(version_id), 0) AS v FROM documents WHERE document_id = %s",
                (document_id,),
            )
            fila_v = await cursor.fetchone()
            siguiente_version = int((fila_v or {}).get("v", 0)) + 1

            # Insertar nueva versión
            await cursor.execute(
                """
                INSERT INTO documents
                    (document_id, version_id, title, source_url, document_type,
                     domain, content_hash, metadata, publication_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    document_id,
                    siguiente_version,
                    title,
                    source_url,
                    document_type,
                    domain,
                    content_hash,
                    Jsonb(metadata or {}),
                    publication_date,
                ),
            )
            fila = await cursor.fetchone()
            assert fila is not None
            return fila["id"]

    async def insert_chunks(
        self,
        document_uuid: UUID,
        chunks: list[tuple[int, str, list[float]] | tuple[int, str, list[float], dict]],
    ) -> int:
        """Inserta chunks en batch. Acepta tuplas (idx, content, embedding) o
        (idx, content, embedding, metadata) para chunker estructural.
        Retorna cantidad indexada.
        """
        if not chunks:
            return 0
        # Normalizar a (idx, content, emb, metadata)
        registros = []
        for item in chunks:
            if len(item) == 3:
                idx, contenido, vector = item
                metadata: dict = {}
            else:
                idx, contenido, vector, metadata = item
            registros.append((document_uuid, idx, contenido, vector, Jsonb(metadata or {})))

        async with self.conn.cursor() as cursor:
            await cursor.executemany(
                """
                INSERT INTO chunks (document_id, chunk_index, content, embedding, metadata)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (document_id, chunk_index) DO UPDATE
                    SET content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata
                """,
                registros,
            )
        return len(chunks)

    # -------------------------------------------------------------------------
    # Retrieval híbrido
    # -------------------------------------------------------------------------

    async def hybrid_search(
        self,
        *,
        query_embedding: list[float],
        query_text: str,
        top_k: int = 5,
        domain: str | None = None,
        validity_status: str | None = "vigente",
        rrf_k: int = 60,
        titles_like: list[str] | None = None,
        w_vector: float = 1.0,
        w_texto: float = 1.0,
    ) -> list[RetrievedChunk]:
        """Búsqueda híbrida vector + BM25 con Reciprocal Rank Fusion.

        Args:
            titles_like: opcional. Lista de substrings; si se provee, solo
                considera chunks de documentos cuyo title contenga alguno
                (case-insensitive). Útil para fetch dirigido por tema.

        RRF score = sum(1 / (k + rank_i)) por cada ranker que incluye el chunk.
        k=60 es estándar (Cormack et al., 2009).
        """
        # Filtros opcionales sobre documents JOIN
        condiciones: list[str] = []
        params_vec: list = [query_embedding]
        params_texto: list = [query_text]

        if domain:
            condiciones.append("d.domain = %s")
            params_vec.append(domain)
            params_texto.append(domain)
        if validity_status:
            condiciones.append("d.validity_status = %s")
            params_vec.append(validity_status)
            params_texto.append(validity_status)
        if titles_like:
            # OR de ILIKEs sobre title — match si CUALQUIER patrón aparece.
            or_clauses = " OR ".join(["d.title ILIKE %s"] * len(titles_like))
            condiciones.append(f"({or_clauses})")
            for pattern in titles_like:
                like_value = f"%{pattern}%"
                params_vec.append(like_value)
                params_texto.append(like_value)

        clausula_where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""

        # 1. Top-N vectorial (cosine).
        # NOTA: cast explícito a ::vector. psycopg adapta list[float] como
        # double precision[] por defecto; pgvector necesita vector.
        params_vec.append(top_k * 3)  # over-fetch para RRF
        sql_vec = f"""
            SELECT c.id, c.document_id, c.content, c.metadata,
                   1 - (c.embedding <=> %s::vector) AS vector_score,
                   d.title, d.source_url, d.id AS doc_uuid,
                   d.publication_date, d.metadata->>'date_precision' AS date_precision,
                   COALESCE(d.metadata->>'issuer', '(s/d)') AS doc_issuer
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            {clausula_where}
            ORDER BY c.embedding <=> %s::vector
            LIMIT %s
        """
        # NOTA: %s para el embedding aparece 2 veces (SELECT distance + ORDER BY).
        # Lo agregamos manualmente para que coincida.
        params_vec_full = [query_embedding, *params_vec[1:-1], query_embedding, params_vec[-1]]

        # 2. Top-N text (BM25-like vía ts_rank)
        params_texto.append(top_k * 3)
        sql_texto = f"""
            SELECT c.id, c.document_id, c.content, c.metadata,
                   ts_rank(c.content_tsv, plainto_tsquery('spanish', %s)) AS text_score,
                   d.title, d.source_url, d.id AS doc_uuid,
                   d.publication_date, d.metadata->>'date_precision' AS date_precision,
                   COALESCE(d.metadata->>'issuer', '(s/d)') AS doc_issuer
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            {clausula_where + (' AND ' if clausula_where else 'WHERE ')}
                  c.content_tsv @@ plainto_tsquery('spanish', %s)
            ORDER BY text_score DESC
            LIMIT %s
        """
        params_texto_full = [query_text, *params_texto[1:-1], query_text, params_texto[-1]]

        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(sql_vec, params_vec_full)
            filas_vec = await cursor.fetchall()

            try:
                await cursor.execute(sql_texto, params_texto_full)
                filas_texto = await cursor.fetchall()
            except Exception:
                # BM25 puede fallar con query vacía o caracteres raros — degrade
                filas_texto = []

        # 3. RRF fusion con pesos adaptativos (Phase 3 hybrid tuning)
        puntajes: dict[UUID, dict] = {}
        for rango, fila in enumerate(filas_vec, start=1):
            cid = fila["id"]
            puntajes[cid] = {
                "fila": fila,
                "rrf": w_vector * (1.0 / (rrf_k + rango)),
                "vector_score": float(fila["vector_score"]),
                "text_score": 0.0,
            }
        for rango, fila in enumerate(filas_texto, start=1):
            cid = fila["id"]
            if cid in puntajes:
                puntajes[cid]["rrf"] += w_texto * (1.0 / (rrf_k + rango))
                puntajes[cid]["text_score"] = float(fila["text_score"])
            else:
                puntajes[cid] = {
                    "fila": fila,
                    "rrf": w_texto * (1.0 / (rrf_k + rango)),
                    "vector_score": 0.0,
                    "text_score": float(fila["text_score"]),
                }

        rankeados = sorted(puntajes.values(), key=lambda x: x["rrf"], reverse=True)[:top_k]

        return [
            RetrievedChunk(
                chunk_id=item["fila"]["id"],
                document_id=item["fila"]["doc_uuid"],
                document_title=item["fila"]["title"],
                document_url=item["fila"]["source_url"],
                content=item["fila"]["content"],
                score=item["rrf"],
                vector_score=item["vector_score"],
                text_score=item["text_score"],
                metadata=item["fila"].get("metadata") or {},
                document_issuer=item["fila"].get("doc_issuer"),
                document_publication_date=(
                    item["fila"]["publication_date"].isoformat()
                    if item["fila"].get("publication_date")
                    else None
                ),
                document_date_precision=item["fila"].get("date_precision"),
            )
            for item in rankeados
        ]


def hash_content(content: bytes | str) -> str:
    """SHA-256 hex de un contenido."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()
