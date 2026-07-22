"""Inyección de CSS con identidad SBS Perú en la UI Streamlit."""

import streamlit as st


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --sbs-blue: #003d7a;
  --sbs-blue-light: #00529b;
  --sbs-red: #dc0014;
  --sbs-bg: #ffffff;
  --sbs-bg-elev: #f5f7fa;
  --sbs-fg: #0d1b2a;
  --sbs-fg-muted: #4a5568;
  --sbs-fg-dim: #8a96a8;
  --sbs-border: #e2e7ee;
  --sbs-border-strong: #c5cdd9;
}

/* Tipografía global */
html, body, [class*="css"] {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
  -webkit-font-smoothing: antialiased;
  font-feature-settings: "cv02", "cv03", "cv04", "cv11";
}
code, pre, .mono { font-family: 'JetBrains Mono', monospace !important; }

/* ── Quitar paddings de Streamlit para que header sea edge-to-edge ───────── */
.stApp > header { display: none; }
[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"] {
  display: none !important; height: 0 !important;
}
[data-testid="stAppViewContainer"] { padding-top: 0 !important; }
[data-testid="stMainBlockContainer"] {
  padding-top: 0 !important;
  padding-bottom: 2rem !important;
  max-width: 100% !important;
}
[data-testid="stMain"] { padding: 0 !important; }
section[data-testid="stMain"] > div,
section[data-testid="stMain"] .block-container,
section[data-testid="stMain"] [data-testid="stMainBlockContainer"] {
  padding-top: 0 !important; margin-top: 0 !important;
}
.sbs-header { margin-top: 0 !important; }
.block-container {
  padding-top: 0 !important;
  padding-left: 0 !important;
  padding-right: 0 !important;
  max-width: 100% !important;
}

/* ── Header SBS edge-to-edge ─────────────────────────────────────────────── */
.sbs-header {
  display: flex; align-items: center; gap: 16px;
  padding: 16px 32px;
  background: #0f2547;
  border-bottom: 3px solid var(--sbs-red);
  color: white;
  margin-bottom: 1.6rem;
}
.sbs-header .sbs-logo {
  width: 48px; height: 48px; border-radius: 6px;
  background: white; color: var(--sbs-blue);
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 15px; letter-spacing: 0.02em;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);
  flex-shrink: 0;
}
.sbs-header .sbs-titulos { display: flex; flex-direction: column; line-height: 1.2; }
.sbs-header h1 {
  margin: 0 !important; font-size: 20px !important;
  font-weight: 600 !important; color: white !important;
  letter-spacing: -0.01em;
}
.sbs-header .subtitulo {
  font-size: 11.5px;
  color: rgba(255,255,255,0.78); font-weight: 500;
  text-transform: uppercase; letter-spacing: 0.1em;
  margin-top: 3px;
}

/* Forzar padding interno solo donde hace falta (contenido) */
.contenido-app {
  padding: 0 40px;
}

/* ── Tabs estilo institucional ───────────────────────────────────────────── */
.stTabs { padding: 0 40px; }
.stTabs [data-baseweb="tab-list"] {
  gap: 0; border-bottom: 1px solid var(--sbs-border);
  background: transparent;
}
.stTabs [data-baseweb="tab"] {
  background: transparent !important;
  font-weight: 500 !important; font-size: 14px !important;
  padding: 12px 22px !important;
  color: var(--sbs-fg-muted);
  border: none;
  border-bottom: 2px solid transparent;
  border-radius: 0;
  transition: all 0.15s;
}
.stTabs [data-baseweb="tab"]:hover {
  color: var(--sbs-blue);
  background: var(--sbs-bg-elev) !important;
}
.stTabs [aria-selected="true"] {
  color: var(--sbs-blue) !important;
  border-bottom: 2px solid var(--sbs-blue) !important;
  background: transparent !important;
  font-weight: 600 !important;
}
/* contenido de tabs con padding */
[data-baseweb="tab-panel"] { padding: 24px 40px 0; }

/* ── Sidebar NAVY cohesivo ───────────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background: #0f2547 !important;
  border-right: none !important;
}
[data-testid="stSidebar"] > div:first-child { padding-top: 0 !important; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
  padding: 0 0.85rem 1rem;
  gap: 0.5rem !important;
}
/* Textos claros por defecto dentro del sidebar */
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
  color: #c7d3e6 !important;
}
/* Marca superior: badge + nombre, integra con el header */
.sidebar-brand {
  margin: 0 -0.85rem 0.6rem;
  height: 74px;
  border-bottom: 1px solid rgba(255,255,255,.09);
  display: flex; align-items: center; gap: 10px; padding-left: 1rem;
}
.sidebar-brand-badge {
  width: 36px; height: 36px; border-radius: 8px;
  background: #fff; color: #0f2547;
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 12px; letter-spacing: 1px;
}
.sidebar-brand-name { line-height: 1.15; }
.sidebar-brand-name b { color: #fff; font-size: 13.5px; font-weight: 600; }
.sidebar-brand-name span { color: #8aa0bf !important; font-size: 10px; }
/* Encabezados de sección (Cobertura, etc.) */
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
  font-size: 10px !important; text-transform: uppercase;
  letter-spacing: 0.1em; color: #7d93b3 !important;
  font-weight: 600 !important;
  margin: 1rem 0 0.4rem !important; padding: 0 !important;
  border: none !important;
}
/* Caja de usuario (dark) */
.sidebar-user {
  background: rgba(255,255,255,.05); border: 1px solid rgba(255,255,255,.08);
  border-radius: 8px; padding: 8px 11px; margin-bottom: 10px; font-size: 12px;
}
.sidebar-user b { color: #fff; }
.sidebar-user span { color: #8aa0bf !important; font-size: 10px; }
/* Botones del sidebar — usar button[kind] (mas especifico, le gana al default) */
[data-testid="stSidebar"] button[kind="secondary"] {
  background: rgba(255,255,255,.08) !important;
  border: 1px solid rgba(255,255,255,.16) !important;
  color: #eaf0f8 !important;
  font-size: 12.5px !important;
  text-align: left !important;
  justify-content: flex-start !important;
}
[data-testid="stSidebar"] button[kind="secondary"] p { color: #eaf0f8 !important; }
[data-testid="stSidebar"] button[kind="secondary"]:hover {
  background: rgba(255,255,255,.16) !important;
  border-color: rgba(255,255,255,.3) !important;
  color: #fff !important;
}
[data-testid="stSidebar"] button[kind="secondary"]:hover p { color: #fff !important; }
[data-testid="stSidebar"] button[kind="primary"] {
  background: #2563eb !important; border-color: #2563eb !important;
  color: #fff !important; text-align: center !important;
  justify-content: center !important; font-weight: 500 !important;
}
[data-testid="stSidebar"] button[kind="primary"] p { color: #fff !important; }
[data-testid="stSidebar"] button[kind="primary"]:hover {
  background: #1d4ed8 !important; border-color: #1d4ed8 !important;
}
/* Métrica de cobertura en claro */
[data-testid="stSidebar"] [data-testid="stMetricValue"] { color: #fff !important; }
[data-testid="stSidebar"] [data-testid="stMetricLabel"] { color: #7d93b3 !important; }
/* Expanders del sidebar (renombrar conversación) */
[data-testid="stSidebar"] [data-testid="stExpander"] details {
  background: transparent !important; border: 1px solid rgba(255,255,255,.1) !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary { color: #b9c7db !important; }
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,.1) !important; }

/* ── Métricas — números grandes en azul SBS ──────────────────────────────── */
[data-testid="stMetricValue"] {
  color: var(--sbs-blue) !important;
  font-weight: 700 !important;
  font-size: 28px !important;
  line-height: 1 !important;
}
[data-testid="stMetricLabel"] {
  text-transform: uppercase; letter-spacing: 0.08em;
  font-size: 10.5px !important; color: var(--sbs-fg-muted) !important;
  font-weight: 500 !important;
}

/* ── Chat ──────────────────────────────────────────────────────────────── */
[data-testid="stChatMessage"] {
  border-radius: 10px;
  padding: 14px 16px !important;
  margin-bottom: 10px;
  border: 1px solid var(--sbs-border);
  background: #ffffff;
  box-shadow: 0 1px 2px rgba(13, 27, 42, 0.03);
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
  background: #f0f5fb;
  border-color: #c5d9eb;
}
[data-testid="stChatMessageContent"] {
  font-size: 14px; line-height: 1.55;
}

/* Input del chat más ancho y sutil */
[data-testid="stChatInputContainer"] {
  border-radius: 10px;
  border: 1px solid var(--sbs-border);
  background: white;
}

/* ── Expanders ──────────────────────────────────────────────────────────── */
[data-testid="stExpander"] details {
  border: 1px solid var(--sbs-border) !important;
  border-radius: 8px !important;
  box-shadow: 0 1px 2px rgba(13, 27, 42, 0.04);
  background: white;
}
[data-testid="stExpander"] summary {
  font-weight: 500;
  padding: 10px 14px !important;
}

/* ── Botones ──────────────────────────────────────────────────────────── */
.stButton > button {
  border-radius: 6px !important;
  font-weight: 500 !important;
  border: 1px solid var(--sbs-border);
  padding: 8px 16px !important;
  transition: all 0.15s;
}
.stButton > button:hover {
  border-color: var(--sbs-blue);
  color: var(--sbs-blue);
}
.stButton > button[kind="primary"] {
  background: var(--sbs-blue) !important;
  border-color: var(--sbs-blue) !important;
  color: white !important;
}
.stButton > button[kind="primary"]:hover {
  background: var(--sbs-blue-light) !important;
  border-color: var(--sbs-blue-light) !important;
  color: white !important;
}

/* ── Inputs (text, search) ───────────────────────────────────────────── */
.stTextInput input, .stTextArea textarea {
  border-radius: 6px !important;
  border: 1px solid var(--sbs-border) !important;
  font-size: 14px !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
  border-color: var(--sbs-blue) !important;
  box-shadow: 0 0 0 3px rgba(0, 61, 122, 0.08) !important;
}
/* Chat input compacto: el textarea sin borde propio (lo tiene el pill),
   altura de una línea que crece al escribir. */
[data-testid="stChatInput"] textarea {
  border: none !important;
  box-shadow: none !important;
  font-size: 14px !important;
  min-height: 26px !important;
  max-height: 140px !important;
  padding-top: 8px !important;
  padding-bottom: 8px !important;
}
[data-testid="stChatInput"] textarea:focus {
  border: none !important; box-shadow: none !important;
}

/* ── Dataframes ─────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
  border: 1px solid var(--sbs-border);
  border-radius: 8px;
  overflow: hidden;
}

/* ── Badges custom ──────────────────────────────────────────────────── */
.via-vector {
  display: inline-block; padding: 3px 10px; border-radius: 999px;
  font-size: 10px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.06em; background: #e3edf8; color: var(--sbs-blue);
  border: 1px solid #c5d9eb;
}
.via-graph {
  display: inline-block; padding: 3px 10px; border-radius: 999px;
  font-size: 10px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.06em; background: #fce4ec; color: #c2185b;
  border: 1px solid #f5b1c8;
}
.via-both {
  display: inline-block; padding: 3px 10px; border-radius: 999px;
  font-size: 10px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.06em; background: #fff3e0; color: #e65100;
  border: 1px solid #ffcc80;
}

/* Score chip */
.score-chip {
  display: inline-block; padding: 2px 8px; border-radius: 4px;
  font-size: 10px; font-family: 'JetBrains Mono', monospace;
  background: var(--sbs-bg-elev); color: var(--sbs-fg);
  border: 1px solid var(--sbs-border);
}

/* ── Fuentes como tarjetas con número prominente ─────────────────────── */
.fuente-wrapper { margin-bottom: 10px; }
.fuente-card {
  display: grid;
  grid-template-columns: 56px 1fr auto;
  gap: 14px;
  align-items: center;
  padding: 12px 16px;
  background: white;
  border: 1px solid var(--sbs-border);
  border-left: 4px solid var(--sbs-blue);
  border-radius: 8px 8px 0 0;
  transition: all 0.15s;
}
.fuente-wrapper:has(details:not([open])) .fuente-card {
  border-radius: 8px;
}
.fuente-card:hover {
  box-shadow: 0 2px 8px rgba(0, 61, 122, 0.08);
  border-left-color: var(--sbs-blue-light);
}
.fuente-card .fuente-num {
  background: var(--sbs-blue);
  color: white;
  font-weight: 700;
  font-size: 13px;
  text-align: center;
  border-radius: 6px;
  padding: 10px 8px;
  line-height: 1.1;
  letter-spacing: 0.02em;
}
.fuente-card .fuente-num small {
  display: block;
  font-size: 9px;
  font-weight: 500;
  opacity: 0.8;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  margin-bottom: 2px;
}
.fuente-card .fuente-body { min-width: 0; }
.fuente-card .fuente-titulo {
  font-weight: 600; font-size: 13px; color: var(--sbs-fg);
  margin-bottom: 4px;
  line-height: 1.3;
}
.fuente-card .fuente-section {
  font-size: 11px; color: var(--sbs-blue);
  font-family: 'JetBrains Mono', monospace;
  background: #eef4fa;
  padding: 2px 8px;
  border-radius: 4px;
  display: inline-block;
}
.fuente-card .fuente-section.sin-section {
  background: #f1f5f9; color: var(--sbs-fg-muted);
}
.fuente-card .fuente-meta {
  display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
}

/* Variantes por via */
.fuente-card.via-graph-card {
  border-left-color: #c2185b;
}
.fuente-card.via-graph-card .fuente-num {
  background: #c2185b;
}
.fuente-card.via-both-card {
  border-left-color: #e65100;
}
.fuente-card.via-both-card .fuente-num {
  background: #e65100;
}

/* Snippet expandible — bloque de PDF citado */
.fuente-snippet {
  border: 1px solid var(--sbs-border);
  border-top: none;
  border-left: 4px solid var(--sbs-blue);
  border-radius: 0 0 8px 8px;
  background: #fafbfd;
  overflow: hidden;
}
.fuente-wrapper:has(.via-graph-card) .fuente-snippet { border-left-color: #c2185b; }
.fuente-wrapper:has(.via-both-card) .fuente-snippet { border-left-color: #e65100; }
.fuente-snippet summary {
  cursor: pointer;
  padding: 8px 16px;
  font-size: 11px;
  color: var(--sbs-blue);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  user-select: none;
  list-style: none;
  display: flex;
  align-items: center;
  gap: 6px;
  background: #f0f5fa;
  border-top: 1px solid var(--sbs-border);
}
.fuente-snippet summary::-webkit-details-marker { display: none; }
.fuente-snippet summary::before {
  content: "▸";
  transition: transform 0.15s;
  font-size: 14px;
  color: var(--sbs-blue);
}
.fuente-snippet[open] summary::before { transform: rotate(90deg); }
.fuente-snippet[open] summary { border-bottom: 1px solid var(--sbs-border); }
.fuente-snippet .snippet-body {
  padding: 14px 18px;
  font-size: 12.5px;
  line-height: 1.55;
  color: var(--sbs-fg);
  background: white;
  font-family: 'Inter', sans-serif;
  white-space: pre-wrap;
  max-height: 320px;
  overflow-y: auto;
  border-top: 1px solid var(--sbs-border);
}
.fuente-snippet .snippet-body em {
  display: block;
  margin-top: 10px;
  color: var(--sbs-fg-dim);
  font-size: 10.5px;
  font-style: italic;
}

/* Highlight [Fuente N] en respuesta — el LLM las usa como referencias */
.contenido-app mark, [data-testid="stChatMessage"] mark,
[data-baseweb="tab-panel"] mark {
  background: #fff3cd;
  color: var(--sbs-blue);
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 3px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.9em;
  border: 1px solid #ffe69c;
}

/* Línea decorativa roja-blanca-roja (Perú) */
.peru-line {
  height: 5px; margin: 3rem -40px -2rem;
  background: linear-gradient(90deg,
    var(--sbs-red) 0% 33%,
    white 33% 67%,
    var(--sbs-red) 67% 100%);
}

/* ── Bloque de cálculo determinista (function calling) ──────────────── */
.calculo-card {
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-left: 4px solid #0284c7;
  border-radius: 8px;
  padding: 14px 18px;
  margin-bottom: 10px;
}
.calculo-card .calculo-seccion {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px dashed #93c5fd;
  font-size: 11.5px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #075985;
  display: flex;
  align-items: center;
  gap: 6px;
}
.calculo-card .calculo-seccion .nota-fuente {
  font-size: 10px;
  font-weight: 400;
  text-transform: none;
  letter-spacing: 0;
  color: #0c4a6e;
  font-style: italic;
  margin-left: auto;
}
.calculo-card .formula {
  color: var(--sbs-fg-dim);
  font-size: 11px;
  font-family: 'JetBrains Mono', monospace;
  font-weight: 400;
}
.calculo-card .calculo-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.calculo-card .calculo-icono {
  background: #0284c7;
  color: white;
  border-radius: 6px;
  padding: 2px 8px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.05em;
}
.calculo-card .calculo-titulo {
  font-weight: 600;
  font-size: 13px;
  color: #0c4a6e;
}
.calculo-card .calculo-fuente {
  font-size: 10.5px;
  color: #075985;
  font-style: italic;
  margin-bottom: 8px;
}
.calculo-card .calculo-grid {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 4px 14px;
  font-size: 12.5px;
  font-family: 'JetBrains Mono', monospace;
}
.calculo-card .calculo-grid dt {
  color: var(--sbs-fg-muted);
  font-weight: 500;
}
.calculo-card .calculo-grid dd {
  margin: 0;
  color: var(--sbs-fg);
  font-weight: 600;
}
.calculo-card .calculo-grid dd.destacar {
  color: #0284c7;
  font-size: 14px;
  font-weight: 700;
}
.calculo-card.tiene-error {
  background: #fef2f2;
  border-color: #fecaca;
  border-left-color: var(--sbs-red);
}

.calculo-deps {
  margin-top: 8px;
  margin-bottom: 6px;
  padding: 6px 10px;
  background: #fff7ed;
  border-left: 3px solid #f97316;
  border-radius: 4px;
  font-size: 11px;
  color: #9a3412;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.calculo-deps strong { color: #ea580c; font-weight: 600; }

.calculo-grid dd.input-derivado {
  color: #ea580c;
  font-style: italic;
}
.calculo-grid dd.input-derivado::after {
  content: " ↗ derivado";
  font-size: 9.5px;
  color: #c2410c;
  font-style: normal;
  margin-left: 4px;
  padding: 1px 5px;
  background: #fed7aa;
  border-radius: 3px;
}

/* Narrativa didáctica del cálculo */
.calculo-narrativa {
  background: #fffbeb;
  border-left: 3px solid #f59e0b;
  border-radius: 4px;
  padding: 10px 14px;
  margin: 6px 0 8px 0;
  font-size: 13px;
  line-height: 1.6;
  color: #1f2937;
}
.calculo-narrativa p { margin: 4px 0; }
.calculo-narrativa ul { margin: 4px 0 4px 16px; padding: 0; }
.calculo-narrativa li { margin: 2px 0; }
.calculo-narrativa strong { color: #b91c1c; font-weight: 600; }
.calculo-narrativa em { color: #1e40af; font-style: italic; }
.calculo-narrativa p.conclusion {
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px dashed #fcd34d;
  font-weight: 500;
  color: #064e3b;
}
.calculo-narrativa p.conclusion strong { color: #047857; }

/* Tabla regulatoria de origen (expandible) */
.tabla-provision-detalle {
  margin-top: 10px;
  padding: 8px 10px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-left: 3px solid #1e40af;
  border-radius: 4px;
  font-size: 12px;
}
.tabla-provision-detalle summary {
  cursor: pointer;
  font-weight: 600;
  color: #1e3a8a;
  user-select: none;
  padding: 2px 0;
}
.tabla-provision-detalle summary:hover { color: #b91c1c; }
.tabla-provision-detalle[open] summary { margin-bottom: 6px; }
.tabla-provision {
  width: 100%;
  border-collapse: collapse;
  margin-top: 4px;
  font-size: 12px;
}
.tabla-provision th,
.tabla-provision td {
  text-align: left;
  padding: 4px 8px;
  border-bottom: 1px solid #e2e8f0;
}
.tabla-provision th {
  background: #eef2ff;
  color: #1e3a8a;
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}
.tabla-provision tr.fila-usada {
  background: #fef3c7;
  font-weight: 600;
}
.tabla-provision tr.fila-usada td:first-child::before {
  content: "→ ";
  color: #b45309;
  font-weight: 700;
}
.tabla-fuente {
  margin-top: 6px;
  font-size: 11px;
  color: #64748b;
  font-style: italic;
}

/* Confianza badges */
.conf-alta { background: #dcfce7; color: #15803d; border: 1px solid #86efac; }
.conf-media { background: #fef3c7; color: #b45309; border: 1px solid #fcd34d; }
.conf-baja { background: #fee2e2; color: #b91c1c; border: 1px solid #fca5a5; }
.conf-badge {
  display: inline-block; padding: 3px 12px; border-radius: 999px;
  font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.06em;
}

/* ── Tipografía de informes (markdown rendido en chat y tabs) ─────────── */
/* Por defecto, Streamlit rinde h1 ≈ 40px y h2 ≈ 32px ("display").
   Para informes regulatorios eso es desproporcionado. Forzamos tamaños
   tipo "documento ejecutivo". */
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] h1,
[data-baseweb="tab-panel"] [data-testid="stMarkdownContainer"] h1 {
  font-size: 20px !important;
  font-weight: 700 !important;
  color: var(--sbs-blue) !important;
  margin: 1.5rem 0 0.6rem !important;
  letter-spacing: -0.01em !important;
}

[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] h2,
[data-baseweb="tab-panel"] [data-testid="stMarkdownContainer"] h2 {
  font-size: 17px !important;
  font-weight: 700 !important;
  color: var(--sbs-blue) !important;
  margin: 1.8rem 0 0.6rem !important;
  padding-bottom: 6px !important;
  border-bottom: 1px solid var(--sbs-border) !important;
  letter-spacing: -0.005em !important;
}

[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] h3,
[data-baseweb="tab-panel"] [data-testid="stMarkdownContainer"] h3 {
  font-size: 14.5px !important;
  font-weight: 600 !important;
  color: var(--sbs-fg) !important;
  margin: 1.2rem 0 0.4rem !important;
  text-transform: none !important;
  letter-spacing: 0 !important;
  border-bottom: none !important;
  padding-bottom: 0 !important;
}

[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] h4 {
  font-size: 13px !important;
  font-weight: 600 !important;
  color: var(--sbs-fg-muted) !important;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin: 1rem 0 0.4rem !important;
}

/* Párrafos y listas dentro del chat */
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p,
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] li {
  font-size: 14px !important;
  line-height: 1.6 !important;
  color: var(--sbs-fg) !important;
}
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] ul,
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] ol {
  margin: 0.5rem 0 1rem 0 !important;
  padding-left: 1.5rem !important;
}
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] li {
  margin-bottom: 0.4rem !important;
}

/* ── Ocultar iconos ancla "🔗" que Streamlit agrega a los headings ────── */
[data-testid="stHeaderActionElements"],
[data-testid="StyledLinkIconContainer"],
[data-testid="stMarkdownContainer"] a.anchor-link,
[data-testid="stMarkdownContainer"] h1 > a,
[data-testid="stMarkdownContainer"] h2 > a,
[data-testid="stMarkdownContainer"] h3 > a,
[data-testid="stMarkdownContainer"] h4 > a,
.stMarkdown h1 .anchor,
.stMarkdown h2 .anchor,
.stMarkdown h3 .anchor,
.stMarkdown svg[viewBox="0 0 20 20"] {
  display: none !important;
}

/* Quitar el "underline en hover" que algunos headings adquieren al pasar el mouse */
[data-testid="stMarkdownContainer"] h1:hover,
[data-testid="stMarkdownContainer"] h2:hover,
[data-testid="stMarkdownContainer"] h3:hover {
  text-decoration: none !important;
}

/* Divider */
hr { margin: 1.5rem 0 !important; border-color: var(--sbs-border) !important; }

/* Toasts y alerts más limpios */
[data-testid="stAlert"] {
  border-radius: 8px;
  border-left-width: 4px;
}
</style>
"""


CHAT_CSS = """
<style>
/* === Chat estilo ChatGPT — Streamlit 1.58+ === */
/* Selectores múltiples para cubrir varias versiones de Streamlit */

/* ─── USUARIO: derecha, burbuja azul SBS ─── */
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]),
div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]),
div[data-testid="stChatMessage"]:has(span[data-testid*="vatarUser"]),
div[data-testid="stChatMessage"]:has(div[data-testid*="vatarUser"]) {
  flex-direction: row-reverse !important;
  background: transparent !important;
  margin-left: auto !important;
  margin-right: 0 !important;
  max-width: 80% !important;
  padding: 4px 0 !important;
  gap: 12px !important;
}

div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) > div:last-child,
div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) > div:last-child,
div[data-testid="stChatMessage"]:has(span[data-testid*="vatarUser"]) > div:last-child,
div[data-testid="stChatMessage"]:has(div[data-testid*="vatarUser"]) > div:last-child {
  background: linear-gradient(135deg, #003d7a 0%, #0656a5 100%) !important;
  color: white !important;
  padding: 12px 18px !important;
  border-radius: 18px 18px 4px 18px !important;
  box-shadow: 0 2px 8px rgba(0,61,122,0.25) !important;
  border: none !important;
}

div[data-testid="stChatMessage"]:has([data-testid*="vatarUser"]) > div:last-child p,
div[data-testid="stChatMessage"]:has([data-testid*="vatarUser"]) > div:last-child span,
div[data-testid="stChatMessage"]:has([data-testid*="vatarUser"]) > div:last-child div,
div[data-testid="stChatMessage"]:has([data-testid*="vatarUser"]) > div:last-child * {
  color: white !important;
  background: transparent !important;
}

/* ─── ASISTENTE: izquierda, fondo gris claro ─── */
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]),
div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]),
div[data-testid="stChatMessage"]:has(span[data-testid*="vatarAssistant"]),
div[data-testid="stChatMessage"]:has(div[data-testid*="vatarAssistant"]) {
  background: transparent !important;
  margin-right: auto !important;
  margin-left: 0 !important;
  max-width: 90% !important;
  padding: 4px 0 !important;
  gap: 12px !important;
}

div[data-testid="stChatMessage"]:has([data-testid*="vatarAssistant"]) > div:last-child {
  background: #f8fafc !important;
  border: 1px solid #e2e8f0 !important;
  padding: 14px 18px !important;
  border-radius: 4px 18px 18px 18px !important;
  box-shadow: 0 1px 3px rgba(15,23,42,0.06) !important;
}

/* ─── Barra de input FIJA al pie (estilo ChatGPT) ─── */
/* Streamlit moderno envuelve el chat_input en [data-testid="stBottom"], que ya
   queda fijo abajo. Lo estilamos como barra blanca con acento rojo superior y
   sombra sutil. Además forzamos el fixed sobre stChatInput como fallback para
   versiones donde stBottom no fija (evita las "barras sueltas" a mitad de página). */
[data-testid="stBottom"],
[data-testid="stBottomBlockContainer"] {
  background: white !important;
  border-top: 2px solid var(--sbs-red) !important;
  box-shadow: 0 -4px 20px rgba(15,23,42,0.10) !important;
}

[data-testid="stChatInput"],
div[data-testid="stChatInput"] {
  position: fixed !important;
  bottom: 0 !important;
  left: 21rem !important;   /* ancho del sidebar de Streamlit */
  right: 0 !important;
  width: auto !important;
  background: white !important;
  border-top: 2px solid var(--sbs-red) !important;
  box-shadow: 0 -4px 20px rgba(15,23,42,0.10) !important;
  padding: 10px 3rem 12px !important;
  z-index: 9999 !important;
  margin: 0 !important;
}

/* Cuando sidebar está colapsado */
[data-testid="stSidebar"][aria-expanded="false"] ~ * [data-testid="stChatInput"] {
  left: 0 !important;
}

/* Espacio al final del chat para que el último mensaje no quede tapado por el input */
[data-testid="stMain"] > div > div:last-child,
.main .block-container,
section.main > div.block-container,
[data-testid="stMain"] .block-container {
  padding-bottom: 220px !important;
  margin-bottom: 60px !important;
}

/* Asegurar que el contenido scrollee bien */
[data-testid="stMainBlockContainer"] {
  padding-bottom: 200px !important;
}

/* Auto-scroll al final cuando hay nuevo mensaje */
@keyframes scrollAnchor {
  from { scroll-margin-bottom: 200px; }
  to { scroll-margin-bottom: 200px; }
}
[data-testid="stChatMessage"]:last-of-type {
  scroll-margin-bottom: 200px;
  animation: scrollAnchor 0.1s;
}

[data-testid="stChatInput"] > div,
div[data-testid="stChatInput"] > div {
  border-radius: 22px !important;
  border: 1px solid #cbd5e1 !important;
  box-shadow: 0 1px 4px rgba(15,23,42,0.06) !important;
  background: #fff !important;
  min-height: 44px !important;
  align-items: center !important;
  padding: 2px 6px 2px 8px !important;
  transition: border-color 0.15s, box-shadow 0.15s !important;
}
[data-testid="stChatInput"] > div:focus-within {
  border-color: var(--sbs-blue) !important;
  box-shadow: 0 0 0 4px rgba(0,61,122,0.12) !important;
  background: white !important;
}

[data-testid="stChatInputSubmitButton"] {
  background: #0f2547 !important;
  color: white !important;
  border-radius: 50% !important;
  width: 34px !important;
  height: 34px !important;
  min-height: 34px !important;
}
[data-testid="stChatInputSubmitButton"]:hover {
  background: #0656a5 !important;
  transform: scale(1.05) !important;
}

/* Margen entre mensajes */
[data-testid="stChatMessage"] {
  margin-bottom: 16px !important;
  padding: 0 !important;
  border: none !important;
}

/* Avatar más prominente */
[data-testid="stChatMessage"] [data-testid*="vatar"] {
  width: 32px !important;
  height: 32px !important;
  border-radius: 50% !important;
}

/* ─── FALLBACK: si :has() no funciona, usar nth-child ─── */
/* Cuando el navegador no soporta :has(), los mensajes se ven al menos limpios */
@supports not selector(:has(*)) {
  [data-testid="stChatMessage"] {
    background: #f8fafc !important;
    border-radius: 12px !important;
    padding: 12px !important;
  }
}
</style>
"""


def inyectar_estilos() -> None:
    """Llamar una vez al inicio de la app Streamlit."""
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(CHAT_CSS, unsafe_allow_html=True)


def render_header() -> None:
    """Header SBS Perú edge-to-edge."""
    st.markdown(
        '<div class="sbs-header">'
        '<div class="sbs-logo">SBS</div>'
        '<div class="sbs-titulos">'
        '<h1>Mesa Experta Regulatoria</h1>'
        '<span class="subtitulo">Consultas sobre normativa financiera peruana '
        '· <span style="opacity:.7;">herramienta independiente, no oficial</span></span>'
        '</div></div>',
        unsafe_allow_html=True,
    )


def render_footer() -> None:
    """Línea inferior tricolor sutil."""
    st.markdown('<div class="peru-line"></div>', unsafe_allow_html=True)


def badge_via(via: str) -> str:
    """Retorna HTML del badge según procedencia del chunk."""
    if via == "vector":
        return '<span class="via-vector">Vector</span>'
    if via == "graph_expansion":
        return '<span class="via-graph">Vía grafo</span>'
    if via == "both":
        return '<span class="via-both">Vector + Grafo</span>'
    return f'<span class="via-vector">{via}</span>'


def badge_confianza(nivel: str, respuesta_texto: str | None = None) -> str:
    """Renderiza badge de confianza honesto.

    Niveles soportados:
    - 'alta' / 'media' / 'baja' (basados en retrieval score)
    - 'sin_evidencia' (LLM dijo NIVEL A)
    - 'parcial' (LLM pidió clarificación, NIVEL B)
    """
    # Override por el backend (nivel ya resuelto)
    if nivel == "sin_evidencia":
        return (
            '<span class="conf-badge" '
            'style="background:#fef3c7;color:#92400e;'
            'border:1px solid #fbbf24;padding:2px 10px;border-radius:10px;'
            'font-size:11px;font-weight:600;">SIN EVIDENCIA</span>'
        )
    if nivel == "parcial":
        return (
            '<span class="conf-badge" '
            'style="background:#dbeafe;color:#1e40af;'
            'border:1px solid #60a5fa;padding:2px 10px;border-radius:10px;'
            'font-size:11px;font-weight:600;">EVIDENCIA PARCIAL</span>'
        )

    # Fallback: detección a posteriori del texto (compat con código viejo)
    if respuesta_texto:
        texto_lower = respuesta_texto.lower()
        sin_evidencia_keywords = (
            "no tengo evidencia",
            "no encuentro evidencia",
            "no hay evidencia",
            "sin información suficiente",
            "no dispongo de información",
            "no se encontró información",
            "no encontré información",
        )
        if any(k in texto_lower for k in sin_evidencia_keywords):
            return (
                '<span class="conf-badge conf-sin-evidencia" '
                'style="background:#fef3c7;color:#92400e;'
                'border:1px solid #fbbf24;">SIN EVIDENCIA</span>'
            )
    return f'<span class="conf-badge conf-{nivel}">{nivel}</span>'


def panel_sin_evidencia(n_fuentes: int = 0) -> str:
    """Tarjeta visual cuando la respuesta no tiene evidencia.

    Si ``n_fuentes > 0``, muestra mensaje matizado (evidencia parcial)
    que reconoce los documentos relacionados encontrados.
    """
    if n_fuentes > 0:
        return (
            '<div style="background:linear-gradient(135deg,#eff6ff,#dbeafe);'
            'border:1px solid #3b82f6;border-radius:12px;padding:20px;'
            'margin:16px 0;display:flex;gap:16px;align-items:center;">'
            '<div style="font-size:42px;">📂</div>'
            '<div style="flex:1;">'
            '<div style="font-weight:700;font-size:16px;color:#1e40af;'
            f'margin-bottom:6px;">Encontré {n_fuentes} documento(s) relacionado(s), '
            'pero ninguno responde directamente</div>'
            '<div style="color:#1e3a8a;font-size:14px;line-height:1.5;">'
            'Los documentos abajo cubren temas cercanos a tu pregunta pero no '
            'tienen la respuesta exacta. Intente <b>reformular más específico</b> '
            '(ej. mencione artículo, número de resolución, o cuenta contable) '
            'o active <b>Grafo</b> + <b>Saltos: 2</b> para explorar conexiones.'
            '</div></div></div>'
        )
    return (
        '<div style="background:linear-gradient(135deg,#fffbeb,#fef3c7);'
        'border:1px solid #fbbf24;border-radius:12px;padding:20px;'
        'margin:16px 0;display:flex;gap:16px;align-items:center;">'
        '<div style="font-size:42px;">🔍</div>'
        '<div style="flex:1;">'
        '<div style="font-weight:700;font-size:16px;color:#92400e;'
        'margin-bottom:6px;">No se encontró información en el corpus</div>'
        '<div style="color:#78350f;font-size:14px;line-height:1.5;">'
        'Esta consulta no encontró documentos relevantes en la base regulatoria. '
        'Intente reformular la pregunta, use términos oficiales (ej. "Resolución SBS", '
        '"Manual de Contabilidad") o active <b>Grafo</b> y suba <b>Saltos</b> a 2.'
        '</div></div></div>'
    )


def _render_tabla_provision_html(
    nombre_tabla: str,
    tabla: dict,
    fila_resaltada: str | None,
    cita_fuente: str,
) -> str:
    """Renderiza una tabla de tasas de provisión como mini-tabla HTML.

    Resalta la fila correspondiente a ``fila_resaltada`` (la categoría usada).
    """
    import html as _h
    orden = ["Normal", "CPP", "Deficiente", "Dudoso", "Pérdida"]
    filas = []
    for cat in orden:
        if cat not in tabla:
            continue
        tasa = tabla[cat]
        clase = ' class="fila-usada"' if cat == fila_resaltada else ""
        filas.append(
            f"<tr{clase}><td>{_h.escape(cat)}</td>"
            f"<td>{tasa * 100:.2f}%</td></tr>"
        )
    return (
        '<details class="tabla-provision-detalle">'
        f'<summary>📋 Ver tabla de origen — {_h.escape(nombre_tabla)}</summary>'
        '<table class="tabla-provision">'
        '<thead><tr><th>Categoría</th><th>Tasa</th></tr></thead>'
        f'<tbody>{"".join(filas)}</tbody>'
        '</table>'
        f'<div class="tabla-fuente">{_h.escape(cita_fuente)}</div>'
        '</details>'
    )


def _render_tabla_clasificacion_html(
    tipo_credito: str,
    rango_resaltado: str,
) -> str:
    """Renderiza la tabla de clasificación por días de atraso usada.

    Resalta el rango correspondiente al resultado.
    """
    import html as _h
    if tipo_credito == "hipotecario":
        nombre = "Hipotecario para vivienda — Res. 11356-2008, Cap. II num. 4"
        filas_data = [
            ("Normal", "0-30 días"),
            ("CPP", "31-60 días"),
            ("Deficiente", "61-120 días"),
            ("Dudoso", "121-365 días"),
            ("Pérdida", "más de 365 días"),
        ]
    elif tipo_credito in ("corporativo", "gran_empresa", "mediana_empresa"):
        nombre = f"No-minorista ({tipo_credito}) — Res. 11356-2008, Cap. II num. 2"
        filas_data = [
            ("Normal", "0 días (+ criterio cualitativo)"),
            ("CPP", "1-60 días (o atrasos > 15d × 2 en 6m)"),
            ("Deficiente", "61-120 días"),
            ("Dudoso", "121-365 días"),
            ("Pérdida", "más de 365 días"),
        ]
    else:
        nombre = f"Minorista ({tipo_credito}) — Res. 11356-2008, Cap. II num. 3"
        filas_data = [
            ("Normal", "0-8 días"),
            ("CPP", "9-30 días"),
            ("Deficiente", "31-60 días"),
            ("Dudoso", "61-120 días"),
            ("Pérdida", "más de 120 días"),
        ]
    filas_html = []
    for cat, rango in filas_data:
        clase = ' class="fila-usada"' if rango == rango_resaltado else ""
        filas_html.append(
            f"<tr{clase}><td>{_h.escape(cat)}</td><td>{_h.escape(rango)}</td></tr>"
        )
    return (
        '<details class="tabla-provision-detalle">'
        f'<summary>📋 Ver tabla de origen — {_h.escape(nombre)}</summary>'
        '<table class="tabla-provision">'
        '<thead><tr><th>Categoría</th><th>Rango de días</th></tr></thead>'
        f'<tbody>{"".join(filas_html)}</tbody>'
        '</table>'
        '<div class="tabla-fuente">Fuente: Res. SBS 11356-2008 (verificada contra portal oficial SBS, 2026-05).</div>'
        '</details>'
    )


def render_calculo_card(
    numero: int, calculo: dict, dependencias_por_input: dict | None = None
) -> str:
    """Renderiza un cálculo determinista como tarjeta destacada.

    Args:
        numero: índice 1-based del cálculo.
        calculo: dict del CalculoResult.
        dependencias_por_input: opcional. Mapa {nombre_input: indice_origen}
            para anotar visualmente "derivado del Cálculo X" en inputs específicos.
    """
    import html as _h
    tool = calculo.get("tool", "")
    error = calculo.get("error")
    inputs = calculo.get("inputs", {}) or {}
    output = calculo.get("output", {}) or {}
    fuente = calculo.get("fuente_normativa", "")
    deps = dependencias_por_input or {}

    if error:
        return (
            f'<div class="calculo-card tiene-error">'
            f'<div class="calculo-head">'
            f'<span class="calculo-icono">⚠ CÁLCULO {numero}</span>'
            f'<span class="calculo-titulo">{_h.escape(tool)}</span></div>'
            f'<div class="calculo-fuente">Error: {_h.escape(error)}</div>'
            f'</div>'
        )

    titulo_humano = {
        "clasificar_deudor": "Clasificación del deudor",
        "calcular_provision": "Cálculo de provisión",
    }.get(tool, tool)

    # Banner de dependencias (si este cálculo recibe inputs de otros)
    deps_banner = ""
    if deps:
        items = []
        for input_nombre, origen in deps.items():
            items.append(
                f'<strong>{_h.escape(input_nombre)}</strong> '
                f'tomado del Cálculo {origen}'
            )
        deps_banner = (
            f'<div class="calculo-deps">'
            f'⛓ <span style="font-weight:600;">Encadenado:</span> '
            + ' · '.join(items)
            + '</div>'
        )

    # Renderizar inputs marcando los derivados — saltamos valores None/vacíos
    # (campos opcionales no provistos por el agente)
    filas = []
    for clave, valor in inputs.items():
        if valor is None or valor == "":
            continue
        clase_input = ' class="input-derivado"' if clave in deps else ""
        # Formato amigable: floats con separador miles y 2 decimales
        if isinstance(valor, float):
            valor_render = f"{valor:,.2f}"
        else:
            valor_render = str(valor)
        filas.append(
            f'<dt>{_h.escape(str(clave))}</dt>'
            f'<dd{clase_input}>{_h.escape(valor_render)}</dd>'
        )

    # Sección de resultado (para clasificar_deudor)
    seccion_resultado_html = ""
    seccion_tasas_html = ""
    seccion_desglose_html = ""
    seccion_narrativa_html = ""

    if tool == "clasificar_deudor":
        categoria = output.get("categoria", "")
        rango = output.get("rango_dias", "")
        desc = output.get("descripcion", "")
        filas_resultado = [
            f'<dt>→ Categoría</dt><dd class="destacar">{_h.escape(str(categoria))}</dd>',
            f'<dt>→ Rango</dt><dd>{_h.escape(str(rango))}</dd>',
        ]
        if desc:
            filas_resultado.append(f'<dt>→ Descripción</dt><dd>{_h.escape(str(desc))}</dd>')
        seccion_resultado_html = (
            '<div class="calculo-seccion">📊 Resultado</div>'
            f'<dl class="calculo-grid">{"".join(filas_resultado)}</dl>'
        )
        # Tabla de origen de la clasificación
        tipo_cred = inputs.get("tipo_credito", "")
        if tipo_cred:
            seccion_resultado_html += _render_tabla_clasificacion_html(
                str(tipo_cred), str(rango)
            )

        # ── Narrativa didáctica ──────────────
        dias = inputs.get("dias_atraso", "?")
        seccion_narrativa_html = (
            '<div class="calculo-seccion">📖 ¿Cómo se llegó a este resultado?</div>'
            f'<div class="calculo-narrativa">'
            f'<p>1. El deudor tiene un crédito <strong>{_h.escape(str(tipo_cred))}</strong> '
            f'con <strong>{_h.escape(str(dias))} días de atraso</strong>.</p>'
            f'<p>2. Busco ese número de días en la tabla oficial de la SBS '
            f'(Res. 11356-2008, Cap. II) para créditos del tipo '
            f'<strong>{_h.escape(str(tipo_cred))}</strong>.</p>'
            f'<p>3. El rango <strong>{_h.escape(str(rango))}</strong> '
            f'corresponde a la categoría <strong>{_h.escape(str(categoria))}</strong>.</p>'
            f'<p class="conclusion">→ Por lo tanto, el deudor se clasifica como '
            f'<strong>{_h.escape(str(categoria))}</strong>.</p>'
            f'</div>'
        )

    elif tool == "calcular_provision":
        desglose = output.get("desglose", {}) or {}
        clasif = inputs.get("clasificacion", "")
        tipo_g = inputs.get("tipo_garantia", "ninguna")
        descuento_pct = desglose.get("descuento_garantia_pct", 0)
        tasa_nc = desglose.get("tasa_aplicada_no_cubierto", 0)
        tasa_c = desglose.get("tasa_aplicada_cubierto", 0)

        # ── Sección: % de provisión aplicados (NO es tasa de interés) ─────
        filas_tasas = []
        if tipo_g and tipo_g != "ninguna":
            filas_tasas.append(
                f'<dt>descuento garantía (haircut)</dt>'
                f'<dd>{descuento_pct * 100:.0f}%'
                f' <span class="formula">(Anexo II — {_h.escape(str(tipo_g))})</span></dd>'
            )
        if tasa_nc > 0:
            filas_tasas.append(
                f'<dt>% provisión (saldo sin garantía)</dt>'
                f'<dd>{tasa_nc * 100:.2f}%'
                f' <span class="formula">(Tabla sin garantía, {_h.escape(str(clasif))})</span></dd>'
            )
        if tasa_c > 0:
            filas_tasas.append(
                f'<dt>% provisión (saldo con garantía)</dt>'
                f'<dd>{tasa_c * 100:.2f}%'
                f' <span class="formula">(Tabla {_h.escape(str(tipo_g))}, {_h.escape(str(clasif))})</span></dd>'
            )
        provision_generica = desglose.get("provision_generica", 0)
        if clasif == "Normal":
            filas_tasas.append(
                f'<dt>% provisión genérica</dt>'
                f'<dd>1.00% <span class="formula">(solo Normal, Cap. III num. 4)</span></dd>'
            )

        if filas_tasas:
            seccion_tasas_html = (
                '<div class="calculo-seccion">📐 % de provisión aplicados'
                '<span class="nota-fuente">No es tasa de interés — Res. 11356-2008 Cap. III + Anexo II</span>'
                '</div>'
                f'<dl class="calculo-grid">{"".join(filas_tasas)}</dl>'
            )

        # ── Sección: desglose aritmético ─────────
        valor_g_orig = desglose.get("valor_garantia_original", 0)
        valor_g_aj = desglose.get("valor_garantia_ajustado", 0)
        saldo_total = desglose.get("saldo_total", 0)
        saldo_c = desglose.get("saldo_cubierto_por_garantia", 0)
        saldo_nc = desglose.get("saldo_no_cubierto", 0)
        prov_nc = desglose.get("provision_no_cubierto", 0)
        prov_c = desglose.get("provision_cubierto", 0)
        prov_total = output.get("monto_provision", 0)
        tasa_efec = output.get("tasa_aplicada", 0)

        filas_desglose = []
        if tipo_g and tipo_g != "ninguna" and valor_g_orig > 0:
            filas_desglose.append(
                f'<dt>valor garantía ajustado</dt>'
                f'<dd>S/ {valor_g_aj:,.2f}'
                f' <span class="formula">= {valor_g_orig:,.0f} × (1 − {descuento_pct*100:.0f}%)</span></dd>'
            )
        filas_desglose.append(
            f'<dt>saldo cubierto</dt>'
            f'<dd>S/ {saldo_c:,.2f}'
            f' <span class="formula">(parte del saldo respaldada)</span></dd>'
        )
        filas_desglose.append(
            f'<dt>saldo no cubierto</dt>'
            f'<dd>S/ {saldo_nc:,.2f}'
            f' <span class="formula">= {saldo_total:,.0f} − {saldo_c:,.0f}</span></dd>'
        )
        if prov_nc > 0:
            filas_desglose.append(
                f'<dt>provisión saldo sin garantía</dt>'
                f'<dd>S/ {prov_nc:,.2f}'
                f' <span class="formula">= S/ {saldo_nc:,.0f} × {tasa_nc*100:.2f}% (% provisión, no interés)</span></dd>'
            )
        if prov_c > 0:
            filas_desglose.append(
                f'<dt>provisión saldo con garantía</dt>'
                f'<dd>S/ {prov_c:,.2f}'
                f' <span class="formula">= S/ {saldo_c:,.0f} × {tasa_c*100:.2f}% (% provisión, no interés)</span></dd>'
            )
        if provision_generica > 0:
            filas_desglose.append(
                f'<dt>provisión genérica</dt>'
                f'<dd>S/ {provision_generica:,.2f}'
                f' <span class="formula">= {saldo_total:,.0f} × 1.00%</span></dd>'
            )

        seccion_desglose_html = (
            '<div class="calculo-seccion">🧾 Desglose aritmético</div>'
            f'<dl class="calculo-grid">{"".join(filas_desglose)}</dl>'
        )

        # ── Sección: resultado final ─────────
        seccion_resultado_html = (
            '<div class="calculo-seccion">💰 Resultado</div>'
            '<dl class="calculo-grid">'
            f'<dt>→ Provisión total</dt>'
            f'<dd class="destacar">S/ {prov_total:,.2f}</dd>'
            f'<dt>→ % provisión efectivo (ponderado)</dt>'
            f'<dd>{tasa_efec * 100:.2f}%'
            f' <span class="formula">= provisión / saldo · NO es tasa de interés</span></dd>'
            '</dl>'
        )

        # ── Narrativa didáctica del cálculo de provisión ─────────
        saldo_in = inputs.get("saldo", 0) or 0
        try:
            saldo_in = float(saldo_in)
        except Exception:  # noqa: BLE001
            saldo_in = 0
        val_g = inputs.get("valor_garantia", 0) or 0
        try:
            val_g = float(val_g)
        except Exception:  # noqa: BLE001
            val_g = 0
        pasos = []
        pasos.append(
            f'<p>1. Saldo del crédito: <strong>S/ {saldo_in:,.2f}</strong>, '
            f'deudor clasificado como <strong>{_h.escape(str(clasif))}</strong>.</p>'
        )
        if tipo_g and tipo_g != "ninguna" and val_g > 0:
            pasos.append(
                f'<p>2. La garantía (<strong>{_h.escape(str(tipo_g))}</strong>) está '
                f'tasada en S/ {val_g:,.2f}. La SBS le aplica un <em>haircut</em> '
                f'(descuento de seguridad) del <strong>{descuento_pct*100:.0f}%</strong> '
                f'(Anexo II): su valor para efectos de cobertura queda en '
                f'<strong>S/ {valor_g_aj:,.2f}</strong>.</p>'
            )
            pasos.append(
                f'<p>3. De los S/ {saldo_in:,.0f} de saldo, esa garantía cubre '
                f'<strong>S/ {saldo_c:,.0f}</strong>. Los <strong>S/ {saldo_nc:,.0f}</strong> '
                f'restantes quedan sin respaldo.</p>'
            )
            pasos.append(
                f'<p>4. La SBS exige reservar contablemente:</p>'
                f'<ul>'
                f'<li><strong>{tasa_nc*100:.2f}%</strong> del saldo sin garantía '
                f'(Tabla 1, categoría {_h.escape(str(clasif))}) → '
                f'<strong>S/ {prov_nc:,.2f}</strong></li>'
                f'<li><strong>{tasa_c*100:.2f}%</strong> del saldo con garantía '
                f'(Tabla 2 — preferida, categoría {_h.escape(str(clasif))}) → '
                f'<strong>S/ {prov_c:,.2f}</strong></li>'
                f'</ul>'
            )
            pasos.append(
                f'<p class="conclusion">→ Provisión total = '
                f'S/ {prov_nc:,.2f} + S/ {prov_c:,.2f} = '
                f'<strong>S/ {prov_total:,.2f}</strong> '
                f'({tasa_efec*100:.2f}% del saldo).</p>'
            )
        else:
            pasos.append(
                f'<p>2. No hay garantía: el 100% del saldo (S/ {saldo_in:,.0f}) '
                f'queda sin cobertura.</p>'
            )
            pasos.append(
                f'<p>3. La SBS exige reservar el <strong>{tasa_nc*100:.2f}%</strong> '
                f'sobre todo el saldo (Tabla 1 sin garantía, categoría '
                f'{_h.escape(str(clasif))}).</p>'
            )
            pasos.append(
                f'<p class="conclusion">→ Provisión = '
                f'S/ {saldo_in:,.0f} × {tasa_nc*100:.2f}% = '
                f'<strong>S/ {prov_total:,.2f}</strong>.</p>'
            )
        seccion_narrativa_html = (
            '<div class="calculo-seccion">📖 ¿Cómo se llegó a este resultado?</div>'
            f'<div class="calculo-narrativa">{"".join(pasos)}</div>'
        )

        # ── Tablas regulatorias de origen (siempre visibles, expandibles) ─────
        try:
            from src.tools.provisiones import obtener_tabla_provision
            tablas_html_parts = []
            # Siempre la tabla "sin garantía" (aplica a la parte no cubierta)
            _, nombre_sg, tabla_sg = obtener_tabla_provision("ninguna")
            tablas_html_parts.append(
                _render_tabla_provision_html(
                    nombre_sg, tabla_sg, str(clasif),
                    "Fuente: Res. SBS 11356-2008, Capítulo III, numeral 2.",
                )
            )
            # Y la tabla específica del tipo de garantía si la hay
            if tipo_g and tipo_g != "ninguna":
                _, nombre_g, tabla_g = obtener_tabla_provision(tipo_g)
                tablas_html_parts.append(
                    _render_tabla_provision_html(
                        nombre_g, tabla_g, str(clasif),
                        "Fuente: Res. SBS 11356-2008, Capítulo III, numeral 3 + Anexo II (haircut).",
                    )
                )
            seccion_resultado_html += "".join(tablas_html_parts)
        except Exception:  # noqa: BLE001
            pass

    grid_inputs_html = "".join(filas)
    seccion_inputs_html = (
        '<div class="calculo-seccion">📥 Inputs</div>'
        f'<dl class="calculo-grid">{grid_inputs_html}</dl>'
    )

    return (
        f'<div class="calculo-card">'
        f'<div class="calculo-head">'
        f'<span class="calculo-icono">🧮 CÁLCULO {numero}</span>'
        f'<span class="calculo-titulo">{_h.escape(titulo_humano)}</span>'
        f'</div>'
        f'<div class="calculo-fuente">📜 {_h.escape(fuente)}</div>'
        f'{deps_banner}'
        f'{seccion_inputs_html}'
        f'{seccion_narrativa_html}'
        f'{seccion_tasas_html}'
        f'{seccion_desglose_html}'
        f'{seccion_resultado_html}'
        f'</div>'
    )


def calcular_dependencias_ui(calculos: list[dict]) -> dict[int, dict[str, int]]:
    """Mismo detector que el backend pero corriendo en la UI sobre el dict.

    Retorna {indice_calculo (1-based): {nombre_input: indice_origen}}.
    """
    mapeo_input_a_output = {
        "calcular_provision": {"clasificacion": "categoria"},
    }
    fuente_output = {
        "clasificar_deudor": ["categoria"],
        "calcular_provision": ["monto_provision"],
    }
    deps: dict[int, dict[str, int]] = {}
    for i, c_i in enumerate(calculos, 1):
        tool_i = c_i.get("tool", "")
        if c_i.get("error") or tool_i not in mapeo_input_a_output:
            continue
        mapping = mapeo_input_a_output[tool_i]
        inputs_i = c_i.get("inputs", {}) or {}
        for input_clave, output_clave in mapping.items():
            valor_input = inputs_i.get(input_clave)
            if valor_input is None:
                continue
            for j, c_j in enumerate(calculos[:i - 1], 1):
                if c_j.get("error") or c_j.get("tool") not in fuente_output:
                    continue
                if output_clave not in fuente_output[c_j["tool"]]:
                    continue
                valor_output = (c_j.get("output") or {}).get(output_clave)
                if valor_output is not None and valor_output == valor_input:
                    deps.setdefault(i, {})[input_clave] = j
                    break
    return deps


import html as _html
import re as _re


def resaltar_referencias_fuente(texto: str) -> str:
    """Convierte cada `[Fuente N]` o `Fuente N` en un `<mark>` para verlas
    fácilmente en la respuesta del LLM."""
    seguro = _html.escape(texto)
    # Acepta: [Fuente 1], [Fuente 1: ...], Fuente 1
    patron = _re.compile(
        r"\[?\s*Fuente\s+(\d+)(?:\s*[:.]\s*[^\]]+?)?\s*\]?",
        _re.IGNORECASE,
    )
    return patron.sub(lambda m: f"<mark>Fuente {m.group(1)}</mark>", seguro)


def render_fuente_card(numero: int, fuente: dict, mostrar_tecnico: bool = False) -> str:
    """Renderiza una tarjeta de fuente con el número prominente.

    `fuente` es el dict del schema Source: {doc_id, title, score, via,
    section_path, url, ...}

    mostrar_tecnico: si True, incluye "Detalles técnicos" (vía, relevancia).
        Reservado para administración — el usuario final no los ve.
    """
    via = fuente.get("via", "vector")
    clase_via = (
        "via-graph-card" if via == "graph_expansion"
        else "via-both-card" if via == "both"
        else ""
    )
    # Limpiar título: quitar extensión .pdf, prefijos técnicos
    titulo_raw = fuente.get("title", "")
    titulo_raw = _re.sub(r"\.pdf$", "", titulo_raw, flags=_re.IGNORECASE)
    titulo_raw = _re.sub(r"^(Res-?SBS-?|res-sbs-)", "Resolución SBS ", titulo_raw, flags=_re.IGNORECASE)
    titulo_raw = titulo_raw.replace("-", " ").replace("_", " ").strip()
    # Capitalizar mejor si vino en minúsculas separadas
    if titulo_raw and titulo_raw == titulo_raw.lower():
        titulo_raw = titulo_raw.title()
    titulo = _html.escape(titulo_raw)[:120]
    section = fuente.get("section_path")
    if section and section not in ("(sin estructura)", "(preámbulo)"):
        section_html = f'<span class="fuente-section">{_html.escape(section)}</span>'
    else:
        section_html = '<span class="fuente-section sin-section">documento completo</span>'

    score = fuente.get("score", 0)
    via_badge_map = {
        "vector": '<span class="via-vector">Vector</span>',
        "graph_expansion": '<span class="via-graph">Vía grafo</span>',
        "both": '<span class="via-both">Vector + Grafo</span>',
    }
    via_badge = via_badge_map.get(via, "")

    # Badge institucional (Mejora #3)
    issuer = fuente.get("issuer") or ""
    issuer_colores = {
        "SBS": "#003d7a",
        "BCRP": "#b91c1c",
        "Congreso": "#7c3aed",
        "MEF": "#15803d",
        "SMV": "#0891b2",
        "INDECOPI": "#ca8a04",
        "SUNAT": "#be185d",
    }
    if issuer and issuer != "(s/d)":
        color_iss = issuer_colores.get(issuer, "#475569")
        issuer_badge = (
            f'<span style="background:{color_iss};color:#fff;'
            f'padding:2px 8px;border-radius:10px;font-size:10px;'
            f'font-weight:600;letter-spacing:0.3px;margin-right:4px;">'
            f'{_html.escape(issuer)}</span>'
        )
    else:
        issuer_badge = ""

    url = fuente.get("url")
    enlace_html = (
        f'<a href="{_html.escape(url)}" target="_blank" style="font-size:10px;'
        f'color:var(--sbs-blue);text-decoration:none;">PDF ↗</a>'
        if url else ""
    )

    snippet_raw = fuente.get("content_snippet") or ""
    snippet_html = ""
    if snippet_raw.strip():
        snippet_seguro = _html.escape(snippet_raw)
        # IMPORTANTE: sin indentación. Streamlit/markdown tratan ≥4 espacios
        # al inicio de línea como bloque de código y rompen el HTML.
        snippet_html = (
            f'<details class="fuente-snippet">'
            f'<summary>Ver fragmento del PDF citado</summary>'
            f'<div class="snippet-body">{snippet_seguro}'
            f'<em>— Texto extraído del PDF; pueden quedar artefactos de formato.</em>'
            f'</div></details>'
        )

    # Versión amigable: solo título + sección + link PDF.
    # Los detalles técnicos (vía retrieval, score) solo se muestran a admin.
    if mostrar_tecnico:
        detalles_tecnicos = (
            f'<details class="fuente-tecnico" style="margin-top:4px;">'
            f'<summary style="font-size:10px;color:#94a3b8;cursor:pointer;">'
            f'Detalles técnicos</summary>'
            f'<div style="font-size:11px;color:#64748b;padding:6px 0;">'
            f'{via_badge}<span class="score-chip">relevancia {score:.2f}</span>'
            f'</div></details>'
        )
    else:
        detalles_tecnicos = ""

    return (
        f'<div class="fuente-wrapper">'
        f'<div class="fuente-card {clase_via}">'
        f'<div class="fuente-num"><small>FUENTE</small>{numero}</div>'
        f'<div class="fuente-body">'
        f'<div class="fuente-titulo">{issuer_badge}{titulo}</div>'
        f'<div class="fuente-meta">{section_html}{enlace_html}</div>'
        f'{detalles_tecnicos}'
        f'</div></div>'
        f'{snippet_html}'
        f'</div>'
    )
