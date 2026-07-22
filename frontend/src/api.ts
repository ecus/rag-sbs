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
}

export type Mensaje = { rol: 'user' | 'assistant'; texto: string; sources?: Source[] }

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
  return post<{ ok: boolean; user: User; memory: Mensaje[]; recovery_code?: string }>(
    '/v1/users/login',
    { email, pin },
  )
}

export async function register(email: string, name: string, pin: string) {
  return post<{ ok: boolean; user: User; recovery_code?: string }>(
    '/v1/users/register',
    { email, name, pin },
  )
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

export async function getMessages(conversationId: string): Promise<Mensaje[]> {
  const r = await fetch(`/v1/conversations/${conversationId}/messages`)
  if (!r.ok) return []
  return (await r.json()) as Mensaje[]
}

// Streaming de la respuesta vía SSE (parse manual del stream).
export type StreamEvent =
  | { type: 'status'; step: string }
  | { type: 'sources'; sources: Source[] }
  | { type: 'token'; text: string }
  | { type: 'metadata'; confidence: string; latency_ms: number }
  | { type: 'error'; message: string }
  | { type: 'done' }

export async function* queryStream(params: {
  query: string
  alias: string
  conversationId?: string | null
  history?: { role: string; content: string }[]
}): AsyncGenerator<StreamEvent> {
  const resp = await fetch('/v1/query/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query: params.query,
      alias: params.alias,
      conversation_id: params.conversationId ?? null,
      history: params.history ?? [],
      options: {},
    }),
  })

  if (resp.status === 403) {
    yield { type: 'error', message: 'Tu acceso está pendiente de aprobación.' }
    return
  }
  if (resp.status === 429) {
    const d = await resp.json().catch(() => ({}))
    yield { type: 'error', message: (d as { detail?: string }).detail || 'Límite alcanzado.' }
    return
  }
  if (!resp.body) {
    yield { type: 'error', message: 'Sin respuesta del servidor.' }
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
        else if (evName === 'error')
          yield { type: 'error', message: (p.message as string) || 'Error' }
        else if (evName === 'done') yield { type: 'done' }
        evName = 'message'
      }
    }
  }
}
