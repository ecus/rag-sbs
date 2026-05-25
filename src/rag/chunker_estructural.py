"""Chunking estructural para documentos SBS Perú.

Estrategia:
  1. Parse jerárquico: detectar `TÍTULO`, `CAPÍTULO`, `SECCIÓN`, `Artículo`, `Anexo`
     usando regex con vocabulario canónico SBS.
  2. Cada `Artículo` se vuelve un chunk natural — coherente y completo.
  3. Artículos cortos se agrupan con vecinos del mismo capítulo (consolidación).
  4. Artículos largos se sub-splittean por párrafos, **preservando la cabecera
     del artículo y el path jerárquico en TODOS los sub-chunks** (clave para retrieval).
  5. Documentos sin estructura detectable caen al chunker recursivo legacy.

Cada chunk emitido lleva metadata con su `section_path`:
  - "Capítulo II > Artículo 5"
  - "Anexo I > Sección 3"
Esto permite que el retriever filtre/boostea por estructura y la UI muestre
breadcrumbs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final

from src.rag.chunker import chunk_text as _chunk_recursivo


# --- Patrones SBS canónicos -------------------------------------------------
RX_TITULO: Final = re.compile(
    r"(?:^|\n)\s*T[IÍ]TULO\s+([IVXLCDM]+|\d+)\.?\s*[—–-]?\s*([^\n]*)",
    re.IGNORECASE,
)
RX_CAPITULO: Final = re.compile(
    r"(?:^|\n)\s*CAP[IÍ]TULO\s+([IVXLCDM]+|\d+)\.?\s*[—–-]?\s*([^\n]*)",
    re.IGNORECASE,
)
RX_SECCION: Final = re.compile(
    r"(?:^|\n)\s*SECCI[ÓO]N\s+([IVXLCDM]+|\d+)\.?\s*[—–-]?\s*([^\n]*)",
    re.IGNORECASE,
)
RX_ARTICULO: Final = re.compile(
    # Acepta "Artículo 5", "Artículo 5°", "Artículo Primero", "Artículo Único"
    r"(?:^|\n)\s*[Aa]rt[ií]culo\s+"
    r"(\d+|Primero|Segundo|Tercero|Cuarto|Quinto|Sexto|S[eé]ptimo|Octavo|Noveno|D[eé]cimo|[ÚU]nico)"
    r"[°ºo]?\.?\s*[—–-]?\s*([^\n]*)",
    re.IGNORECASE,
)
RX_ANEXO: Final = re.compile(
    r"(?:^|\n)\s*ANEXO\s+([IVXLCDM]+|\d+)\.?\s*[—–-]?\s*([^\n]*)",
    re.IGNORECASE,
)

# Aproximación: 1 token ≈ 4 chars en español
CHARS_POR_TOKEN_ES = 4


@dataclass
class Marca:
    """Una marca estructural detectada en el texto."""

    nivel: str            # 'titulo' | 'capitulo' | 'seccion' | 'articulo' | 'anexo'
    numero: str           # 'I', '5', etc.
    titulo: str           # encabezado humano
    inicio: int           # offset en el texto original
    fin_encabezado: int   # offset donde termina la línea del encabezado


def _detectar_marcas(texto: str) -> list[Marca]:
    """Encuentra todas las marcas estructurales en el texto, ordenadas por offset."""
    marcas: list[Marca] = []

    for rx, nivel in (
        (RX_TITULO, "titulo"),
        (RX_CAPITULO, "capitulo"),
        (RX_SECCION, "seccion"),
        (RX_ARTICULO, "articulo"),
        (RX_ANEXO, "anexo"),
    ):
        for match in rx.finditer(texto):
            numero = match.group(1).strip()
            titulo = (match.group(2) or "").strip().rstrip(".:—–-").strip()
            marcas.append(
                Marca(
                    nivel=nivel,
                    numero=numero,
                    titulo=titulo,
                    inicio=match.start(),
                    fin_encabezado=match.end(),
                )
            )

    marcas.sort(key=lambda m: m.inicio)
    return marcas


@dataclass
class BloqueEstructural:
    """Un fragmento del texto con su contexto jerárquico."""

    section_path: str           # "Capítulo II > Artículo 5"
    nivel: str                  # nivel del más profundo (típicamente 'articulo')
    encabezado: str             # primera línea del bloque
    contenido: str              # contenido completo (incluyendo encabezado)
    metadata: dict = field(default_factory=dict)


def _construir_bloques(texto: str, marcas: list[Marca]) -> list[BloqueEstructural]:
    """Convierte el texto + marcas en bloques jerárquicos con section_path.

    Estrategia de "nivel hoja":
      - Identifica el nivel más profundo presente entre los marcadores.
      - Emite bloques en ESE nivel + siempre en `anexo`.
      - Esto permite que docs estructurados con `Capítulo` + sub-numeración
        (sin `Artículo N` propios) sigan siendo chunkeados sensatamente.
    """
    if not marcas:
        return [
            BloqueEstructural(
                section_path="(sin estructura)",
                nivel="documento",
                encabezado="",
                contenido=texto,
            )
        ]

    # Stack para mantener jerarquía actual (capítulo, sección, etc.)
    pila: dict[str, Marca] = {}
    bloques: list[BloqueEstructural] = []
    orden_niveles = ["titulo", "capitulo", "seccion", "articulo", "anexo"]

    # Determinar nivel hoja del documento (el más profundo presente)
    niveles_presentes = {m.nivel for m in marcas}
    nivel_hoja = next(
        (n for n in ("articulo", "seccion", "capitulo", "titulo") if n in niveles_presentes),
        "capitulo",
    )
    # Anexos siempre se emiten como bloques (son secciones independientes)
    niveles_emitir = {nivel_hoja, "anexo"}

    # Texto antes de la primera marca, si tiene contenido sustancial
    if marcas[0].inicio > 200:
        preambulo = texto[: marcas[0].inicio].strip()
        if preambulo:
            bloques.append(
                BloqueEstructural(
                    section_path="(preámbulo)",
                    nivel="preambulo",
                    encabezado="Preámbulo",
                    contenido=preambulo,
                )
            )

    for i, marca in enumerate(marcas):
        # Limpiar pila de niveles inferiores (estamos abriendo un nivel más alto/igual)
        idx_actual = orden_niveles.index(marca.nivel) if marca.nivel in orden_niveles else 99
        for nivel_existente in list(pila.keys()):
            if orden_niveles.index(nivel_existente) >= idx_actual:
                del pila[nivel_existente]
        pila[marca.nivel] = marca

        # Solo emitimos bloques en el nivel hoja del documento (+ anexos siempre)
        if marca.nivel not in niveles_emitir:
            continue

        # Determinar fin del bloque: hasta la siguiente marca de nivel <= actual
        fin_bloque = len(texto)
        for siguiente in marcas[i + 1 :]:
            if orden_niveles.index(siguiente.nivel) <= idx_actual:
                fin_bloque = siguiente.inicio
                break

        contenido = texto[marca.inicio:fin_bloque].strip()
        if len(contenido) < 30:
            continue   # ruido (línea aislada del encabezado sin cuerpo)

        # Reconstruir section_path desde la pila
        partes_path = []
        for nivel in orden_niveles:
            if nivel in pila:
                m = pila[nivel]
                etiqueta = nivel.capitalize()
                partes_path.append(f"{etiqueta} {m.numero}")
        section_path = " > ".join(partes_path)

        bloques.append(
            BloqueEstructural(
                section_path=section_path,
                nivel=marca.nivel,
                encabezado=texto[marca.inicio:marca.fin_encabezado].strip(),
                contenido=contenido,
                metadata={
                    "structural_level": marca.nivel,
                    "structural_number": marca.numero,
                    "structural_title": marca.titulo,
                    # también guardamos el contexto: capítulo / título padre
                    "parent_capitulo": pila.get("capitulo").numero if "capitulo" in pila else None,
                    "parent_titulo": pila.get("titulo").numero if "titulo" in pila else None,
                },
            )
        )

    return bloques


def _consolidar_bloques_pequenos(
    bloques: list[BloqueEstructural], tamano_min_chars: int = 400
) -> list[BloqueEstructural]:
    """Combina bloques consecutivos del mismo capítulo si individualmente son pequeños.

    Útil cuando hay muchos artículos cortos de 1-2 líneas (definiciones, etc.) —
    los agrupamos para que cada chunk tenga sustancia semántica.
    """
    if not bloques:
        return bloques

    consolidados: list[BloqueEstructural] = []
    actual: BloqueEstructural | None = None

    for b in bloques:
        if actual is None:
            actual = b
            continue

        # ¿Pertenecen al mismo capítulo y son pequeños?
        mismo_cap = (
            actual.metadata.get("parent_capitulo") == b.metadata.get("parent_capitulo")
            and actual.metadata.get("parent_titulo") == b.metadata.get("parent_titulo")
        )
        ambos_pequenos = len(actual.contenido) < tamano_min_chars and len(b.contenido) < tamano_min_chars

        if mismo_cap and ambos_pequenos:
            # Combinar
            actual = BloqueEstructural(
                section_path=actual.section_path + "  +  " + b.section_path.split(" > ")[-1],
                nivel=actual.nivel,
                encabezado=actual.encabezado,
                contenido=actual.contenido + "\n\n" + b.contenido,
                metadata={
                    **actual.metadata,
                    "consolidated": True,
                },
            )
        else:
            consolidados.append(actual)
            actual = b

    if actual is not None:
        consolidados.append(actual)
    return consolidados


def _dividir_bloque_grande(
    bloque: BloqueEstructural, tamano_max_chars: int
) -> list[BloqueEstructural]:
    """Si un bloque supera tamano_max_chars, lo parte por párrafos manteniendo
    el encabezado del bloque + section_path en cada sub-chunk.

    Esto es clave: aunque un sub-chunk no contenga el encabezado del artículo,
    sí preserva el `section_path` en metadata para que el retriever sepa de
    dónde viene.
    """
    if len(bloque.contenido) <= tamano_max_chars:
        return [bloque]

    parrafos = [p.strip() for p in re.split(r"\n\s*\n", bloque.contenido) if p.strip()]
    if len(parrafos) <= 1:
        # No hay párrafos identificables — usar fallback de chunker recursivo
        sub_textos = _chunk_recursivo(
            bloque.contenido,
            chunk_size_tokens=tamano_max_chars // CHARS_POR_TOKEN_ES,
            overlap_tokens=64,
        )
        return [
            BloqueEstructural(
                section_path=f"{bloque.section_path} (parte {i+1}/{len(sub_textos)})",
                nivel=bloque.nivel,
                encabezado=bloque.encabezado,
                contenido=texto,
                metadata={**bloque.metadata, "sub_chunk": True, "sub_index": i},
            )
            for i, texto in enumerate(sub_textos)
        ]

    # Agrupar párrafos hasta llenar tamano_max_chars, manteniendo encabezado
    sub_bloques: list[BloqueEstructural] = []
    actual: list[str] = [bloque.encabezado] if bloque.encabezado else []
    len_actual = sum(len(p) for p in actual)
    sub_index = 0
    for parrafo in parrafos:
        if parrafo == bloque.encabezado:
            continue   # ya incluido como cabecera
        if len_actual + len(parrafo) > tamano_max_chars and len(actual) > (1 if bloque.encabezado else 0):
            sub_bloques.append(
                BloqueEstructural(
                    section_path=f"{bloque.section_path} (parte {sub_index+1})",
                    nivel=bloque.nivel,
                    encabezado=bloque.encabezado,
                    contenido="\n\n".join(actual),
                    metadata={**bloque.metadata, "sub_chunk": True, "sub_index": sub_index},
                )
            )
            sub_index += 1
            # Nuevo sub-bloque arranca con encabezado para no perder contexto
            actual = [bloque.encabezado] if bloque.encabezado else []
            len_actual = sum(len(p) for p in actual)
        actual.append(parrafo)
        len_actual += len(parrafo)

    if actual and (len(actual) > 1 or not bloque.encabezado):
        sub_bloques.append(
            BloqueEstructural(
                section_path=(
                    f"{bloque.section_path} (parte {sub_index+1})"
                    if sub_index > 0 else bloque.section_path
                ),
                nivel=bloque.nivel,
                encabezado=bloque.encabezado,
                contenido="\n\n".join(actual),
                metadata={**bloque.metadata, "sub_chunk": sub_index > 0, "sub_index": sub_index},
            )
        )

    return sub_bloques


def chunk_estructural(
    texto: str,
    *,
    chunk_size_tokens: int = 768,
    consolidar_pequenos: bool = True,
    fallback_si_sin_estructura: bool = True,
) -> list[tuple[str, dict]]:
    """Chunker estructural. Retorna lista de (texto_chunk, metadata).

    Si no detecta estructura suficiente (< 3 marcas), cae al chunker recursivo
    legacy y retorna metadata mínima.
    """
    if not texto or not texto.strip():
        return []

    marcas = _detectar_marcas(texto)

    # Si no hay estructura mínima (≥3 marcas), fallback al recursivo
    if len(marcas) < 3 and fallback_si_sin_estructura:
        textos = _chunk_recursivo(texto, chunk_size_tokens=chunk_size_tokens)
        return [(t, {"structural": False}) for t in textos]

    bloques = _construir_bloques(texto, marcas)
    if consolidar_pequenos:
        bloques = _consolidar_bloques_pequenos(bloques)

    tamano_max_chars = chunk_size_tokens * CHARS_POR_TOKEN_ES
    salida: list[tuple[str, dict]] = []
    for b in bloques:
        sub = _dividir_bloque_grande(b, tamano_max_chars)
        for s in sub:
            if len(s.contenido.strip()) < 80:
                continue   # filtra chunks triviales
            md = {
                "structural": True,
                "section_path": s.section_path,
                **s.metadata,
            }
            salida.append((s.contenido, md))

    # Guardrail de cobertura: si los chunks estructurales no llegan a cubrir
    # al menos el 60% del texto, el detector de marcas falló (typical caso:
    # numerales con jerarquía "3.1 / 4.2" que no matchean la regex de
    # "Artículo N"). En ese caso, complementamos con chunks recursivos del
    # texto completo para no perder contenido crítico (ej. tablas SBS).
    chars_cubiertos = sum(len(t) for t, _ in salida)
    if texto and chars_cubiertos / len(texto) < 0.60 and fallback_si_sin_estructura:
        cobertura = chars_cubiertos / len(texto) if texto else 0
        textos_recursivos = _chunk_recursivo(texto, chunk_size_tokens=chunk_size_tokens)
        # Mantenemos los chunks estructurales (sirven para metadata jerárquica)
        # y añadimos los recursivos para asegurar cobertura completa.
        for t in textos_recursivos:
            salida.append(
                (
                    t,
                    {
                        "structural": False,
                        "section_path": "(fallback-recursivo)",
                        "reason_fallback": f"cobertura_estructural={cobertura:.0%}",
                    },
                )
            )

    return salida
