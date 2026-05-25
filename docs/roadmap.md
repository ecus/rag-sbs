---
title: Roadmap
---

# Roadmap del producto

## Fase 0 — Demo técnica (✓ completado)

- ✅ Pipeline RAG end-to-end con pgvector
- ✅ Function calling determinista para clasificación y provisiones
- ✅ Knowledge Graph L1 (citaciones) y L2 (tópicos)
- ✅ Topic router con anti-mezcla de regulaciones
- ✅ Validación contra fuente oficial (texto literal PDF)
- ✅ UI Streamlit con cards didácticas + tablas regulatorias visibles
- ✅ Switch a Gemini 2.5 Flash + Object Store cloud-agnóstico
- ✅ Documentación + GitHub Pages

## Fase 1 — Deploy público (en curso)

- ⏳ AWS Lightsail con Caddy + HTTPS
- ⏳ Backups automáticos pg_dump → S3
- ⏳ Re-ingesta del corpus completo con scheduler
- ⏳ Smoke tests automatizados (las 5 queries demostrables)

## Fase 2 — Migración a GCP (junio 2026)

- ⏳ Cloud Run para API + UI (scale-to-zero)
- ⏳ Cloud SQL Postgres con pgvector (db-f1-micro)
- ⏳ Cloud Storage para PDFs + backups
- ⏳ Cloud Build CI/CD desde GitHub
- ⏳ Domain mapping + SSL gestionado

## Fase 3 — Producto vendible (Q3 2026)

### Multi-tenant
- Google OAuth login
- Espacios por cliente con corpus custom
- Roles: admin, analista, viewer

### Agentes especializados
- Provisiones (✓ ya tenemos)
- Scoring crediticio (nuevo)
- Patrimonio efectivo / Basilea
- Contable / NIIF
- Cumplimiento PLAFT
- Riesgo operacional / TI / Ciberseguridad

### MCP / integraciones
- Notion (notas y planes de acción)
- Slack (notificaciones de cambios normativos)
- Excel/Google Sheets (modelos de scoring)
- JIRA (tickets de implementación)
- SBS portal scraper (corpus actualizado automático)

### Modo "Plan de acción"
- Output estructurado en fases con regulación aplicable, hitos, métricas
- Casos: "Implementar scoring microcréditos", "Auditoría PLAFT", "Migración Basilea IV"

## Fase 4 — Escalado (Q4 2026)

- Expansión de corpus: SMV, SUNAT, INDECOPI, NIIF, Basilea III/IV
- Evaluación con RAGAS (faithfulness, context precision, answer relevancy)
- Cache semántico con Redis para queries frecuentes
- Export PDF de informes con branding del cliente
- Dashboard de métricas de uso por cliente

## Pricing model (tentativo)

| Plan | Precio/mes | Incluye |
|---|---|---|
| Free | $0 | Hasta 50 queries/mes, sin corpus custom |
| Starter | $49 | 500 queries/mes, 1 usuario, 1 dominio |
| Pro | $199 | 5,000 queries/mes, 5 usuarios, corpus custom, integraciones básicas |
| Enterprise | custom | Multi-usuario, SLA, MCPs, soporte priority |
