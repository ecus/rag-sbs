// Detector de siglas ambiguas (portado de src/agents/acronyms.py).
// Solo incluimos las siglas con ≥2 significados: son las únicas que disparan
// desambiguación. Las de un solo significado no son ambiguas.

export type Significado = {
  sigla: string
  significado: string
  contexto: string
  norma_principal: string
}

export type SiglaAmbigua = { sigla: string; opciones: Significado[] }

const ACRONIMOS_AMBIGUOS: Record<string, Significado[]> = {
  RCD: [
    { sigla: 'RCD', significado: 'Reporte Crediticio de Deudores', contexto: 'Reporte regulatorio mensual de cartera por deudor', norma_principal: 'Res SBS 11356-2008 Anexo 6 / Manual Contabilidad' },
    { sigla: 'RCD', significado: 'Riesgo Cambiario Crediticio', contexto: 'Gestión de riesgo cambiario en cartera', norma_principal: 'Res SBS 774-2025' },
    { sigla: 'RCD', significado: 'Reglamento de Conducta de Mercado', contexto: 'Reglas de transparencia y conducta con usuarios', norma_principal: 'Res SBS 3274-2017' },
  ],
  PDD: [
    { sigla: 'PDD', significado: 'Probabilidad de Default (Probability of Default)', contexto: 'Métrica de riesgo de crédito (modelo IRB Basilea)', norma_principal: 'Res SBS 14354-2009 / Basilea II-III' },
    { sigla: 'PDD', significado: 'Plan de Desarrollo Distrital', contexto: 'Planificación municipal (no financiero)', norma_principal: 'MEF / municipalidades' },
  ],
  RPC: [
    { sigla: 'RPC', significado: 'Requerimiento de Patrimonio por Riesgo de Crédito', contexto: 'Capital regulatorio por exposiciones crediticias', norma_principal: 'Res SBS 14354-2009' },
    { sigla: 'RPC', significado: 'Registro Público del Mercado de Valores', contexto: 'Registro SMV de emisiones públicas', norma_principal: 'Ley Mercado de Valores DL 861' },
  ],
  APP: [
    { sigla: 'APP', significado: 'Asociación Público-Privada', contexto: 'Modalidad de inversión MEF / PROINVERSIÓN', norma_principal: 'DL 1362 / Reglamento MEF' },
    { sigla: 'APP', significado: 'Aplicación móvil (App)', contexto: 'Software para dispositivos móviles (TI/ciberseguridad)', norma_principal: 'Res SBS 504-2021 Ciberseguridad' },
  ],
}

const PATRON = /\b([A-ZÁÉÍÓÚ]{2,5})\b/g

function estaExplicado(query: string, sigla: string): boolean {
  const qLower = query.toLowerCase()
  const sig = sigla.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  // "SIGLA (...)" o "(...SIGLA...)"
  const inline = new RegExp(`\\b${sig}\\s*\\([^)]+\\)|\\([^)]*${sig}[^)]*\\)`, 'i')
  if (inline.test(query)) return true
  // Si aparece alguna palabra clave del significado, se considera explicado.
  const opts = ACRONIMOS_AMBIGUOS[sigla] || []
  for (const s of opts) {
    const palabras = (s.significado.match(/\b\w{4,}\b/g) || [])
      .map((w) => w.toLowerCase())
      .filter((w) => !['para', 'como', 'este', 'esta'].includes(w))
      .slice(0, 3)
    if (palabras.some((p) => qLower.includes(p))) return true
  }
  return false
}

export function detectarSiglas(query: string): SiglaAmbigua[] {
  if (!query || query.length < 3) return []
  const encontradas = new Set<string>()
  for (const m of query.matchAll(PATRON)) {
    const s = m[1].toUpperCase()
    if (ACRONIMOS_AMBIGUOS[s]) encontradas.add(s)
  }
  const res: SiglaAmbigua[] = []
  for (const sigla of encontradas) {
    const opciones = ACRONIMOS_AMBIGUOS[sigla]
    if (opciones.length < 2) continue
    if (estaExplicado(query, sigla)) continue
    res.push({ sigla, opciones })
  }
  return res
}

// Reemplaza cada sigla por "SIGLA (significado elegido)" en la query.
export function aplicarSiglas(query: string, elecciones: Record<string, string>): string {
  let q = query
  for (const [sigla, significado] of Object.entries(elecciones)) {
    if (!significado) continue
    const re = new RegExp(`\\b${sigla}\\b`)
    q = q.replace(re, `${sigla} (${significado})`)
  }
  return q
}
