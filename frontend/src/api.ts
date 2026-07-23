// Cliente de la API RAG SBS. Usa rutas relativas /v1/* (el proxy de Vite las
// reenvía a la API desplegada en dev; en prod se serviría desde el mismo host).

export type User = {
  id: string
  email: string
  name: string
  status: string
  organization?: string | null
  role?: string | null
}

export type Conversation = {
  id: string
  title: string
  n_mensajes: number
  updated_at?: string
}

export type Source = {
  title?: string
  issuer?: string
  section_path?: string
  url?: string
  content_snippet?: string
  publication_date?: string | null   // ISO 'AAAA-MM-DD'
  date_precision?: string | null      // 'dia' | 'anio'
}

export type Calculo = {
  tool: string
  inputs: Record<string, unknown>
  output: Record<string, unknown>
  fuente_normativa: string
  error?: string | null
}

export type Mensaje = {
  rol: 'user' | 'assistant'
  texto: string
  sources?: Source[]
  calculations?: Calculo[]
  confidence?: string
  latencyMs?: number
  voted?: 'up' | 'down'
  error?: { title?: string; message: string; hint?: string }
}

export type PlanQuestion = {
  id: string
  label: string
  type: 'text' | 'select' | 'multiselect'
  options?: string[] | null
  rationale?: string | null
}

export type PlanResponse = {
  action: 'answer_directly' | 'ask_clarifications'
  reason?: string | null
  questions: PlanQuestion[]
}

export async function plan(query: string): Promise<PlanResponse> {
  const { status, data } = await post<PlanResponse>('/v1/plan', { query })
  if (status !== 200 || !data?.action) return { action: 'answer_directly', questions: [] }
  return { action: data.action, reason: data.reason, questions: data.questions || [] }
}

export type QueryOptions = {
  expansion_enabled?: boolean
  max_hops?: number
  report_mode?: boolean
  hyde?: boolean
}

async function post<T>(path: string, body: unknown): Promise<{ status: number; data: T }> {
  const r = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  let data: T
  try {
    data = (await r.json()) as T
  } catch {
    data = {} as T
  }
  return { status: r.status, data }
}

export async function login(email: string, pin: string) {
  return post<{ ok: boolean; user: User; memory: Mensaje[]; recovery_code?: string; admin_token?: string }>(
    '/v1/users/login',
    { email, pin },
  )
}

// ---- Administración (usa el token de sesión admin como Bearer) ----
async function adminGet<T>(path: string, token: string): Promise<T | null> {
  const r = await fetch(path, { headers: { Authorization: `Bearer ${token}` } })
  if (!r.ok) return null
  return (await r.json()) as T
}
async function adminPost<T>(path: string, token: string, body: unknown): Promise<{ status: number; data: T }> {
  const r = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  })
  let data: T
  try {
    data = (await r.json()) as T
  } catch {
    data = {} as T
  }
  return { status: r.status, data }
}

export type PendingUser = { id?: string; email: string; name?: string; organization?: string | null; role?: string | null }
export type DashboardData = {
  total_consultas: number
  usuarios_activos: number
  latencia_avg_ms: number
  dias: number
  consultas_por_dia: { dia: string; consultas: number }[]
  top_documentos: { documento: string; referencias: number }[]
  top_consultas: { consulta: string; veces: number }[]
  distribucion_confianza: { confianza: string; n: number }[]
}
export type FeedbackComentario = { vote?: string; email?: string; question?: string; answer?: string; comment?: string; created_at?: string }
export type FeedbackSummary = {
  likes: number
  dislikes: number
  comentarios: FeedbackComentario[]
  dislikes_detalle: FeedbackComentario[]
}
export type UserAnalytics = { alias: string; total: number; ultima?: string; conf_alta?: number; sin_evidencia?: number; lat_avg_ms?: number }

export const adminApi = {
  pending: (t: string) => adminGet<PendingUser[]>('/v1/users/pending', t),
  approve: (t: string, email: string) => adminPost('/v1/users/approve', t, { email }),
  reject: (t: string, email: string) => adminPost('/v1/users/reject', t, { email }),
  setLimit: (t: string, email: string, limite: number) => adminPost('/v1/users/set-limit', t, { email, limite_diario: limite }),
  settings: (t: string) => adminGet<{ global_daily_limit?: string; global_hourly_limit?: string }>('/v1/users/settings', t),
  setGlobalLimits: (t: string, dia: number, hora: number) => adminPost('/v1/users/settings/limits', t, { global_daily_limit: dia, global_hourly_limit: hora }),
  dashboard: (t: string, dias = 30) => adminGet<DashboardData>(`/v1/analytics/dashboard?dias=${dias}`, t),
  feedback: (t: string) => adminGet<FeedbackSummary>('/v1/users/feedback/summary', t),
  users: (t: string) => adminGet<UserAnalytics[]>('/v1/analytics/users', t),
  resetPin: (t: string, email: string) => adminPost('/v1/users/admin/reset-pin', t, { email }),

  // ---- Fase 2: ingesta / catálogo / runs / export ----
  bgStatus: (t: string) => adminGet<BgStatus>('/v1/background/status', t),
  bgStart: (t: string) => adminPost('/v1/background/start', t, {}),
  bgPause: (t: string) => adminPost('/v1/background/pause', t, {}),
  bgTick: (t: string) => adminPost('/v1/background/tick', t, {}),
  bgScrape: (t: string) => adminPost('/v1/background/scrape', t, { sbs: true, bcrp: true }),
  catalog: (t: string) => adminGet<{ items: CatalogItem[]; stats: Record<string, unknown> }>('/v1/ingest/catalog', t),
  runs: (t: string) => adminGet<IngestRun[]>('/v1/ingest/runs', t),
  events: (t: string) => adminGet<IngestEvent[]>('/v1/ingest/events', t),
  scan: (t: string, dryRun: boolean) => adminPost('/v1/ingest/scan', t, { dry_run: dryRun }),
  seed: (t: string, issuer?: string) => adminPost(`/v1/ingest/seed${issuer ? `?only_issuer=${encodeURIComponent(issuer)}` : ''}`, t, {}),
}

export type BgStatus = {
  config: { enabled: boolean; max_docs_total?: number; max_cost_total?: number; max_cost_daily?: number; docs_per_tick?: number; schedule_until?: string }
  estado: {
    today: { docs: number; chunks: number; cost: number; last?: string | null }
    total: { docs: number; chunks: number; cost: number }
    queue: { failed: number; completed: number; pending: number }
  }
}
export type CatalogItem = { name: string; url: string; source_type?: string; domain?: string; document_type?: string }
export type IngestRun = { id: string; started_at?: string; finished_at?: string; status?: string; sources_scanned?: number; docs_new?: number; docs_modified?: number; docs_unchanged?: number; errors?: number; triggered_by?: string; dry_run?: boolean }
export type IngestEvent = { id: string; event_type?: string; summary?: string; created_at?: string; notified?: boolean }

// Descarga el CSV de consultas por período (fetch con token → blob).
export async function exportCsv(token: string, desde: string, hasta: string): Promise<boolean> {
  const r = await fetch(`/v1/analytics/export?desde=${desde}&hasta=${hasta}`, { headers: { Authorization: `Bearer ${token}` } })
  if (!r.ok) return false
  const blob = await r.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `consultas_${desde}_a_${hasta}.csv`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
  return true
}

export async function register(email: string, name: string, pin: string) {
  return post<{ ok: boolean; user: User; recovery_code?: string }>(
    '/v1/users/register',
    { email, name, pin },
  )
}

export async function recoverPin(email: string, recoveryCode: string, newPin: string) {
  return post<{ ok: boolean; recovery_code?: string }>('/v1/users/recover', {
    email,
    recovery_code: recoveryCode,
    new_pin: newPin,
  })
}

export async function deleteAccount(email: string, pin: string) {
  return post<{ ok: boolean }>('/v1/users/me/delete', { email, pin })
}

export type SurveyData = {
  email?: string
  rating_overall?: number | null
  rating_accuracy?: number | null
  rating_speed?: number | null
  rating_ux?: number | null
  would_recommend?: string | null
  missing_feature?: string | null
  comments?: string | null
  closed_reason?: string
}

export async function sendSurvey(data: SurveyData) {
  return post<{ ok: boolean }>('/v1/users/survey', data)
}

export async function touchActivity(userId: string) {
  try {
    await fetch('/v1/users/activity', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId }),
    })
  } catch {
    /* best-effort */
  }
}

export async function listConversations(email: string): Promise<Conversation[]> {
  const r = await fetch(`/v1/conversations?email=${encodeURIComponent(email)}`)
  if (!r.ok) return []
  return (await r.json()) as Conversation[]
}

export async function createConversation(email: string, userId?: string) {
  const { data } = await post<Conversation>('/v1/conversations', {
    email,
    user_id: userId,
  })
  return data
}

export async function renameConversation(conversationId: string, email: string, title: string) {
  const r = await fetch(`/v1/conversations/${conversationId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, title }),
  })
  return r.ok
}

export async function deleteConversation(conversationId: string, email: string) {
  const r = await fetch(`/v1/conversations/${conversationId}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  })
  return r.ok
}

export async function getMessages(conversationId: string): Promise<Mensaje[]> {
  const r = await fetch(`/v1/conversations/${conversationId}/messages`)
  if (!r.ok) return []
  return (await r.json()) as Mensaje[]
}

export type Topico = { label: string; kind: string; citaciones: number }

export async function getTopics(limit = 20): Promise<Topico[]> {
  const r = await fetch(`/v1/graph/topics?limit=${limit}`)
  if (!r.ok) return []
  return (await r.json()) as Topico[]
}

export type TopicoDetalle = {
  indice: number | null
  label: string
  miembros: number
  documentos_unicos: number
  docs_top: { id: string; title: string; chunks_del_topico: number; chunks_totales: number }[]
  samples: { doc_title: string; snippet: string }[]
  por_issuer: { issuer: string; docs: number }[]
}

export async function getTopicsDetails(): Promise<TopicoDetalle[]> {
  const r = await fetch('/v1/graph/topics/details')
  if (!r.ok) return []
  const d = (await r.json()) as { topicos?: TopicoDetalle[] }
  return d.topicos || []
}

export type GNode = {
  id: string
  label: string
  color: string
  size: number
  kind: string
  issuer: string
  grado: number
  doc_title?: string
}
export type GEdge = { from: string; to: string; relation: string; peso: number }

type RawEdge = { from: string; to: string; relation: string; peso_hub?: number; score?: number }

export async function getGraphData(limitNodes = 120, maxEdgesPerNode = 0, kind?: string): Promise<{ nodes: GNode[]; edges: GEdge[] }> {
  const kindParam = kind && kind !== 'all' ? `&kind=${encodeURIComponent(kind)}` : ''
  const r = await fetch(`/v1/graph/data?limit_nodes=${limitNodes}&max_edges_per_node=${maxEdgesPerNode}${kindParam}`)
  if (!r.ok) return { nodes: [], edges: [] }
  const d = (await r.json()) as { nodes: GNode[]; edges: RawEdge[] }
  // Preferimos `score` (similitud de embedding, buen discriminador de fuerza);
  // si el backend aún no lo expone, caemos a `peso_hub` (proxy por grado).
  const edges = (d.edges || []).map((e) => ({
    from: e.from,
    to: e.to,
    relation: e.relation,
    peso: e.score ?? e.peso_hub ?? 0,
  }))
  return { nodes: d.nodes || [], edges }
}

// Streaming de la respuesta vía SSE (parse manual del stream).
export type StreamEvent =
  | { type: 'status'; step: string }
  | { type: 'sources'; sources: Source[] }
  | { type: 'token'; text: string }
  | { type: 'metadata'; confidence: string; latency_ms: number }
  | { type: 'calculations'; calculations: Calculo[] }
  | { type: 'error'; message: string; title?: string; hint?: string }
  | { type: 'done' }

export async function sendFeedback(payload: {
  email?: string
  conversationId?: string | null
  question?: string
  answer?: string
  vote: 'up' | 'down'
  comment?: string
}) {
  return post<{ ok: boolean; id?: string }>('/v1/users/feedback', {
    email: payload.email,
    conversation_id: payload.conversationId ?? null,
    question: payload.question,
    answer: payload.answer,
    vote: payload.vote,
    comment: payload.comment ?? null,
  })
}

export async function* queryStream(params: {
  query: string
  alias: string
  conversationId?: string | null
  history?: { role: string; content: string }[]
  options?: QueryOptions
}): AsyncGenerator<StreamEvent> {
  const resp = await fetch('/v1/query/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query: params.query,
      alias: params.alias,
      conversation_id: params.conversationId ?? null,
      history: params.history ?? [],
      options: { stream: true, ...(params.options ?? {}) },
    }),
  })

  if (resp.status === 403) {
    yield {
      type: 'error',
      title: 'Acceso pendiente de aprobación',
      message: 'Tu cuenta todavía no fue aprobada por un administrador.',
      hint: 'Vas a poder consultar en cuanto aprueben tu acceso.',
    }
    return
  }
  if (resp.status === 429) {
    const d = await resp.json().catch(() => ({}))
    yield {
      type: 'error',
      title: 'Límite de consultas alcanzado',
      message: (d as { detail?: string }).detail || 'Se alcanzó el límite de consultas permitidas.',
      hint: 'Esperá un momento o intentá más tarde. El límite protege la cuota del servicio.',
    }
    return
  }
  if (resp.status === 503) {
    yield {
      type: 'error',
      title: 'Servicio momentáneamente saturado',
      message: 'El modelo está sobrecargado en este momento.',
      hint: 'Reintentá en unos segundos.',
    }
    return
  }
  if (!resp.ok) {
    yield {
      type: 'error',
      title: 'No se pudo completar la consulta',
      message: `El servidor respondió con un error (${resp.status}).`,
      hint: 'Reintentá; si persiste, avisá al administrador.',
    }
    return
  }
  if (!resp.body) {
    yield { type: 'error', title: 'Sin respuesta', message: 'El servidor no devolvió contenido.' }
    return
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let evName = 'message'

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (line.startsWith('event:')) {
        evName = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        const raw = line.slice(5).trim()
        let payload: unknown = raw
        try {
          payload = JSON.parse(raw)
        } catch {
          /* texto plano */
        }
        const p = payload as Record<string, unknown>
        if (evName === 'token') yield { type: 'token', text: (p.text as string) || '' }
        else if (evName === 'sources') yield { type: 'sources', sources: payload as Source[] }
        else if (evName === 'metadata')
          yield {
            type: 'metadata',
            confidence: (p.confidence as string) || '',
            latency_ms: (p.latency_ms as number) || 0,
          }
        else if (evName === 'status') yield { type: 'status', step: (p.step as string) || '' }
        else if (evName === 'calculations')
          yield { type: 'calculations', calculations: (payload as Calculo[]) || [] }
        else if (evName === 'error')
          yield { type: 'error', message: (p.message as string) || 'Error' }
        else if (evName === 'done') yield { type: 'done' }
        evName = 'message'
      }
    }
  }
}
