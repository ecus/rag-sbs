"""Router determinista por tema regulatorio.

Filtra el contexto recuperado para evitar mezclar regulaciones distintas que
producen números distintos pero comparten vocabulario superficial. Ejemplo
canónico: una consulta sobre PROVISIONES (Res. 11356-2008) no debe traer
chunks sobre PATRIMONIO EFECTIVO (Res. 14354-2009) — ambos hablan de
"créditos hipotecarios" y "porcentajes", pero son cálculos distintos.

Se aplica DESPUÉS del retrieval/rerank, antes de pasar el contexto al LLM.
"""

from __future__ import annotations

from dataclasses import dataclass

# Topics conocidos del corpus SBS. Cada uno declara:
#   - keywords_query: si la query las contiene, este tema "se activa".
#   - titulos_permitidos: substrings de title que SÍ son relevantes al tema.
#   - titulos_excluidos: substrings de title que NO deben aparecer si el tema
#     está activado en SOLO modo (sin otros temas competidores).


@dataclass
class TopicMatch:
    topic: str
    score: int
    keywords_hit: list[str]


_TOPICS: dict[str, dict] = {
    "provisiones": {
        "keywords_query": [
            "provisión", "provision", "provisiones",
            "exigencia de provision", "provisión específica", "provisión genérica",
            "categoría", "categoria", "deudor",
            "clasificación", "clasificacion", "días de atraso", "dias de atraso",
            "normal", "cpp", "deficiente", "dudoso", "pérdida", "perdida",
            # Señales de cálculo concreto (sin mencionar "provisión")
            "atraso", "garantía", "garantia", "saldo", "hipotecario",
            "consumo no revolvente", "microempresa", "pequeña empresa",
            "días", "dias", "dias mora", "días mora",
        ],
        "titulos_permitidos": [
            "11356", "14353", "2368-2023", "4345-2023", "975-2025", "3780",
            "clasificación del deudor", "clasificacion del deudor",
            "provisiones genéricas", "provisiones genericas",
            "evaluación crediticia", "evaluacion crediticia",
        ],
        "titulos_excluidos_si_unico": [
            "14354",
            "patrimonio efectivo",   # Title legible del chunk en DB
            "patrimonio",
            "requerimiento de patrimonio",
        ],
    },
    "patrimonio_efectivo": {
        "keywords_query": [
            "patrimonio efectivo", "apr", "activos ponderados",
            "factor de ponderación", "factor de ponderacion",
            "capital regulatorio", "ratio de capital", "basilea",
            "requerimiento de capital", "indicador prudencial",
        ],
        "titulos_permitidos": [
            "14354", "3986-2024",
            "patrimonio efectivo", "requerimiento de patrimonio",
        ],
        "titulos_excluidos_si_unico": [
            "11356", "14353",
            "clasificación del deudor", "clasificacion del deudor",
            "provisiones genéricas",
        ],
    },
    "operaciones_cartera": {
        "keywords_query": [
            "titulización", "titulizacion", "cartera", "fideicomiso",
            "transferencia de cartera", "fideicomiso de titulización",
        ],
        "titulos_permitidos": ["480-2019", "1010-1999", "1308-2013"],
        "titulos_excluidos_si_unico": [],
    },
    "plaft": {
        "keywords_query": [
            "plaft", "lavado de activos", "uif", "beneficiario final",
            "debida diligencia", "kyc",
        ],
        "titulos_permitidos": ["789-2018"],
        "titulos_excluidos_si_unico": [],
    },
    "tasas_intereses": {
        "keywords_query": [
            "tasa moratoria", "tasa compensatoria", "interés moratorio",
            "interes moratorio", "intereses moratorios", "intereses compensatorios",
            "tea", "tcea", "tasa máxima", "tasa maxima",
            "tope de tasa", "tope tasa", "circular bcrp", "circular del bcrp",
            "usura", "transparencia", "tasa de interés", "tasa de interes",
            "interés convencional", "interes convencional",
        ],
        "titulos_permitidos": [
            "8181-2012", "transparencia",
            "bcrp", "circular bcrp", "tasa máxima", "tasa maxima",
            "tasas máximas", "tasas maximas",
        ],
        "titulos_excluidos_si_unico": [
            "11356", "14354", "14353",  # No mezclar con provisiones / patrimonio
            "clasificación del deudor", "patrimonio efectivo",
        ],
    },
    "ciberseguridad": {
        "keywords_query": [
            "ciberseguridad", "sgsi", "seguridad de la información",
            "seguridad de la informacion", "ti", "riesgo tecnológico",
        ],
        "titulos_permitidos": ["504-2021", "2116-2009"],
        "titulos_excluidos_si_unico": [],
    },
}


def titulos_permitidos_para_query(query: str) -> list[str]:
    """Devuelve los substrings de title que deben incluirse para esta query.

    Lista vacía si no se detecta tema único. Útil para hacer un re-fetch
    dirigido cuando el retrieval inicial no traje ningún chunk de los docs
    relevantes al tema.
    """
    temas = detectar_temas(query)
    if not temas or len(temas) > 1:
        return []
    cfg = _TOPICS[temas[0].topic]
    return cfg.get("titulos_permitidos", [])


def detectar_temas(query: str) -> list[TopicMatch]:
    """Detecta qué temas se activan según las keywords en la query.

    Retorna lista ordenada descendente por score. Vacía si nada matchea.
    """
    q = query.lower()
    matches: list[TopicMatch] = []
    for topic, cfg in _TOPICS.items():
        hits = [kw for kw in cfg["keywords_query"] if kw in q]
        if hits:
            matches.append(TopicMatch(topic=topic, score=len(hits), keywords_hit=hits))
    matches.sort(key=lambda m: m.score, reverse=True)
    return matches


def filtrar_fragmentos_por_tema(
    fragmentos: list,
    query: str,
) -> tuple[list, dict]:
    """Filtra ``fragmentos`` removiendo los que pertenecen a temas excluidos.

    Args:
        fragmentos: lista de RetrievedChunk (con atributo ``title``).
        query: query original del usuario.

    Returns:
        (fragmentos_filtrados, telemetria) donde ``telemetria`` incluye qué
        temas se detectaron y cuántos chunks se removieron.

    Lógica:
      - Si la query activa UN solo tema, removemos chunks cuyo ``title``
        contenga alguno de los ``titulos_excluidos_si_unico``.
      - Si la query activa VARIOS temas, no filtramos (puede ser una pregunta
        comparativa legítima).
      - Si no se activa ningún tema, no filtramos.
      - Nunca devolvemos lista vacía: si todos los chunks se filtrarían,
        devolvemos los originales (failsafe).
    """
    temas = detectar_temas(query)
    telemetria = {
        "temas_detectados": [t.topic for t in temas],
        "keywords_hit": {t.topic: t.keywords_hit for t in temas},
        "chunks_removidos": 0,
        "modo": "sin_filtro",
    }
    if not temas or len(temas) > 1:
        return fragmentos, telemetria

    tema = temas[0]
    cfg = _TOPICS[tema.topic]
    excluidos = cfg.get("titulos_excluidos_si_unico", [])
    if not excluidos:
        return fragmentos, telemetria

    permitidos = cfg.get("titulos_permitidos", [])
    filtrados = []
    removidos = 0
    boosteados = 0
    for f in fragmentos:
        title = (
            getattr(f, "document_title", None)
            or getattr(f, "title", None)
            or ""
        ).lower()
        if any(exc.lower() in title for exc in excluidos):
            removidos += 1
            continue
        # Boost de score si el title matchea los titulos_permitidos del tema
        # (sube ese chunk al tope del ranking).
        if permitidos and any(p.lower() in title for p in permitidos):
            try:
                f.score = float(getattr(f, "score", 0) or 0) + 0.50
                boosteados += 1
            except Exception:  # noqa: BLE001
                pass
        filtrados.append(f)

    # Failsafe: nunca devolver vacío
    if not filtrados:
        telemetria["modo"] = "failsafe_no_filtro"
        return fragmentos, telemetria

    # Reordenar por score (descendente) tras el boost
    try:
        filtrados.sort(key=lambda f: float(getattr(f, "score", 0) or 0), reverse=True)
    except Exception:  # noqa: BLE001
        pass

    telemetria["chunks_removidos"] = removidos
    telemetria["chunks_boosteados"] = boosteados
    telemetria["modo"] = f"filtrado_por_{tema.topic}"
    return filtrados, telemetria
