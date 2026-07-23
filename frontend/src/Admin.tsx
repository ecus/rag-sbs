import { useEffect, useState } from 'react'
import {
  adminApi,
  exportCsv,
  type PendingUser,
  type DashboardData,
  type FeedbackSummary,
  type UserAnalytics,
  type BgStatus,
  type IngestRun,
  type IngestEvent,
} from './api'

type Sec = 'monitoreo' | 'accesos' | 'limites' | 'feedback' | 'usuarios' | 'pin' | 'ingesta' | 'fuentes' | 'runs' | 'export'

const SECCIONES: { key: Sec; label: string }[] = [
  { key: 'monitoreo', label: 'Monitoreo' },
  { key: 'accesos', label: 'Accesos' },
  { key: 'limites', label: 'Límites' },
  { key: 'feedback', label: 'Feedback' },
  { key: 'usuarios', label: 'Usuarios' },
  { key: 'pin', label: 'Reset PIN' },
  { key: 'ingesta', label: 'Ingesta' },
  { key: 'fuentes', label: 'Fuentes' },
  { key: 'runs', label: 'Actividad' },
  { key: 'export', label: 'Export' },
]

const fecha = (s?: string | null) => (s ? new Date(s).toLocaleString() : '—')

function Barra({ datos }: { datos: [string, number][] }) {
  const max = datos.reduce((m, d) => Math.max(m, d[1]), 1)
  return (
    <div className="bars">
      {datos.map(([k, v], i) => (
        <div className="bar-row" key={i}>
          <span className="bar-lbl" title={k}>{k}</span>
          <div className="bar-track"><div className="bar-fill" style={{ width: `${(v / max) * 100}%` }} /></div>
          <span className="bar-val">{v.toLocaleString()}</span>
        </div>
      ))}
    </div>
  )
}

function Monitoreo({ token }: { token: string }) {
  const [dias, setDias] = useState(30)
  const [d, setD] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    setLoading(true)
    adminApi.dashboard(token, dias).then((r) => { setD(r); setLoading(false) })
  }, [token, dias])
  if (loading) return <div className="loading">Cargando…</div>
  if (!d) return <div className="loading">Sin datos.</div>
  return (
    <>
      <div className="ad-period">
        Período:
        {[7, 30, 90].map((n) => (
          <button key={n} className={`chip ${dias === n ? 'chip-on' : ''}`} onClick={() => setDias(n)}>{n} días</button>
        ))}
      </div>
      <div className="ad-metrics">
        <div className="ad-metric"><b>{(d.total_consultas || 0).toLocaleString()}</b><span>Consultas</span></div>
        <div className="ad-metric"><b>{d.usuarios_activos || 0}</b><span>Usuarios activos</span></div>
        <div className="ad-metric"><b>{Math.round(d.latencia_avg_ms || 0)} ms</b><span>Latencia media</span></div>
      </div>
      {d.consultas_por_dia?.length > 0 && (
        <><h4 className="ad-h">Consultas por día</h4><Barra datos={d.consultas_por_dia.map((x) => [x.dia, x.consultas])} /></>
      )}
      {d.top_documentos?.length > 0 && (
        <><h4 className="ad-h">Documentos más referenciados</h4><Barra datos={d.top_documentos.slice(0, 10).map((x) => [x.documento, x.referencias])} /></>
      )}
      {d.distribucion_confianza?.length > 0 && (
        <><h4 className="ad-h">Distribución de confianza</h4><Barra datos={d.distribucion_confianza.map((x) => [x.confianza, x.n])} /></>
      )}
    </>
  )
}

function Accesos({ token }: { token: string }) {
  const [pend, setPend] = useState<PendingUser[]>([])
  const [loading, setLoading] = useState(true)
  const cargar = () => { setLoading(true); adminApi.pending(token).then((r) => { setPend(r || []); setLoading(false) }) }
  useEffect(cargar, [token])
  async function accion(email: string, aprobar: boolean) {
    await (aprobar ? adminApi.approve(token, email) : adminApi.reject(token, email))
    setPend((p) => p.filter((u) => u.email !== email))
  }
  if (loading) return <div className="loading">Cargando…</div>
  if (pend.length === 0) return <div className="loading">No hay solicitudes de acceso pendientes.</div>
  return (
    <div className="ad-list">
      {pend.map((u) => (
        <div className="ad-row" key={u.email}>
          <div>
            <b>{u.name || u.email}</b>
            <span>{u.email}{u.organization ? ` · ${u.organization}` : ''}{u.role ? ` · ${u.role}` : ''}</span>
          </div>
          <div className="ad-row-acts">
            <button className="btn-ok" onClick={() => accion(u.email, true)}>Aprobar</button>
            <button className="btn-no" onClick={() => accion(u.email, false)}>Rechazar</button>
          </div>
        </div>
      ))}
    </div>
  )
}

function Limites({ token }: { token: string }) {
  const [email, setEmail] = useState('')
  const [lim, setLim] = useState('20')
  const [gd, setGd] = useState('')
  const [gh, setGh] = useState('')
  const [msg, setMsg] = useState('')
  useEffect(() => {
    adminApi.settings(token).then((s) => { if (s) { setGd(s.global_daily_limit || '0'); setGh(s.global_hourly_limit || '0') } })
  }, [token])
  async function guardarUsuario() {
    if (!email.trim()) return
    const { status } = await adminApi.setLimit(token, email.trim(), Number(lim))
    setMsg(status === 200 ? `Límite de ${email} actualizado.` : 'Error al actualizar.')
  }
  async function guardarGlobal() {
    const { status } = await adminApi.setGlobalLimits(token, Number(gd), Number(gh))
    setMsg(status === 200 ? 'Límites globales guardados.' : 'Error al guardar.')
  }
  return (
    <div className="ad-forms">
      <div className="ad-card">
        <div className="ad-card-t">Límite por usuario</div>
        <input placeholder="email del usuario" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input type="number" placeholder="límite diario (0 = sin límite)" value={lim} onChange={(e) => setLim(e.target.value)} />
        <button className="btn-primary" onClick={guardarUsuario}>Actualizar límite</button>
      </div>
      <div className="ad-card">
        <div className="ad-card-t">Límites globales (protegen la cuota de Gemini)</div>
        <label>Máx. por día</label>
        <input type="number" value={gd} onChange={(e) => setGd(e.target.value)} />
        <label>Máx. por hora (0 = sin límite)</label>
        <input type="number" value={gh} onChange={(e) => setGh(e.target.value)} />
        <button className="btn-primary" onClick={guardarGlobal}>Guardar límites globales</button>
      </div>
      {msg && <p className="ad-msg">{msg}</p>}
    </div>
  )
}

function Feedback({ token }: { token: string }) {
  const [d, setD] = useState<FeedbackSummary | null>(null)
  const [loading, setLoading] = useState(true)
  useEffect(() => { adminApi.feedback(token).then((r) => { setD(r); setLoading(false) }) }, [token])
  if (loading) return <div className="loading">Cargando…</div>
  if (!d) return <div className="loading">Sin datos.</div>
  const total = (d.likes || 0) + (d.dislikes || 0)
  const pct = total ? Math.round(((d.likes || 0) / total) * 100) : 0
  const coments = d.dislikes_detalle?.length ? d.dislikes_detalle : d.comentarios || []
  return (
    <>
      <div className="ad-metrics">
        <div className="ad-metric"><b>{d.likes || 0}</b><span>👍 Positivos</span></div>
        <div className="ad-metric"><b>{d.dislikes || 0}</b><span>👎 Negativos</span></div>
        <div className="ad-metric"><b>{pct}%</b><span>Satisfacción</span></div>
      </div>
      <h4 className="ad-h">Comentarios ({coments.length})</h4>
      <div className="ad-list">
        {coments.map((c, i) => (
          <div className="ad-coment" key={i}>
            <div className="ad-coment-txt">{c.comment || '(sin comentario)'}</div>
            <div className="ad-coment-meta">{c.email || 'anónimo'}{c.created_at ? ` · ${new Date(c.created_at).toLocaleDateString()}` : ''}</div>
            {c.question && <div className="ad-coment-q">P: {c.question}</div>}
          </div>
        ))}
        {coments.length === 0 && <div className="loading">Sin comentarios.</div>}
      </div>
    </>
  )
}

function Usuarios({ token }: { token: string }) {
  const [u, setU] = useState<UserAnalytics[]>([])
  const [loading, setLoading] = useState(true)
  useEffect(() => { adminApi.users(token).then((r) => { setU(r || []); setLoading(false) }) }, [token])
  if (loading) return <div className="loading">Cargando…</div>
  return (
    <table className="tbl">
      <thead><tr><th>Usuario</th><th>Consultas</th><th>Últ. actividad</th><th>Conf. alta</th><th>Sin evid.</th><th>Latencia</th></tr></thead>
      <tbody>
        {u.map((x, i) => (
          <tr key={i}>
            <td>{x.alias}</td>
            <td>{x.total}</td>
            <td>{x.ultima ? new Date(x.ultima).toLocaleDateString() : '—'}</td>
            <td>{x.conf_alta ?? '—'}</td>
            <td>{x.sin_evidencia ?? '—'}</td>
            <td>{x.lat_avg_ms ? `${Math.round(x.lat_avg_ms)} ms` : '—'}</td>
          </tr>
        ))}
        {u.length === 0 && <tr><td colSpan={6} className="loading">Sin datos.</td></tr>}
      </tbody>
    </table>
  )
}

function ResetPin({ token }: { token: string }) {
  const [email, setEmail] = useState('')
  const [msg, setMsg] = useState('')
  async function reset() {
    if (!email.trim()) return
    const { status } = await adminApi.resetPin(token, email.trim())
    setMsg(status === 200 ? `PIN de ${email} reseteado. El usuario definirá uno nuevo al ingresar.` : 'Error al resetear.')
  }
  return (
    <div className="ad-card" style={{ maxWidth: 420 }}>
      <div className="ad-card-t">Resetear PIN de un usuario</div>
      <p className="ad-sub">Borra el PIN y el código de recuperación. El usuario definirá un PIN nuevo en su próximo ingreso.</p>
      <input placeholder="email del usuario" value={email} onChange={(e) => setEmail(e.target.value)} />
      <button className="btn-danger" onClick={reset}>Resetear PIN</button>
      {msg && <p className="ad-msg">{msg}</p>}
    </div>
  )
}

function Ingesta({ token }: { token: string }) {
  const [d, setD] = useState<BgStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState('')
  const cargar = () => { setLoading(true); adminApi.bgStatus(token).then((r) => { setD(r); setLoading(false) }) }
  useEffect(cargar, [token])
  async function accion(nombre: string, fn: () => Promise<unknown>) {
    setBusy(nombre); setMsg('')
    try { await fn(); setMsg('Listo.') } catch { setMsg('Error.') }
    setBusy(''); cargar()
  }
  if (loading) return <div className="loading">Cargando…</div>
  if (!d) return <div className="loading">Sin datos.</div>
  const c = d.config, e = d.estado
  return (
    <>
      <div className="ad-metrics">
        <div className="ad-metric"><b>{e.total.docs}</b><span>Docs ingestados</span></div>
        <div className="ad-metric"><b>${(e.total.cost || 0).toFixed(3)}</b><span>Costo total</span></div>
        <div className="ad-metric"><b>${(e.today.cost || 0).toFixed(3)}</b><span>Costo hoy</span></div>
        <div className="ad-metric"><b>{e.queue.pending}</b><span>En cola</span></div>
      </div>
      <div className="ad-mini">
        Estado: <b style={{ color: c.enabled ? '#15803d' : '#b91c1c' }}>{c.enabled ? 'Activo' : 'Pausado'}</b>
        {' · '}Cola: {e.queue.completed} completados · {e.queue.failed} fallidos
        {' · '}Tope: {e.total.docs}/{c.max_docs_total} docs · ${(e.total.cost || 0).toFixed(2)}/${c.max_cost_total}
      </div>
      <p className="ad-warn">⚠ "Descubrir URLs" y "Procesar ahora" consumen cuota de Gemini (embeddings). Usar con criterio.</p>
      <div className="ad-actions">
        {c.enabled ? (
          <button className="btn-no" disabled={!!busy} onClick={() => accion('pause', () => adminApi.bgPause(token))}>⏸ Pausar</button>
        ) : (
          <button className="btn-ok" disabled={!!busy} onClick={() => accion('start', () => adminApi.bgStart(token))}>▶ Activar</button>
        )}
        <button className="btn-ghost" disabled={!!busy} onClick={() => accion('scrape', () => adminApi.bgScrape(token))}>{busy === 'scrape' ? 'Descubriendo…' : '🔍 Descubrir URLs'}</button>
        <button className="btn-ghost" disabled={!!busy} onClick={() => accion('tick', () => adminApi.bgTick(token))}>{busy === 'tick' ? 'Procesando…' : '⚡ Procesar ahora'}</button>
        <button className="btn-ghost" disabled={!!busy} onClick={cargar}>↻ Refrescar</button>
      </div>
      {msg && <p className="ad-msg">{msg}</p>}
    </>
  )
}

function Fuentes({ token }: { token: string }) {
  const [stats, setStats] = useState<Record<string, unknown> | null>(null)
  const [nItems, setNItems] = useState(0)
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState('')
  useEffect(() => { adminApi.catalog(token).then((r) => { if (r) { setStats(r.stats); setNItems(r.items?.length || 0) } }) }, [token])
  async function accion(nombre: string, fn: () => Promise<unknown>) {
    setBusy(nombre); setMsg('')
    try { await fn(); setMsg('Acción disparada.') } catch { setMsg('Error.') }
    setBusy('')
  }
  return (
    <>
      <div className="ad-metrics">
        <div className="ad-metric"><b>{nItems}</b><span>Fuentes en catálogo</span></div>
        {stats && Object.entries(stats)
          .filter(([, v]) => typeof v === 'number' || typeof v === 'string')
          .slice(0, 3)
          .map(([k, v]) => (
            <div className="ad-metric" key={k}><b>{String(v)}</b><span>{k.replace(/_/g, ' ')}</span></div>
          ))}
      </div>
      <p className="ad-warn">⚠ "Disparar scan" (no dry-run) descarga y procesa documentos → consume Gemini. El "dry-run" solo detecta cambios (sin costo).</p>
      <div className="ad-actions">
        <button className="btn-ghost" disabled={!!busy} onClick={() => accion('dry', () => adminApi.scan(token, true))}>{busy === 'dry' ? 'Escaneando…' : '🔎 Scan (dry-run, sin costo)'}</button>
        <button className="btn-primary" disabled={!!busy} onClick={() => accion('scan', () => adminApi.scan(token, false))}>{busy === 'scan' ? 'Disparando…' : '⚡ Disparar scan real'}</button>
        <button className="btn-ghost" disabled={!!busy} onClick={() => accion('seed', () => adminApi.seed(token))}>{busy === 'seed' ? 'Poblando…' : '🌱 Poblar catálogo'}</button>
      </div>
      {msg && <p className="ad-msg">{msg}</p>}
    </>
  )
}

function Actividad({ token }: { token: string }) {
  const [runs, setRuns] = useState<IngestRun[]>([])
  const [events, setEvents] = useState<IngestEvent[]>([])
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    Promise.all([adminApi.runs(token), adminApi.events(token)]).then(([r, e]) => {
      setRuns((r || []).slice(0, 15)); setEvents((e || []).slice(0, 15)); setLoading(false)
    })
  }, [token])
  if (loading) return <div className="loading">Cargando…</div>
  return (
    <>
      <h4 className="ad-h">Últimos runs del scheduler</h4>
      <table className="tbl">
        <thead><tr><th>Inicio</th><th>Estado</th><th>Nuevos</th><th>Modif.</th><th>Sin cambio</th><th>Errores</th><th>Por</th></tr></thead>
        <tbody>
          {runs.map((r) => (
            <tr key={r.id}>
              <td>{fecha(r.started_at)}</td>
              <td>{r.status}{r.dry_run ? ' (dry)' : ''}</td>
              <td>{r.docs_new ?? '—'}</td><td>{r.docs_modified ?? '—'}</td><td>{r.docs_unchanged ?? '—'}</td>
              <td>{r.errors ?? 0}</td><td>{r.triggered_by || '—'}</td>
            </tr>
          ))}
          {runs.length === 0 && <tr><td colSpan={7} className="loading">Sin runs.</td></tr>}
        </tbody>
      </table>
      <h4 className="ad-h">Eventos recientes</h4>
      <div className="ad-list">
        {events.map((ev) => (
          <div className="ad-row" key={ev.id}>
            <div><b>{ev.event_type}</b><span>{ev.summary}</span></div>
            <span className="ad-mini">{fecha(ev.created_at)}</span>
          </div>
        ))}
        {events.length === 0 && <div className="loading">Sin eventos.</div>}
      </div>
    </>
  )
}

function Export({ token }: { token: string }) {
  const hoy = new Date().toISOString().slice(0, 10)
  const [desde, setDesde] = useState(hoy)
  const [hasta, setHasta] = useState(hoy)
  const [msg, setMsg] = useState('')
  async function descargar() {
    setMsg('Generando…')
    const ok = await exportCsv(token, desde, hasta)
    setMsg(ok ? 'Descarga iniciada.' : 'Error al exportar.')
  }
  return (
    <div className="ad-card" style={{ maxWidth: 440 }}>
      <div className="ad-card-t">Exportar consultas a CSV</div>
      <label>Desde</label>
      <input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} />
      <label>Hasta</label>
      <input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} />
      <button className="btn-primary" onClick={descargar}>Descargar CSV</button>
      {msg && <p className="ad-msg">{msg}</p>}
    </div>
  )
}

export default function Admin({ token }: { token: string }) {
  const [sec, setSec] = useState<Sec>('monitoreo')
  return (
    <div className="pane admin">
      <div className="ad-tabs">
        {SECCIONES.map((s) => (
          <button key={s.key} className={`ad-tab ${sec === s.key ? 'on' : ''}`} onClick={() => setSec(s.key)}>{s.label}</button>
        ))}
      </div>
      <div className="ad-body">
        {sec === 'monitoreo' && <Monitoreo token={token} />}
        {sec === 'accesos' && <Accesos token={token} />}
        {sec === 'limites' && <Limites token={token} />}
        {sec === 'feedback' && <Feedback token={token} />}
        {sec === 'usuarios' && <Usuarios token={token} />}
        {sec === 'pin' && <ResetPin token={token} />}
        {sec === 'ingesta' && <Ingesta token={token} />}
        {sec === 'fuentes' && <Fuentes token={token} />}
        {sec === 'runs' && <Actividad token={token} />}
        {sec === 'export' && <Export token={token} />}
      </div>
    </div>
  )
}
