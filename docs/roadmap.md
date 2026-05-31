---
title: Roadmap
---

# Roadmap

## ✅ Fase 0 — Demo técnica (completada · enero-marzo 2026)

- [x] Pipeline RAG end-to-end con pgvector
- [x] Function calling determinista (clasificación, provisiones)
- [x] Knowledge Graph L1 (citaciones) y L2 (tópicos)
- [x] Topic router con anti-mezcla de regulaciones
- [x] Validación contra fuente oficial (texto literal PDF)
- [x] UI Streamlit con cards didácticas + tablas regulatorias visibles

## ✅ Fase 1 — Deploy público (completada · abril 2026)

- [x] AWS Lightsail VM Ubuntu 22.04, 2GB RAM, USD 12/mes
- [x] Caddy reverse proxy con Let's Encrypt automático
- [x] Dominio nip.io
- [x] Backups automáticos pg_dump → S3 con cron
- [x] Switch a Gemini 2.5 Flash + Object Store cloud-agnóstico

## ✅ Fase 2 — Corpus regulatorio multiinstitucional (completada · mayo 2026)

- [x] **SBS**: 110+ resoluciones, circulares, manuales
- [x] **BCRP**: 290+ circulares + notas informativas
- [x] **Congreso**: 72+ leyes y decretos legislativos
- [x] **MEF**: 54+ decretos supremos
- [x] **SMV**: 25+ resoluciones de superintendente
- [x] **SUNAT**: 29 informes y resoluciones
- [x] **INDECOPI**: 12 lineamientos y resoluciones
- [x] **BIS**: 3 documentos Basilea III (LCR, marco regulador, reformas)
- [x] **BID**: adopción Basilea III LATAM

## ✅ Fase 3 — Manual de Contabilidad SBS completo (completada · mayo 2026)

- [x] Capítulo I: Disposiciones Generales (4 versiones, vigencias 2020-2027)
- [x] Capítulo II: Estados Financieros (2 versiones)
- [x] Capítulo III: Catálogo de Cuentas / Plan de Cuentas (4 versiones)
- [x] Capítulo IV: Descripción y Dinámica de Cuentas (4 versiones)
- [x] Resolución 895-98 fundacional (manual histórico completo, 4.8MB)
- [x] Modificatorias clave: 682-2019, 349-2021, 7197-2012, 3932-2022

## ✅ Fase 4 — Retrieval avanzado (completada · mayo 2026)

- [x] **Hybrid search adaptativo**: pesos vector vs BM25 según perfil de query
  - Lexical fuerte (2+ entidades): w_vector=0.6, w_texto=1.4
  - Lexical simple: 0.8 / 1.2
  - Semantic (¿qué/cómo?): 1.3 / 0.7
  - Balanced: 1.0 / 1.0
- [x] **LLM Re-ranker** con prompt de 5 niveles de discriminación (0-10)
  - 18 candidatos pre-rerank → top 7 final
- [x] **OCR fallback** con Tesseract español
  - Activado cuando chars promedio/página < 50
  - Cap defensivo: 30 páginas máximo, DPI 200
- [x] **Topic router determinista** con re-fetch dirigido
- [x] **Graph-augmented retrieval** multi-hop (1 o 2 saltos)

## ✅ Fase 5 — Analytics + memoria persistente (completada · mayo 2026)

- [x] **Alias obligatorio** al entrar a la app
- [x] Tabla `user_sessions` + `query_log` con metadata completa
- [x] **Memoria persistente**: recupera últimas 6 conversaciones al login
- [x] **Dashboard analytics** en modo técnico con drill-down por usuario
- [x] **Self-healing**: cron `*/15` limpia runs zombies, cleanup al startup
- [x] **Wizard "Asistente de consulta"**: rol + caso + objetivo → consulta estructurada
- [x] **Modo usuario vs modo técnico** (UX separada)
- [x] **Chat conversacional** (burbujas usuario/asistente alineadas)
- [x] **Español peruano neutro** en LLM (sin voseo argentino)

## ⏳ Fase 6 — Migración GCP Cloud Run (Q3 2026)

- [ ] Cloud Run service: API (scale-to-zero, autoscale)
- [ ] Cloud Run service: UI Streamlit
- [ ] Cloud SQL Postgres con pgvector extension (db-f1-micro)
- [ ] Memorystore Redis (sem cache)
- [ ] Cloud Scheduler para crons (reemplazo de APScheduler in-process)
- [ ] Cloud Storage para PDFs + backups
- [ ] Cloud Build CI/CD desde GitHub
- [ ] Domain mapping + SSL gestionado
- [ ] Migración de datos vía pg_dump + pg_restore

## ⏳ Fase 7 — Multi-tenant + Auth (Q4 2026)

- [ ] Google OAuth login (Workspace) y Azure AD
- [ ] Tenants con datos aislados (row-level security en pg)
- [ ] Roles: admin, analista, viewer
- [ ] Cuotas por tenant (queries/día, GB de corpus)
- [ ] Espacios por cliente con corpus custom
- [ ] Billing por uso (Stripe)

## ⏳ Fase 8 — Agentes especializados (Q1 2027)

Orchestrator que rutea según consulta a sub-agentes especializados:

- [ ] **Compliance**: PLAFT, GAFI, sanciones internacionales
- [ ] **Riesgos**: cálculos VaR, stress testing, capital regulatorio
- [ ] **Contable**: asientos, cuentas afectadas, modelo NIIF
- [ ] **Crédito**: scoring, provisiones, garantías
- [ ] **TI**: ciberseguridad, continuidad de negocio, riesgo operacional
- [ ] **Mercado de valores**: emisiones, OPA, hechos importancia

## ⏳ Fase 9 — Integraciones externas (Q2 2027)

- [ ] **MCP server** para Claude Desktop / Cursor IDE
- [ ] **Slack** webhook para alertas regulatorias
- [ ] **Notion** sync de notas y planes de acción
- [ ] **Power BI / Tableau** plugin para reportes
- [ ] **Excel / Google Sheets** para modelos de scoring
- [ ] **JIRA** tickets de implementación normativa
- [ ] **API pública** con rate limiting + API keys
- [ ] **SDK Python** para clientes corporativos

## ⏳ Fase 10 — Modo "Plan de acción" (Q3 2027)

Output estructurado en fases con regulación aplicable, hitos, métricas. Casos:

- "Implementar scoring de microcréditos"
- "Auditoría PLAFT anual"
- "Migración a Basilea IV (RFNE / NSFR)"
- "Adecuación al Reglamento de Gestión de Riesgos de Modelo"

---

## Métricas objetivo

| Métrica | Hoy (v0.4) | Meta v1.0 (Q4 2026) |
|---|---|---|
| Documentos en corpus | ~900 | 2,000+ |
| Chunks vectorizados | ~29,000 | 60,000+ |
| Confianza promedio | "ALTA" en ~60% | "ALTA" en ~85% |
| Latencia query P95 | 4-15s | <5s |
| Costo por query | ~USD 0.01 | <USD 0.005 |
| Uptime | 99.5% | 99.9% |
| Instituciones | 9 | 12+ (sumando CMF Chile, CNBV México, FOGADE Venezuela) |
| Usuarios concurrentes | 1 (single-tenant) | 50+ (multi-tenant) |

---

## Pricing model tentativo (post Fase 7)

| Plan | Precio/mes | Incluye |
|---|---|---|
| **Free** | $0 | 50 queries/mes, corpus público, 1 alias |
| **Starter** | $49 | 500 queries/mes, 1 usuario, 1 dominio custom |
| **Pro** | $199 | 5,000 queries/mes, 5 usuarios, corpus custom, integraciones básicas, dashboard analytics |
| **Enterprise** | custom | Multi-usuario ilimitado, SLA 99.9%, MCPs custom, soporte priority, SSO |

---

## Costos operativos actuales

| Concepto | Costo |
|---|---|
| AWS Lightsail VM 2GB | USD 12/mes |
| Gemini 2.5 Flash (corpus actual + queries demo) | ~USD 2.50 total acumulado en mayo |
| Dominio nip.io | $0 |
| **Total mensual estimado a régimen** | **USD 18-25/mes** |

Cap de seguridad configurado: **USD 9.50 total** (worker se autoapaga).
