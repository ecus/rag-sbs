"""Exporter de grafo a vault Obsidian.

Genera un directorio `vault/` con:
  - `<documento>.md` por cada documento, con frontmatter YAML + wikilinks
  - `_resolutions/<Res-SBS-X-Y>.md` por cada resolución citada
  - `_index.md` con resumen de tópicos y enlaces

El usuario abre Obsidian apuntando al directorio y ve el grafo nativo.
"""

from __future__ import annotations

import logging
from pathlib import Path

from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)


def _frontmatter(metadata: dict) -> str:
    """Renderiza frontmatter YAML simple."""
    lineas = ["---"]
    for clave, valor in metadata.items():
        if valor is None:
            continue
        if isinstance(valor, list):
            lineas.append(f"{clave}:")
            for item in valor:
                lineas.append(f"  - {item}")
        else:
            lineas.append(f"{clave}: {valor}")
    lineas.append("---")
    return "\n".join(lineas)


def _normalizar_nombre_archivo(label: str) -> str:
    """Elimina caracteres problemáticos en filesystems."""
    return label.replace("/", "-").replace("\\", "-")[:200]


async def exportar_a_vault(
    pool: AsyncConnectionPool,
    *,
    output_dir: str = "vault",
) -> dict:
    """Genera vault Obsidian desde graph_nodes/edges + documents/chunks."""
    base = Path(output_dir)
    base.mkdir(parents=True, exist_ok=True)
    (base / "_resolutions").mkdir(exist_ok=True)
    (base / "_leyes").mkdir(exist_ok=True)
    (base / "_circulares").mkdir(exist_ok=True)

    archivos_documentos = 0
    archivos_referencias = 0

    async with pool.connection() as conn:
        async with conn.cursor() as cursor:
            # 1. Cargar todos los documentos
            await cursor.execute(
                """
                SELECT d.id, d.document_id, d.title, d.domain, d.document_type,
                       d.source_url, d.metadata
                FROM documents d
                ORDER BY d.title
                """
            )
            documentos = list(await cursor.fetchall())

            # 2. Por cada documento: cargar citas + relacionados
            for (
                doc_uuid, doc_slug, titulo, dominio, tipo_doc, source_url, _meta
            ) in documentos:
                await cursor.execute(
                    """
                    SELECT n.kind, n.label, COUNT(*) AS evidencias
                    FROM graph_edges e
                    JOIN graph_nodes nd ON nd.id = e.src_node
                    JOIN graph_nodes n ON n.id = e.dst_node
                    WHERE nd.kind = 'document' AND nd.document_id = %s
                      AND e.relation IN ('cites', 'self_reference')
                    GROUP BY n.kind, n.label
                    ORDER BY evidencias DESC
                    """,
                    (doc_uuid,),
                )
                citas = list(await cursor.fetchall())

                await cursor.execute(
                    """
                    WITH mi_doc_node AS (
                        SELECT id FROM graph_nodes
                        WHERE kind = 'document' AND document_id = %s LIMIT 1
                    ),
                    mis_targets AS (
                        SELECT e.dst_node FROM graph_edges e
                        JOIN mi_doc_node m ON m.id = e.src_node
                        WHERE e.relation = 'cites'
                    )
                    SELECT d.title, d.id, COUNT(*) AS comp
                    FROM graph_edges e
                    JOIN mis_targets t ON t.dst_node = e.dst_node
                    JOIN graph_nodes nd ON nd.id = e.src_node
                    JOIN documents d ON d.id = nd.document_id
                    WHERE nd.kind = 'document'
                      AND e.relation = 'cites'
                      AND nd.id <> (SELECT id FROM mi_doc_node)
                    GROUP BY d.id, d.title
                    ORDER BY comp DESC
                    LIMIT 5
                    """,
                    (doc_uuid,),
                )
                relacionados = list(await cursor.fetchall())

                tags = []
                if dominio:
                    tags.append(f"dominio/{dominio}")
                if tipo_doc:
                    tags.append(f"tipo/{tipo_doc}")

                cuerpo: list[str] = [
                    _frontmatter({
                        "title": titulo,
                        "document_id": doc_slug,
                        "domain": dominio,
                        "document_type": tipo_doc,
                        "source_url": source_url,
                        "tags": tags,
                    }),
                    "",
                    f"# {titulo}",
                    "",
                    f"**Document ID**: `{doc_slug}`",
                    f"**Source**: {source_url or '(no registrada)'}",
                    "",
                ]

                if citas:
                    cuerpo.append("## Citas detectadas")
                    cuerpo.append("")
                    for kind, label, evidencias in citas:
                        cuerpo.append(
                            f"- [[{label}]] *(tipo: {kind}, {evidencias} ocurrencias)*"
                        )
                    cuerpo.append("")

                if relacionados:
                    cuerpo.append("## Documentos relacionados")
                    cuerpo.append("*Comparten citas con este documento.*")
                    cuerpo.append("")
                    for titulo_rel, _id_rel, comp in relacionados:
                        nombre = _normalizar_nombre_archivo(titulo_rel.rsplit(".", 1)[0])
                        cuerpo.append(f"- [[{nombre}]] — {comp} citas compartidas")
                    cuerpo.append("")

                cuerpo.append("---")
                cuerpo.append("*Generado automáticamente por RAG SBS Knowledge Graph L1.*")

                nombre_archivo = _normalizar_nombre_archivo(titulo.rsplit(".", 1)[0])
                ruta = base / f"{nombre_archivo}.md"
                ruta.write_text("\n".join(cuerpo), encoding="utf-8")
                archivos_documentos += 1

            # 3. Resoluciones / leyes / circulares como notas-stub
            await cursor.execute(
                """
                SELECT n.kind, n.label, COUNT(e.id) AS citaciones
                FROM graph_nodes n
                LEFT JOIN graph_edges e ON e.dst_node = n.id
                WHERE n.kind IN ('resolution', 'ley', 'circular')
                GROUP BY n.kind, n.label
                ORDER BY citaciones DESC
                """
            )
            referencias = list(await cursor.fetchall())

            for kind, label, citaciones in referencias:
                sub = {
                    "resolution": "_resolutions",
                    "ley": "_leyes",
                    "circular": "_circulares",
                }[kind]
                cuerpo = [
                    _frontmatter({
                        "label": label,
                        "kind": kind,
                        "citation_count": citaciones,
                        "tags": [f"tipo/{kind}"],
                    }),
                    "",
                    f"# {label}",
                    "",
                    f"**Tipo**: {kind}",
                    f"**Citaciones recibidas**: {citaciones}",
                    "",
                    "*Esta nota se generó automáticamente como referencia de cita.*",
                    "*Cuando se ingese el documento original al sistema, se enriquecerá.*",
                ]
                ruta = base / sub / f"{_normalizar_nombre_archivo(label)}.md"
                ruta.write_text("\n".join(cuerpo), encoding="utf-8")
                archivos_referencias += 1

            # 4. Índice
            await cursor.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM graph_nodes) AS nodos,
                    (SELECT COUNT(*) FROM graph_edges) AS aristas,
                    (SELECT COUNT(*) FROM documents) AS documentos
                """
            )
            fila_stats = await cursor.fetchone()
            n_nodos, n_aristas, n_docs = fila_stats  # type: ignore[misc]

        indice = [
            "---",
            "title: Índice del Cerebro Digital SBS",
            "tags: [indice]",
            "---",
            "",
            "# Cerebro Digital — Corpus Regulatorio SBS",
            "",
            f"- **Documentos indexados**: {n_docs}",
            f"- **Nodos del grafo**: {n_nodos}",
            f"- **Aristas (citas + relaciones)**: {n_aristas}",
            "",
            "## Cómo navegar",
            "1. Abre el grafo nativo de Obsidian (Ctrl+G / Cmd+G).",
            "2. Filtra por tag: `tag:#dominio/riesgo_credito`, `tag:#tipo/resolucion`, etc.",
            "3. Click en un wikilink `[[Res-SBS-XXXXX-AAAA]]` para abrir la nota.",
            "",
            "## Documentos",
            "",
        ]
        for (
            _doc_uuid, _slug, titulo, _dom, _tipo, _url, _meta
        ) in documentos:
            nombre = _normalizar_nombre_archivo(titulo.rsplit(".", 1)[0])
            indice.append(f"- [[{nombre}]]")
        (base / "_index.md").write_text("\n".join(indice), encoding="utf-8")

    return {
        "ruta_vault": str(base.resolve()),
        "documentos_exportados": archivos_documentos,
        "notas_referencia_creadas": archivos_referencias,
    }
