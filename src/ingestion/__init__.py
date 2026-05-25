"""Módulo de ingesta automática.

Compone:
- Source registry (doc_sources)
- Downloader con ETag/Last-Modified
- Differ (hash + clasificación de cambios)
- Pipeline integrado (download → parse → chunk → embed → upsert)
- Scheduler con APScheduler

Endpoints expuestos en src.api.routes_ingest_scan.
"""
