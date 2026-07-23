import { useState } from 'react'
import { sendSurvey, type User } from './api'

function Estrellas({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <div className="stars">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          className={`star ${n <= value ? 'on' : ''}`}
          onClick={() => onChange(n)}
          aria-label={`${n} estrellas`}
        >
          ★
        </button>
      ))}
    </div>
  )
}

export default function Survey({
  user,
  reason,
  onDone,
}: {
  user: User
  reason: 'manual' | 'timeout'
  onDone: () => void
}) {
  const [overall, setOverall] = useState(0)
  const [accuracy, setAccuracy] = useState(0)
  const [speed, setSpeed] = useState(0)
  const [recommend, setRecommend] = useState('')
  const [missing, setMissing] = useState('')
  const [comments, setComments] = useState('')
  const [busy, setBusy] = useState(false)

  async function enviar() {
    setBusy(true)
    try {
      await sendSurvey({
        email: user.email,
        rating_overall: overall || null,
        rating_accuracy: accuracy || null,
        rating_speed: speed || null,
        would_recommend: recommend || null,
        missing_feature: missing.trim() || null,
        comments: comments.trim() || null,
        closed_reason: reason,
      })
    } catch {
      /* best-effort */
    } finally {
      setBusy(false)
      onDone()
    }
  }

  return (
    <div className="modal-overlay">
      <div className="modal survey">
        <div className="modal-h">Antes de salir, ¿cómo te fue?</div>
        {reason === 'timeout' && (
          <p className="survey-note">Tu sesión se cerró por inactividad. Tu opinión nos ayuda a mejorar.</p>
        )}

        <div className="survey-row">
          <span>Experiencia general</span>
          <Estrellas value={overall} onChange={setOverall} />
        </div>
        <div className="survey-row">
          <span>Precisión de las respuestas</span>
          <Estrellas value={accuracy} onChange={setAccuracy} />
        </div>
        <div className="survey-row">
          <span>Velocidad</span>
          <Estrellas value={speed} onChange={setSpeed} />
        </div>

        <div className="survey-field">
          <label>¿La recomendarías?</label>
          <div className="survey-chips">
            {[
              ['si', 'Sí'],
              ['tal_vez', 'Tal vez'],
              ['no', 'No'],
            ].map(([v, l]) => (
              <button
                key={v}
                className={`chip ${recommend === v ? 'chip-on' : ''}`}
                onClick={() => setRecommend(v)}
              >
                {l}
              </button>
            ))}
          </div>
        </div>

        <div className="survey-field">
          <label>¿Qué te faltó? (opcional)</label>
          <input value={missing} onChange={(e) => setMissing(e.target.value)} placeholder="Una función, un tipo de consulta…" />
        </div>
        <div className="survey-field">
          <label>Comentarios (opcional)</label>
          <textarea rows={2} value={comments} onChange={(e) => setComments(e.target.value)} />
        </div>

        <div className="survey-actions">
          <button className="btn-primary" disabled={busy} onClick={enviar}>
            {busy ? 'Enviando…' : 'Enviar y salir'}
          </button>
          <button className="btn-ghost" onClick={onDone}>
            Omitir
          </button>
        </div>
      </div>
    </div>
  )
}
