import { Component, lazy, Suspense, useEffect, useRef, useState, type MouseEvent as ReactMouseEvent, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// Code-splitting: Tópicos y sobre todo el Mapa (con la pesada librería de
// force-graph) se cargan solo al abrir su tab, no en el bundle inicial del chat.
const Topicos = lazy(() => import('./Topicos'))
const Mapa = lazy(() => import('./Mapa'))
const Admin = lazy(() => import('./Admin'))
import Logo from './Logo'
import { detectarSiglas, aplicarSiglas, type SiglaAmbigua } from './acronyms'
import {
  createConversation,
  deleteAccount,
  deleteConversation,
  getMessages,
  listConversations,
  plan,
  queryStream,
  renameConversation,
  sendFeedback,
  touchActivity,
  type Calculo,
  type Conversation,
  type Mensaje,
  type PlanQuestion,
  type QueryOptions,
  type Source,
  type User,
} from './api'

// Nombres legibles de los pasos del pipeline (eventos SSE `status`).
const NOMBRE_PASO: Record<string, string> = {
  rewrite: 'Reformulando consulta',
  hyde: 'Ampliando la búsqueda',
  embedding: 'Generando embeddings',
  retrieval: 'Recuperando normativa',
  graph_expansion: 'Expandiendo vía grafo',
  rerank: 'Re-ordenando fuentes',
  calc: 'Verificando cálculos',
  generation: 'Redactando respuesta',
}

const CONF_LABEL: Record<string, string> = { alta: 'Confianza alta', media: 'Confianza media', baja: 'Confianza baja' }

// Convierte las citas "[Fuente N ...]" en enlaces markdown [N](#cita-N) que se
// renderizan como chips. Maneja dos formatos:
//   [Fuente 1, 2, 3]                              → números sueltos
//   [Fuente 1, Capítulo II; Fuente 2, numeral 3]  → con ubicación, separados por ;
function preprocesarCitas(texto: string): string {
  return (texto || '').replace(/\[\s*Fuente[s]?\b([^\]]*)\]/gi, (_m, inner: string) => {
    const nums: string[] = []
    for (const seg of inner.split(';')) {
      const limpio = seg.replace(/fuente[s]?/gi, '').trim()
      if (/^[\d\s,y]+$/.test(limpio)) {
        // solo números → [Fuente 1, 2, 3]
        limpio.split(/[,\s]+|y/).forEach((x) => {
          if (/^\d+$/.test(x) && !nums.includes(x)) nums.push(x)
        })
      } else {
        // con ubicación → tomar el primer número como id de fuente
        const mm = limpio.match(/(\d+)/)
        if (mm && !nums.includes(mm[1])) nums.push(mm[1])
      }
    }
    if (!nums.length) return _m
    return nums.map((n) => `[${n}](#cita-${n})`).join('')
  })
}

// Chip de cita (reemplaza los enlaces #cita-N). Click → popover con el detalle
// de la fuente (institución, título, ubicación, fragmento y link al PDF) ahí
// mismo, sin tener que bajar a las cards. Estilo NotebookLM.
const MESES_ABBR = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
// Formatea la fecha respetando la precisión: 'anio' → "2010"; 'dia' → "10 dic 2010".
// Nunca inventa día/mes cuando solo se conoce el año.
function fmtFecha(pub?: string | null, prec?: string | null): string | null {
  if (!pub) return null
  const [y, m, d] = pub.split('-').map(Number)
  if (!y) return null
  if (prec === 'anio' || !m || !d) return String(y)
  return `${d} ${MESES_ABBR[m - 1]} ${y}`
}

function Cita({ href, children, sources }: { href?: string; children?: ReactNode; sources?: Source[] }) {
  const [open, setOpen] = useState(false)
  if (!href || !href.startsWith('#cita-')) {
    return <a href={href} target="_blank" rel="noreferrer">{children}</a>
  }
  const n = parseInt(href.slice(6), 10)
  const src = sources?.[n - 1]
  const toggle = (e: ReactMouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setOpen((v) => !v)
  }
  return (
    <span className="cita-wrap">
      <sup className={`cita ${open ? 'on' : ''}`} onClick={toggle}>{n}</sup>
      {open && (
        <>
          <span className="cita-backdrop" onClick={() => setOpen(false)} />
          <span className="cita-pop" onClick={(e) => e.stopPropagation()}>
            <span className="cita-pop-head">
              <span className="src-num">{n}</span>
              {src?.issuer && src.issuer !== '(s/d)' && <span className="iss">{src.issuer}</span>}
              {fmtFecha(src?.publication_date, src?.date_precision) && (
                <span className="src-fecha">{fmtFecha(src?.publication_date, src?.date_precision)}</span>
              )}
              {src?.url && (
                <a className="cita-pop-link" href={src.url} target="_blank" rel="noreferrer">Ver PDF ↗</a>
              )}
            </span>
            <span className="cita-pop-title">{src?.title || `Fuente ${n}`}</span>
            {src?.section_path && <span className="cita-pop-path">{src.section_path}</span>}
            {src?.content_snippet ? (
              <span className="cita-pop-snip">{src.content_snippet}</span>
            ) : (
              <span className="cita-pop-empty">Fragmento no disponible para esta cita.</span>
            )}
          </span>
        </>
      )}
    </span>
  )
}

function FeedbackBar({ msg, onVote }: { msg: Mensaje; onVote: (v: 'up' | 'down', c?: string) => void }) {
  const [openComment, setOpenComment] = useState(false)
  const [comment, setComment] = useState('')
  if (msg.voted) {
    return <div className="fb-done">Gracias por tu feedback.</div>
  }
  return (
    <div className="fb">
      <span className="fb-q">¿Te resultó útil esta respuesta?</span>
      <button className="fb-btn" title="Sí, útil" onClick={() => onVote('up')}>
        👍
      </button>
      <button className="fb-btn" title="No útil" onClick={() => setOpenComment((v) => !v)}>
        👎
      </button>
      {openComment && (
        <div className="fb-form">
          <input
            placeholder="¿Qué faltó o estuvo mal? (opcional)"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && onVote('down', comment)}
          />
          <button className="fb-send" onClick={() => onVote('down', comment)}>
            Enviar
          </button>
        </div>
      )}
    </div>
  )
}

function CuentaModal({ user, onClose, onDeleted }: { user: User; onClose: () => void; onDeleted: () => void }) {
  const [confirmando, setConfirmando] = useState(false)
  const [pin, setPin] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  async function eliminar() {
    setErr('')
    if (!/^\d{4,8}$/.test(pin)) return setErr('Ingresá tu PIN para confirmar.')
    setBusy(true)
    try {
      const { status } = await deleteAccount(user.email, pin.trim())
      if (status === 200) onDeleted()
      else if (status === 401) setErr('PIN incorrecto.')
      else if (status === 403) setErr('La cuenta de administrador no puede eliminarse.')
      else setErr('No se pudo eliminar la cuenta.')
    } catch {
      setErr('No se pudo conectar al servidor.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-h">Mi cuenta</div>
        <div className="modal-row">
          <span>Nombre</span>
          <b>{user.name}</b>
        </div>
        <div className="modal-row">
          <span>Email</span>
          <b>{user.email}</b>
        </div>

        <div className="modal-danger">
          <div className="modal-danger-t">Eliminar mi cuenta</div>
          <p>Borra tu cuenta, historial y conversaciones de forma permanente. Las métricas agregadas se conservan anonimizadas.</p>
          {!confirmando ? (
            <button className="btn-danger" onClick={() => setConfirmando(true)}>
              Eliminar mi cuenta y datos
            </button>
          ) : (
            <div className="modal-confirm">
              <input
                type="password"
                maxLength={8}
                placeholder="Confirmá con tu PIN"
                value={pin}
                onChange={(e) => setPin(e.target.value)}
              />
              <button className="btn-danger" disabled={busy} onClick={eliminar}>
                {busy ? 'Eliminando…' : 'Eliminar definitivamente'}
              </button>
              <button className="btn-ghost" onClick={() => { setConfirmando(false); setPin(''); setErr('') }}>
                Cancelar
              </button>
            </div>
          )}
          {err && <p className="err">{err}</p>}
        </div>

        <button className="btn-ghost modal-close" onClick={onClose}>
          Cerrar
        </button>
      </div>
    </div>
  )
}

// Heurística de "sin evidencia" para ofrecer reintento enriquecido.
const MARCADORES_SIN_EV = [
  'no es posible calcular',
  'no puedo calcular',
  'no se puede calcular con la informaci',
  'no se encontró evidencia',
  'no se encontro evidencia',
  'no hay evidencia',
  'no dispongo de informaci',
  'no encontré información',
  'no encontre informacion',
]
function sinEvidencia(texto: string): boolean {
  const t = (texto || '').toLowerCase()
  return MARCADORES_SIN_EV.some((m) => t.includes(m))
}

const TOOL_ES: Record<string, string> = {
  clasificar_deudor: 'Clasificación del deudor',
  calcular_provision: 'Cálculo de provisión',
  cronograma_amortizacion: 'Cronograma de amortización',
}

function CalcCard({ c }: { c: Calculo }) {
  const entradas = Object.entries(c.inputs || {})
  const salidas = Object.entries(c.output || {})
  return (
    <div className={`calc ${c.error ? 'calc-err' : ''}`}>
      <div className="calc-h">🧮 {TOOL_ES[c.tool] || c.tool}</div>
      {c.error ? (
        <div className="calc-error">{c.error}</div>
      ) : (
        <div className="calc-body">
          {entradas.length > 0 && (
            <div className="calc-col">
              <span className="calc-lbl">Datos</span>
              {entradas.map(([k, v]) => (
                <div className="calc-kv" key={k}><span>{k}</span>{String(v)}</div>
              ))}
            </div>
          )}
          <div className="calc-col">
            <span className="calc-lbl">Resultado</span>
            {salidas.map(([k, v]) => (
              <div className="calc-kv" key={k}><span>{k}</span><b>{typeof v === 'object' ? JSON.stringify(v) : String(v)}</b></div>
            ))}
          </div>
        </div>
      )}
      {c.fuente_normativa && <div className="calc-src">Base: {c.fuente_normativa}</div>}
    </div>
  )
}

const ROLES = ['Compliance officer', 'Auditor', 'Riesgos', 'Contabilidad/IFRS', 'Tecnología/Ciberseguridad', 'Legal', 'Operaciones', 'Inversionista', 'Asesor regulatorio']
const OBJETIVOS = ['Informe integral', 'Identificar normas aplicables', 'Calcular requerimiento', 'Tratamiento contable', 'Evaluar riesgos', 'Qué documentos presentar', 'Comparar escenarios']
const TEMAS = ['Riesgo de crédito', 'Riesgo operacional', 'LAFT', 'Gobierno corporativo', 'Ciberseguridad', 'Contabilidad', 'Patrimonio/Basilea', 'Titulización/Fideicomiso', 'Pensiones', 'Mercado de valores', 'Protección al consumidor', 'Tributario']

function Wizard({ onClose, onGenerar }: { onClose: () => void; onGenerar: (prompt: string) => void }) {
  const [rol, setRol] = useState('')
  const [caso, setCaso] = useState('')
  const [objetivo, setObjetivo] = useState('')
  const [temas, setTemas] = useState<string[]>([])

  function toggleTema(t: string) {
    setTemas((p) => (p.includes(t) ? p.filter((x) => x !== t) : [...p, t]))
  }
  function generar() {
    const partes = [
      rol && `Actúo como ${rol}.`,
      caso && `Caso: ${caso}`,
      objetivo && `Necesito: ${objetivo}.`,
      temas.length && `Temas relevantes: ${temas.join(', ')}.`,
    ].filter(Boolean)
    onGenerar(partes.join('\n'))
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal wizard" onClick={(e) => e.stopPropagation()}>
        <div className="modal-h">🪄 Asistente para formular tu consulta</div>
        <div className="wz-field">
          <label>Tu rol</label>
          <select value={rol} onChange={(e) => setRol(e.target.value)}>
            <option value="">Elegí…</option>
            {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>
        <div className="wz-field">
          <label>Describí el caso</label>
          <textarea rows={3} value={caso} onChange={(e) => setCaso(e.target.value)} placeholder="Ej: un crédito de consumo con 45 días de atraso…" />
        </div>
        <div className="wz-field">
          <label>¿Qué necesitás?</label>
          <select value={objetivo} onChange={(e) => setObjetivo(e.target.value)}>
            <option value="">Elegí…</option>
            {OBJETIVOS.map((o) => <option key={o} value={o}>{o}</option>)}
          </select>
        </div>
        <div className="wz-field">
          <label>Temas relevantes</label>
          <div className="wz-temas">
            {TEMAS.map((t) => (
              <button key={t} className={`chip ${temas.includes(t) ? 'chip-on' : ''}`} onClick={() => toggleTema(t)}>{t}</button>
            ))}
          </div>
        </div>
        <div className="survey-actions">
          <button className="btn-primary" disabled={!caso.trim() && !objetivo} onClick={generar}>Generar consulta</button>
          <button className="btn-ghost" onClick={onClose}>Cancelar</button>
        </div>
      </div>
    </div>
  )
}

function ClarificationForm({
  questions,
  reason,
  onSubmit,
  onSkip,
}: {
  questions: PlanQuestion[]
  reason?: string
  onSubmit: (r: Record<string, string>) => void
  onSkip: () => void
}) {
  const [resp, setResp] = useState<Record<string, string>>({})
  const set = (id: string, v: string) => setResp((p) => ({ ...p, [id]: v }))
  return (
    <div className="clarify">
      <div className="clarify-h">Para darte una mejor respuesta, ayudame con esto:</div>
      {reason && <div className="clarify-reason">{reason}</div>}
      {questions.map((q) => (
        <div className="clarify-q" key={q.id}>
          <label>{q.label}</label>
          {q.rationale && <span className="clarify-rat">{q.rationale}</span>}
          {q.type === 'select' && q.options ? (
            <select value={resp[q.id] || ''} onChange={(e) => set(q.id, e.target.value)}>
              <option value="">Elegí…</option>
              {q.options.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          ) : q.type === 'multiselect' && q.options ? (
            <div className="wz-temas">
              {q.options.map((o) => {
                const sel = (resp[q.id] || '').split('|').filter(Boolean)
                const on = sel.includes(o)
                return (
                  <button
                    key={o}
                    className={`chip ${on ? 'chip-on' : ''}`}
                    onClick={() => set(q.id, (on ? sel.filter((x) => x !== o) : [...sel, o]).join('|'))}
                  >
                    {o}
                  </button>
                )
              })}
            </div>
          ) : (
            <input value={resp[q.id] || ''} onChange={(e) => set(q.id, e.target.value)} />
          )}
        </div>
      ))}
      <div className="clarify-actions">
        <button className="btn-primary" onClick={() => onSubmit({ ...resp, ...Object.fromEntries(Object.entries(resp).map(([k, v]) => [k, v.replace(/\|/g, ', ')])) })}>
          Continuar con esa info
        </button>
        <button className="btn-ghost" onClick={onSkip}>Saltar y responder igual</button>
      </div>
    </div>
  )
}

function SiglasForm({
  siglas,
  onResolve,
  onSkip,
}: {
  siglas: SiglaAmbigua[]
  onResolve: (e: Record<string, string>) => void
  onSkip: () => void
}) {
  const [sel, setSel] = useState<Record<string, string>>({})
  return (
    <div className="clarify">
      <div className="clarify-h">Detecté siglas con más de un significado. ¿A cuál te referís?</div>
      {siglas.map((s) => (
        <div className="clarify-q" key={s.sigla}>
          <label>{s.sigla}</label>
          <div className="siglas-ops">
            {s.opciones.map((op) => (
              <button
                key={op.significado}
                className={`sigla-op ${sel[s.sigla] === op.significado ? 'on' : ''}`}
                onClick={() => setSel((p) => ({ ...p, [s.sigla]: op.significado }))}
              >
                <b>{op.significado}</b>
                <span>{op.contexto}</span>
                {op.norma_principal && <em>{op.norma_principal}</em>}
              </button>
            ))}
          </div>
        </div>
      ))}
      <div className="clarify-actions">
        <button
          className="btn-primary"
          disabled={siglas.some((s) => !sel[s.sigla])}
          onClick={() => onResolve(sel)}
        >
          Continuar
        </button>
        <button className="btn-ghost" onClick={onSkip}>Consultar sin especificar</button>
      </div>
    </div>
  )
}

// Panel colapsible de fuentes citadas (cerrado por defecto: el detalle de cada
// cita ya se ve inline en el popover del chip).
function SourcesPanel({ sources }: { sources: Source[] }) {
  const [open, setOpen] = useState(false)
  // Conservamos el número de cita original (índice en el orden de relevancia con
  // el que el modelo las citó) y ordenamos la VISTA por fecha desc (más reciente
  // primero) para escanear. El badge sigue apuntando a la cita correcta.
  const ordenadas = sources
    .map((s, i) => ({ s, cita: i + 1 }))
    .sort((a, b) => (b.s.publication_date || '').localeCompare(a.s.publication_date || ''))
  return (
    <div className="srcs">
      <button className={`srcs-toggle ${open ? 'open' : ''}`} onClick={() => setOpen((v) => !v)}>
        <span className="srcs-chev">▸</span>
        Fuentes citadas ({sources.length})
      </button>
      {open && (
        <div className="src-grid">
          {ordenadas.slice(0, 6).map(({ s, cita }) => (
            <SourceCard s={s} n={cita} key={cita} />
          ))}
        </div>
      )}
    </div>
  )
}

function SourceCard({ s, n }: { s: Source; n?: number }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="src" id={n ? `fuente-${n}` : undefined}>
      <a href={s.url || undefined} target="_blank" rel="noreferrer" className="src-head">
        <span className="src-top">
          {n != null && <span className="src-num">{n}</span>}
          {s.issuer && s.issuer !== '(s/d)' && <span className="iss">{s.issuer}</span>}
          {fmtFecha(s.publication_date, s.date_precision) && (
            <span className="src-fecha">{fmtFecha(s.publication_date, s.date_precision)}</span>
          )}
          {s.url && <span className="src-pdf">PDF ↗</span>}
        </span>
        <span className="src-t">{s.title}</span>
      </a>
      {s.section_path && <div className="src-path">{s.section_path}</div>}
      {s.content_snippet && (
        <button className="src-more" onClick={() => setOpen((v) => !v)}>
          {open ? 'Ocultar fragmento' : 'Ver fragmento del PDF'}
        </button>
      )}
      {open && s.content_snippet && <div className="src-snip">{s.content_snippet}</div>}
    </div>
  )
}

const EJEMPLOS: { ico: string; texto: string }[] = [
  { ico: '📄', texto: '¿Qué dice la Resolución SBS 11356-2008 sobre clasificación del deudor?' },
  { ico: '🛡️', texto: '¿Cuáles son las provisiones procíclicas vigentes?' },
  { ico: '🧮', texto: 'Cronograma de un crédito de S/ 1,000 al 38% a 12 meses' },
  { ico: '📋', texto: '¿Qué se declara en el Reporte Crediticio de Deudores?' },
]

// Aísla fallos de una sección para no tirar toda la app (white-screen).
class ErrorBoundary extends Component<{ children: ReactNode }, { error: boolean }> {
  state = { error: false }
  static getDerivedStateFromError() { return { error: true } }
  render() {
    if (this.state.error) {
      return (
        <div className="err-card" style={{ margin: '26px' }}>
          <div className="err-t">⚠ No se pudo cargar esta sección</div>
          <div className="err-m">Ocurrió un error al mostrar el contenido. Probá recargar la página.</div>
        </div>
      )
    }
    return this.props.children
  }
}

const TIMEOUT_MIN = 20 // cierre por inactividad

export default function Chat({ user, adminToken, onExit, onTimeout }: { user: User; adminToken?: string; onExit: () => void; onTimeout: () => void }) {
  const [convs, setConvs] = useState<Conversation[]>([])
  const [convId, setConvId] = useState<string | null>(null)
  const [msgs, setMsgs] = useState<Mensaje[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [paso, setPaso] = useState<string>('')
  const [sbOpen, setSbOpen] = useState(false) // drawer en móvil
  const [tab, setTab] = useState<'consultar' | 'topicos' | 'mapa' | 'admin'>('consultar')
  const [opts, setOpts] = useState<{ graph: boolean; hops: number; informe: boolean; agente: boolean; hyde: boolean }>({
    graph: false,
    hops: 1,
    informe: false,
    agente: false,
    hyde: false,
  })
  const [cuentaOpen, setCuentaOpen] = useState(false)
  const [wizardOpen, setWizardOpen] = useState(false)
  const [planPend, setPlanPend] = useState<{ query: string; questions: PlanQuestion[]; reason?: string } | null>(null)
  const [siglasPend, setSiglasPend] = useState<{ query: string; siglas: SiglaAmbigua[] } | null>(null)
  const [ultimaQuery, setUltimaQuery] = useState('')
  const [editId, setEditId] = useState<string | null>(null) // conversación en edición de título
  const [editVal, setEditVal] = useState('')
  const [delId, setDelId] = useState<string | null>(null) // conversación con confirmación de borrado
  const chatRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    listConversations(user.email).then(setConvs)
    // Nota: las métricas por usuario ya las registra la API en cada consulta
    // (log_query con alias). /v1/analytics/session es admin-only, no se llama aquí.
  }, [user.email])

  useEffect(() => {
    chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight })
  }, [msgs, streaming])

  // Cierre por inactividad + heartbeat de actividad (throttle 60s).
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>
    let ultimoPing = 0
    const reiniciar = () => {
      clearTimeout(timer)
      timer = setTimeout(onTimeout, TIMEOUT_MIN * 60 * 1000)
      const ahora = Date.now()
      if (ahora - ultimoPing > 60_000) {
        ultimoPing = ahora
        touchActivity(user.id)
      }
    }
    const eventos = ['mousedown', 'keydown', 'scroll', 'touchstart'] as const
    eventos.forEach((e) => window.addEventListener(e, reiniciar, { passive: true }))
    reiniciar()
    return () => {
      clearTimeout(timer)
      eventos.forEach((e) => window.removeEventListener(e, reiniciar))
    }
  }, [user.id, onTimeout])

  async function nuevaConversacion() {
    setTab('consultar') // volver al chat aunque estemos en Tópicos/Mapa/Admin
    const c = await createConversation(user.email, user.id)
    if (c) {
      setConvs((p) => [c, ...p])
      setConvId(c.id)
      setMsgs([])
    }
  }

  async function abrirConversacion(c: Conversation) {
    setTab('consultar')
    setConvId(c.id)
    setMsgs(await getMessages(c.id))
  }

  // Gate de siglas: si la consulta tiene siglas ambiguas sin explicar, pedimos
  // desambiguación antes de nada. Luego pasa al gate del planner.
  function enviar(texto: string) {
    const q = texto.trim()
    if (!q || streaming) return
    const siglas = detectarSiglas(q)
    if (siglas.length) {
      setInput('')
      setSiglasPend({ query: q, siglas })
      return
    }
    enviarConPlan(q)
  }

  // Gate del planner: si el modo Agente está activo, primero consulta /v1/plan.
  // Si el planner pide clarificaciones, las mostramos antes de responder.
  async function enviarConPlan(texto: string) {
    const q = texto.trim()
    if (!q || streaming) return
    if (opts.agente) {
      setInput('')
      setStreaming(true)
      setPaso('Analizando tu consulta')
      const pl = await plan(q)
      setStreaming(false)
      setPaso('')
      if (pl.action === 'ask_clarifications' && pl.questions.length) {
        setPlanPend({ query: q, questions: pl.questions, reason: pl.reason || undefined })
        return
      }
    }
    _stream(q)
  }

  async function _stream(texto: string, force?: Partial<typeof opts>) {
    const q = texto.trim()
    if (!q) return
    setTab('consultar')
    setInput('')
    setPlanPend(null)
    setUltimaQuery(q)

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
    setPaso('')

    const eff = { ...opts, ...force }
    const history = msgs.slice(-6).map((m) => ({ role: m.rol, content: m.texto }))
    const options: QueryOptions = {
      expansion_enabled: eff.graph,
      max_hops: eff.graph ? eff.hops : 0,
      report_mode: eff.informe,
      hyde: eff.hyde,
    }
    let acc = ''
    let srcs: Source[] = []
    let calcs: Calculo[] = []
    let conf: string | undefined
    let lat: number | undefined
    let err: Mensaje['error']
    try {
      for await (const ev of queryStream({ query: q, alias: user.email, conversationId: cid, history, options })) {
        if (ev.type === 'token') {
          acc += ev.text
          setMsgs((p) => {
            const c = [...p]
            c[c.length - 1] = { rol: 'assistant', texto: acc, sources: srcs, calculations: calcs }
            return c
          })
        } else if (ev.type === 'sources') {
          srcs = ev.sources
        } else if (ev.type === 'calculations') {
          calcs = ev.calculations
        } else if (ev.type === 'status') {
          setPaso(NOMBRE_PASO[ev.step] || ev.step)
        } else if (ev.type === 'metadata') {
          conf = ev.confidence
          lat = ev.latency_ms
        } else if (ev.type === 'error') {
          err = { title: ev.title, message: ev.message, hint: ev.hint }
        }
      }
    } catch {
      err = err || { title: 'Error de conexión', message: 'No se pudo contactar al servidor.', hint: 'Revisá tu conexión y reintentá.' }
    } finally {
      setMsgs((p) => {
        const c = [...p]
        c[c.length - 1] = {
          rol: 'assistant',
          texto: acc || (err ? '' : '(sin respuesta)'),
          sources: srcs,
          calculations: calcs,
          confidence: conf,
          latencyMs: lat,
          error: err,
        }
        return c
      })
      setStreaming(false)
      setPaso('')
      listConversations(user.email).then(setConvs)
    }
  }

  // El usuario eligió el significado de las siglas → reemplaza y continúa.
  function resolverSiglas(elecciones: Record<string, string>) {
    if (!siglasPend) return
    const q = aplicarSiglas(siglasPend.query, elecciones)
    setSiglasPend(null)
    enviarConPlan(q)
  }

  // El usuario responde las clarificaciones del planner → consulta enriquecida.
  function enviarClarificado(respuestas: Record<string, string>) {
    if (!planPend) return
    const extra = planPend.questions
      .map((q) => {
        const r = respuestas[q.id]
        return r ? `- ${q.label} ${r}` : ''
      })
      .filter(Boolean)
      .join('\n')
    const enriquecida = extra ? `${planPend.query}\n\nContexto adicional:\n${extra}` : planPend.query
    _stream(enriquecida)
  }

  // "Probar de otra forma": reintenta la última consulta forzando grafo + 2 saltos.
  function reintentar() {
    if (!ultimaQuery || streaming) return
    // Reintento enriquecido: grafo + 2 saltos + HyDE (pasaje hipotético para
    // mejorar el match en consultas vagas).
    _stream(ultimaQuery, { graph: true, hops: 2, agente: false, hyde: true })
  }

  function empezarEdicion(c: Conversation) {
    setDelId(null)
    setEditId(c.id)
    setEditVal(c.title)
  }

  async function guardarTitulo(c: Conversation) {
    const t = editVal.trim()
    setEditId(null)
    if (!t || t === c.title) return
    const ok = await renameConversation(c.id, user.email, t)
    if (ok) setConvs((p) => p.map((x) => (x.id === c.id ? { ...x, title: t } : x)))
  }

  async function confirmarBorrado(c: Conversation) {
    setDelId(null)
    const ok = await deleteConversation(c.id, user.email)
    if (ok) {
      setConvs((p) => p.filter((x) => x.id !== c.id))
      if (convId === c.id) {
        setConvId(null)
        setMsgs([])
      }
    }
  }

  function limpiarHistorial() {
    setMsgs([])
    setConvId(null)
  }

  async function votar(idx: number, vote: 'up' | 'down', comment?: string) {
    const m = msgs[idx]
    const pregunta = idx > 0 ? msgs[idx - 1].texto : ''
    setMsgs((p) => {
      const c = [...p]
      c[idx] = { ...c[idx], voted: vote }
      return c
    })
    await sendFeedback({
      email: user.email,
      conversationId: convId,
      question: pregunta,
      answer: m.texto,
      vote,
      comment,
    })
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
          <div className="sb-badge"><Logo size={34} variant="dark" /></div>
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
          {convs.length === 0 && <div style={{ fontSize: 12, color: '#7d93b3' }}>Aún no tienes conversaciones.</div>}
          {convs.map((c) =>
            editId === c.id ? (
              <div key={c.id} className="sb-conv-row editing">
                <input
                  className="sb-conv-edit"
                  autoFocus
                  value={editVal}
                  onChange={(e) => setEditVal(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') guardarTitulo(c)
                    if (e.key === 'Escape') setEditId(null)
                  }}
                  onBlur={() => guardarTitulo(c)}
                />
              </div>
            ) : delId === c.id ? (
              <div key={c.id} className="sb-conv-row confirm">
                <span className="sb-conv-del-q">¿Borrar?</span>
                <span className="sb-conv-acts static">
                  <button className="del-yes" title="Confirmar" onClick={() => confirmarBorrado(c)}>Sí</button>
                  <button title="Cancelar" onClick={() => setDelId(null)}>No</button>
                </span>
              </div>
            ) : (
              <div key={c.id} className={`sb-conv-row ${c.id === convId ? 'active' : ''}`}>
                <button
                  className="sb-conv"
                  onClick={() => abrirYcerrar(() => abrirConversacion(c))}
                  title={c.title}
                >
                  {c.title}
                </button>
                <span className="sb-conv-acts">
                  <button title="Renombrar" onClick={() => empezarEdicion(c)}>✎</button>
                  <button title="Borrar" onClick={() => setDelId(c.id)}>🗑</button>
                </span>
              </div>
            ),
          )}
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
          <div className="sb-foot-actions">
            <button className="sb-account" onClick={() => setCuentaOpen(true)}>
              Mi cuenta
            </button>
            <button className="sb-exit" onClick={onExit}>
              Cerrar sesión
            </button>
          </div>
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
            <a className={tab === 'consultar' ? 'active' : ''} onClick={() => setTab('consultar')}>
              Consultar
            </a>
            <a className={tab === 'topicos' ? 'active' : ''} onClick={() => setTab('topicos')}>
              Tópicos
            </a>
            <a className={tab === 'mapa' ? 'active' : ''} onClick={() => setTab('mapa')}>
              Mapa
            </a>
            {adminToken && (
              <a className={`nav-admin ${tab === 'admin' ? 'active' : ''}`} onClick={() => setTab('admin')}>
                Admin
              </a>
            )}
          </nav>
        </div>

        {tab === 'topicos' && (
          <Suspense fallback={<div className="loading" style={{ padding: 26 }}>Cargando…</div>}>
            <Topicos />
          </Suspense>
        )}
        {tab === 'mapa' && (
          <Suspense fallback={<div className="loading" style={{ padding: 26 }}>Cargando mapa…</div>}>
            <Mapa />
          </Suspense>
        )}
        {tab === 'admin' && adminToken && (
          <ErrorBoundary>
            <Suspense fallback={<div className="loading" style={{ padding: 26 }}>Cargando panel…</div>}>
              <Admin token={adminToken} />
            </Suspense>
          </ErrorBoundary>
        )}
        {tab === 'consultar' && (
        <>
        <div className="chat" ref={chatRef}>
          {vacio && !siglasPend && !planPend ? (
            <div className="empty">
              <h2>¿Sobre qué normativa quieres consultar?</h2>
              <p>Escribe tu pregunta abajo, o elige un ejemplo</p>
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
                  {m.rol === 'assistant' && m.error ? (
                    <div className="err-card">
                      <div className="err-t">⚠ {m.error.title || 'No se pudo completar la consulta'}</div>
                      <div className="err-m">{m.error.message}</div>
                      {m.error.hint && <div className="err-h">{m.error.hint}</div>}
                    </div>
                  ) : (
                    <div className="bubble">
                      {m.rol === 'assistant' ? (
                        m.texto ? (
                          <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            components={{ a: (props) => <Cita {...props} sources={m.sources} /> }}
                          >
                            {preprocesarCitas(m.texto)}
                          </ReactMarkdown>
                        ) : streaming && i === msgs.length - 1 ? (
                          <span className="typing">{paso ? `${paso}…` : '▍'}</span>
                        ) : (
                          ''
                        )
                      ) : (
                        m.texto
                      )}
                    </div>
                  )}
                </div>
                {m.rol === 'assistant' && m.calculations && m.calculations.length > 0 && (
                  <div className="calcs">
                    {m.calculations.map((c, j) => (
                      <CalcCard c={c} key={j} />
                    ))}
                  </div>
                )}
                {m.rol === 'assistant' && m.texto && !(streaming && i === msgs.length - 1) && (
                  <div className="msg-meta">
                    {m.confidence && (
                      <span className={`conf conf-${m.confidence}`}>
                        {CONF_LABEL[m.confidence] || m.confidence}
                      </span>
                    )}
                    {m.latencyMs != null && <span className="lat">⏱ {(m.latencyMs / 1000).toFixed(1)}s</span>}
                    {i === msgs.length - 1 && sinEvidencia(m.texto) && (
                      <button className="retry-btn" disabled={streaming} onClick={reintentar} title="Reintenta con expansión por grafo">
                        🔁 Probar de otra forma
                      </button>
                    )}
                    <FeedbackBar msg={m} onVote={(v, c) => votar(i, v, c)} />
                  </div>
                )}
                {m.rol === 'assistant' && m.sources && m.sources.length > 0 && (
                  <SourcesPanel sources={m.sources} />
                )}
              </div>
            ))
          )}
          {siglasPend && (
            <SiglasForm
              siglas={siglasPend.siglas}
              onResolve={resolverSiglas}
              onSkip={() => { const q = siglasPend.query; setSiglasPend(null); enviarConPlan(q) }}
            />
          )}
          {planPend && (
            <ClarificationForm
              questions={planPend.questions}
              reason={planPend.reason}
              onSubmit={(r) => enviarClarificado(r)}
              onSkip={() => _stream(planPend.query)}
            />
          )}
        </div>

        <div className="composer">
          <div className="opts">
            <button className="opt" onClick={() => setWizardOpen(true)} title="Asistente para formular tu consulta">
              🪄 Asistente
            </button>
            <button
              className={`opt ${opts.agente ? 'opt-on' : ''}`}
              onClick={() => setOpts((o) => ({ ...o, agente: !o.agente }))}
              title="El agente pide clarificaciones si tu consulta es ambigua"
            >
              Agente
            </button>
            <button
              className={`opt ${opts.graph ? 'opt-on' : ''}`}
              onClick={() => setOpts((o) => ({ ...o, graph: !o.graph }))}
              title="Enriquece la búsqueda con el grafo de conocimiento"
            >
              Grafo
            </button>
            {opts.graph && (
              <button
                className="opt opt-on"
                onClick={() => setOpts((o) => ({ ...o, hops: o.hops === 1 ? 2 : 1 }))}
                title="Saltos de expansión en el grafo"
              >
                {opts.hops} salto{opts.hops > 1 ? 's' : ''}
              </button>
            )}
            <button
              className={`opt ${opts.informe ? 'opt-on' : ''}`}
              onClick={() => setOpts((o) => ({ ...o, informe: !o.informe }))}
              title="Respuesta estructurada por dimensiones"
            >
              Informe
            </button>
            {!vacio && (
              <button className="opt opt-clear" onClick={limpiarHistorial} title="Vaciar el chat actual">
                🗑 Limpiar
              </button>
            )}
          </div>
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
        </>
        )}
      </main>

      {cuentaOpen && (
        <CuentaModal user={user} onClose={() => setCuentaOpen(false)} onDeleted={onExit} />
      )}
      {wizardOpen && (
        <Wizard
          onClose={() => setWizardOpen(false)}
          onGenerar={(prompt) => {
            setInput(prompt)
            setOpts((o) => ({ ...o, graph: true, hops: 2, informe: true, agente: true }))
            setWizardOpen(false)
          }}
        />
      )}
    </div>
  )
}
