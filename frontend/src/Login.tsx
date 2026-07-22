import { useState } from 'react'
import { login, register, type User, type Mensaje } from './api'

export default function Login({ onAuth }: { onAuth: (u: User, mem: Mensaje[]) => void }) {
  const [tab, setTab] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [pin, setPin] = useState('')
  const [name, setName] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const pinOk = /^\d{4,8}$/.test(pin)

  async function doLogin() {
    setErr('')
    if (!/^[^@]+@[^@]+\.[^@]+$/.test(email)) return setErr('Ingresá un email válido.')
    if (!pinOk) return setErr('El PIN debe tener 4 a 8 dígitos.')
    setBusy(true)
    try {
      const { status, data } = await login(email.trim(), pin.trim())
      if (status === 200) onAuth(data.user, data.memory || [])
      else if (status === 401) setErr('Email o PIN incorrectos.')
      else if (status === 429) setErr('Demasiados intentos, esperá un minuto.')
      else setErr('No se pudo iniciar sesión.')
    } catch {
      setErr('No se pudo conectar al servidor.')
    } finally {
      setBusy(false)
    }
  }

  async function doRegister() {
    setErr('')
    if (!/^[^@]+@[^@]+\.[^@]+$/.test(email)) return setErr('Ingresá un email válido.')
    if (!name.trim()) return setErr('Ingresá tu nombre.')
    if (!pinOk) return setErr('El PIN debe tener 4 a 8 dígitos.')
    setBusy(true)
    try {
      const { status, data } = await register(email.trim(), name.trim(), pin.trim())
      if (status === 200) onAuth(data.user, [])
      else if (status === 409) setErr('Ese email ya está registrado, iniciá sesión.')
      else setErr('No se pudo crear la cuenta.')
    } catch {
      setErr('No se pudo conectar al servidor.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-wrap">
      <div className="login-card">
        <div className="brand-center">
          <div className="badge">SBS</div>
          <div className="brand-title">Mesa Experta Regulatoria</div>
          <div className="brand-sub">
            Consultas sobre normativa financiera peruana
            <br />
            <small>Herramienta independiente, no oficial</small>
          </div>
        </div>

        <div className="tabs-row">
          <button className={`tab-btn ${tab === 'login' ? 'active' : ''}`} onClick={() => setTab('login')}>
            Iniciar sesión
          </button>
          <button className={`tab-btn ${tab === 'register' ? 'active' : ''}`} onClick={() => setTab('register')}>
            Crear cuenta
          </button>
        </div>

        {tab === 'register' && (
          <div className="field">
            <label>Nombre y apellido</label>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="ej. Juan Pérez" />
          </div>
        )}
        <div className="field">
          <label>Email</label>
          <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="usuario@empresa.com" />
        </div>
        <div className="field">
          <label>PIN (4-8 dígitos)</label>
          <input
            type="password"
            maxLength={8}
            value={pin}
            onChange={(e) => setPin(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && (tab === 'login' ? doLogin() : doRegister())}
          />
        </div>

        {err && <p className="err">{err}</p>}

        <button className="btn-primary" disabled={busy} onClick={tab === 'login' ? doLogin : doRegister}>
          {busy ? 'Un momento…' : tab === 'login' ? 'Iniciar sesión' : 'Crear cuenta y solicitar acceso'}
        </button>

        <p className="policy">
          Tu email y consultas se usan solo para identificarte y medir la calidad del servicio.
          Registramos datos técnicos con fines de seguridad y monitoreo. No compartimos tus datos
          con fines comerciales.
        </p>
      </div>
    </div>
  )
}
