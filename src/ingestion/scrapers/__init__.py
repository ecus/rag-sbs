"""Scrapers de portales regulatorios oficiales.

Cada scraper descubre URLs de PDFs vigentes y las inserta en pending_sources.
El worker de background los consume con rate limiting.
"""
