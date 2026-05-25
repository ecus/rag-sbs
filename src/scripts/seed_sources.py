"""Pobla las fuentes iniciales de SBS.

Ejecutar:
  podman exec rag-sbs-api python -m src.scripts.seed_sources
  o desde host con venv activa:
  python -m src.scripts.seed_sources
"""

from __future__ import annotations

import asyncio
import logging

import psycopg

from src.config import get_settings
from src.ingestion.repository import IngestionRepository

logger = logging.getLogger(__name__)


# Fuentes verificadas durante la validación end-to-end.
# Estas URLs son `intranet2.sbs.gob.pe` (sin Incapsula).
FUENTES_INICIALES = [
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
        },
    },
    {
        "name": "res-sbs-14353-2009-provisiones-genericas",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/968/v1.0/Adjuntos/14353-2009.r.pdf",
        "source_type": "direct_pdf",
        "domain": "riesgo_credito",
        "document_type": "resolucion",
        "cron_expr": "10 2 * * *",
        "metadata": {
            "title": "Reglamento para la Constitución de Provisiones Procíclicas",
            "resolution_number": "14353-2009",
        },
    },
    {
        "name": "res-sbs-2368-2023-modif-reglamento-deudor",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/2290/v2.0/Adjuntos/2368-2023.pdf",
        "source_type": "direct_pdf",
        "domain": "riesgo_credito",
        "document_type": "resolucion",
        "cron_expr": "20 2 * * *",
        "metadata": {
            "title": "Modificación del Reglamento para la Evaluación y Clasificación del Deudor",
            "resolution_number": "2368-2023",
        },
    },
    {
        "name": "res-sbs-1802-2014-cumplimiento-cooperativas",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/930/v1.0/Adjuntos/1802-2014.r.pdf",
        "source_type": "direct_pdf",
        "domain": "legal",
        "document_type": "resolucion",
        "cron_expr": "30 2 * * *",
        "metadata": {
            "title": "Reglamento de Cumplimiento Normativo en Cooperativas",
            "resolution_number": "1802-2014",
        },
    },
    {
        "name": "res-sbs-272-2017-gobierno-corporativo",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/1708/v4.0/Adjuntos/272-2017.R.pdf",
        "source_type": "direct_pdf",
        "domain": "gobierno",
        "document_type": "resolucion",
        "cron_expr": "40 2 * * *",
        "metadata": {
            "title": "Reglamento de Gobierno Corporativo y Gestión Integral de Riesgos",
            "resolution_number": "272-2017",
        },
    },
    {
        "name": "res-sbs-2116-2009-riesgo-operacional",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/842/v4.0/Adjuntos/2116-2009%20actualizado%20con%20la%20877-2020.doc.pdf",
        "source_type": "direct_pdf",
        "domain": "riesgo_operacional",
        "document_type": "resolucion",
        "cron_expr": "50 2 * * *",
        "metadata": {
            "title": "Reglamento para la Gestión del Riesgo Operacional",
            "resolution_number": "2116-2009",
        },
    },
    {
        "name": "res-sbs-3780-2011-evaluacion-crediticia",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/774/v3.0/Adjuntos/3780-2011.r.pdf",
        "source_type": "direct_pdf",
        "domain": "riesgo_credito",
        "document_type": "resolucion",
        "cron_expr": "0 3 * * *",
        "metadata": {
            "title": "Reglamento de Gestión de Riesgo de Crédito (evaluación crediticia)",
            "resolution_number": "3780-2011",
        },
    },
    {
        "name": "res-sbs-504-2021-sgsi-c",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/2046/v2.0/Adjuntos/504-2021.R.pdf",
        "source_type": "direct_pdf",
        "domain": "ti_seguridad",
        "document_type": "resolucion",
        "cron_expr": "10 3 * * *",
        "metadata": {
            "title": "Reglamento para la Gestión de la Seguridad de la Información y la Ciberseguridad (SGSI-C)",
            "resolution_number": "504-2021",
        },
    },
    {
        "name": "res-sbs-789-2018-reglamento-plaft",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/1766/v5.0/Adjuntos/789-2018.R.pdf",
        "source_type": "direct_pdf",
        "domain": "laft",
        "document_type": "resolucion",
        "cron_expr": "20 3 * * *",
        "metadata": {
            "title": "Reglamento de Gestión de Riesgos de Lavado de Activos y Financiamiento del Terrorismo",
            "resolution_number": "789-2018",
        },
    },
    # ----- Bloque añadido para cubrir titulización / transferencia de cartera -----
    {
        "name": "res-sbs-14354-2009-patrimonio-efectivo-riesgo-credito",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/976/v10.0/Adjuntos/14354-2009.r.pdf",
        "source_type": "direct_pdf",
        "domain": "riesgo_credito",
        "document_type": "resolucion",
        "cron_expr": "30 3 * * *",
        "metadata": {
            "title": "Reglamento para el Requerimiento de Patrimonio Efectivo por Riesgo de Crédito",
            "resolution_number": "14354-2009",
        },
    },
    {
        "name": "res-sbs-1010-1999-reglamento-fideicomiso",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/1192/v1.0/Adjuntos/1010-1999%20r%20(Oct-2021).doc.pdf",
        "source_type": "direct_pdf",
        "domain": "operaciones_estructuradas",
        "document_type": "resolucion",
        "cron_expr": "40 3 * * *",
        "metadata": {
            "title": "Reglamento del Fideicomiso y de las Empresas de Servicios Fiduciarios",
            "resolution_number": "1010-1999",
        },
    },
    {
        "name": "res-sbs-1308-2013-transferencia-cartera",
        "url": "https://intranet2.sbs.gob.pe/intranet/INT_CN/DV_INT_CN/1065/v1.0/Adjuntos/1308-2013.r.pdf",
        "source_type": "direct_pdf",
        "domain": "operaciones_estructuradas",
        "document_type": "resolucion",
        "cron_expr": "50 3 * * *",
        "metadata": {
            "title": "Reglamento para la Transferencia y Adquisición de Cartera Crediticia",
            "resolution_number": "1308-2013",
        },
    },
    {
        "name": "res-sbs-480-2019-operaciones-cartera",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/1827/v1.0/Adjuntos/480-2019.R.pdf",
        "source_type": "direct_pdf",
        "domain": "operaciones_estructuradas",
        "document_type": "resolucion",
        "cron_expr": "0 4 * * *",
        "metadata": {
            "title": "Reglamento de Operaciones con Cartera (480-2019)",
            "resolution_number": "480-2019",
        },
    },
    {
        "name": "res-sbs-3986-2024-modificatoria",
        "url": "https://intranet2.sbs.gob.pe/dv_int_cn/2461/v1.0/Adjuntos/Resoluci%C3%B3n%20SBS%20N%C2%B003986-2024.pdf",
        "source_type": "direct_pdf",
        "domain": "operaciones_estructuradas",
        "document_type": "resolucion",
        "cron_expr": "10 4 * * *",
        "metadata": {
            "title": "Resolución SBS Nº 03986-2024 (modificatoria reciente)",
            "resolution_number": "3986-2024",
        },
    },
]


async def seed() -> None:
    config = get_settings()
    dsn = config.database_url.replace("postgresql+psycopg://", "postgresql://")

    async with await psycopg.AsyncConnection.connect(dsn) as conn:
        repo = IngestionRepository(conn)
        for fuente in FUENTES_INICIALES:
            fila = await repo.upsert_source(fuente)
            print(f"  ✓ {fila['name']:<50}  {fila['url']}")
        await conn.commit()

    print(f"\n{len(FUENTES_INICIALES)} fuentes registradas.")


if __name__ == "__main__":
    asyncio.run(seed())
