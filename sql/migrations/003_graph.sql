-- =============================================================================
-- Migration 003 — Knowledge Graph L1 (citas explícitas)
-- =============================================================================
-- L1: nodos = (document | resolution | ley | circular | articulo | anexo)
-- L2 vendrá en Sprint 2.5 (BERTopic). L3 (similitud) y L4 (operacional) en Fases 2 y 3.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- graph_nodes — entidades del grafo
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS graph_nodes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind            TEXT NOT NULL,                          -- document|resolution|ley|circular|articulo|anexo|topic
    label           TEXT NOT NULL,                          -- "Res. SBS 11356-2008", "Artículo 6", etc.
    document_id     UUID REFERENCES documents(id) ON DELETE CASCADE,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (kind, label)
);

CREATE INDEX idx_graph_nodes_kind     ON graph_nodes(kind);
CREATE INDEX idx_graph_nodes_doc      ON graph_nodes(document_id) WHERE document_id IS NOT NULL;
CREATE INDEX idx_graph_nodes_label    ON graph_nodes(label);

-- -----------------------------------------------------------------------------
-- graph_edges — relaciones entre nodos
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS graph_edges (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    src_node            UUID NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE,
    dst_node            UUID NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE,
    relation            TEXT NOT NULL,                      -- cites|mentions|modifies|derogates|same_topic
    score               FLOAT NOT NULL DEFAULT 1.0,         -- confianza
    evidence_chunk_id   UUID REFERENCES chunks(id) ON DELETE SET NULL,
    metadata            JSONB DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (src_node, dst_node, relation, evidence_chunk_id)
);

CREATE INDEX idx_graph_edges_src      ON graph_edges(src_node);
CREATE INDEX idx_graph_edges_dst      ON graph_edges(dst_node);
CREATE INDEX idx_graph_edges_relation ON graph_edges(relation);
