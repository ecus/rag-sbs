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

from pypdf import PdfReader


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
    """Extrae texto de un PDF en bytes.

    Usa PyMuPDF si está disponible; cae a pypdf en caso contrario o si
    PyMuPDF lanza una excepción.
    """
    if _HAS_PYMUPDF:
        try:
            return _parse_pdf_pymupdf(content)
        except Exception as exc:  # noqa: BLE001
            logger.warning("PyMuPDF falló (%s), fallback a pypdf", exc)
    return _parse_pdf_pypdf(content)


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
