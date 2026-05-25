"""Topic Modeling L2: clustering K-means + naming via LLM.

Aprovechamos que los embeddings ya están en pgvector. Pipeline:
  1. SELECT id, content, embedding FROM chunks
  2. K-means(n_clusters) sobre la matriz de embeddings
  3. Para cada cluster: tomar los 5 chunks más cercanos al centroide
  4. LLM: "estos 5 fragmentos hablan de qué? dame 3-5 palabras como label"
  5. Persistir:
     - 1 nodo `kind='topic'` por cluster con label generado
     - aristas `relation='same_topic'` entre cada chunk's documento y el nodo del tópico
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

import numpy as np
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from sklearn.cluster import KMeans

from src.graph.repository import GraphRepository
from src.llm import LLMProvider

logger = logging.getLogger(__name__)


@dataclass
class TopicoDescubierto:
    """Resultado de un cluster nombrado."""

    indice: int                          # 0..n-1
    label: str                           # "provisiones, deudor, garantía"
    miembros: list[UUID]                 # chunk_ids del cluster
    snippets_representativos: list[str]  # textos cortos para mostrar


PROMPT_NOMBRAR_TOPICO = """\
Te paso 5 fragmentos de documentos de la SBS Perú que un algoritmo agrupó en un mismo tópico.
Tu tarea: producir UN label corto (3-6 palabras) que describa el tema común.

REGLAS:
- Idioma OBLIGATORIO: español de Perú. Prohibido cualquier otro idioma, alfabeto
  o sistema de escritura (NO chino, NO tailandés, NO árabe, NO cirílico, NO japonés).
  Solo caracteres latinos (a-z, A-Z, áéíóú, ñ).
- Solo el label, sin comillas ni explicaciones, sin punto final.
- Vocabulario regulatorio peruano (provisiones, garantías, riesgo crediticio, etc.).
- Sin verbos, solo conceptos.
- Si los fragmentos no tienen tema claro, responde exactamente: "Misceláneo".
- Ejemplos de labels válidos: "Provisiones crediticias", "Riesgo operacional",
  "Patrimonio efectivo", "Gobierno corporativo", "Prevención de lavado".

FRAGMENTOS:
{fragmentos}

LABEL:"""


_REGEX_LATIN = None


def _es_label_valido(label: str) -> bool:
    """True si el label solo contiene caracteres latinos + signos comunes."""
    import re
    global _REGEX_LATIN
    if _REGEX_LATIN is None:
        _REGEX_LATIN = re.compile(r"^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ0-9\s\-,./()&:;'\"]+$")
    label = (label or "").strip()
    if not label or len(label) < 3 or len(label) > 80:
        return False
    return bool(_REGEX_LATIN.match(label))


def _kmeans_chunks(embeddings: np.ndarray, n_clusters: int) -> tuple[np.ndarray, np.ndarray]:
    """Ejecuta K-means y retorna (labels_por_chunk, centroides)."""
    km = KMeans(
        n_clusters=n_clusters,
        random_state=42,
        n_init=10,
        max_iter=300,
    )
    etiquetas = km.fit_predict(embeddings)
    return etiquetas, km.cluster_centers_


def _miembros_mas_cercanos(
    embeddings: np.ndarray, etiquetas: np.ndarray, centroides: np.ndarray, top_n: int = 5
) -> dict[int, list[int]]:
    """Para cada cluster: retorna los índices de chunks más cercanos al centroide."""
    cercanos: dict[int, list[int]] = {}
    for k, centroide in enumerate(centroides):
        miembros_idx = np.where(etiquetas == k)[0]
        if len(miembros_idx) == 0:
            cercanos[k] = []
            continue
        # distancias entre centroide y cada miembro
        dists = np.linalg.norm(embeddings[miembros_idx] - centroide, axis=1)
        orden = np.argsort(dists)[:top_n]
        cercanos[k] = [int(miembros_idx[i]) for i in orden]
    return cercanos


async def _nombrar_con_llm(llm: LLMProvider, snippets: list[str]) -> str:
    """Llama al LLM para producir un label corto. Reintenta si sale corrupto."""
    if not snippets:
        return "Vacío"
    bloque = "\n---\n".join(s[:400] for s in snippets[:5])
    prompt = PROMPT_NOMBRAR_TOPICO.format(fragmentos=bloque)
    for intento in range(3):
        try:
            resultado = await llm.generate(
                prompt, system=None, temperature=0.1 + intento * 0.2, max_tokens=40
            )
            texto = getattr(resultado, "text", resultado) or ""
            label = str(texto).strip().split("\n")[0].strip(' "\'.,;:')
            if _es_label_valido(label):
                return label
            logger.warning(
                "Label inválido (intento %d): %r — reintentando", intento + 1, label[:50]
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM falló al nombrar tópico (intento %d): %s", intento + 1, exc)
    return "Misceláneo"


async def _nombrar_con_llm_LEGACY(llm: LLMProvider, snippets: list[str]) -> str:
    """Versión legacy preservada por compatibilidad — no usar."""
    if not snippets:
        return "Vacío"
    bloque = "\n---\n".join(s[:400] for s in snippets[:5])
    prompt = PROMPT_NOMBRAR_TOPICO.format(fragmentos=bloque)
    try:
        resultado = await llm.generate(
            prompt, system=None, temperature=0.1, max_tokens=40
        )
        label = resultado.text.strip().strip('"').strip("'").strip(".")
        # cap a 80 chars y primera línea
        label = label.split("\n")[0][:80]
        return label or "Sin nombre"
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM no pudo nombrar tópico: %s", exc)
        return "Sin nombre"


async def descubrir_topicos(
    pool: AsyncConnectionPool,
    llm: LLMProvider,
    *,
    n_topicos: int = 8,
) -> dict:
    """Pipeline completo: K-means → naming → persistencia.

    Antes de poblar, elimina nodos `kind='topic'` previos para no acumular.
    """
    # 1. Cargar todos los chunks con sus embeddings
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                SELECT c.id, c.content, c.document_id, c.embedding
                FROM chunks c
                ORDER BY c.id
                """
            )
            filas = list(await cursor.fetchall())

    if len(filas) < n_topicos * 2:
        return {
            "error": f"insuficientes chunks ({len(filas)}) para {n_topicos} clusters",
        }

    chunk_ids = [f["id"] for f in filas]
    contenidos = [f["content"] for f in filas]
    document_ids = [f["document_id"] for f in filas]
    # pgvector + register_vector_async retorna numpy.ndarray
    embeddings = np.vstack([np.asarray(f["embedding"], dtype=np.float32) for f in filas])

    # 2. K-means
    logger.info("K-means sobre %d chunks → %d clusters", len(filas), n_topicos)
    etiquetas, centroides = _kmeans_chunks(embeddings, n_topicos)

    # 3. Miembros representativos
    representativos = _miembros_mas_cercanos(embeddings, etiquetas, centroides, top_n=5)

    # 4. Nombrar cada cluster con LLM
    topicos: list[TopicoDescubierto] = []
    for k in range(n_topicos):
        snippets = [contenidos[i] for i in representativos[k]]
        label = await _nombrar_con_llm(llm, snippets)
        miembros_uuids = [chunk_ids[i] for i in np.where(etiquetas == k)[0]]
        topicos.append(
            TopicoDescubierto(
                indice=k,
                label=label,
                miembros=miembros_uuids,
                snippets_representativos=[s[:200] for s in snippets[:3]],
            )
        )
        logger.info("  Tópico %d: %r (%d miembros)", k, label, len(miembros_uuids))

    # 5. Persistir
    async with pool.connection() as conn:
        async with conn.cursor() as cursor:
            # Limpia tópicos anteriores (cascade borra sus aristas)
            await cursor.execute("DELETE FROM graph_nodes WHERE kind = 'topic'")

        repo = GraphRepository(conn)

        # Mapa chunk_id → document_uuid (para deduplicar aristas doc → topic)
        chunk_a_doc: dict[UUID, UUID] = {
            cid: did for cid, did in zip(chunk_ids, document_ids)
        }

        # Para cada tópico, crear el nodo + aristas a los documentos miembros
        topicos_resumen = []
        for top in topicos:
            etiqueta_completa = f"Topic-{top.indice:02d}: {top.label}"
            nodo_topico = await repo.upsert_node(
                kind="topic",
                label=etiqueta_completa,
                metadata={
                    "indice": top.indice,
                    "label_llm": top.label,
                    "tamano": len(top.miembros),
                    "snippets": top.snippets_representativos,
                },
            )

            # Documentos únicos que aportan chunks a este tópico (peso = #chunks)
            conteo_por_doc: dict[UUID, int] = {}
            for chunk_id in top.miembros:
                doc_uuid = chunk_a_doc.get(chunk_id)
                if doc_uuid:
                    conteo_por_doc[doc_uuid] = conteo_por_doc.get(doc_uuid, 0) + 1

            for doc_uuid, conteo in conteo_por_doc.items():
                # Buscar el nodo `kind='document'` correspondiente
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "SELECT id FROM graph_nodes WHERE kind='document' AND document_id=%s",
                        (doc_uuid,),
                    )
                    fila = await cursor.fetchone()
                if not fila:
                    continue
                nodo_doc = fila[0]
                # peso normalizado: conteo / total_miembros del tópico (0..1)
                score = conteo / max(len(top.miembros), 1)
                await repo.insert_edge(
                    src_node=nodo_doc,
                    dst_node=nodo_topico,
                    relation="same_topic",
                    score=round(float(score), 3),
                    metadata={"chunks_en_topico": conteo},
                )

            topicos_resumen.append({
                "indice": top.indice,
                "label": top.label,
                "miembros": len(top.miembros),
                "documentos_unicos": len(conteo_por_doc),
            })

    return {
        "n_topicos": n_topicos,
        "chunks_clusterizados": len(filas),
        "topicos": topicos_resumen,
    }
