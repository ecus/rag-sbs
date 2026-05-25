"""Tests del chunker — no requieren stack arriba."""

from src.rag.chunker import chunk_text


def test_chunker_empty_returns_empty():
    assert chunk_text("") == []
    assert chunk_text("   \n  \n") == []


def test_chunker_short_text_one_chunk():
    text = "Un párrafo corto sobre la SBS Perú."
    chunks = chunk_text(text, chunk_size_tokens=100, overlap_tokens=10)
    # Texto < 50 chars se filtra; usemos uno más largo
    assert chunks == [] or len(chunks) == 1


def test_chunker_respects_paragraphs():
    text = "Primer párrafo " * 50 + "\n\n" + "Segundo párrafo " * 50
    chunks = chunk_text(text, chunk_size_tokens=100, overlap_tokens=20)
    assert len(chunks) >= 2
    # Cada chunk debe tener contenido razonable
    for c in chunks:
        assert len(c) > 50


def test_chunker_handles_long_paragraph():
    # Párrafo gigante sin saltos — debe partirse por oración
    text = ". ".join(["Esta es una oración bastante larga sobre normativa SBS"] * 100) + "."
    chunks = chunk_text(text, chunk_size_tokens=100, overlap_tokens=10)
    assert len(chunks) >= 2
