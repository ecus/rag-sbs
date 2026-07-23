import { useEffect, useMemo, useRef, useState } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import { getGraphData, type GNode } from './api'

// Con miles de documentos el grafo completo es un "ovillo" ilegible. Dos modos:
//  - Explorar (por defecto): arranca mostrando los nodos más conectados como
//    puntos de entrada; al elegir/click en una norma se muestra SOLO su red
//    (vecinos a 1-2 saltos). Nunca se renderizan más de unas decenas de nodos.
//  - Ver todo: el grafo acotado clásico, con umbral de fuerza de enlaces.
// Además: canvas (no SVG), etiquetas selectivas y (al desplegar) sparsificación
// de aristas en el backend vía max_edges_per_node.

type Sel = { id: string; label: string; issuer: string; grado: number; kind: string } | null

const FILTROS = [
  { key: 'all', label: 'Todo' },
  { key: 'resolution', label: 'Resoluciones' },
  { key: 'ley', label: 'Leyes' },
  { key: 'circular', label: 'Circulares' },
  { key: 'document', label: 'Documentos' },
]

// Un "Artículo-N" suelto es un número sin la norma que lo contiene, así que un
// mismo nodo puede unir documentos que citan el art. 52 de leyes DISTINTAS →
// falsos puentes. Esos se ocultan del grafo y se muestran como atributos en el
// panel. En cambio, los artículos CALIFICADOS con su norma ("Ley-26702 · Art. 52")
// sí son entidades reales y se dibujan como nodos: conectar dos documentos por
// uno de ellos es una relación legítima.
const RX_ART_SUELTO = /^Articulo-\d+$/
const esPuenteFalso = (kind: string, label: string) => kind === 'articulo' && RX_ART_SUELTO.test(label || '')

// "Articulo-52" → "art. 52" para las etiquetas del panel.
const artLabel = (label: string) => (label || '').replace(/^Articulo-/i, 'art. ')

export default function Mapa() {
  const wrapRef = useRef<HTMLDivElement>(null)
  const fgRef = useRef<any>(null)
  const [modo, setModo] = useState<'explorar' | 'todo'>('explorar')
  const [limit, setLimit] = useState(120)
  const [filtro, setFiltro] = useState('all')
  const [busca, setBusca] = useState('')
  const [minPeso, setMinPeso] = useState(0.35) // umbral de arista (modo Ver todo)
  const [hops, setHops] = useState(1) // saltos de vecindad (modo Explorar)
  const [raw, setRaw] = useState<{ nodes: GNode[]; edges: { from: string; to: string; relation: string; peso: number }[] }>({
    nodes: [],
    edges: [],
  })
  const [loading, setLoading] = useState(true)
  const [sel, setSel] = useState<Sel>(null)
  const [hover, setHover] = useState<string | null>(null)
  const [size, setSize] = useState({ w: 800, h: 460 })

  useEffect(() => {
    setLoading(true)
    // En modo Explorar traemos más nodos (mejor cobertura para navegar),
    // sparsificados en el backend. Pasamos el filtro por tipo (kind) para que
    // el backend traiga esos nodos (p.ej. circulares, que tienen bajo grado y
    // de otro modo nunca entran al top-N).
    const n = modo === 'explorar' ? 350 : limit
    getGraphData(n, 8, filtro).then((d) => {
      setRaw(d)
      setLoading(false)
    })
  }, [limit, modo, filtro])

  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const ro = new ResizeObserver(() => setSize({ w: el.clientWidth, h: el.clientHeight }))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])


  // Índice id→nodo (incluye artículos, que no se dibujan pero sí alimentan el
  // panel de detalle) y el conjunto de nodos ocultos (falsos puentes).
  const nodeById = useMemo(() => {
    const m = new Map<string, GNode>()
    for (const n of raw.nodes) m.set(n.id, n)
    return m
  }, [raw.nodes])
  const ocultos = useMemo(() => {
    const s = new Set<string>()
    for (const n of raw.nodes) if (esPuenteFalso(n.kind, n.label)) s.add(n.id)
    return s
  }, [raw.nodes])
  // Aristas "visibles": ninguno de sus extremos es un falso puente. Así los
  // artículos dejan de conectar documentos entre sí.
  const edgesVis = useMemo(
    () => raw.edges.filter((e) => !ocultos.has(e.from) && !ocultos.has(e.to)),
    [raw.edges, ocultos],
  )

  const data = useMemo(() => {
    const q = busca.trim().toLowerCase()
    let base = raw.nodes.filter((n) => !esPuenteFalso(n.kind, n.label))
    if (filtro !== 'all') base = base.filter((n) => n.kind === filtro)

    if (modo === 'explorar') {
      if (sel) {
        // Vecindario acotado: por cada nodo de la frontera tomamos solo sus
        // aristas más fuertes (top-K por peso). Los falsos puentes (artículos)
        // no se traversan, así el subgrafo queda legible y sin uniones espurias.
        const K1 = 24 // vecinos directos máx.
        const K2 = 6 // por cada vecino en el 2º salto
        const set = new Set<string>([sel.id])
        let frontera: string[] = [sel.id]
        for (let h = 0; h < hops; h++) {
          const tope = h === 0 ? K1 : K2
          const sig: string[] = []
          for (const id of frontera) {
            const incid = edgesVis
              .filter((e) => e.from === id || e.to === id)
              .sort((a, b) => b.peso - a.peso)
              .slice(0, tope)
            for (const e of incid) {
              const v = e.from === id ? e.to : e.from
              if (!set.has(v)) {
                set.add(v)
                sig.push(v)
              }
            }
          }
          frontera = sig
        }
        const nodes = raw.nodes.filter((n) => set.has(n.id) && !esPuenteFalso(n.kind, n.label))
        const links = edgesVis
          .filter((e) => set.has(e.from) && set.has(e.to))
          .map((e) => ({ source: e.from, target: e.to, relation: e.relation, peso: e.peso }))
        return { nodes: nodes.map((n) => ({ ...n })), links }
      }
      // Sin semilla: puntos de entrada = nodos más conectados (o resultados de búsqueda)
      let entrada = [...base].sort((a, b) => b.grado - a.grado)
      if (q) entrada = entrada.filter((n) => (n.label || '').toLowerCase().includes(q))
      entrada = entrada.slice(0, q ? 40 : 30)
      // Aristas entre los puntos de entrada → muestra el "backbone" del grafo.
      const ids = new Set(entrada.map((n) => n.id))
      const links = edgesVis
        .filter((e) => e.peso >= minPeso && ids.has(e.from) && ids.has(e.to))
        .map((e) => ({ source: e.from, target: e.to, relation: e.relation, peso: e.peso }))
      return { nodes: entrada.map((n) => ({ ...n })), links }
    }

    // Modo Ver todo
    let nodes = base
    if (q) nodes = nodes.filter((n) => (n.label || '').toLowerCase().includes(q))
    const ids = new Set(nodes.map((n) => n.id))
    const links = edgesVis
      .filter((e) => e.peso >= minPeso && ids.has(e.from) && ids.has(e.to))
      .map((e) => ({ source: e.from, target: e.to, relation: e.relation, peso: e.peso }))
    return { nodes: nodes.map((n) => ({ ...n })), links }
  }, [raw, edgesVis, filtro, busca, minPeso, modo, sel, hops])

  // Detalle del nodo seleccionado: sus relaciones agrupadas por tipo + los
  // artículos que cita (mostrados como atributos, ya no como nodos-puente).
  const detalle = useMemo(() => {
    if (!sel) return null
    const citaA: { id: string; label: string }[] = []
    const citadoPor: { id: string; label: string }[] = []
    const mismoTopico: { id: string; label: string }[] = []
    const otros: { id: string; label: string; rel: string }[] = []
    const articulos: string[] = []
    const vistos = new Set<string>()
    for (const e of raw.edges) {
      const saliente = e.from === sel.id
      const entrante = e.to === sel.id
      if (!saliente && !entrante) continue
      const otroId = saliente ? e.to : e.from
      const otro = nodeById.get(otroId)
      if (!otro) continue
      if (esPuenteFalso(otro.kind, otro.label)) {
        if (saliente) {
          const al = artLabel(otro.label)
          if (!articulos.includes(al)) articulos.push(al)
        }
        continue
      }
      const clave = `${otroId}|${e.relation}|${saliente}`
      if (vistos.has(clave)) continue
      vistos.add(clave)
      const item = { id: otroId, label: otro.label }
      if (e.relation === 'same_topic') mismoTopico.push(item)
      else if (e.relation === 'cites' && saliente) citaA.push(item)
      else if (e.relation === 'cites' && entrante) citadoPor.push(item)
      else otros.push({ ...item, rel: e.relation })
    }
    return { citaA, citadoPor, mismoTopico, otros, articulos }
  }, [sel, raw.edges, nodeById])

  // Saltar a un nodo relacionado desde el panel de detalle (re-centra la red).
  const irA = (id: string) => {
    const n = nodeById.get(id)
    if (!n) return
    setSel({ id: n.id, label: n.label, issuer: n.issuer, grado: n.grado, kind: n.kind })
  }

  const foco = hover || sel?.id || null
  const vecinosVis = useMemo(() => {
    const m = new Map<string, Set<string>>()
    for (const l of data.links) {
      if (!m.has(l.source)) m.set(l.source, new Set())
      if (!m.has(l.target)) m.set(l.target, new Set())
      m.get(l.source)!.add(l.target)
      m.get(l.target)!.add(l.source)
    }
    return m
  }, [data.links])
  const enFoco = (id: string) => !foco || id === foco || vecinosVis.get(foco)?.has(id)

  // Afina la física del grafo para que no se apelmace (más repulsión, enlaces
  // con distancia fija y tope de alcance para que los nodos sueltos no vuelen).
  useEffect(() => {
    const fg = fgRef.current
    if (!fg || loading) return
    const charge = fg.d3Force?.('charge')
    if (charge) {
      charge.strength(-160)
      charge.distanceMax(500)
    }
    const link = fg.d3Force?.('link')
    if (link) link.distance(60)
    fg.d3ReheatSimulation?.()
  }, [data, loading])

  return (
    <div className="pane pane-full">
      <div className="mapa-controls">
        <div className="mapa-modes">
          <button className={`chip ${modo === 'explorar' ? 'chip-on' : ''}`} onClick={() => { setModo('explorar'); setSel(null) }}>
            Explorar
          </button>
          <button className={`chip ${modo === 'todo' ? 'chip-on' : ''}`} onClick={() => { setModo('todo'); setSel(null) }}>
            Ver todo
          </button>
        </div>
        <input
          className="mapa-search"
          placeholder={modo === 'explorar' ? 'Buscar norma para explorar…' : 'Buscar norma…'}
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
        />
        {FILTROS.map((f) => (
          <button key={f.key} className={`chip ${filtro === f.key ? 'chip-on' : ''}`} onClick={() => setFiltro(f.key)}>
            {f.label}
          </button>
        ))}
        {modo === 'explorar' ? (
          <label className="mapa-slider" title="Saltos de vecindad desde la norma seleccionada">
            Saltos
            <select className="mapa-limit" value={hops} onChange={(e) => setHops(Number(e.target.value))}>
              <option value={1}>1</option>
              <option value={2}>2</option>
            </select>
          </label>
        ) : (
          <>
            <label className="mapa-slider" title="Oculta las conexiones más débiles">
              Enlaces
              <input type="range" min={0} max={1} step={0.05} value={minPeso} onChange={(e) => setMinPeso(Number(e.target.value))} />
            </label>
            <select className="mapa-limit" value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
              <option value={80}>80 nodos</option>
              <option value={120}>120 nodos</option>
              <option value={200}>200 nodos</option>
              <option value={350}>350 nodos</option>
            </select>
          </>
        )}
        <span className="mapa-count">
          {data.nodes.length} nodos · {data.links.length} conexiones
        </span>
      </div>

      <div className="mapa-body">
        <div className="mapa-canvas" ref={wrapRef}>
          {loading ? (
            <div className="loading" style={{ padding: 40 }}>Cargando grafo…</div>
          ) : (
            <ForceGraph2D
              ref={fgRef}
              width={size.w}
              height={size.h}
              graphData={data}
              nodeId="id"
              nodeRelSize={4}
              nodeVal={(n: any) => Math.max(1, ((n.size || 10) / 4 / 4) ** 2)}
              cooldownTicks={100}
              warmupTicks={30}
              d3VelocityDecay={0.35}
              onEngineStop={() => fgRef.current?.zoomToFit(500, 70)}
              linkColor={(l: any) => {
                const s = typeof l.source === 'object' ? l.source.id : l.source
                const t = typeof l.target === 'object' ? l.target.id : l.target
                if (foco && (s === foco || t === foco)) {
                  // Al resaltar, el color de la arista dice de qué relación se trata.
                  return l.relation === 'same_topic' ? 'rgba(15,110,86,0.85)' : 'rgba(37,99,235,0.7)'
                }
                if (foco) return 'rgba(148,163,184,0.12)'
                // En reposo: mismo-tópico teal (vínculo temático, el más significativo)
                // y citas en gris tenue.
                return l.relation === 'same_topic' ? 'rgba(15,110,86,0.55)' : 'rgba(100,116,139,0.4)'
              }}
              linkWidth={(l: any) => {
                const s = typeof l.source === 'object' ? l.source.id : l.source
                const t = typeof l.target === 'object' ? l.target.id : l.target
                if (foco && (s === foco || t === foco)) return 1.8
                return l.relation === 'same_topic' ? 1.4 : 0.8
              }}
              onNodeHover={(n: any) => setHover(n ? n.id : null)}
              onBackgroundClick={() => { if (modo === 'todo') setSel(null) }}
              onNodeClick={(n: any) => {
                setSel({ id: n.id, label: n.label, issuer: n.issuer, grado: n.grado, kind: n.kind })
                if (fgRef.current) {
                  fgRef.current.centerAt(n.x, n.y, 500)
                  fgRef.current.zoom(2.4, 500)
                }
              }}
              nodeCanvasObjectMode={() => 'replace'}
              nodePointerAreaPaint={(n: any, color: string, ctx: CanvasRenderingContext2D) => {
                // El área clickeable debe coincidir con el círculo visible (si no,
                // force-graph usa un punto diminuto en el centro y cuesta acertar).
                const r = Math.max(6, (n.size || 10) / 4)
                ctx.fillStyle = color
                ctx.beginPath()
                ctx.arc(n.x, n.y, r, 0, 2 * Math.PI)
                ctx.fill()
              }}
              nodeCanvasObject={(n: any, ctx: CanvasRenderingContext2D, scale: number) => {
                const activo = enFoco(n.id)
                const r = Math.max(2, (n.size || 10) / 4)
                ctx.beginPath()
                ctx.arc(n.x, n.y, r, 0, 2 * Math.PI)
                ctx.fillStyle = activo ? n.color : 'rgba(203,213,225,0.25)'
                ctx.fill()
                if (foco === n.id) {
                  ctx.lineWidth = 2 / scale
                  ctx.strokeStyle = '#dc0014'
                  ctx.stroke()
                }
                const isSel = sel && n.id === sel.id
                // En explorar hay pocos nodos → etiquetamos siempre; en ver todo, selectivo.
                const show =
                  modo === 'explorar'
                    ? activo
                    : isSel || n.id === foco || (activo && foco) || scale > 1.6 || (scale > 0.9 && n.grado > 25)
                if (!show || !activo) return
                const label = (n.label || '').slice(0, 26)
                const fs = Math.min(11 / scale, 6)
                ctx.font = `${isSel || n.id === foco ? 700 : 400} ${fs}px Inter, sans-serif`
                ctx.fillStyle = isSel || n.id === foco ? '#dc0014' : '#0f172a'
                ctx.textAlign = 'center'
                ctx.fillText(label, n.x, n.y + r + fs)
              }}
            />
          )}
        </div>

        <aside className="mapa-side">
          {modo === 'explorar' && sel ? (
            <button className="mapa-back" onClick={() => setSel(null)}>← Volver a puntos de entrada</button>
          ) : null}
          <div className="mapa-side-t">Selección</div>
          {sel ? (
            <div>
              <div className="sel-label">{sel.label}</div>
              <div className="sel-row"><span>Tipo</span>{sel.kind}</div>
              <div className="sel-row"><span>Institución</span>{sel.issuer}</div>
              <div className="sel-row"><span>Conexiones</span>{sel.grado}</div>

              {detalle && detalle.mismoTopico.length > 0 && (
                <div className="rel-grupo">
                  <div className="rel-h" style={{ color: '#0f6e56' }}>
                    <span className="rel-line" style={{ background: '#0f6e56' }} />
                    Mismo tópico que <em>({detalle.mismoTopico.length})</em>
                  </div>
                  {detalle.mismoTopico.slice(0, 12).map((r) => (
                    <button key={'mt' + r.id} className="rel-item" onClick={() => irA(r.id)}>{r.label}</button>
                  ))}
                </div>
              )}

              {detalle && detalle.citaA.length > 0 && (
                <div className="rel-grupo">
                  <div className="rel-h" style={{ color: '#2563eb' }}>
                    <span className="rel-line" style={{ background: '#64748b' }} />
                    Cita a <em>({detalle.citaA.length})</em>
                  </div>
                  {detalle.citaA.slice(0, 12).map((r) => (
                    <button key={'ca' + r.id} className="rel-item" onClick={() => irA(r.id)}>{r.label}</button>
                  ))}
                  {detalle.citaA.length > 12 && <div className="rel-mas">y {detalle.citaA.length - 12} más…</div>}
                </div>
              )}

              {detalle && detalle.citadoPor.length > 0 && (
                <div className="rel-grupo">
                  <div className="rel-h" style={{ color: '#64748b' }}>
                    <span className="rel-line" style={{ background: '#94a3b8' }} />
                    Citado por <em>({detalle.citadoPor.length})</em>
                  </div>
                  {detalle.citadoPor.slice(0, 12).map((r) => (
                    <button key={'cp' + r.id} className="rel-item" onClick={() => irA(r.id)}>{r.label}</button>
                  ))}
                  {detalle.citadoPor.length > 12 && <div className="rel-mas">y {detalle.citadoPor.length - 12} más…</div>}
                </div>
              )}

              {detalle && detalle.articulos.length > 0 && (
                <div className="rel-grupo">
                  <div className="rel-h" style={{ color: '#94a3b8' }}>Artículos citados</div>
                  <div className="art-chips">
                    {detalle.articulos.slice(0, 24).map((a) => (
                      <span key={a} className="art-chip">{a}</span>
                    ))}
                  </div>
                  <div className="rel-mas">No conectan documentos entre sí (el número de artículo por sí solo no identifica la norma).</div>
                </div>
              )}
            </div>
          ) : (
            <p className="mapa-hint">
              {modo === 'explorar'
                ? 'Busca o haz clic en una norma para ver su red de vínculos. Ideal para corpus grandes.'
                : 'Pasa el mouse para resaltar la red de una norma; haz clic para fijarla y ver su detalle.'}
            </p>
          )}
          <div className="mapa-side-t" style={{ marginTop: 18 }}>Instituciones (documentos)</div>
          {[
            ['SBS', '#003d7a'],
            ['BCRP', '#b91c1c'],
            ['Congreso', '#7c3aed'],
            ['MEF', '#15803d'],
            ['SMV', '#0891b2'],
            ['SUNAT', '#be185d'],
          ].map(([k, c]) => (
            <div className="leg" key={k}>
              <span className="dot" style={{ background: c }} />
              {k}
            </div>
          ))}
          <div className="mapa-side-t" style={{ marginTop: 16 }}>Tipo de norma</div>
          {[
            ['Resolución', '#5b6b8c'],
            ['Ley', '#334155'],
            ['Circular', '#8a94a6'],
            ['Artículo (de una norma)', '#aab4c4'],
            ['Anexo', '#c7cfdb'],
          ].map(([k, c]) => (
            <div className="leg" key={k}>
              <span className="dot" style={{ background: c }} />
              {k}
            </div>
          ))}
          <div className="mapa-side-t" style={{ marginTop: 16 }}>Tipo de conexión</div>
          <div className="leg"><span className="leg-line" style={{ background: '#0f6e56' }} />Mismo tópico</div>
          <div className="leg"><span className="leg-line" style={{ background: '#64748b' }} />Cita</div>
          <p className="mapa-hint" style={{ marginTop: 10 }}>
            Los documentos se colorean por institución; las normas, por tipo. Un artículo
            calificado con su norma ("Ley 26702 · Art. 52") sí es un nodo real; los números
            de artículo sueltos, en cambio, se muestran solo en el detalle del nodo (no
            identifican la norma, así que unían documentos sin relación).
          </p>
        </aside>
      </div>
    </div>
  )
}
