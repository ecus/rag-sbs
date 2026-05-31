"""Parser de documentos PDF/HTML/texto.

Parser principal: PyMuPDF (fitz). Preserva mejor el layout y las tablas que pypdf.
Fallback: pypdf (puro Python) si PyMuPDF falla o no está instalado.

Lección incorporada: pypdf no extrae tablas estructuradas — el texto de cada celda
sale concatenado en una sola línea, lo que rompe el RAG al consultar rangos
regulatorios (ej. tabla de clasificación SBS Res 11356-2008). PyMuPDF preserva
saltos de línea por celda gracias a su detección de bloques.
"""

from __future__ import annotations

import logging
from io import BytesIO

logger = logging.getLogger(__name__)

try:
    import fitz  # PyMuPDF
    _HAS_PYMUPDF = True
except ImportError:  # pragma: no cover
    _HAS_PYMUPDF = False

try:
    import pytesseract  # type: ignore
    from PIL import Image  # type: ignore
    _HAS_OCR = True
except ImportError:  # pragma: no cover
    _HAS_OCR = False

from pypdf import PdfReader

# Umbral debajo del cual consideramos que el PDF es escaneado / sin texto
_UMBRAL_TEXTO_MIN_PROMEDIO = 50  # chars promedio por página
_OCR_MAX_PAGINAS = 30            # cap defensivo para no quemar CPU en PDFs gigantes
_OCR_DPI = 200                   # balance calidad/velocidad


def _es_pdf_escaneado(texto_extraido: str, n_paginas: int) -> bool:
    """Heurística: muy poco texto en muchas páginas → escaneado."""
    if n_paginas == 0:
        return False
    promedio = len(texto_extraido.strip()) / n_paginas
    return promedio < _UMBRAL_TEXTO_MIN_PROMEDIO and n_paginas >= 1


def _ocr_pdf_pymupdf(content: bytes) -> str:
    """OCR de cada página renderizando a PNG y pasando por Tesseract (spa)."""
    if not (_HAS_OCR and _HAS_PYMUPDF):
        return ""
    doc = fitz.open(stream=content, filetype="pdf")
    try:
        textos = []
        for i, pagina in enumerate(doc):
            if i >= _OCR_MAX_PAGINAS:
                logger.warning(
                    "OCR truncado a %d páginas (PDF tenía %d)",
                    _OCR_MAX_PAGINAS, doc.page_count,
                )
                break
            try:
                # Renderizar página a pixmap → PIL → tesseract
                pix = pagina.get_pixmap(dpi=_OCR_DPI, alpha=False)
                img_bytes = pix.tobytes("png")
                from io import BytesIO as _BIO
                img = Image.open(_BIO(img_bytes))
                txt = pytesseract.image_to_string(img, lang="spa")
                textos.append(txt or "")
            except Exception as exc:  # noqa: BLE001
                logger.warning("OCR falló en página %d: %s", i, exc)
                textos.append("")
        logger.info(
            "OCR completado: %d páginas, %d chars totales",
            len(textos), sum(len(t) for t in textos),
        )
        return "\n\n".join(textos)
    finally:
        doc.close()


def _parse_pdf_pymupdf(content: bytes) -> str:
    """Extrae texto con PyMuPDF, conservando estructura por bloques."""
    doc = fitz.open(stream=content, filetype="pdf")
    paginas = []
    try:
        for pagina in doc:
            # "blocks" agrupa celdas de tabla en líneas separadas — preserva
            # mejor las tablas que el modo "text" plano.
            try:
                texto = pagina.get_text("text") or ""
            except Exception:  # noqa: BLE001
                texto = ""
            paginas.append(texto)
    finally:
        doc.close()
    return "\n\n".join(paginas)


def _parse_pdf_pypdf(content: bytes) -> str:
    """Fallback con pypdf — usado solo si PyMuPDF no está disponible o falla."""
    lector = PdfReader(BytesIO(content))
    paginas = []
    for pagina in lector.pages:
        try:
            texto = pagina.extract_text() or ""
            paginas.append(texto)
        except Exception:  # noqa: BLE001
            paginas.append("")
    return "\n\n".join(paginas)


def parse_pdf(content: bytes) -> str:
    """Extrae texto de un PDF.

    Cadena de extracción:
    1. PyMuPDF (mejor preserva tablas y estructura)
    2. pypdf (fallback puro Python)
    3. OCR Tesseract en español (si los 2 anteriores extraen muy poco texto,
       PDF probablemente escaneado)
    """
    texto = ""
    n_paginas = 0
    if _HAS_PYMUPDF:
        try:
            texto = _parse_pdf_pymupdf(content)
            # Contar páginas para heurística
            try:
                doc = fitz.open(stream=content, filetype="pdf")
                n_paginas = doc.page_count
                doc.close()
            except Exception:  # noqa: BLE001
                pass
        except Exception as exc:  # noqa: BLE001
            logger.warning("PyMuPDF falló (%s), fallback a pypdf", exc)

    if not texto.strip():
        texto = _parse_pdf_pypdf(content)
        if not n_paginas:
            try:
                n_paginas = len(PdfReader(BytesIO(content)).pages)
            except Exception:  # noqa: BLE001
                n_paginas = 1

    # Fallback OCR si extracción nativa devuelve casi nada
    if _es_pdf_escaneado(texto, n_paginas):
        logger.info(
            "PDF detectado como escaneado (%.1f chars/pág en %d pág) → OCR",
            len(texto.strip()) / max(1, n_paginas), n_paginas,
        )
        texto_ocr = _ocr_pdf_pymupdf(content)
        if len(texto_ocr.strip()) > len(texto.strip()):
            return texto_ocr

    return texto


def parse_text(content: bytes, encoding: str = "utf-8") -> str:
    """Decodifica texto plano."""
    return content.decode(encoding, errors="replace")


def parse_by_filename(filename: str, content: bytes) -> str:
    """Despacha según extensión."""
    nombre = filename.lower()
    if nombre.endswith(".pdf"):
        return parse_pdf(content)
    if nombre.endswith((".txt", ".md")):
        return parse_text(content)
    raise ValueError(f"Formato no soportado en MVP: {filename}")
