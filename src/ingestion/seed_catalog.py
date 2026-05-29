"""Catálogo curado de fuentes regulatorias peruanas.

Cada entrada tiene URL oficial verificada manualmente al 2026-05.
Cubre 6 reguladoras / fuentes: SBS, BCRP, SMV, INDECOPI, MEF, Leyes.

Convenciones:
- ``name``: slug único (kebab-case).
- ``url``: URL pública del PDF/HTML oficial.
- ``source_type``: ``direct_pdf`` por ahora (toda la lista descarga PDFs).
- ``domain``: bucket para el topic_router. Valores:
    riesgo_credito, riesgo_operacional, ti_seguridad, laft,
    gobierno, legal, operaciones_estructuradas, tasas_intereses,
    mercado_valores, tributario, consumidor, fiscal.
- ``document_type``: ``resolucion`` | ``circular`` | ``ley`` |
    ``decreto_supremo`` | ``nota_informativa`` | ``directiva``.
- ``cron_expr``: cron para chequeo de cambios. Distribuido a lo largo del día
    para no saturar el scheduler en un solo minuto.
- ``metadata``: contexto adicional (título legible, número, año, etc.).

Para agregar nuevas fuentes:
1. Verifica la URL en el portal oficial.
2. Añade entrada con un cron_expr único.
3. Restart API → el scheduler la registra automáticamente.
"""

from __future__ import annotations

# ============================================================================
# SBS — Superintendencia de Banca, Seguros y AFP
# ============================================================================

SBS = [
    {
        "name": "res-sbs-11356-2008-clasificacion-deudor",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/1097/v12.0/Adjuntos/11356-2008.r.pdf",
        "source_type": "direct_pdf",
        "domain": "riesgo_credito",
        "document_type": "resolucion",
        "cron_expr": "0 2 * * *",
        "metadata": {
            "title": "Reglamento para la Evaluación y Clasificación del Deudor",
            "resolution_number": "11356-2008",
            "year": 2008,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-2368-2023-modif-reglamento-deudor",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/2290/v2.0/Adjuntos/2368-2023.pdf",
        "source_type": "direct_pdf",
        "domain": "riesgo_credito",
        "document_type": "resolucion",
        "cron_expr": "5 2 * * *",
        "metadata": {
            "title": "Modificación del Reglamento para la Evaluación y Clasificación del Deudor",
            "resolution_number": "2368-2023",
            "year": 2023,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-04345-2023-definiciones",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/2326/v1.0/Adjuntos/04345-2023.R.pdf",
        "source_type": "direct_pdf",
        "domain": "riesgo_credito",
        "document_type": "resolucion",
        "cron_expr": "10 2 * * *",
        "metadata": {
            "title": "Modificación del Reglamento del Deudor (definiciones Cap. I)",
            "resolution_number": "4345-2023",
            "year": 2023,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-975-2025-modificatoria",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/2486/v1.0/Adjuntos/975-2025.R.pdf",
        "source_type": "direct_pdf",
        "domain": "riesgo_credito",
        "document_type": "resolucion",
        "cron_expr": "15 2 * * *",
        "metadata": {
            "title": "Modificación del Reglamento del Deudor (definiciones Cap. I)",
            "resolution_number": "975-2025",
            "year": 2025,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-14353-2009-provisiones-genericas",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/968/v1.0/Adjuntos/14353-2009.r.pdf",
        "source_type": "direct_pdf",
        "domain": "riesgo_credito",
        "document_type": "resolucion",
        "cron_expr": "20 2 * * *",
        "metadata": {
            "title": "Reglamento para la Constitución de Provisiones Procíclicas",
            "resolution_number": "14353-2009",
            "year": 2009,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-14354-2009-patrimonio-efectivo-riesgo-credito",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/976/v10.0/Adjuntos/14354-2009.r.pdf",
        "source_type": "direct_pdf",
        "domain": "riesgo_credito",
        "document_type": "resolucion",
        "cron_expr": "25 2 * * *",
        "metadata": {
            "title": "Reglamento para el Requerimiento de Patrimonio Efectivo por Riesgo de Crédito",
            "resolution_number": "14354-2009",
            "year": 2009,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-3780-2011-evaluacion-crediticia",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/774/v3.0/Adjuntos/3780-2011.r.pdf",
        "source_type": "direct_pdf",
        "domain": "riesgo_credito",
        "document_type": "resolucion",
        "cron_expr": "30 2 * * *",
        "metadata": {
            "title": "Reglamento de Gestión de Riesgo de Crédito",
            "resolution_number": "3780-2011",
            "year": 2011,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-8181-2012-transparencia",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/763/v4.0/adjuntos/8181-2012.R.pdf",
        "source_type": "direct_pdf",
        "domain": "tasas_intereses",
        "document_type": "resolucion",
        "cron_expr": "35 2 * * *",
        "metadata": {
            "title": "Reglamento de Transparencia de Información y Contratación",
            "resolution_number": "8181-2012",
            "year": 2012,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-789-2018-reglamento-plaft",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/1766/v5.0/Adjuntos/789-2018.R.pdf",
        "source_type": "direct_pdf",
        "domain": "laft",
        "document_type": "resolucion",
        "cron_expr": "40 2 * * *",
        "metadata": {
            "title": "Reglamento PLAFT — Gestión de Riesgos de Lavado de Activos",
            "resolution_number": "789-2018",
            "year": 2018,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-272-2017-gobierno-corporativo",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/1708/v4.0/Adjuntos/272-2017.R.pdf",
        "source_type": "direct_pdf",
        "domain": "gobierno",
        "document_type": "resolucion",
        "cron_expr": "45 2 * * *",
        "metadata": {
            "title": "Reglamento de Gobierno Corporativo y Gestión Integral de Riesgos",
            "resolution_number": "272-2017",
            "year": 2017,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-504-2021-sgsi-c",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/2046/v2.0/Adjuntos/504-2021.R.pdf",
        "source_type": "direct_pdf",
        "domain": "ti_seguridad",
        "document_type": "resolucion",
        "cron_expr": "50 2 * * *",
        "metadata": {
            "title": "Reglamento de Seguridad de la Información y Ciberseguridad (SGSI-C)",
            "resolution_number": "504-2021",
            "year": 2021,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-2116-2009-riesgo-operacional",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/842/v4.0/Adjuntos/2116-2009%20actualizado%20con%20la%20877-2020.doc.pdf",
        "source_type": "direct_pdf",
        "domain": "riesgo_operacional",
        "document_type": "resolucion",
        "cron_expr": "55 2 * * *",
        "metadata": {
            "title": "Reglamento de Gestión del Riesgo Operacional",
            "resolution_number": "2116-2009",
            "year": 2009,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-1802-2014-cumplimiento-cooperativas",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/930/v1.0/Adjuntos/1802-2014.r.pdf",
        "source_type": "direct_pdf",
        "domain": "legal",
        "document_type": "resolucion",
        "cron_expr": "0 3 * * *",
        "metadata": {
            "title": "Reglamento de Cumplimiento Normativo en Cooperativas",
            "resolution_number": "1802-2014",
            "year": 2014,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-1010-1999-reglamento-fideicomiso",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/1192/v1.0/Adjuntos/1010-1999%20r%20(Oct-2021).doc.pdf",
        "source_type": "direct_pdf",
        "domain": "operaciones_estructuradas",
        "document_type": "resolucion",
        "cron_expr": "5 3 * * *",
        "metadata": {
            "title": "Reglamento del Fideicomiso y de las Empresas de Servicios Fiduciarios",
            "resolution_number": "1010-1999",
            "year": 1999,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-1308-2013-transferencia-cartera",
        "url": "https://intranet2.sbs.gob.pe/intranet/INT_CN/DV_INT_CN/1065/v1.0/Adjuntos/1308-2013.r.pdf",
        "source_type": "direct_pdf",
        "domain": "operaciones_estructuradas",
        "document_type": "resolucion",
        "cron_expr": "10 3 * * *",
        "metadata": {
            "title": "Reglamento para la Transferencia y Adquisición de Cartera Crediticia",
            "resolution_number": "1308-2013",
            "year": 2013,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-480-2019-operaciones-cartera",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/1827/v1.0/Adjuntos/480-2019.R.pdf",
        "source_type": "direct_pdf",
        "domain": "operaciones_estructuradas",
        "document_type": "resolucion",
        "cron_expr": "15 3 * * *",
        "metadata": {
            "title": "Reglamento de Operaciones con Cartera",
            "resolution_number": "480-2019",
            "year": 2019,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-3986-2024",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/2461/v1.0/Adjuntos/Resoluci%C3%B3n%20SBS%20N%C2%B003986-2024.pdf",
        "source_type": "direct_pdf",
        "domain": "operaciones_estructuradas",
        "document_type": "resolucion",
        "cron_expr": "20 3 * * *",
        "metadata": {
            "title": "Resolución SBS Nº 03986-2024",
            "resolution_number": "3986-2024",
            "year": 2024,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-3274-2017-transparencia-modif",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/1731/v7.0/Adjuntos/3274-2017.R.pdf",
        "source_type": "direct_pdf",
        "domain": "tasas_intereses",
        "document_type": "resolucion",
        "cron_expr": "25 3 * * *",
        "metadata": {
            "title": "Modificación del Reglamento de Transparencia",
            "resolution_number": "3274-2017",
            "year": 2017,
            "issuer": "SBS",
        },
    },
    # ===== Expansión 2026-05: top citaciones del grafo + recientes =====
    {
        "name": "res-sbs-11699-2008-disposicion-credito-revolvente",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/1134/v9.0/Adjuntos/11699-2008.r.pdf",
        "source_type": "direct_pdf",
        "domain": "riesgo_credito",
        "document_type": "resolucion",
        "cron_expr": "50 3 * * *",
        "metadata": {
            "title": "Resolución SBS 11699-2008 (provisiones cíclicas / créditos revolventes)",
            "resolution_number": "11699-2008",
            "year": 2008,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-1754-2024-modificatoria",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/2361/v1.0/Adjuntos/1754-2024.R.pdf",
        "source_type": "direct_pdf",
        "domain": "riesgo_credito",
        "document_type": "resolucion",
        "cron_expr": "55 3 * * *",
        "metadata": {
            "title": "Resolución SBS 1754-2024",
            "resolution_number": "1754-2024",
            "year": 2024,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-2286-2024-tarjetas-credito-autenticacion",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/2410/v1.0/Adjuntos/2286-2024.R.pdf",
        "source_type": "direct_pdf",
        "domain": "ti_seguridad",
        "document_type": "resolucion",
        "cron_expr": "0 5 * * *",
        "metadata": {
            "title": "Modifica Reglamento Tarjetas + SGSI-C (autenticación operaciones)",
            "resolution_number": "2286-2024",
            "year": 2024,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-3884-2024",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/2452/v1.0/Adjuntos/3884-2024.R.pdf",
        "source_type": "direct_pdf",
        "domain": "riesgo_credito",
        "document_type": "resolucion",
        "cron_expr": "5 5 * * *",
        "metadata": {
            "title": "Resolución SBS 3884-2024",
            "resolution_number": "3884-2024",
            "year": 2024,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-2220-2025",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/2506/v1.0/Adjuntos/Res.SBS%202220-2025.pdf",
        "source_type": "direct_pdf",
        "domain": "riesgo_credito",
        "document_type": "resolucion",
        "cron_expr": "10 5 * * *",
        "metadata": {
            "title": "Resolución SBS 2220-2025",
            "resolution_number": "2220-2025",
            "year": 2025,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-3289-2025",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/2525/v1.0/Adjuntos/Resoluci%c3%b3n%20SBS%20N%c2%b0%203289-2025.pdf",
        "source_type": "direct_pdf",
        "domain": "riesgo_credito",
        "document_type": "resolucion",
        "cron_expr": "15 5 * * *",
        "metadata": {
            "title": "Resolución SBS 3289-2025",
            "resolution_number": "3289-2025",
            "year": 2025,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-3932-2022",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/2222/v1.0/Adjuntos/3932-2022.R.pdf",
        "source_type": "direct_pdf",
        "domain": "riesgo_credito",
        "document_type": "resolucion",
        "cron_expr": "20 5 * * *",
        "metadata": {
            "title": "Resolución SBS 3932-2022",
            "resolution_number": "3932-2022",
            "year": 2022,
            "issuer": "SBS",
        },
    },
]


# ============================================================================
# BCRP — Banco Central de Reserva del Perú
# ============================================================================

BCRP = [
    {
        "name": "circular-bcrp-0008-2021-tasa-maxima",
        "url": "https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2021/circular-0008-2021-bcrp.pdf",
        "source_type": "direct_pdf",
        "domain": "tasas_intereses",
        "document_type": "circular",
        "cron_expr": "30 3 * * *",
        "metadata": {
            "title": "Tasas Máximas de Interés Convencional Compensatorio y Moratorio",
            "resolution_number": "0008-2021-BCRP",
            "year": 2021,
            "issuer": "BCRP",
        },
    },
    {
        "name": "bcrp-nota-2026-04-tasas-maximas",
        "url": "https://www.bcrp.gob.pe/docs/Transparencia/Notas-Informativas/2026/nota-informativa-2026-04-07.pdf",
        "source_type": "direct_pdf",
        "domain": "tasas_intereses",
        "document_type": "nota_informativa",
        "cron_expr": "35 3 * * *",
        "metadata": {
            "title": "Actualización Tasas Máximas — mayo-octubre 2026",
            "year": 2026,
            "issuer": "BCRP",
        },
    },
    {
        "name": "bcrp-nota-2025-10-tasas-maximas",
        "url": "https://www.bcrp.gob.pe/docs/Transparencia/Notas-Informativas/2025/nota-informativa-2025-10-09-2.pdf",
        "source_type": "direct_pdf",
        "domain": "tasas_intereses",
        "document_type": "nota_informativa",
        "cron_expr": "40 3 * * *",
        "metadata": {
            "title": "Actualización Tasas Máximas — noviembre 2025-abril 2026",
            "year": 2025,
            "issuer": "BCRP",
        },
    },
    {
        "name": "circular-bcrp-021-2007-tasa-interes",
        "url": "https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2007/Circular-021-2007-BCRP.pdf",
        "source_type": "direct_pdf",
        "domain": "tasas_intereses",
        "document_type": "circular",
        "cron_expr": "45 3 * * *",
        "metadata": {
            "title": "Disposiciones sobre Tasas de Interés (cálculo TEA)",
            "resolution_number": "021-2007-BCRP",
            "year": 2007,
            "issuer": "BCRP",
        },
    },
]


# ============================================================================
# SMV — Superintendencia del Mercado de Valores
# (URLs sujetas a verificación — agregar más conforme se identifiquen)
# ============================================================================

SMV = [
    # NOTA: SMV tiene su propio portal que requiere navegación.
    # Por ahora dejamos placeholder vacío; se irán agregando en próximas iteraciones.
]


# ============================================================================
# INDECOPI — Protección al Consumidor
# ============================================================================

INDECOPI = [
    # NOTA: Las directivas de INDECOPI están en busquedas.elperuano.pe.
    # Agregar URLs específicas conforme se identifiquen.
]


# ============================================================================
# Leyes del Congreso — fundamentales para sistema financiero
# ============================================================================

LEYES = [
    # Ley General del Sistema Financiero - URL del Congreso
    {
        "name": "ley-26702-ley-general-sistema-financiero",
        "url": "https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/ley-general.pdf",
        "source_type": "direct_pdf",
        "domain": "legal",
        "document_type": "ley",
        "cron_expr": "0 4 * * *",
        "metadata": {
            "title": "Ley General del Sistema Financiero y del Sistema de Seguros (Ley 26702)",
            "year": 1996,
            "issuer": "Congreso",
        },
    },
    {
        "name": "ley-28587-proteccion-consumidor-servicios-financieros",
        "url": "https://www.leyes.congreso.gob.pe/Documentos/Leyes/28587.pdf",
        "source_type": "direct_pdf",
        "domain": "tasas_intereses",
        "document_type": "ley",
        "cron_expr": "10 4 * * *",
        "metadata": {
            "title": "Ley Complementaria a la Ley de Protección al Consumidor en Materia de Servicios Financieros (Ley 28587)",
            "year": 2005,
            "issuer": "Congreso",
        },
    },
    {
        "name": "ley-29571-codigo-proteccion-consumidor-cap-v",
        "url": "https://www2.congreso.gob.pe/sicr/cendocbib/con4_uibd.nsf/3DA3DB413B41B94E05257A07005F8EE5/%24FILE/29571_CapV.pdf",
        "source_type": "direct_pdf",
        "domain": "tasas_intereses",
        "document_type": "ley",
        "cron_expr": "15 4 * * *",
        "metadata": {
            "title": "Código de Protección y Defensa del Consumidor — Capítulo V (servicios financieros)",
            "year": 2010,
            "issuer": "Congreso",
        },
    },
]


# ============================================================================
# SUNAT — placeholder (se agregará en próximas iteraciones)
# ============================================================================

SUNAT = [
    # NOTA: Normas tributarias relevantes a banca (intereses, IGV, etc.)
    # Agregar conforme se identifiquen.
]


# ============================================================================
# Catálogo agregado
# ============================================================================

CATALOGO_COMPLETO: list[dict] = SBS + BCRP + SMV + INDECOPI + LEYES + SUNAT


def listar_por_issuer() -> dict[str, list[dict]]:
    """Agrupa fuentes por institución emisora."""
    grupos: dict[str, list[dict]] = {}
    for fuente in CATALOGO_COMPLETO:
        issuer = fuente.get("metadata", {}).get("issuer", "Otros")
        grupos.setdefault(issuer, []).append(fuente)
    return grupos


def listar_por_dominio() -> dict[str, list[dict]]:
    """Agrupa fuentes por dominio temático."""
    grupos: dict[str, list[dict]] = {}
    for fuente in CATALOGO_COMPLETO:
        dom = fuente.get("domain", "otros")
        grupos.setdefault(dom, []).append(fuente)
    return grupos


def stats() -> dict:
    """Resumen del catálogo."""
    grupos_issuer = listar_por_issuer()
    grupos_dominio = listar_por_dominio()
    return {
        "total_fuentes": len(CATALOGO_COMPLETO),
        "por_institucion": {k: len(v) for k, v in grupos_issuer.items()},
        "por_dominio": {k: len(v) for k, v in grupos_dominio.items()},
    }
