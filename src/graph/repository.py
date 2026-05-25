"""Repository: graph_nodes + graph_edges sobre Postgres."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


class GraphRepository:
    """Operaciones sobre el grafo persistido."""

    def __init__(self, conn: AsyncConnection) -> None:
        self.conn = conn

    # -------------------------------------------------------------------------
    # Nodos
    # -------------------------------------------------------------------------

    async def upsert_node(
        self,
        *,
        kind: str,
        label: str,
        document_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> UUID:
        """Inserta nodo o retorna el existente (kind, label)."""
        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                INSERT INTO graph_nodes (kind, label, document_id, metadata)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (kind, label) DO UPDATE
                    SET document_id = COALESCE(graph_nodes.document_id, EXCLUDED.document_id),
                        metadata = graph_nodes.metadata || EXCLUDED.metadata
                RETURNING id
                """,
                (kind, label, document_id, Jsonb(metadata or {})),
            )
            fila = await cursor.fetchone()
            assert fila is not None
            return fila["id"]

    async def get_node(self, node_id: UUID) -> dict | None:
        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute("SELECT * FROM graph_nodes WHERE id = %s", (node_id,))
            return await cursor.fetchone()

    async def list_nodes(
        self, *, kind: str | None = None, limit: int = 200
    ) -> list[dict]:
        sql = "SELECT * FROM graph_nodes"
        parametros: list[Any] = []
        if kind:
            sql += " WHERE kind = %s"
            parametros.append(kind)
        sql += " ORDER BY label LIMIT %s"
        parametros.append(limit)
        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(sql, parametros)
            return list(await cursor.fetchall())

    # -------------------------------------------------------------------------
    # Aristas
    # -------------------------------------------------------------------------

    async def insert_edge(
        self,
        *,
        src_node: UUID,
        dst_node: UUID,
        relation: str,
        score: float = 1.0,
        evidence_chunk_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Idempotente por (src, dst, relation, evidence_chunk_id)."""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO graph_edges
                    (src_node, dst_node, relation, score, evidence_chunk_id, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (src_node, dst_node, relation, evidence_chunk_id) DO NOTHING
                """,
                (
                    src_node,
                    dst_node,
                    relation,
                    score,
                    evidence_chunk_id,
                    Jsonb(metadata or {}),
                ),
            )

    async def list_edges_from(
        self, src_node: UUID, *, relations: list[str] | None = None, limit: int = 100
    ) -> list[dict]:
        """Vecinos salientes con info del destino."""
        sql = """
            SELECT e.*, n.kind AS dst_kind, n.label AS dst_label,
                   n.document_id AS dst_document_id
            FROM graph_edges e
            JOIN graph_nodes n ON n.id = e.dst_node
            WHERE e.src_node = %s
        """
        parametros: list[Any] = [src_node]
        if relations:
            sql += " AND e.relation = ANY(%s)"
            parametros.append(relations)
        sql += " ORDER BY e.score DESC LIMIT %s"
        parametros.append(limit)
        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(sql, parametros)
            return list(await cursor.fetchall())

    async def list_edges_to(
        self, dst_node: UUID, *, relations: list[str] | None = None, limit: int = 100
    ) -> list[dict]:
        """Vecinos entrantes con info del origen (¿quién me cita?)."""
        sql = """
            SELECT e.*, n.kind AS src_kind, n.label AS src_label,
                   n.document_id AS src_document_id
            FROM graph_edges e
            JOIN graph_nodes n ON n.id = e.src_node
            WHERE e.dst_node = %s
        """
        parametros: list[Any] = [dst_node]
        if relations:
            sql += " AND e.relation = ANY(%s)"
            parametros.append(relations)
        sql += " ORDER BY e.score DESC LIMIT %s"
        parametros.append(limit)
        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(sql, parametros)
            return list(await cursor.fetchall())

    async def estadisticas(self) -> dict:
        """Conteos rápidos para UI."""
        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM graph_nodes) AS nodos_total,
                    (SELECT COUNT(*) FROM graph_edges) AS aristas_total,
                    (SELECT json_object_agg(kind, total)
                     FROM (SELECT kind, COUNT(*) AS total FROM graph_nodes GROUP BY kind) k)
                        AS nodos_por_tipo,
                    (SELECT json_object_agg(relation, total)
                     FROM (SELECT relation, COUNT(*) AS total FROM graph_edges GROUP BY relation) r)
                        AS aristas_por_tipo
                """
            )
            fila = await cursor.fetchone()
            return dict(fila) if fila else {}

    async def truncate_all(self) -> None:
        """Borra grafo completo (rebuild desde cero)."""
        async with self.conn.cursor() as cursor:
            await cursor.execute("TRUNCATE graph_edges, graph_nodes CASCADE")

    # -------------------------------------------------------------------------
    # Queries especializadas — documentos relacionados
    # -------------------------------------------------------------------------

    async def documentos_relacionados(
        self, document_id: UUID, *, limit: int = 10
    ) -> list[dict]:
        """Documentos que comparten citas con el documento dado.

        Estrategia: documentos que citan (o son citados por) las mismas
        resoluciones/leyes/circulares que este documento. Score = cantidad
        de citas compartidas.
        """
        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                WITH mi_doc_node AS (
                    SELECT id FROM graph_nodes
                    WHERE kind = 'document' AND document_id = %s
                    LIMIT 1
                ),
                mis_citas AS (
                    -- nodos que cita mi documento
                    SELECT e.dst_node
                    FROM graph_edges e
                    JOIN mi_doc_node m ON m.id = e.src_node
                    WHERE e.relation = 'cites'
                ),
                otros_documentos AS (
                    -- otros nodos document que citan los mismos targets
                    SELECT e.src_node, COUNT(*) AS citas_compartidas
                    FROM graph_edges e
                    JOIN mis_citas mc ON mc.dst_node = e.dst_node
                    JOIN graph_nodes nd ON nd.id = e.src_node
                    WHERE e.relation = 'cites'
                      AND nd.kind = 'document'
                      AND e.src_node <> (SELECT id FROM mi_doc_node)
                    GROUP BY e.src_node
                )
                SELECT n.id, n.label, n.document_id, n.metadata,
                       d.title AS document_title, d.source_url,
                       od.citas_compartidas
                FROM otros_documentos od
                JOIN graph_nodes n ON n.id = od.src_node
                LEFT JOIN documents d ON d.id = n.document_id
                ORDER BY od.citas_compartidas DESC
                LIMIT %s
                """,
                (document_id, limit),
            )
            return list(await cursor.fetchall())
