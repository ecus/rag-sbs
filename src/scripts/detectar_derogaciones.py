"""Detección de derogaciones EXPLÍCITAS en voz activa, para marcar vigencia.

Señal factual (no heurística): una norma dice "deróguese / déjase sin efecto la
Resolución SBS N° X-AAAA". El objeto del verbo es, sin ambigüedad, la norma
derogada. Se descarta la derogación PARCIAL ("deróguese el artículo N de la
Resolución X") porque no mata la norma entera.

Solo interesa cuando la norma derogada ES un documento del corpus (matcheable por
resolution_number). El resto (Decretos viejos, normas EF/SAFP externas) se ignora.

Modo dry-run por defecto: imprime lo que marcaría, sin escribir. Con `--apply`
escribe validity_status='derogada' + metadata (superseded_by_label, fecha).

Uso (en el contenedor):  python -m src.scripts.detectar_derogaciones [--apply]
"""

from __future__ import annotations

import asyncio
import re
import sys

from psycopg_pool import AsyncConnectionPool

from src.config import get_settings
from src.graph.extractor import (
    RX_CIRCULAR,
    RX_LEY,
    RX_RESOLUCION,
    _label_circular,
    _label_ley,
    _label_resolucion,
)

# Verbo de derogación en voz activa + determinante ("deróguese la ...").
RX_DEROGA = re.compile(
    r"(?i)\b(der[oó]g(?:u[eé]ense|uese|anse|ase|an|a)|d[eé]j[ae](?:se|nse)\s+sin\s+efecto)\s+(?:la|el|las|los)\s+"
)
# Si tras el determinante viene "artículo/numeral/…", es derogación PARCIAL.
RX_PARCIAL = re.compile(
    r"(?i)^\s*(art[ií]culo|numeral|inciso|p[aá]rrafo|disposici[oó]n|literal|"
    r"ap[aá]rtado|t[ií]tulo|cap[ií]tulo|secci[oó]n)\b"
)


def extraer_derogaciones(texto: str) -> list[tuple[str, str]]:
    """Devuelve [(kind, label)] de normas ENTERAS derogadas en voz activa."""
    out: list[tuple[str, str]] = []
    for m in RX_DEROGA.finditer(texto):
        cola = texto[m.end() : m.end() + 160].replace("\n", " ")
        if RX_PARCIAL.match(cola):
            continue  # derogación parcial → no mata la norma
        cab = cola[:90]
        mr = RX_RESOLUCION.search(cab)
        if mr and mr.start() < 45:
            out.append(("resolution", _label_resolucion(mr.group(1), mr.group(2))))
            continue
        mc = RX_CIRCULAR.search(cab)
        if mc and mc.start() < 45:
            out.append(("circular", _label_circular(mc.group(1))))
            continue
        ml = RX_LEY.search(cab)
        if ml and ml.start() < 45:
            out.append(("ley", _label_ley(ml.group(1))))
    return out


def _norm_resnum(resnum: str) -> str | None:
    """'0011356-2008' o '11356-2008' → 'Res-SBS-11356-2008'."""
    m = re.match(r"\s*0*(\d{1,6})\s*[-—–]\s*(\d{4})\s*$", resnum or "")
    return _label_resolucion(m.group(1), m.group(2)) if m else None


async def main(apply: bool) -> None:
    dsn = get_settings().database_url.replace("postgresql+psycopg://", "postgresql://")
    pool = AsyncConnectionPool(conninfo=dsn, min_size=1, max_size=4, open=False)
    await pool.open()

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            # Mapa: label canónico de resolución → documento del corpus
            await cur.execute(
                "SELECT id, document_id, resolution_number, title, publication_date FROM documents"
            )
            docs = await cur.fetchall()
            label_a_doc: dict[str, tuple] = {}
            for d in docs:
                lbl = _norm_resnum(d[2]) if d[2] else None
                if lbl:
                    label_a_doc[lbl] = d

            # Recorrer chunks agrupando por documento derogante
            await cur.execute(
                """
                SELECT c.content, d.document_id, d.resolution_number, d.publication_date, d.title
                FROM chunks c JOIN documents d ON d.id = c.document_id
                WHERE c.content ~* 'der[oó]g|d[eé]j[ae]se sin efecto'
                """
            )
            filas = await cur.fetchall()

    # target_label → (derogante_doc_id, derogante_label, fecha)
    derogadas: dict[str, dict] = {}
    total_extraidas = 0
    for contenido, drg_docid, drg_resnum, drg_pub, drg_title in filas:
        drg_label = _norm_resnum(drg_resnum) if drg_resnum else None
        for kind, label in extraer_derogaciones(contenido or ""):
            total_extraidas += 1
            if kind != "resolution":
                continue  # por ahora solo resoluciones (matcheo limpio por resnum)
            if label in label_a_doc and label != drg_label:
                # La norma derogada ES un documento del corpus
                derogadas.setdefault(
                    label,
                    {
                        "doc": label_a_doc[label],
                        "por_label": drg_label or drg_docid,
                        "por_titulo": (drg_title or "")[:60],
                        "fecha": drg_pub.isoformat() if drg_pub else None,
                    },
                )

    print(f"Derogaciones de norma extraídas (voz activa): {total_extraidas}")
    print(f"Que apuntan a un documento del corpus (resoluciones): {len(derogadas)}\n")
    for lbl, info in list(derogadas.items())[:40]:
        doc = info["doc"]
        print(f"  DEROGADA {lbl:22} ({(doc[3] or '')[:38]:38}) ← por {info['por_label']} [{info['fecha']}]")

    if apply and derogadas:
        async with pool.connection() as conn:
            for lbl, info in derogadas.items():
                doc_uuid = info["doc"][0]
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        UPDATE documents
                        SET validity_status = 'derogada',
                            metadata = COALESCE(metadata,'{}'::jsonb) || %s::jsonb
                        WHERE id = %s
                        """,
                        (
                            __import__("json").dumps(
                                {
                                    "superseded_by_label": info["por_label"],
                                    "superseded_by_title": info["por_titulo"],
                                    "superseded_date": info["fecha"],
                                }
                            ),
                            doc_uuid,
                        ),
                    )
            await conn.commit()
        print(f"\n✔ Aplicado: {len(derogadas)} documentos marcados validity_status='derogada'.")
    else:
        print("\n(dry-run — sin escribir. Usar --apply para persistir.)")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main("--apply" in sys.argv))
