---
title: RAG SBS — Mesa Experta Regulatoria
description: Sistema RAG agéntico sobre normativa financiera peruana
---

<h1 align="center">🏛️ RAG SBS</h1>
<h3 align="center">Mesa Experta Regulatoria Bancaria · Perú</h3>

<p align="center">
  <strong>1,100 documentos</strong> · <strong>40,161 chunks</strong> · <strong>12 instituciones</strong>
</p>

<p align="center">
  <a href="https://3.220.87.49.nip.io">🌐 <strong>Demo en vivo</strong></a> ·
  <a href="https://github.com/eurrutia/rag-sbs">📦 GitHub</a> ·
  <a href="architecture.md">🏗️ Arquitectura</a> ·
  <a href="changelog.md">📝 Changelog</a>
</p>

---

## 🎯 ¿Qué es?

Una **mesa experta regulatoria** que responde consultas técnicas de banca peruana **citando la fuente oficial PDF** y realizando **cálculos numéricos deterministas** (sin alucinación).

```mermaid
flowchart LR
    U[👤<br/>Compliance<br/>Riesgos<br/>Contabilidad] -->|pregunta| MESA[🏛️ Mesa Experta]
    MESA -->|busca en| C[📚 Corpus<br/>1,100 docs<br/>9 emisores]
    MESA -->|calcula con| F[🧮 Funciones<br/>deterministas]
    MESA -->|cita| R[📄 PDFs<br/>oficiales]
    MESA -->|responde| U

    style MESA fill:#003d7a,color:#fff
```

---

## 🌍 Cobertura institucional

```mermaid
mindmap
  root((RAG SBS))
    🏦 SBS
      Resoluciones
      Circulares
      Manual Contabilidad I-IV
      Memorias 2017-2024
    💰 BCRP
      Circulares
      Notas informativas
      Reportes estabilidad
    ⚖️ Congreso
      Leyes
      Decretos Legislativos
      Decretos Urgencia
    🏛️ MEF
      DS tributarios
      NIIF / NIC
      Estrategia deuda
    📈 SMV
      Resoluciones
      TUO Mercado Valores
      Reglamento clasificadoras
    💵 SUNAT
      Informes tributarios
      ITF / IGV financiero
      Bancarización
    🛡️ INDECOPI
      Lineamientos consumidor
      Resoluciones SPC
    🌐 Internacional
      BIS Basilea III
      BID adopción LATAM
      GAFI 40 Recomendaciones
    🇵🇪 Banca Pública
      Banco de la Nación
      COFIDE
      AgroBanco
```

---

## ⚡ Ejemplo 1 — Cálculo regulatorio

> **Usuario**: *"Hipotecario S/ 200,000, atraso 100 días, garantía S/ 180,000. ¿Qué hago?"*

```mermaid
flowchart LR
    Q[Pregunta] --> CL[🧮 clasificar_deudor 100d]
    CL --> RES1[Deficiente<br/>rango 61-120 días]
    Q --> PR[🧮 calcular_provision]
    RES1 --> PR
    PR --> RES2[S/ 38,750<br/>5% sobre exposición]
    RES2 --> ANS[📝 Respuesta con:<br/>citas Res SBS 11356<br/>tabla regulatoria<br/>desglose paso a paso]

    style CL fill:#10b981,color:#fff
    style PR fill:#10b981,color:#fff
    style ANS fill:#4285f4,color:#fff
```

---

## 🆚 Ejemplo 2 — Anti-alucinación

> **Usuario**: *"¿Cuál es la tasa de provisión hipotecaria para CPP?"*

<table>
<tr>
<th>Sistema</th>
<th>Respuesta</th>
<th>Veredicto</th>
</tr>
<tr>
<td>Gemini directo</td>
<td>"0.63%"</td>
<td>❌ Inventado</td>
</tr>
<tr>
<td><strong>RAG SBS</strong></td>
<td>"2.50% con garantía preferida / 5.00% sin garantía"<br/><i>fuente: Res. SBS 11356-2008 Cap. III</i></td>
<td>✅ Verificable</td>
</tr>
</table>

---

## 🧠 Ejemplo 3 — Caso integral

Para casos complejos hay un **wizard** que arma la consulta estructurada:

```mermaid
flowchart TB
    R[👤 Rol:<br/>Compliance officer] --> W[🪄 Wizard]
    C[📋 Caso:<br/>Empresa de crédito<br/>+ titulización<br/>+ fideicomiso] --> W
    O[🎯 Objetivo:<br/>Informe regulatorio<br/>integral] --> W
    T[🏷️ Temas:<br/>Riesgo crédito,<br/>Gobierno,<br/>Manual Contab.] --> W

    W --> Q[Consulta estructurada<br/>+ toggles auto:<br/>Grafo + Informe + Agente]
    Q --> INF[📊 Informe 7 secciones:<br/>1. Resumen ejecutivo<br/>2. Marco regulatorio<br/>3. Riesgos<br/>4. Contable<br/>5. IT<br/>6. Gobierno<br/>7. Recomendaciones]

    style W fill:#fef3c7,color:#92400e
    style INF fill:#10b981,color:#fff
```

**Output real obtenido**: 7 fuentes citadas (scores 0.70–0.90), confianza ALTA, 15s latencia, incluye Res SBS 1308-2013, 3780-2011, 14354-2009, 1010-99, 3986-2024.

---

## ✨ Capacidades v0.5

### 🔎 Retrieval inteligente

```mermaid
flowchart LR
    Q[Query] --> P{Profiler}
    P -->|Lexical fuerte<br/>'Res 11356-2008 Art 5'| BM[BM25 prioridad<br/>w=1.4]
    P -->|Semántico<br/>'qué es titulización?'| VEC[Vector prioridad<br/>w=1.3]
    P -->|Balanced| MIX[Equal weights]

    BM --> H[Hybrid search<br/>RRF ponderado]
    VEC --> H
    MIX --> H
    H --> R[Re-ranker LLM<br/>top 25 → 10]

    style BM fill:#f97316,color:#fff
    style VEC fill:#4285f4,color:#fff
    style R fill:#10b981,color:#fff
```

### 🧠 Memoria sin sesgo

```mermaid
flowchart TB
    Q[💬 Nueva pregunta:<br/>'qué es el RCD?']
    H[Historial:<br/>10 turnos sobre<br/>titulización]

    Q --> F[🧠 Filtro semántico<br/>cosine vs cada turno]
    H --> F

    F --> R1[Turno 1 titulización<br/>score 0.32 ❌]
    F --> R2[Turno 3 contabilización<br/>score 0.41 ❌]
    F --> R3[Turno 9 último<br/>score 0.45 ✅ siempre]

    R1 --> CLEAN[Contexto limpio<br/>al LLM]
    R2 --> CLEAN
    R3 --> CLEAN

    CLEAN --> ANS[Respuesta de RCD<br/>sin sesgo de titulización]

    style F fill:#dbeafe,color:#1e40af,stroke:#3b82f6,stroke-width:3px
    style CLEAN fill:#10b981,color:#fff
```

### 🔍 Detector de acrónimos

Para acrónimos ambiguos comunes (RCD, PDD, RPC, SAR, GIR, etc.) el sistema pregunta antes de buscar:

> ⚠️ Detecté `RCD`. ¿A cuál te referís?
>
> - 📋 **Reporte Crediticio de Deudores** — Res SBS 11356-2008
> - 💱 **Riesgo Cambiario Crediticio** — Res SBS 774-2025
> - 🛡 **Reglamento de Conducta de Mercado** — Res SBS 3274-2017

---

## 🏗️ Stack técnico

<p align="center">
<img alt="python" src="https://img.shields.io/badge/Python_3.11-3776AB?style=flat-square&logo=python&logoColor=white">
<img alt="fastapi" src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white">
<img alt="streamlit" src="https://img.shields.io/badge/Streamlit-FF4B4B?style=flat-square&logo=streamlit&logoColor=white">
<img alt="postgres" src="https://img.shields.io/badge/PostgreSQL_16-336791?style=flat-square&logo=postgresql&logoColor=white">
<img alt="pgvector" src="https://img.shields.io/badge/pgvector-336791?style=flat-square">
<img alt="redis" src="https://img.shields.io/badge/Redis-DC382D?style=flat-square&logo=redis&logoColor=white">
<img alt="docker" src="https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white">
<img alt="gemini" src="https://img.shields.io/badge/Gemini_2.5_Flash-4285F4?style=flat-square&logo=google&logoColor=white">
<img alt="tesseract" src="https://img.shields.io/badge/Tesseract_OCR-5C5C5C?style=flat-square">
<img alt="caddy" src="https://img.shields.io/badge/Caddy_v2-1F88C0?style=flat-square&logo=caddy&logoColor=white">
</p>

Detalle completo en [Arquitectura](architecture.md).

---

## 📚 Documentos del proyecto

- 🏗️ [**Arquitectura técnica**](architecture.md) — Diagramas, ADRs, pipeline detallado
- 📝 [**Changelog**](changelog.md) — Historial v0.1 → v0.5
- 🗺️ [**Roadmap**](roadmap.md) — Fase 0 → Fase 10
- 📋 [**Casos de uso**](casos-de-uso.md) — Demos end-to-end
- 🏛️ [**Mapeo regulatorio**](regulatorio.md) — Corpus por área

---

## 👤 Sobre el autor

**Erik Urrutia** — Ingeniero, consultor regulatorio.

Este sistema es **portafolio personal** que demuestra:
- 🎯 RAG production-grade con cero alucinación numérica
- 🧠 Memoria conversacional sin sesgo (filtro semántico)
- 🕸️ Knowledge graph navegable con ~12K aristas
- 🛡️ Self-healing y observabilidad operacional
- 💰 Costos controlados (~$20/mes total)

📧 [eurrutia489@gmail.com](mailto:eurrutia489@gmail.com)
