import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  createConversation,
  getMessages,
  listConversations,
  queryStream,
  type Conversation,
  type Mensaje,
  type Source,
  type User,
} from './api'

const EJEMPLOS: { ico: string; texto: string }[] = [
  { ico: '📄', texto: '¿Qué dice la Resolución SBS 11356-2008 sobre clasificación del deudor?' },
  { ico: '🛡️', texto: '¿Cuáles son las provisiones procíclicas vigentes?' },
  { ico: '🧮', texto: 'Cronograma de un crédito de S/ 1,000 al 38% a 12 meses' },
  { ico: '📋', texto: '¿Qué se declara en el Reporte Crediticio de Deudores?' },
]

export default function Chat({ user, onExit }: { user: User; onExit: () => void }) {
  const [convs, setConvs] = useState<Conversation[]>([])
  const [convId, setConvId] = useState<string | null>(null)
  const [msgs, setMsgs] = useState<Mensaje[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [sbOpen, setSbOpen] = useState(false) // drawer en móvil
  const chatRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    listConversations(user.email).then(setConvs)
  }, [user.email])

  useEffect(() => {
    chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight })
  }, [msgs, streaming])

  async function nuevaConversacion() {
    const c = await createConversation(user.email, user.id)
    if (c) {
      setConvs((p) => [c, ...p])
      setConvId(c.id)
      setMsgs([])
    }
  }

  async function abrirConversacion(c: Conversation) {
    setConvId(c.id)
    setMsgs(await getMessages(c.id))
  }

  async function enviar(texto: string) {
    const q = texto.trim()
    if (!q || streaming) return
    setInput('')

    let cid = convId
    if (!cid) {
      const c = await createConversation(user.email, user.id)
      if (c) {
        cid = c.id
        setConvId(c.id)
        setConvs((p) => [c, ...p])
      }
    }

    setMsgs((p) => [...p, { rol: 'user', texto: q }, { rol: 'assistant', texto: '' }])
    setStreaming(true)

    const history = msgs.slice(-6).map((m) => ({ role: m.rol, content: m.texto }))
    let acc = ''
    let srcs: Source[] = []
    try {
      for await (const ev of queryStream({ query: q, alias: user.email, conversationId: cid, history })) {
        if (ev.type === 'token') {
          acc += ev.text
          setMsgs((p) => {
            const c = [...p]
            c[c.length - 1] = { rol: 'assistant', texto: acc, sources: srcs }
            return c
          })
        } else if (ev.type === 'sources') {
          srcs = ev.sources
        } else if (ev.type === 'error') {
          acc = acc || `⚠ ${ev.message}`
          setMsgs((p) => {
            const c = [...p]
            c[c.length - 1] = { rol: 'assistant', texto: acc }
            return c
          })
        }
      }
    } finally {
      setMsgs((p) => {
        const c = [...p]
        c[c.length - 1] = { rol: 'assistant', texto: acc || '(sin respuesta)', sources: srcs }
        return c
      })
      setStreaming(false)
      listConversations(user.email).then(setConvs)
    }
  }

  const vacio = msgs.length === 0

  function abrirYcerrar(fn: () => void) {
    fn()
    setSbOpen(false)
  }

  return (
    <div className="app">
      {sbOpen && <div className="sb-overlay" onClick={() => setSbOpen(false)} />}
      <aside className={`sidebar ${sbOpen ? 'open' : ''}`}>
        <div className="sb-brand">
          <div className="sb-badge">SBS</div>
          <div>
            <b>Mesa Experta</b>
            <span>Regulación · Perú</span>
          </div>
        </div>
        <div className="sb-body">
          <button className="sb-new" onClick={() => abrirYcerrar(nuevaConversacion)}>
            + Nueva consulta
          </button>
          <div className="sb-label">Conversaciones</div>
          {convs.length === 0 && <div style={{ fontSize: 12, color: '#7d93b3' }}>Aún no tenés conversaciones.</div>}
          {convs.map((c) => (
            <button
              key={c.id}
              className={`sb-conv ${c.id === convId ? 'active' : ''}`}
              onClick={() => abrirYcerrar(() => abrirConversacion(c))}
            >
              {c.title}
            </button>
          ))}
        </div>
        <div className="sb-foot">
          <div className="k">Cobertura</div>
          <div className="v">
            2,870 <small>documentos</small>
          </div>
          <div className="sb-user">
            <b>{user.name}</b>
            {user.email}
          </div>
          <button className="sb-exit" onClick={onExit}>
            Cerrar sesión
          </button>
        </div>
      </aside>

      <main className="main">
        <div className="topbar">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
            <button className="burger" onClick={() => setSbOpen(true)} aria-label="Menú">
              ≡
            </button>
            <div style={{ minWidth: 0 }}>
              <div className="t">Mesa Experta Regulatoria</div>
              <div className="s">Consultas sobre normativa financiera peruana · no oficial</div>
            </div>
          </div>
          <nav className="nav">
            <a className="active">Consultar</a>
            <a>Tópicos</a>
            <a>Mapa</a>
          </nav>
        </div>

        <div className="chat" ref={chatRef}>
          {vacio ? (
            <div className="empty">
              <h2>¿Sobre qué normativa querés consultar?</h2>
              <p>Escribí tu pregunta abajo, o elegí un ejemplo</p>
              <div className="examples">
                {EJEMPLOS.map((e, i) => (
                  <button key={i} className="ex-card" onClick={() => enviar(e.texto)}>
                    <span className="ico">{e.ico}</span>
                    {e.texto}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            msgs.map((m, i) => (
              <div key={i}>
                <div className={`msg ${m.rol}`}>
                  <div className="bubble">
                    {m.rol === 'assistant' ? (
                      m.texto ? (
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.texto}</ReactMarkdown>
                      ) : (
                        streaming && i === msgs.length - 1 ? '▍' : ''
                      )
                    ) : (
                      m.texto
                    )}
                  </div>
                </div>
                {m.rol === 'assistant' && m.sources && m.sources.length > 0 && (
                  <div className="srcs">
                    <h4>Fuentes citadas ({m.sources.length})</h4>
                    <div className="src-grid">
                      {m.sources.slice(0, 6).map((s, j) => (
                        <a
                          className="src"
                          key={j}
                          href={s.url || undefined}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {s.issuer && s.issuer !== '(s/d)' && <span className="iss">{s.issuer}</span>}
                          <span className="src-t">{s.title}</span>
                          {s.url && <span className="src-pdf">PDF ↗</span>}
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        <div className="composer">
          <div className="box">
            <textarea
              rows={1}
              placeholder="Escribí tu consulta regulatoria…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  enviar(input)
                }
              }}
            />
            <button className="send" disabled={streaming || !input.trim()} onClick={() => enviar(input)}>
              ↑
            </button>
          </div>
        </div>
      </main>
    </div>
  )
}
