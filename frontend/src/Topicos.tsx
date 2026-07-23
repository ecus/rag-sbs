import { useEffect, useState } from 'react'
import { getTopics, getTopicsDetails, type Topico, type TopicoDetalle } from './api'

const TIPO_ES: Record<string, string> = {
  ley: 'Ley',
  resolution: 'Resolución',
  circular: 'Circular',
  article: 'Artículo',
  anexo: 'Anexo',
  topic: 'Tópico',
  document: 'Documento',
}

// Color institucional (misma paleta que el Mapa) para los badges por tópico.
const COLOR_ISSUER: Record<string, string> = {
  SBS: '#003d7a',
  BCRP: '#b91c1c',
  Congreso: '#7c3aed',
  MEF: '#15803d',
  SMV: '#0891b2',
  INDECOPI: '#ca8a04',
  SUNAT: '#be185d',
}

export default function Topicos() {
  const [temas, setTemas] = useState<TopicoDetalle[]>([])
  const [items, setItems] = useState<Topico[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([getTopicsDetails(), getTopics(20)]).then(([t, i]) => {
      setTemas(t)
      setItems(i)
      setLoading(false)
    })
  }, [])

  const max = items.reduce((m, i) => Math.max(m, i.citaciones), 1)
  const totalDocs = temas.reduce((s, t) => s + t.documentos_unicos, 0)
  const totalChunks = temas.reduce((s, t) => s + t.miembros, 0)

  return (
    <div className="pane">
      <h2 className="pane-title">Áreas temáticas del corpus</h2>
      <p className="pane-sub">Agrupación automática de la normativa por temas, con sus documentos y un fragmento representativo.</p>

      {loading ? (
        <div className="loading">Cargando…</div>
      ) : (
        <>
          {temas.length === 0 && (
            <div className="tp-empty">
              Las áreas temáticas aún no fueron generadas para este corpus. Se construyen desde el panel de
              administración (agrupamiento automático de la normativa). Mientras tanto, abajo tienes las normas más citadas.
            </div>
          )}
          {temas.length > 0 && (
            <>
              <div className="tp-metrics">
                <div className="tp-metric">
                  <b>{temas.length}</b>
                  <span>áreas temáticas</span>
                </div>
                <div className="tp-metric">
                  <b>{totalChunks.toLocaleString()}</b>
                  <span>fragmentos analizados</span>
                </div>
                <div className="tp-metric">
                  <b>{totalDocs.toLocaleString()}</b>
                  <span>documentos agrupados</span>
                </div>
              </div>

              <div className="tp-grid">
                {temas.map((t, i) => (
                  <div className="tp-card" key={i}>
                    <div className="tp-card-h">
                      <span className="tp-num">{(t.indice ?? i) + 1}</span>
                      <span className="tp-label">{t.label}</span>
                    </div>
                    <div className="tp-sub">
                      {t.miembros.toLocaleString()} fragmentos · {t.documentos_unicos} documentos
                    </div>
                    {t.por_issuer.length > 0 && (
                      <div className="tp-badges">
                        {t.por_issuer.slice(0, 6).map((p, j) => (
                          <span
                            className="tp-badge"
                            key={j}
                            style={{ background: COLOR_ISSUER[p.issuer] || '#94a3b8' }}
                          >
                            {p.issuer} {p.docs}
                          </span>
                        ))}
                      </div>
                    )}
                    {t.docs_top.length > 0 && (
                      <div className="tp-docs">
                        <div className="tp-docs-t">📚 Documentos</div>
                        {t.docs_top.slice(0, 4).map((d, j) => (
                          <div className="tp-doc" key={j} title={d.title}>
                            <span>{d.title}</span>
                            <small>{d.chunks_del_topico}</small>
                          </div>
                        ))}
                      </div>
                    )}
                    {t.samples[0]?.snippet && (
                      <div className="tp-snip">
                        <div className="tp-docs-t">💡 Fragmento representativo</div>
                        <p>{t.samples[0].snippet}</p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}

          <h2 className="pane-title" style={{ marginTop: 30 }}>Normas más citadas</h2>
          <p className="pane-sub">Ordenadas por número de referencias detectadas en el corpus.</p>
          {items.length === 0 ? (
            <div className="loading">Aún no hay entidades citadas.</div>
          ) : (
            <>
              <div className="bars">
                {items.slice(0, 12).map((it, i) => (
                  <div className="bar-row" key={i}>
                    <span className="bar-lbl" title={it.label}>{it.label}</span>
                    <div className="bar-track">
                      <div className="bar-fill" style={{ width: `${(it.citaciones / max) * 100}%` }} />
                    </div>
                    <span className="bar-val">{it.citaciones.toLocaleString()}</span>
                  </div>
                ))}
              </div>

              <table className="tbl">
                <thead>
                  <tr>
                    <th>Tipo</th>
                    <th>Norma</th>
                    <th style={{ textAlign: 'right' }}>Citaciones</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((it, i) => (
                    <tr key={i}>
                      <td>{TIPO_ES[it.kind] || it.kind}</td>
                      <td>{it.label}</td>
                      <td style={{ textAlign: 'right' }}>{it.citaciones.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </>
      )}
    </div>
  )
}
