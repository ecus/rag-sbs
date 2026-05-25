# =============================================================================
# RAG SBS — Makefile
# =============================================================================
# Comandos del día a día. Ver README.md para descripción completa.

# Detect podman vs docker
COMPOSE := $(shell command -v podman-compose 2>/dev/null || command -v docker-compose 2>/dev/null || echo "podman compose")

.PHONY: help
help:  ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# -----------------------------------------------------------------------------
# Local (Podman)
# -----------------------------------------------------------------------------

.PHONY: local-up
local-up:  ## Levanta el stack local (api + postgres + redis)
	$(COMPOSE) -f podman-compose.yml up -d --build
	@echo "✅ Stack arriba. API en http://localhost:8000  Postgres en :5432  Redis en :6379"
	@echo "👉 Verifica: make health"

.PHONY: local-down
local-down:  ## Baja el stack
	$(COMPOSE) -f podman-compose.yml down

.PHONY: local-logs
local-logs:  ## Sigue logs de todos los servicios
	$(COMPOSE) -f podman-compose.yml logs -f

.PHONY: local-restart
local-restart:  ## Reinicia el stack
	$(COMPOSE) -f podman-compose.yml restart

.PHONY: local-rebuild
local-rebuild:  ## Reconstruye imágenes desde cero
	$(COMPOSE) -f podman-compose.yml build --no-cache

# -----------------------------------------------------------------------------
# Operativos
# -----------------------------------------------------------------------------

.PHONY: health
health:  ## Curl al endpoint /v1/health
	@curl -s http://localhost:8000/v1/health | python -m json.tool || \
		echo "❌ API no responde. ¿Está arriba? → make local-up"

.PHONY: local-ingest
local-ingest:  ## Ingesta los PDFs de data/sample/
	@echo "📥 Ingesta de data/sample/..."
	@for f in data/sample/*.pdf; do \
		[ -f "$$f" ] || { echo "⚠️  No hay PDFs en data/sample/"; exit 0; }; \
		echo "  → $$f"; \
		curl -s -X POST -F "file=@$$f" http://localhost:8000/v1/ingest | python -m json.tool; \
	done

.PHONY: query
query:  ## Consulta vanilla (sin grafo). Uso: make query Q="¿qué dice X?"
	@curl -s -X POST http://localhost:8000/v1/query \
		-H "Content-Type: application/json" \
		-d "{\"query\":\"$(Q)\",\"options\":{\"expansion_enabled\":false}}" | python -m json.tool

.PHONY: query-graph
query-graph:  ## Consulta con graph-augmented retrieval. Uso: make query-graph Q="..."
	@curl -s -X POST http://localhost:8000/v1/query \
		-H "Content-Type: application/json" \
		-d "{\"query\":\"$(Q)\",\"options\":{\"expansion_enabled\":true,\"max_hops\":1,\"rerank_enabled\":true}}" | python -m json.tool

.PHONY: query-no-rerank
query-no-rerank:  ## Consulta SIN rerank (para A/B con/sin cross-encoder)
	@curl -s -X POST http://localhost:8000/v1/query \
		-H "Content-Type: application/json" \
		-d "{\"query\":\"$(Q)\",\"options\":{\"expansion_enabled\":true,\"max_hops\":2,\"rerank_enabled\":false}}" | python -m json.tool

.PHONY: ui
ui:  ## Abre la UI Streamlit en el navegador
	@open http://localhost:8501 || xdg-open http://localhost:8501 || echo "Abrir manualmente: http://localhost:8501"

.PHONY: query-ab
query-ab:  ## A/B: corre la misma query vanilla y graph-aug, muestra fuentes lado a lado
	@echo "═══ VANILLA ═══" && curl -s -X POST http://localhost:8000/v1/query \
		-H "Content-Type: application/json" \
		-d "{\"query\":\"$(Q)\",\"options\":{\"expansion_enabled\":false}}" | \
		python -c "import sys,json; r=json.load(sys.stdin); print(f'  conf={r[\"confidence\"]}'); [print(f'  [{s[\"via\"]:<16}] {s[\"score\"]:.3f}  {s[\"title\"][:60]}') for s in r['sources']]"
	@echo ""
	@echo "═══ GRAPH-AUG ═══" && curl -s -X POST http://localhost:8000/v1/query \
		-H "Content-Type: application/json" \
		-d "{\"query\":\"$(Q)\",\"options\":{\"expansion_enabled\":true,\"max_hops\":1}}" | \
		python -c "import sys,json; r=json.load(sys.stdin); print(f'  conf={r[\"confidence\"]}  expansion={r[\"graph_expansion\"]}'); [print(f'  [{s[\"via\"]:<16}] {s[\"score\"]:.3f}  {s[\"title\"][:60]}') for s in r['sources']]"

.PHONY: seed-sources
seed-sources:  ## Pobla las fuentes iniciales SBS en doc_sources
	$(COMPOSE) -f podman-compose.yml exec api python -m src.scripts.seed_sources

.PHONY: scan
scan:  ## Dispara scan manual (descarga + diff + reindex de cambios)
	@curl -s -X POST http://localhost:8000/v1/ingest/scan \
		-H "Content-Type: application/json" \
		-d '{"force": false}' | python -m json.tool

.PHONY: scan-force
scan-force:  ## Scan forzado (ignora ETag/hash cache)
	@curl -s -X POST http://localhost:8000/v1/ingest/scan \
		-H "Content-Type: application/json" \
		-d '{"force": true}' | python -m json.tool

.PHONY: scan-dry
scan-dry:  ## Scan dry-run (detecta cambios sin reindexar)
	@curl -s -X POST http://localhost:8000/v1/ingest/scan \
		-H "Content-Type: application/json" \
		-d '{"dry_run": true, "force": true}' | python -m json.tool

.PHONY: runs
runs:  ## Lista ejecuciones del scheduler
	@curl -s http://localhost:8000/v1/ingest/runs?limit=10 | python -m json.tool

.PHONY: sources
sources:  ## Lista fuentes registradas
	@curl -s http://localhost:8000/v1/ingest/sources | python -m json.tool

.PHONY: events
events:  ## Lista eventos de cambio pendientes de notificar
	@curl -s http://localhost:8000/v1/ingest/events | python -m json.tool

.PHONY: rebuild-graph
rebuild-graph:  ## Reconstruye el knowledge graph L1 desde los chunks indexados
	@curl -s -X POST http://localhost:8000/v1/graph/rebuild | python -m json.tool

.PHONY: graph-stats
graph-stats:  ## Estadísticas del knowledge graph
	@curl -s http://localhost:8000/v1/graph | python -m json.tool

.PHONY: graph-topics
graph-topics:  ## Top entidades más citadas (proxy de tópicos en L1)
	@curl -s 'http://localhost:8000/v1/graph/topics?limit=20' | python -m json.tool

.PHONY: build-topics
build-topics:  ## L2: K-means + LLM nombra clusters (~1 min vs Ollama)
	@curl -s -X POST 'http://localhost:8000/v1/graph/topics/build?n_topicos=8' | python -m json.tool

.PHONY: classify-citations
classify-citations:  ## Promueve cites → modifies/derogates (regex, instantáneo)
	@curl -s -X POST 'http://localhost:8000/v1/graph/citations/classify' | python -m json.tool

.PHONY: export-obsidian
export-obsidian:  ## Genera vault Obsidian en ./vault/ — ábrelo con Obsidian
	@curl -s -X POST 'http://localhost:8000/v1/export/obsidian?output_dir=/app/vault' | python -m json.tool
	@echo "👉 Abre $(PWD)/vault/ con Obsidian para ver el grafo nativo"

.PHONY: psql
psql:  ## Abre psql sobre la BD local
	$(COMPOSE) -f podman-compose.yml exec postgres psql -U rag -d ragdb

# -----------------------------------------------------------------------------
# Calidad de código
# -----------------------------------------------------------------------------

.PHONY: test
test:  ## Corre tests
	pytest

.PHONY: test-fast
test-fast:  ## Corre tests sin coverage (más rápido)
	pytest --no-cov -x

.PHONY: lint
lint:  ## ruff check + mypy
	ruff check src tests
	ruff format --check src tests
	mypy src

.PHONY: lint-fix
lint-fix:  ## ruff fix + format
	ruff check --fix src tests
	ruff format src tests

# -----------------------------------------------------------------------------
# Setup local (sin Podman)
# -----------------------------------------------------------------------------

.PHONY: setup
setup:  ## Crea venv y instala deps (para correr fuera de container)
	python3.11 -m venv .venv
	./.venv/bin/pip install --upgrade pip
	./.venv/bin/pip install -e ".[dev]"
	@echo "✅ Activa con: source .venv/bin/activate"

.PHONY: ollama-pull
ollama-pull:  ## Descarga modelos LLM locales (~6GB)
	ollama pull llama3.1:8b
	ollama pull nomic-embed-text
	@echo "✅ Modelos Ollama descargados"

# -----------------------------------------------------------------------------
# Limpieza
# -----------------------------------------------------------------------------

.PHONY: clean
clean:  ## ⚠️  Detiene stack y BORRA volúmenes (datos perdidos)
	$(COMPOSE) -f podman-compose.yml down -v
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage

# -----------------------------------------------------------------------------
# Bloque C Sprint 3+ (cloud)
# -----------------------------------------------------------------------------

.PHONY: cloud-up
cloud-up:  ## (Sprint 3) Despliega a GCP
	@echo "Pendiente — Bloque C Sprint 3"

.PHONY: cloud-down
cloud-down:  ## (Sprint 3) Apaga deployment cloud
	@echo "Pendiente — Bloque C Sprint 3"

.PHONY: export-obsidian
export-obsidian:  ## (Sprint 2) Exporta vault Obsidian
	@echo "Pendiente — Bloque C Sprint 2"
