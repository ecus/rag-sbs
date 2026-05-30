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
    # ===== Expansión 2026-05 (lote 2) =====
    {
        "name": "res-sbs-5570-2019-revolvente-factor-conversion",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/1877/v1.0/Adjuntos/5570-2019.R.pdf",
        "source_type": "direct_pdf",
        "domain": "riesgo_credito",
        "document_type": "resolucion",
        "cron_expr": "25 5 * * *",
        "metadata": {
            "title": "Modificación Reglamento Deudor + Factor Conversión Crediticia",
            "resolution_number": "5570-2019",
            "year": 2019,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-6285-2013-sobreendeudamiento-consumo",
        "url": "https://intranet2.sbs.gob.pe/intranet/INT_CN/DV_INT_CN/714/v1.0/Adjuntos/6285-2013.r.pdf",
        "source_type": "direct_pdf",
        "domain": "riesgo_credito",
        "document_type": "resolucion",
        "cron_expr": "30 5 * * *",
        "metadata": {
            "title": "Reglamento para la Gestión del Riesgo de Sobreendeudamiento de Consumo",
            "resolution_number": "6285-2013",
            "year": 2013,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-6523-2013-tarjetas-credito-debito",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/718/v6.0/Adjuntos/6523-2013.R.pdf",
        "source_type": "direct_pdf",
        "domain": "ti_seguridad",
        "document_type": "resolucion",
        "cron_expr": "35 5 * * *",
        "metadata": {
            "title": "Reglamento de Tarjetas de Crédito y Débito",
            "resolution_number": "6523-2013",
            "year": 2013,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-6328-2009-reglamento-auditoria-interna",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/715/v3.0/Adjuntos/6328-2009.pdf",
        "source_type": "direct_pdf",
        "domain": "gobierno",
        "document_type": "resolucion",
        "cron_expr": "40 5 * * *",
        "metadata": {
            "title": "Reglamento de Auditoría Interna",
            "resolution_number": "6328-2009",
            "year": 2009,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-41-2005-riesgo-operacional-mes",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/1369/v1.0/adjuntos/0041-2005.r.pdf",
        "source_type": "direct_pdf",
        "domain": "riesgo_operacional",
        "document_type": "resolucion",
        "cron_expr": "45 5 * * *",
        "metadata": {
            "title": "Resolución SBS 41-2005 (riesgo operacional / MES)",
            "resolution_number": "41-2005",
            "year": 2005,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-1928-2015-mod-gobierno-corporativo",
        "url": "https://intranet2.sbs.gob.pe/intranet/INT_CN/DV_INT_CN/1660/v1.0/Adjuntos/1928-2015.r.pdf",
        "source_type": "direct_pdf",
        "domain": "gobierno",
        "document_type": "resolucion",
        "cron_expr": "50 5 * * *",
        "metadata": {
            "title": "Modificación Reglamento de Gobierno Corporativo",
            "resolution_number": "1928-2015",
            "year": 2015,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-1049-2021-operaciones-permitidas",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/2062/v1.0/Adjuntos/1049-2021.doc.pdf",
        "source_type": "direct_pdf",
        "domain": "operaciones_estructuradas",
        "document_type": "resolucion",
        "cron_expr": "55 5 * * *",
        "metadata": {
            "title": "Reglamento de Operaciones de las Empresas del Sistema Financiero",
            "resolution_number": "1049-2021",
            "year": 2021,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-2755-2018",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/1790/v2.0/Adjuntos/2755-2018.R.pdf",
        "source_type": "direct_pdf",
        "domain": "riesgo_credito",
        "document_type": "resolucion",
        "cron_expr": "0 6 * * *",
        "metadata": {
            "title": "Resolución SBS 2755-2018",
            "resolution_number": "2755-2018",
            "year": 2018,
            "issuer": "SBS",
        },
    },
    # ===== Expansión 2026-05 (lote 3) =====
    {
        "name": "res-sbs-877-2020-mod-riesgo-operacional",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/1894/v2.0/Adjuntos/877-2020.R.pdf",
        "source_type": "direct_pdf",
        "domain": "riesgo_operacional",
        "document_type": "resolucion",
        "cron_expr": "5 6 * * *",
        "metadata": {
            "title": "Modifica Reglamento Riesgo Operacional 2116-2009",
            "resolution_number": "877-2020",
            "year": 2020,
            "issuer": "SBS",
        },
    },
    {
        "name": "circ-sbs-g-139-2009-continuidad-negocio",
        "url": "https://www.sbs.gob.pe/Portals/0/jer/Auto_Nuevas_Empresas/Normas_Comunes/10.%20Gesti%C3%B3n%20de%20la%20Continuidad%20de%20Negocios_Circ.%20SBS%20G-139-2009.pdf",
        "source_type": "direct_pdf",
        "domain": "riesgo_operacional",
        "document_type": "circular",
        "cron_expr": "10 6 * * *",
        "metadata": {
            "title": "Circular SBS G-139-2009 — Gestión de Continuidad del Negocio",
            "resolution_number": "G-139-2009",
            "year": 2009,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-2660-2015-plaft-v2",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/1540/v2.0/Adjuntos/2660-2015.r.pdf",
        "source_type": "direct_pdf",
        "domain": "laft",
        "document_type": "resolucion",
        "cron_expr": "15 6 * * *",
        "metadata": {
            "title": "Reglamento Gestión Riesgos LAFT (versión 2015, predecesora 789-2018)",
            "resolution_number": "2660-2015",
            "year": 2015,
            "issuer": "SBS",
        },
    },
    {
        "name": "res-sbs-3201-2013-apertura-sucursales",
        "url": "https://intranet2.sbs.gob.pe/intranet/INT_CN/DV_INT_CN/885/v2.0/Adjuntos/3201-2013.r.pdf",
        "source_type": "direct_pdf",
        "domain": "operaciones_estructuradas",
        "document_type": "resolucion",
        "cron_expr": "20 6 * * *",
        "metadata": {
            "title": "Reglamento Apertura, Conversión, Traslado y Cierre de Oficinas",
            "resolution_number": "3201-2013",
            "year": 2013,
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
    {
        "name": "ley-30822-coopac",
        "url": "https://www.mef.gob.pe/es/por-instrumento/ley/17927-ley-30822/file",
        "source_type": "direct_pdf",
        "domain": "legal",
        "document_type": "ley",
        "cron_expr": "20 4 * * *",
        "metadata": {
            "title": "Ley 30822 — Régimen de las Cooperativas de Ahorro y Crédito (COOPAC)",
            "year": 2018,
            "issuer": "Congreso",
        },
    },
    {
        "name": "ley-31143-antiusura",
        "url": "https://img.lpderecho.pe/wp-content/uploads/2021/03/Ley-31143-LP.pdf",
        "source_type": "direct_pdf",
        "domain": "tasas_intereses",
        "document_type": "ley",
        "cron_expr": "25 4 * * *",
        "metadata": {
            "title": "Ley 31143 — Protección contra la Usura (modifica Ley 28587)",
            "year": 2021,
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
FUENTES_CURADAS_V2 = [
    {'name': 'res-sbs-11356-2008', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/1097/v6.0/Adjuntos/11356-2008.r.pdf', 'source_type': 'direct_pdf', 'domain': 'riesgo_credito', 'document_type': 'resolucion', 'cron_expr': '0 3 * * *', 'metadata': {'title': 'Resolución SBS N° 11356-2008 — Reglamento para Evaluación y Clasificación del Deudor y Exigencia de Provisiones', 'issuer': 'SBS', 'year': 2008, 'resolution_number': '11356-2008'}},
    {'name': 'res-sbs-3780-2011', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/774/v5.0/Adjuntos/3780-2011.R.pdf', 'source_type': 'direct_pdf', 'domain': 'riesgo_credito', 'document_type': 'resolucion', 'cron_expr': '1 3 * * *', 'metadata': {'title': 'Resolución SBS N° 3780-2011 — Reglamento de Gestión de Riesgo de Crédito', 'issuer': 'SBS', 'year': 2011, 'resolution_number': '3780-2011'}},
    {'name': 'res-sbs-14354-2009', 'url': 'https://www.sbs.gob.pe/Portals/0/jer/Auto_Nuevas_Empresas/Sistema_Financiero/9.%20Reg.%20de%20Requerimiento%20de%20Patrimonio%20Efectivo%20por%20Riesgo%20de%20Cr%C3%A9dito_Res.%20SBS%20N%C2%B0%2014354-2009.pdf', 'source_type': 'direct_pdf', 'domain': 'riesgo_credito', 'document_type': 'resolucion', 'cron_expr': '4 3 * * *', 'metadata': {'title': 'Resolución SBS N° 14354-2009 — Reglamento de Patrimonio Efectivo por Riesgo de Crédito', 'issuer': 'SBS', 'year': 2009, 'resolution_number': '14354-2009'}},
    {'name': 'res-sbs-3240-2023', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/2305/v1.0/Adjuntos/3240-2023.R.pdf', 'source_type': 'direct_pdf', 'domain': 'riesgo_credito', 'document_type': 'resolucion', 'cron_expr': '6 3 * * *', 'metadata': {'title': 'Resolución SBS N° 3240-2023 — Disposiciones de Riesgo de Crédito', 'issuer': 'SBS', 'year': 2023, 'resolution_number': '3240-2023'}},
    {'name': 'res-sbs-332-2023', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/2245/v1.0/Adjuntos/332-2023.R.pdf', 'source_type': 'direct_pdf', 'domain': 'riesgo_credito', 'document_type': 'resolucion', 'cron_expr': '8 3 * * *', 'metadata': {'title': 'Resolución SBS N° 332-2023 — Reglamento de Seguros de Crédito y Fianza', 'issuer': 'SBS', 'year': 2023, 'resolution_number': '332-2023'}},
    {'name': 'res-sbs-689-2023', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/2255/v1.0/Adjuntos/689-2023.R.pdf', 'source_type': 'direct_pdf', 'domain': 'riesgo_credito', 'document_type': 'resolucion', 'cron_expr': '9 3 * * *', 'metadata': {'title': 'Resolución SBS N° 689-2023 — Modificación Patrimonio Efectivo', 'issuer': 'SBS', 'year': 2023, 'resolution_number': '689-2023'}},
    {'name': 'res-sbs-2917-2023', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/2296/v1.0/Adjuntos/2917-2023.r.pdf', 'source_type': 'direct_pdf', 'domain': 'riesgo_credito', 'document_type': 'resolucion', 'cron_expr': '10 3 * * *', 'metadata': {'title': 'Resolución SBS N° 2917-2023 — Programa Reactiva Perú / Garantías', 'issuer': 'SBS', 'year': 2023, 'resolution_number': '2917-2023'}},
    {'name': 'res-sbs-3594-2023', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/2309/v1.0/Adjuntos/3594-2023.R.pdf', 'source_type': 'direct_pdf', 'domain': 'riesgo_credito', 'document_type': 'resolucion', 'cron_expr': '11 3 * * *', 'metadata': {'title': 'Resolución SBS N° 3594-2023 — Disposiciones complementarias riesgo de crédito', 'issuer': 'SBS', 'year': 2023, 'resolution_number': '3594-2023'}},
    {'name': 'res-sbs-3421-2023', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/2308/v1.0/Adjuntos/3421-2023.R.pdf', 'source_type': 'direct_pdf', 'domain': 'riesgo_credito', 'document_type': 'resolucion', 'cron_expr': '12 3 * * *', 'metadata': {'title': 'Resolución SBS N° 3421-2023 — Modificaciones a riesgo de crédito', 'issuer': 'SBS', 'year': 2023, 'resolution_number': '3421-2023'}},
    {'name': 'res-sbs-774-2025', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/2482/v2.0/Adjuntos/R.0774-2025.pdf', 'source_type': 'direct_pdf', 'domain': 'riesgo_credito', 'document_type': 'resolucion', 'cron_expr': '13 3 * * *', 'metadata': {'title': 'Resolución SBS N° 774-2025 — Patrimonio Efectivo por Riesgo de Crédito (actualización)', 'issuer': 'SBS', 'year': 2025, 'resolution_number': '774-2025'}},
    {'name': 'res-sbs-556-2025', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/2480/v1.0/Adjuntos/556-2025.R.pdf', 'source_type': 'direct_pdf', 'domain': 'riesgo_credito', 'document_type': 'resolucion', 'cron_expr': '15 3 * * *', 'metadata': {'title': 'Resolución SBS N° 556-2025 — Modificación riesgos sistema financiero', 'issuer': 'SBS', 'year': 2025, 'resolution_number': '556-2025'}},
    {'name': 'res-sbs-1689-2025', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/2497/v1.0/Adjuntos/01689-2025.R.pdf', 'source_type': 'direct_pdf', 'domain': 'riesgo_credito', 'document_type': 'resolucion', 'cron_expr': '16 3 * * *', 'metadata': {'title': 'Resolución SBS N° 1689-2025 — Disposiciones para empresas del sistema financiero', 'issuer': 'SBS', 'year': 2025, 'resolution_number': '1689-2025'}},
    {'name': 'res-sbs-890-2025', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/2484/v1.0/Adjuntos/Resoluci%C3%B3n%20SBS%20N%C2%B0%20890-2025.pdf', 'source_type': 'direct_pdf', 'domain': 'riesgo_credito', 'document_type': 'resolucion', 'cron_expr': '17 3 * * *', 'metadata': {'title': 'Resolución SBS N° 890-2025 — Disposiciones complementarias', 'issuer': 'SBS', 'year': 2025, 'resolution_number': '890-2025'}},
    {'name': 'res-sbs-3028-2010', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/874/v1.0/Adjuntos/3028-2010.r.pdf', 'source_type': 'direct_pdf', 'domain': 'riesgo_credito', 'document_type': 'resolucion', 'cron_expr': '18 3 * * *', 'metadata': {'title': 'Resolución SBS N° 3028-2010 — Modificación cartera de créditos', 'issuer': 'SBS', 'year': 2010, 'resolution_number': '3028-2010'}},
    {'name': 'res-sbs-4221-2023', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/2322/v1.0/Adjuntos/4221-2023.r.pdf', 'source_type': 'direct_pdf', 'domain': 'riesgo_credito', 'document_type': 'resolucion', 'cron_expr': '19 3 * * *', 'metadata': {'title': 'Resolución SBS N° 4221-2023 — Nuevo Reglamento para Gestión del Riesgo de Liquidez', 'issuer': 'SBS', 'year': 2023, 'resolution_number': '4221-2023'}},
    {'name': 'res-sbs-3954-2022', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/2228/v1.0/Adjuntos/3954-2022.R.pdf', 'source_type': 'direct_pdf', 'domain': 'riesgo_credito', 'document_type': 'resolucion', 'cron_expr': '20 3 * * *', 'metadata': {'title': 'Resolución SBS N° 3954-2022 — Modificación riesgo de liquidez', 'issuer': 'SBS', 'year': 2022, 'resolution_number': '3954-2022'}},
    {'name': 'res-sbs-3953-2022', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/2227/v1.0/Adjuntos/3953-2022.R.pdf', 'source_type': 'direct_pdf', 'domain': 'riesgo_credito', 'document_type': 'resolucion', 'cron_expr': '21 3 * * *', 'metadata': {'title': 'Resolución SBS N° 3953-2022 — Modificación riesgos financieros', 'issuer': 'SBS', 'year': 2022, 'resolution_number': '3953-2022'}},
    {'name': 'res-sbs-2354-2021', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/2107/v1.0/Adjuntos/2354-2021.doc.pdf', 'source_type': 'direct_pdf', 'domain': 'riesgo_operacional', 'document_type': 'resolucion', 'cron_expr': '23 3 * * *', 'metadata': {'title': 'Resolución SBS N° 2354-2021 — Disposiciones de gestión de riesgo operacional', 'issuer': 'SBS', 'year': 2021, 'resolution_number': '2354-2021'}},
    {'name': 'res-sbs-211-2021', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/2033/v1.0/Adjuntos/211-2021.R.pdf', 'source_type': 'direct_pdf', 'domain': 'riesgo_operacional', 'document_type': 'resolucion', 'cron_expr': '24 3 * * *', 'metadata': {'title': 'Resolución SBS N° 211-2021 — Continuidad del negocio / riesgo operacional', 'issuer': 'SBS', 'year': 2021, 'resolution_number': '211-2021'}},
    {'name': 'res-sbs-4906-2017', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/1753/v1.0/Adjuntos/4906-2017.pdf', 'source_type': 'direct_pdf', 'domain': 'riesgo_operacional', 'document_type': 'resolucion', 'cron_expr': '25 3 * * *', 'metadata': {'title': 'Resolución SBS N° 4906-2017 — Reglamento de Riesgos de Mercado', 'issuer': 'SBS', 'year': 2017, 'resolution_number': '4906-2017'}},
    {'name': 'res-sbs-504-2021', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/2046/v4.0/Adjuntos/504-2021.R.pdf', 'source_type': 'direct_pdf', 'domain': 'ti_seguridad', 'document_type': 'resolucion', 'cron_expr': '26 3 * * *', 'metadata': {'title': 'Resolución SBS N° 504-2021 — Reglamento de Seguridad de la Información y Ciberseguridad', 'issuer': 'SBS', 'year': 2021, 'resolution_number': '504-2021'}},
    {'name': 'res-sbs-504-2021-anexos', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/2046/v1.0/Adjuntos/504-2021.doc.pdf', 'source_type': 'direct_pdf', 'domain': 'ti_seguridad', 'document_type': 'resolucion', 'cron_expr': '28 3 * * *', 'metadata': {'title': 'Resolución SBS N° 504-2021 — Anexos Reglamento Ciberseguridad', 'issuer': 'SBS', 'year': 2021, 'resolution_number': '504-2021'}},
    {'name': 'circ-sbs-g-140-2009', 'url': 'https://www.sbs.gob.pe/Portals/0/jer/Auto_Nuevas_Empresas/Normas_Comunes/9.%20Gesti%C3%B3n%20de%20la%20Seguridad%20de%20la%20Informaci%C3%B3n_Circ.%20SBS%20G-140-2009.pdf', 'source_type': 'direct_pdf', 'domain': 'ti_seguridad', 'document_type': 'circular', 'cron_expr': '29 3 * * *', 'metadata': {'title': 'Circular SBS G-140-2009 — Gestión de la Seguridad de la Información', 'issuer': 'SBS', 'year': 2009}},
    {'name': 'res-sbs-3966-2018', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/1800/v1.0/Adjuntos/3966-2018.pdf', 'source_type': 'direct_pdf', 'domain': 'ti_seguridad', 'document_type': 'resolucion', 'cron_expr': '30 3 * * *', 'metadata': {'title': 'Resolución SBS N° 3966-2018 — Modificaciones a normas de TI / Conducta de Mercado', 'issuer': 'SBS', 'year': 2018, 'resolution_number': '3966-2018'}},
    {'name': 'res-sbs-6523-2013-v3', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/718/v3.0/Adjuntos/6523-2013.pdf', 'source_type': 'direct_pdf', 'domain': 'ti_seguridad', 'document_type': 'resolucion', 'cron_expr': '32 3 * * *', 'metadata': {'title': 'Resolución SBS N° 6523-2013 (v3) — Tarjetas de Crédito y Débito', 'issuer': 'SBS', 'year': 2013, 'resolution_number': '6523-2013'}},
    {'name': 'res-sbs-272-2017', 'url': 'https://www.sbs.gob.pe/Portals/0/jer/Auto_Nuevas_Empresas/Normas_Comunes/5.%20Reg.%20de%20Gobierno%20Corporativo_Res.%20SBS%20N%C2%B0%20272-2017.pdf', 'source_type': 'direct_pdf', 'domain': 'gobierno', 'document_type': 'resolucion', 'cron_expr': '35 3 * * *', 'metadata': {'title': 'Resolución SBS N° 272-2017 — Reglamento de Gobierno Corporativo y Gestión Integral de Riesgos', 'issuer': 'SBS', 'year': 2017, 'resolution_number': '272-2017'}},
    {'name': 'res-sbs-37-2008', 'url': 'https://intranet2.sbs.gob.pe/intranet/int_cn/dv_int_cn/1363/v3.0/Adjuntos/0037-2008.r.pdf', 'source_type': 'direct_pdf', 'domain': 'gobierno', 'document_type': 'resolucion', 'cron_expr': '36 3 * * *', 'metadata': {'title': 'Resolución SBS N° 37-2008 — Reglamento de la Gestión Integral de Riesgos', 'issuer': 'SBS', 'year': 2008, 'resolution_number': '37-2008'}},
    {'name': 'res-sbs-11699-2008', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/1134/v24.0/Adjuntos/11699-2008.R.pdf', 'source_type': 'direct_pdf', 'domain': 'gobierno', 'document_type': 'resolucion', 'cron_expr': '37 3 * * *', 'metadata': {'title': 'Resolución SBS N° 11699-2008 — Reglamento de Auditoría Interna', 'issuer': 'SBS', 'year': 2008, 'resolution_number': '11699-2008'}},
    {'name': 'res-sbs-17026-2010', 'url': 'https://www.sbs.gob.pe/Portals/0/jer/pf_normatividad/20160719_Res-17026-2010.pdf', 'source_type': 'direct_pdf', 'domain': 'gobierno', 'document_type': 'resolucion', 'cron_expr': '39 3 * * *', 'metadata': {'title': 'Resolución SBS N° 17026-2010 — Reglamento de Auditoría Externa', 'issuer': 'SBS', 'year': 2010, 'resolution_number': '17026-2010'}},
    {'name': 'res-sbs-6941-2008', 'url': 'https://intranet2.sbs.gob.pe/intranet/INT_CN/DV_INT_CN/742/v1.0/Adjuntos/6941-2008.r.pdf', 'source_type': 'direct_pdf', 'domain': 'gobierno', 'document_type': 'resolucion', 'cron_expr': '40 3 * * *', 'metadata': {'title': 'Resolución SBS N° 6941-2008 — Normas complementarias gobierno corporativo', 'issuer': 'SBS', 'year': 2008, 'resolution_number': '6941-2008'}},
    {'name': 'res-sbs-53-2023', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/2240/v1.0/Adjuntos/0053-2023.R.pdf', 'source_type': 'direct_pdf', 'domain': 'gobierno', 'document_type': 'resolucion', 'cron_expr': '41 3 * * *', 'metadata': {'title': 'Resolución SBS N° 53-2023 — Reglamento de Gestión de Riesgos de Modelo', 'issuer': 'SBS', 'year': 2023, 'resolution_number': '53-2023'}},
    {'name': 'res-sbs-789-2018', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/1766/v1.0/Adjuntos/789-2018.pdf', 'source_type': 'direct_pdf', 'domain': 'laft', 'document_type': 'resolucion', 'cron_expr': '43 3 * * *', 'metadata': {'title': 'Resolución SBS N° 789-2018 — Norma para Prevención del Lavado de Activos y FT (UIF-Perú)', 'issuer': 'SBS', 'year': 2018, 'resolution_number': '789-2018'}},
    {'name': 'res-sbs-4705-2017', 'url': 'https://intranet2.sbs.gob.pe/intranet/INT_CN/DV_INT_CN/1748/v1.0/Adjuntos/4705-2017.pdf', 'source_type': 'direct_pdf', 'domain': 'laft', 'document_type': 'resolucion', 'cron_expr': '44 3 * * *', 'metadata': {'title': 'Resolución SBS N° 4705-2017 — Modifica Reglamento de Gestión de Riesgos LAFT', 'issuer': 'SBS', 'year': 2017, 'resolution_number': '4705-2017'}},
    {'name': 'res-sbs-4706-2017', 'url': 'https://intranet2.sbs.gob.pe/intranet/INT_CN/DV_INT_CN/1750/v2.0/Adjuntos/4706-2017.r.pdf', 'source_type': 'direct_pdf', 'domain': 'laft', 'document_type': 'resolucion', 'cron_expr': '45 3 * * *', 'metadata': {'title': 'Resolución SBS N° 4706-2017 — Disposiciones complementarias LAFT', 'issuer': 'SBS', 'year': 2017, 'resolution_number': '4706-2017'}},
    {'name': 'res-sbs-2660-2015', 'url': 'https://www.sbs.gob.pe/Portals/0/jer/Auto_Nuevas_Empresas/Normas_Comunes/7.%20Reg.%20Gesti%C3%B3n%20de%20Riesgos%20de%20Lavado%20de%20Activos_Res.%20SBS%20N%C2%B0%202660-2015.pdf', 'source_type': 'direct_pdf', 'domain': 'laft', 'document_type': 'resolucion', 'cron_expr': '46 3 * * *', 'metadata': {'title': 'Resolución SBS N° 2660-2015 — Reglamento de Gestión de Riesgos LAFT', 'issuer': 'SBS', 'year': 2015, 'resolution_number': '2660-2015'}},
    {'name': 'ley-27693-concordada', 'url': 'https://www.sbs.gob.pe/Portals/5/jer/NORM_GEN_LAFT/19112018_Version_Concordada_Ley%2027693.pdf', 'source_type': 'direct_pdf', 'domain': 'laft', 'document_type': 'ley', 'cron_expr': '47 3 * * *', 'metadata': {'title': 'Ley N° 27693 — Versión Concordada UIF-Perú', 'issuer': 'SBS'}},
    {'name': 'dl-1249-laft', 'url': 'https://www.sbs.gob.pe/Portals/5/jer/norm_gen_laft/DL1249.pdf', 'source_type': 'direct_pdf', 'domain': 'laft', 'document_type': 'decreto_legislativo', 'cron_expr': '48 3 * * *', 'metadata': {'title': 'Decreto Legislativo N° 1249 — Lucha contra LAFT', 'issuer': 'SBS'}},
    {'name': 'res-sbs-3274-2017', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/1731/v7.0/Adjuntos/3274-2017%20R%20mod.doc.pdf', 'source_type': 'direct_pdf', 'domain': 'proteccion_consumidor', 'document_type': 'resolucion', 'cron_expr': '49 3 * * *', 'metadata': {'title': 'Resolución SBS N° 3274-2017 — Reglamento de Gestión de Conducta de Mercado del Sistema Financiero', 'issuer': 'SBS', 'year': 2017, 'resolution_number': '3274-2017'}},
    {'name': 'res-sbs-3274-2017-v3', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/1731/v3.0/Adjuntos/3274-2017.R.pdf', 'source_type': 'direct_pdf', 'domain': 'proteccion_consumidor', 'document_type': 'resolucion', 'cron_expr': '50 3 * * *', 'metadata': {'title': 'Resolución SBS N° 3274-2017 (v3) — Conducta de Mercado', 'issuer': 'SBS', 'year': 2017, 'resolution_number': '3274-2017'}},
    {'name': 'res-sbs-3748-2021', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/2138/v1.0/Adjuntos/3748-2021.R.pdf', 'source_type': 'direct_pdf', 'domain': 'proteccion_consumidor', 'document_type': 'resolucion', 'cron_expr': '51 3 * * *', 'metadata': {'title': 'Resolución SBS N° 3748-2021 — Modificación Conducta de Mercado', 'issuer': 'SBS', 'year': 2021, 'resolution_number': '3748-2021'}},
    {'name': 'res-sbs-4143-2019', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/1865/v5.0/Adjuntos/4143-2019.R.pdf', 'source_type': 'direct_pdf', 'domain': 'proteccion_consumidor', 'document_type': 'resolucion', 'cron_expr': '53 3 * * *', 'metadata': {'title': 'Resolución SBS N° 4143-2019 — Reglamento de Conducta de Mercado del Sistema de Seguros', 'issuer': 'SBS', 'year': 2019, 'resolution_number': '4143-2019'}},
    {'name': 'res-sbs-4143-2019-v1', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/1865/v1.0/Adjuntos/4143-2019.R.pdf', 'source_type': 'direct_pdf', 'domain': 'proteccion_consumidor', 'document_type': 'resolucion', 'cron_expr': '54 3 * * *', 'metadata': {'title': 'Resolución SBS N° 4143-2019 (v1) — Conducta de Mercado Seguros', 'issuer': 'SBS', 'year': 2019, 'resolution_number': '4143-2019'}},
    {'name': 'res-sbs-4036-2022', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/2230/v1.0/Adjuntos/4036-2022.r.pdf', 'source_type': 'direct_pdf', 'domain': 'proteccion_consumidor', 'document_type': 'resolucion', 'cron_expr': '55 3 * * *', 'metadata': {'title': 'Resolución SBS N° 4036-2022 — Reglamento de Gestión de Reclamos y Requerimientos', 'issuer': 'SBS', 'year': 2022, 'resolution_number': '4036-2022'}},
    {'name': 'res-sbs-4036-2022-anexo', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/2230/v1.0/Anexos/4036-2022(ANEXO).R.pdf', 'source_type': 'direct_pdf', 'domain': 'proteccion_consumidor', 'document_type': 'resolucion', 'cron_expr': '56 3 * * *', 'metadata': {'title': 'Resolución SBS N° 4036-2022 — Anexos Reclamos y Requerimientos', 'issuer': 'SBS', 'year': 2022, 'resolution_number': '4036-2022'}},
    {'name': 'res-sbs-2304-2020', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/1991/v1.0/adjuntos/2304-2020.r.pdf', 'source_type': 'direct_pdf', 'domain': 'proteccion_consumidor', 'document_type': 'resolucion', 'cron_expr': '57 3 * * *', 'metadata': {'title': 'Resolución SBS N° 2304-2020 — Modificación Conducta de Mercado', 'issuer': 'SBS', 'year': 2020, 'resolution_number': '2304-2020'}},
    {'name': 'res-sbs-2154-2020', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/1971/v1.0/Adjuntos/2154-2020.R.pdf', 'source_type': 'direct_pdf', 'domain': 'proteccion_consumidor', 'document_type': 'resolucion', 'cron_expr': '58 3 * * *', 'metadata': {'title': 'Resolución SBS N° 2154-2020 — Disposiciones de Protección al Consumidor', 'issuer': 'SBS', 'year': 2020, 'resolution_number': '2154-2020'}},
    {'name': 'res-sbs-2891-2018', 'url': 'https://intranet2.sbs.gob.pe/dv_int_cn/1794/v1.0/Adjuntos/2891-2018.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'resolucion', 'cron_expr': '59 3 * * *', 'metadata': {'title': 'Resolución SBS N° 2891-2018 — Reglamento de Cuentas Básicas', 'issuer': 'SBS', 'year': 2018, 'resolution_number': '2891-2018'}},
    {'name': 'res-sbs-465-2017', 'url': 'https://intranet2.sbs.gob.pe/intranet/INT_CN/DV_INT_CN/1711/v1.0/Adjuntos/465-2017.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'resolucion', 'cron_expr': '0 3 * * *', 'metadata': {'title': 'Resolución SBS N° 465-2017 — Modificación Reglamento Operaciones con Dinero Electrónico', 'issuer': 'SBS', 'year': 2017, 'resolution_number': '465-2017'}},
    {'name': 'res-sbs-661-2021', 'url': 'https://www.sbs.gob.pe/Portals/0/jer/Rela_COOPAC_Disol/Res661-2021.pdf', 'source_type': 'direct_pdf', 'domain': 'gobierno', 'document_type': 'resolucion', 'cron_expr': '1 3 * * *', 'metadata': {'title': 'Resolución SBS N° 661-2021 — Disposiciones COOPAC', 'issuer': 'SBS', 'year': 2021, 'resolution_number': '661-2021'}},
    {'name': 'reg-registro-coopac', 'url': 'https://www.sbs.gob.pe/Portals/0/jer/SUPER_COOPAC/Reglamento%20de%20Registro%20Nacional%20de%20COOPAC.pdf', 'source_type': 'direct_pdf', 'domain': 'gobierno', 'document_type': 'reglamento', 'cron_expr': '2 3 * * *', 'metadata': {'title': 'Reglamento del Registro Nacional de COOPAC', 'issuer': 'SBS'}},
    {'name': 'circ-bcrp-0002-2024', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2024/circular-0002-2024-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'circular', 'cron_expr': '3 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0002-2024 — Reglamento de Acreditación de Poderes', 'issuer': 'BCRP', 'year': 2024, 'resolution_number': '0002-2024'}},
    {'name': 'circ-bcrp-0003-2024', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2024/circular-0003-2024-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'tasas_intereses', 'document_type': 'circular', 'cron_expr': '4 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0003-2024 — Índice de reajuste diario', 'issuer': 'BCRP', 'year': 2024, 'resolution_number': '0003-2024'}},
    {'name': 'circ-bcrp-0006-2024', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2024/circular-0006-2024-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'circular', 'cron_expr': '5 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0006-2024 — Reporte instrumentos y canales de pago', 'issuer': 'BCRP', 'year': 2024, 'resolution_number': '0006-2024'}},
    {'name': 'circ-bcrp-0008-2024', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2024/circular-0008-2024-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'tasas_intereses', 'document_type': 'circular', 'cron_expr': '6 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0008-2024 — Disposiciones de encaje en moneda nacional', 'issuer': 'BCRP', 'year': 2024, 'resolution_number': '0008-2024'}},
    {'name': 'circ-bcrp-0008-2024-anexos', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2024/circular-0008-2024-bcrp-reportes-y-anexos.pdf', 'source_type': 'direct_pdf', 'domain': 'tasas_intereses', 'document_type': 'circular', 'cron_expr': '7 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0008-2024 — Reportes y Anexos (encaje)', 'issuer': 'BCRP', 'year': 2024, 'resolution_number': '0008-2024'}},
    {'name': 'circ-bcrp-0009-2024', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2024/circular-0009-2024-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'circular', 'cron_expr': '8 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0009-2024 — Reglamento niveles de calidad Servicios de Pago', 'issuer': 'BCRP', 'year': 2024, 'resolution_number': '0009-2024'}},
    {'name': 'circ-bcrp-0011-2024', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2024/circular-0011-2024-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'circular', 'cron_expr': '9 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0011-2024 — Reglamento Pilotos Innovación Dinero Digital', 'issuer': 'BCRP', 'year': 2024, 'resolution_number': '0011-2024'}},
    {'name': 'circ-bcrp-0012-2024', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2024/circular-0012-2024-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'circular', 'cron_expr': '10 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0012-2024 — Disposiciones sistema de pagos', 'issuer': 'BCRP', 'year': 2024, 'resolution_number': '0012-2024'}},
    {'name': 'circ-bcrp-0017-2024-anexo', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2024/circular-0017-2024-bcrp-anexo.pdf', 'source_type': 'direct_pdf', 'domain': 'tasas_intereses', 'document_type': 'circular', 'cron_expr': '11 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0017-2024 — Anexo', 'issuer': 'BCRP', 'year': 2024, 'resolution_number': '0017-2024'}},
    {'name': 'circ-bcrp-0020-2024', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2024/circular-0020-2024-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'circular', 'cron_expr': '12 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0020-2024 — Reglamento Empresas de Servicios de Canje', 'issuer': 'BCRP', 'year': 2024, 'resolution_number': '0020-2024'}},
    {'name': 'circ-bcrp-0021-2024', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2024/circular-0021-2024-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'circular', 'cron_expr': '13 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0021-2024 — Reglamento Servicio Compensación Transferencias Inmediatas', 'issuer': 'BCRP', 'year': 2024, 'resolution_number': '0021-2024'}},
    {'name': 'circ-bcrp-0024-2024', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2024/circular-0024-2024-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'tasas_intereses', 'document_type': 'circular', 'cron_expr': '14 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0024-2024 — Disposiciones BCRP', 'issuer': 'BCRP', 'year': 2024, 'resolution_number': '0024-2024'}},
    {'name': 'circ-bcrp-0032-2024', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2024/circular-0032-2024-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'circular', 'cron_expr': '15 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0032-2024 — Moneda numismática', 'issuer': 'BCRP', 'year': 2024, 'resolution_number': '0032-2024'}},
    {'name': 'circ-bcrp-0011-2023', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2023/circular-0011-2023-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'tasas_intereses', 'document_type': 'circular', 'cron_expr': '16 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0011-2023 — Disposiciones de encaje en moneda extranjera', 'issuer': 'BCRP', 'year': 2023, 'resolution_number': '0011-2023'}},
    {'name': 'circ-bcrp-0013-2023', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2023/circular-0013-2023-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'circular', 'cron_expr': '17 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0013-2023 — Modificación Interoperabilidad Servicios de Pago', 'issuer': 'BCRP', 'year': 2023, 'resolution_number': '0013-2023'}},
    {'name': 'circ-bcrp-0024-2023', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2023/circular-0024-2023-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'circular', 'cron_expr': '18 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0024-2023 — Moneda Serie Constructores República (Valdés)', 'issuer': 'BCRP', 'year': 2023, 'resolution_number': '0024-2023'}},
    {'name': 'circ-bcrp-0003-2022', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2022/circular-0003-2022-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'tasas_intereses', 'document_type': 'circular', 'cron_expr': '19 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0003-2022 — Disposiciones de encaje moneda nacional', 'issuer': 'BCRP', 'year': 2022, 'resolution_number': '0003-2022'}},
    {'name': 'circ-bcrp-0005-2022', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2022/circular-0005-2022-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'circular', 'cron_expr': '20 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0005-2022 — Operaciones de Reporte de Créditos con Garantía del Gobierno', 'issuer': 'BCRP', 'year': 2022, 'resolution_number': '0005-2022'}},
    {'name': 'circ-bcrp-0012-2022', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2022/circular-0012-2022-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'circular', 'cron_expr': '21 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0012-2022 — Reglamento del Servicio de Compensación de Transferencias Inmediatas', 'issuer': 'BCRP', 'year': 2022, 'resolution_number': '0012-2022'}},
    {'name': 'circ-bcrp-0016-2022', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2022/circular-0016-2022-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'tasas_intereses', 'document_type': 'circular', 'cron_expr': '22 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0016-2022 — Reportes operaciones cambiarias y derivados financieros', 'issuer': 'BCRP', 'year': 2022, 'resolution_number': '0016-2022'}},
    {'name': 'circ-bcrp-0017-2022', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2022/circular-0017-2022-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'tasas_intereses', 'document_type': 'circular', 'cron_expr': '23 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0017-2022 — Reportes Tasas de Interés Mercado de Dinero', 'issuer': 'BCRP', 'year': 2022, 'resolution_number': '0017-2022'}},
    {'name': 'circ-bcrp-0024-2022', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2022/circular-0024-2022-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'circular', 'cron_expr': '24 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0024-2022 — Reglamento Interoperabilidad Servicios de Pago', 'issuer': 'BCRP', 'year': 2022, 'resolution_number': '0024-2022'}},
    {'name': 'circ-bcrp-0025-2022', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2022/circular-0025-2022-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'tasas_intereses', 'document_type': 'circular', 'cron_expr': '25 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0025-2022 — Disposiciones de encaje en moneda nacional', 'issuer': 'BCRP', 'year': 2022, 'resolution_number': '0025-2022'}},
    {'name': 'circ-bcrp-0027-2022', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2022/circular-0027-2022-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'circular', 'cron_expr': '26 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0027-2022 — Reglamento de Acuerdos de Pago con Tarjetas', 'issuer': 'BCRP', 'year': 2022, 'resolution_number': '0027-2022'}},
    {'name': 'circ-bcrp-0028-2022', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2022/circular-0028-2022-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'circular', 'cron_expr': '27 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0028-2022 — Reglamento Convenio de Pagos y Créditos Recíprocos ALADI', 'issuer': 'BCRP', 'year': 2022, 'resolution_number': '0028-2022'}},
    {'name': 'circ-bcrp-0010-2021', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2021/circular-0010-2021-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'tasas_intereses', 'document_type': 'circular', 'cron_expr': '29 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0010-2021 — Precisiones implementación tasas de interés', 'issuer': 'BCRP', 'year': 2021, 'resolution_number': '0010-2021'}},
    {'name': 'circ-bcrp-0011-2021', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2021/circular-0011-2021-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'circular', 'cron_expr': '30 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0011-2021 — Operaciones de Reporte de Cartera de Créditos', 'issuer': 'BCRP', 'year': 2021, 'resolution_number': '0011-2021'}},
    {'name': 'circ-bcrp-0020-2021', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2021/circular-0020-2021-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'circular', 'cron_expr': '31 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0020-2021 — Reglamento Servicio de Canje de Cheques', 'issuer': 'BCRP', 'year': 2021, 'resolution_number': '0020-2021'}},
    {'name': 'circ-bcrp-0021-2021', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2021/circular-0021-2021-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'circular', 'cron_expr': '32 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0021-2021 — Reglamento Servicio de Compensación de Transferencias', 'issuer': 'BCRP', 'year': 2021, 'resolution_number': '0021-2021'}},
    {'name': 'circ-bcrp-0028-2021', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2021/circular-0028-2021-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'tasas_intereses', 'document_type': 'circular', 'cron_expr': '33 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0028-2021 — Swaps Cambiarios del Banco Central', 'issuer': 'BCRP', 'year': 2021, 'resolution_number': '0028-2021'}},
    {'name': 'circ-bcrp-0029-2021', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2021/circular-0029-2021-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'circular', 'cron_expr': '34 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0029-2021 — Sistema Liquidación Bruta en Tiempo Real', 'issuer': 'BCRP', 'year': 2021, 'resolution_number': '0029-2021'}},
    {'name': 'circ-bcrp-0003-2020', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2020/circular-0003-2020-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'circular', 'cron_expr': '35 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0003-2020 — Reglamento Servicio Pago con Códigos QR', 'issuer': 'BCRP', 'year': 2020, 'resolution_number': '0003-2020'}},
    {'name': 'circ-bcrp-0005-2020', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2020/circular-0005-2020-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'circular', 'cron_expr': '36 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0005-2020 — Reglamento Sistema Liquidación de Valores BCRP', 'issuer': 'BCRP', 'year': 2020, 'resolution_number': '0005-2020'}},
    {'name': 'circ-bcrp-0007-2020', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2020/circular-0007-2020-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'tasas_intereses', 'document_type': 'circular', 'cron_expr': '37 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0007-2020 — Cálculo del tipo de cambio', 'issuer': 'BCRP', 'year': 2020, 'resolution_number': '0007-2020'}},
    {'name': 'circ-bcrp-0016-2020', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2020/circular-0016-2020-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'circular', 'cron_expr': '38 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0016-2020 — Operaciones de Reporte de Valores', 'issuer': 'BCRP', 'year': 2020, 'resolution_number': '0016-2020'}},
    {'name': 'circ-bcrp-0017-2020', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2020/circular-0017-2020-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'circular', 'cron_expr': '39 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0017-2020 — Operaciones Reporte Créditos Garantía Gobierno', 'issuer': 'BCRP', 'year': 2020, 'resolution_number': '0017-2020'}},
    {'name': 'circ-bcrp-0021-2020', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2020/circular-0021-2020-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'circular', 'cron_expr': '40 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0021-2020 — Operaciones de Reporte con Reprogramaciones', 'issuer': 'BCRP', 'year': 2020, 'resolution_number': '0021-2020'}},
    {'name': 'circ-bcrp-0033-2020', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2020/circular-0033-2020-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'circular', 'cron_expr': '41 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0033-2020 — Operaciones de Reporte de Cartera de Créditos', 'issuer': 'BCRP', 'year': 2020, 'resolution_number': '0033-2020'}},
    {'name': 'circ-bcrp-0035-2020', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2020/circular-0035-2020-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'tasas_intereses', 'document_type': 'circular', 'cron_expr': '42 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0035-2020 — Swaps de Tasas de Interés', 'issuer': 'BCRP', 'year': 2020, 'resolution_number': '0035-2020'}},
    {'name': 'circ-bcrp-0036-2020', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2020/circular-0036-2020-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'circular', 'cron_expr': '43 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0036-2020 — Operaciones Condicionadas a Expansión del Crédito', 'issuer': 'BCRP', 'year': 2020, 'resolution_number': '0036-2020'}},
    {'name': 'circ-bcrp-0005-2025', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2025/circular-0005-2025-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'circular', 'cron_expr': '44 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0005-2025 — Modificación niveles de calidad Servicios de Pago', 'issuer': 'BCRP', 'year': 2025, 'resolution_number': '0005-2025'}},
    {'name': 'circ-bcrp-0007-2025', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2025/circular-0007-2025-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'tasas_intereses', 'document_type': 'circular', 'cron_expr': '45 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0007-2025 — Requerimiento información Balanza de Pagos', 'issuer': 'BCRP', 'year': 2025, 'resolution_number': '0007-2025'}},
    {'name': 'circ-bcrp-0008-2025', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2025/circular-0008-2025-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'tasas_intereses', 'document_type': 'circular', 'cron_expr': '46 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0008-2025 — Disposiciones de encaje moneda nacional', 'issuer': 'BCRP', 'year': 2025, 'resolution_number': '0008-2025'}},
    {'name': 'circ-bcrp-0022-2025', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2025/circular-0022-2025-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'circular', 'cron_expr': '47 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0022-2025 — Reglamento General Sistema Nacional de Pagos', 'issuer': 'BCRP', 'year': 2025, 'resolution_number': '0022-2025'}},
    {'name': 'circ-bcrp-0023-2025', 'url': 'https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2025/circular-0023-2025-bcrp.pdf', 'source_type': 'direct_pdf', 'domain': 'tasas_intereses', 'document_type': 'circular', 'cron_expr': '48 3 * * *', 'metadata': {'title': 'Circular BCRP N° 0023-2025 — Créditos de Regulación Monetaria', 'issuer': 'BCRP', 'year': 2025, 'resolution_number': '0023-2025'}},
    {'name': 'ley-mercado-valores-smv', 'url': 'https://www.smv.gob.pe/uploads/PeruLeyMercadoValores.pdf', 'source_type': 'direct_pdf', 'domain': 'mercado_valores', 'document_type': 'ley', 'cron_expr': '49 3 * * *', 'metadata': {'title': 'Ley del Mercado de Valores (Decreto Legislativo N° 861) — Publicación SMV', 'issuer': 'SMV'}},
    {'name': 'ley-organica-smv', 'url': 'https://www.smv.gob.pe/uploads/peruleyorganicasmv.pdf', 'source_type': 'direct_pdf', 'domain': 'mercado_valores', 'document_type': 'ley', 'cron_expr': '50 3 * * *', 'metadata': {'title': 'Ley Orgánica de la SMV', 'issuer': 'SMV'}},
    {'name': 'rof-smv', 'url': 'https://www.smv.gob.pe/uploads/ROF.pdf', 'source_type': 'direct_pdf', 'domain': 'mercado_valores', 'document_type': 'reglamento', 'cron_expr': '51 3 * * *', 'metadata': {'title': 'Reglamento de Organización y Funciones (ROF) de la SMV', 'issuer': 'SMV'}},
    {'name': 'ley-fondos-inversion', 'url': 'https://www.smv.gob.pe/uploads/Ley_FondosInversion2.pdf', 'source_type': 'direct_pdf', 'domain': 'mercado_valores', 'document_type': 'ley', 'cron_expr': '52 3 * * *', 'metadata': {'title': 'Ley de Fondos de Inversión y sus Sociedades Administradoras', 'issuer': 'SMV'}},
    {'name': 'res-smv-033-2020', 'url': 'https://www.smv.gob.pe/Uploads/RSUP_033-2020.pdf', 'source_type': 'direct_pdf', 'domain': 'mercado_valores', 'document_type': 'resolucion', 'cron_expr': '53 3 * * *', 'metadata': {'title': 'Resolución de Superintendente N° 033-2020-SMV/02 — Disposiciones sociedades emisoras RPMV', 'issuer': 'SMV', 'year': 2020, 'resolution_number': '033-2020'}},
    {'name': 'codigo-bgc-smv-2013', 'url': 'https://www.smv.gob.pe/ConsultasP8/temp/GobCorporativo2013.pdf', 'source_type': 'direct_pdf', 'domain': 'gobierno', 'document_type': 'codigo', 'cron_expr': '54 3 * * *', 'metadata': {'title': 'Código de Buen Gobierno Corporativo para las Sociedades Peruanas (2013)', 'issuer': 'SMV', 'year': 2013}},
    {'name': 'principios-bg-smv', 'url': 'https://www.smv.gob.pe/ConsultasP8/temp/principios_buen_gobierno.pdf', 'source_type': 'direct_pdf', 'domain': 'gobierno', 'document_type': 'codigo', 'cron_expr': '55 3 * * *', 'metadata': {'title': 'Principios de Buen Gobierno para las Sociedades Peruanas', 'issuer': 'SMV'}},
    {'name': 'tuo-lmv-ds-020-2023', 'url': 'https://www.smv.gob.pe/ServicioConsultaNormas/uploads/TUO_LMV_DECRETO_SUPREMO_N_020_2023_EF.pdf', 'source_type': 'direct_pdf', 'domain': 'mercado_valores', 'document_type': 'decreto_supremo', 'cron_expr': '56 3 * * *', 'metadata': {'title': 'TUO Ley del Mercado de Valores — D.S. N° 020-2023-EF', 'issuer': 'SMV', 'year': 2023, 'resolution_number': '020-2023'}},
    {'name': 'circ-emisores-smv', 'url': 'https://www.smv.gob.pe/ConsultasP8/temp/CIRCULAR_EMISORES.pdf', 'source_type': 'direct_pdf', 'domain': 'mercado_valores', 'document_type': 'circular', 'cron_expr': '57 3 * * *', 'metadata': {'title': 'Circular para Emisores SMV', 'issuer': 'SMV'}},
    {'name': 'ley-26702', 'url': 'https://leyes.congreso.gob.pe/Documentos/Leyes/26702.pdf', 'source_type': 'direct_pdf', 'domain': 'gobierno', 'document_type': 'ley', 'cron_expr': '58 3 * * *', 'metadata': {'title': 'Ley N° 26702 — Ley General del Sistema Financiero y del Sistema de Seguros y Orgánica de la SBS', 'issuer': 'Congreso'}},
    {'name': 'ley-27693', 'url': 'https://leyes.congreso.gob.pe/Documentos/Leyes/27693.pdf', 'source_type': 'direct_pdf', 'domain': 'laft', 'document_type': 'ley', 'cron_expr': '59 3 * * *', 'metadata': {'title': 'Ley N° 27693 — Crea la Unidad de Inteligencia Financiera (UIF) — Perú', 'issuer': 'Congreso'}},
    {'name': 'dl-861', 'url': 'https://leyes.congreso.gob.pe/Documentos/DecretosLegislativos/00861.pdf', 'source_type': 'direct_pdf', 'domain': 'mercado_valores', 'document_type': 'decreto_legislativo', 'cron_expr': '0 3 * * *', 'metadata': {'title': 'Decreto Legislativo N° 861 — Ley del Mercado de Valores', 'issuer': 'Congreso'}},
    {'name': 'dl-1106', 'url': 'https://www.leyes.congreso.gob.pe/Documentos/DecretosLegislativos/01106.pdf', 'source_type': 'direct_pdf', 'domain': 'laft', 'document_type': 'decreto_legislativo', 'cron_expr': '1 3 * * *', 'metadata': {'title': 'Decreto Legislativo N° 1106 — Lucha eficaz contra lavado de activos y crimen organizado', 'issuer': 'Congreso'}},
    {'name': 'ley-29985', 'url': 'https://leyes.congreso.gob.pe/Documentos/Leyes/29985.pdf', 'source_type': 'direct_pdf', 'domain': 'operaciones_estructuradas', 'document_type': 'ley', 'cron_expr': '2 3 * * *', 'metadata': {'title': 'Ley N° 29985 — Ley del Dinero Electrónico', 'issuer': 'Congreso'}},
    {'name': 'ley-28587', 'url': 'https://leyes.congreso.gob.pe/Documentos/Leyes/28587.pdf', 'source_type': 'direct_pdf', 'domain': 'proteccion_consumidor', 'document_type': 'ley', 'cron_expr': '3 3 * * *', 'metadata': {'title': 'Ley N° 28587 — Complementaria de Protección al Consumidor en Servicios Financieros', 'issuer': 'Congreso'}},
    {'name': 'directiva-004-2022-mef', 'url': 'https://www.mef.gob.pe/contenidos/archivos-descarga/Directiva_0004_2022EF5301.pdf', 'source_type': 'direct_pdf', 'domain': 'politica_fiscal', 'document_type': 'directiva', 'cron_expr': '4 3 * * *', 'metadata': {'title': 'Directiva N° 004-2022-EF/53.01 — MEF', 'issuer': 'MEF', 'year': 2022, 'resolution_number': '004-2022'}},
]

# Agregar fuentes curadas v2 al catálogo completo (post-research)
CATALOGO_COMPLETO = CATALOGO_COMPLETO + FUENTES_CURADAS_V2
