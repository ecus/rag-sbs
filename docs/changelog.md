---
title: Changelog
---

# Changelog

## v0.4 — mayo 2026 (current)

### Phase 5 — Analytics + memoria persistente
- ✨ **Alias de usuario obligatorio**: pantalla de identificación al entrar
- ✨ **Memoria persistente**: recupera últimas 6 conversaciones al login del mismo alias
- ✨ Tabla `query_log` + `user_sessions` (SQL migration 005)
- ✨ Endpoints `/v1/analytics/{session,users,user/{alias}/queries,user/{alias}/memory}`
- ✨ Dashboard de analytics en modo técnico con drill-down por usuario
- ✨ Self-healing scheduler: cron `*/15` limpia runs zombies > 30 min
- ✨ Wizard "Asistente para formular consulta" (rol + caso + objetivo)
- ✨ Modo usuario vs modo técnico (toggle en sidebar)
- ✨ Chat conversacional: burbujas usuario (derecha azul) / asistente (izquierda gris)
- ✨ Tabs renombrados (Consultar / Tópicos / Mapa regulatorio)
- ✨ Grafo más espaciado (default 250 vs 130, repulsión 9000 vs 3500)
- 🐛 Fix: contradicción "Confianza ALTA" + texto "no tengo evidencia"
- 🐛 Fix: cleanup automático de 321 runs zombies acumulados
- 🐛 Fix: español peruano neutro en LLM (sin voseo argentino)
- 🐛 Fix: contador de documentos del sidebar lee live de `documents` (no del grafo cacheado)

### Phase 4 — Retrieval avanzado
- ✨ **Hybrid search adaptativo**: `query_profile.py` detecta lexical/semantic/balanced
- ✨ **LLM Re-ranker mejorado**: prompt de 5 niveles + 18 candidatos pre-rerank
- ✨ **OCR fallback Tesseract español** para PDFs escaneados
- ✨ Cadena de parser de 3 niveles: PyMuPDF → pypdf → OCR
- ✨ Telemetría reranker: # chunks que cambiaron de orden

### Phase 3 — Manual de Contabilidad SBS completo
- ✨ 16 PDFs del Manual (Cap I, II, III, IV + Res 895-98 + modificatorias)
- ✨ Nuevo dominio temático: `contabilidad`
- ✨ Priority 10 (máxima) en el catálogo curado

### Catálogo curado v5
- ✨ +28 fuentes nuevas (tras dedupe de 64 candidatas)
- ✨ Foco: riesgo mercado/liquidez SBS, Basilea III paquete, Sandbox modificado 2025, Sistema Nacional de Pagos BCRP, Ley 32123 modernización SPP, DL 1646 reforma LGSF, BCBS 239 + d572 clima

### Mejoras de prompt LLM
- ✨ 3 niveles de manejo de evidencia (A sin info / B clarificación / C respuesta)
- ✨ NIVEL B: en lugar de "sin evidencia", el LLM describe lo encontrado + formula 2-3 preguntas concretas de clarificación
- ✨ Idioma: español peruano formal explícito en system prompt

---

## v0.3 — abril 2026

### Phase 2 — Corpus multiinstitucional
- ✨ Catálogo v2-v4: 311 → 385 fuentes verificadas
- ✨ +SUNAT (29), +INDECOPI (12), +BIS (3), +BID (1)
- ✨ Web scrapers HTML para portales (SBS, MEF, SMV, Congreso)
- ✨ Worker background con caps de costo ($9.50/$1.50/día)

### Mejoras UI institucionales
- ✨ Badges institucionales en cards de fuentes (SBS azul, BCRP rojo, etc.)
- ✨ Coloreo de nodos del grafo por institución emisora
- ✨ Breakdown del corpus por institución en sidebar
- ✨ Endpoint `/v1/stats/by-issuer`

### Bug fixes
- 🐛 Fix BCRP `document_id` duplicate key: incrementa `version_id` automáticamente
- 🐛 Fix robots.txt bloquea SBS Portals/0/: ignorar para `.gob.pe` (fair use)
- 🐛 Fix `last_status` NULL en doc_sources tras processing path del worker
- 🐛 Fix scheduler no procesaba el catálogo si la cola estaba vacía

---

## v0.2 — marzo 2026

### Phase 1 — Deploy AWS Lightsail
- ✨ Ubuntu 22.04 LTS, 2GB RAM, USD 12/mes
- ✨ docker-compose.prod.yml stack: postgres + redis + api + ui + caddy
- ✨ Caddy + nip.io + Let's Encrypt automático
- ✨ Backups pg_dump → S3 con cron diario

### Migración Gemini
- ✨ LLMProvider abstracción: Ollama (local) ↔ Gemini (cloud)
- ✨ `google-genai>=1.0.0` SDK oficial
- ✨ Embeddings `gemini-embedding-001` (768d)
- ✨ Object Store abstracto (S3/GCS/local) en `src/storage/object_store.py`

---

## v0.1 — febrero 2026

### Phase 0 — Demo técnica
- ✨ FastAPI + Streamlit MVP
- ✨ pgvector hybrid search + RRF
- ✨ Knowledge graph L1 (citas) + L2 (K-means tópicos)
- ✨ Calculator agent (function calling) para clasificación + provisiones
- ✨ Topic router determinista anti-mezcla
- ✨ Parser PyMuPDF con fallback pypdf
- ✨ Chunker estructural (Capítulo > Sección > Artículo > Anexo)
- ✨ Validación contra fuente oficial SBS

---

## Política de versionado

Versionado semántico relajado:

- **MAJOR** (1.0 → 2.0): cambios de arquitectura (migración GCP, multi-tenant)
- **MINOR** (0.3 → 0.4): nuevas features funcionales (analytics, OCR, etc.)
- **PATCH** (0.4.1): bug fixes y mejoras pequeñas
