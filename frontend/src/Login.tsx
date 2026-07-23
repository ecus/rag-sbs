import { useState } from 'react'
import Logo from './Logo'
import { login, register, recoverPin, type User, type Mensaje } from './api'

export default function Login({ onAuth }: { onAuth: (u: User, mem: Mensaje[], adminToken?: string) => void }) {
  const [tab, setTab] = useState<'login' | 'register' | 'recover'>('login')
  const [email, setEmail] = useState('')
  const [pin, setPin] = useState('')
  const [name, setName] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  // Recuperación de PIN
  const [recCode, setRecCode] = useState('')
  const [newPin, setNewPin] = useState('')

  // Pantalla de código de recuperación (tras registro o reset). Bloquea hasta confirmar.
  const [codigo, setCodigo] = useState<string | null>(null)
  const [pendiente, setPendiente] = useState<{ u: User; mem: Mensaje[] } | null>(null)

  const pinOk = /^\d{4,8}$/.test(pin)

  async function doLogin() {
    setErr('')
    if (!/^[^@]+@[^@]+\.[^@]+$/.test(email)) return setErr('Ingresá un email válido.')
    if (!pinOk) return setErr('El PIN debe tener 4 a 8 dígitos.')
    setBusy(true)
    try {
      const { status, data } = await login(email.trim(), pin.trim())
      if (status === 200) onAuth(data.user, data.memory || [], data.admin_token)
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
      if (status === 200) {
        if (data.recovery_code) {
          setCodigo(data.recovery_code)
          setPendiente({ u: data.user, mem: [] })
        } else {
          onAuth(data.user, [])
        }
      } else if (status === 409) setErr('Ese email ya está registrado, iniciá sesión.')
      else setErr('No se pudo crear la cuenta.')
    } catch {
      setErr('No se pudo conectar al servidor.')
    } finally {
      setBusy(false)
    }
  }

  async function doRecover() {
    setErr('')
    if (!/^[^@]+@[^@]+\.[^@]+$/.test(email)) return setErr('Ingresá un email válido.')
    if (!/^[A-Za-z0-9-]{8,12}$/.test(recCode.trim())) return setErr('Ingresá el código de recuperación (formato XXXX-XXXX).')
    if (!/^\d{4,8}$/.test(newPin)) return setErr('El nuevo PIN debe tener 4 a 8 dígitos.')
    setBusy(true)
    try {
      const { status, data } = await recoverPin(email.trim(), recCode.trim(), newPin.trim())
      if (status === 200 && data.ok) {
        setCodigo(data.recovery_code || null)
        setPendiente(null) // tras recuperar, vuelve a iniciar sesión
      } else if (status === 401 || status === 400) setErr('Email o código de recuperación incorrectos.')
      else setErr('No se pudo restablecer el PIN.')
    } catch {
      setErr('No se pudo conectar al servidor.')
    } finally {
      setBusy(false)
    }
  }

  // Pantalla de código de recuperación (una sola vez)
  if (codigo) {
    return (
      <div className="login-wrap">
        <div className="login-card">
          <div className="brand-center">
            <div style={{ marginBottom: 12 }}><Logo size={52} variant="light" /></div>
            <div className="brand-title">Guardá tu código de recuperación</div>
            <div className="brand-sub">Es la única forma de recuperar el acceso si olvidas tu PIN.</div>
          </div>
          <div className="rec-code">{codigo}</div>
          <p className="policy">
            Anotalo en un lugar seguro. No volveremos a mostrarlo. Sin este código y tu PIN no podremos
            restablecer tu cuenta.
          </p>
          <button
            className="btn-primary"
            onClick={() => {
              const p = pendiente
              setCodigo(null)
              if (p) onAuth(p.u, p.mem)
              else setTab('login')
            }}
          >
            Ya lo anoté, continuar
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="login-wrap">
      <div className="login-card">
        <div className="brand-center">
          <div style={{ marginBottom: 12 }}><Logo size={52} variant="light" /></div>
          <div className="brand-title">Mesa Experta Regulatoria</div>
          <div className="brand-sub">
            Consultas sobre normativa financiera peruana
            <br />
            <small>Herramienta independiente, no oficial</small>
          </div>
        </div>

        {tab !== 'recover' ? (
          <div className="tabs-row">
            <button className={`tab-btn ${tab === 'login' ? 'active' : ''}`} onClick={() => setTab('login')}>
              Iniciar sesión
            </button>
            <button className={`tab-btn ${tab === 'register' ? 'active' : ''}`} onClick={() => setTab('register')}>
              Crear cuenta
            </button>
          </div>
        ) : (
          <div className="tabs-row">
            <button className="tab-btn active">Recuperar acceso</button>
          </div>
        )}

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

        {tab === 'recover' ? (
          <>
            <div className="field">
              <label>Código de recuperación</label>
              <input value={recCode} onChange={(e) => setRecCode(e.target.value)} placeholder="XXXX-XXXX" />
            </div>
            <div className="field">
              <label>Nuevo PIN (4-8 dígitos)</label>
              <input
                type="password"
                maxLength={8}
                value={newPin}
                onChange={(e) => setNewPin(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && doRecover()}
              />
            </div>
          </>
        ) : (
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
        )}

        {err && <p className="err">{err}</p>}

        <button
          className="btn-primary"
          disabled={busy}
          onClick={tab === 'login' ? doLogin : tab === 'register' ? doRegister : doRecover}
        >
          {busy
            ? 'Un momento…'
            : tab === 'login'
              ? 'Iniciar sesión'
              : tab === 'register'
                ? 'Crear cuenta y solicitar acceso'
                : 'Restablecer PIN'}
        </button>

        {tab === 'login' && (
          <button className="link-btn" onClick={() => { setErr(''); setTab('recover') }}>
            ¿Olvidaste tu PIN?
          </button>
        )}
        {tab === 'recover' && (
          <button className="link-btn" onClick={() => { setErr(''); setTab('login') }}>
            ← Volver a iniciar sesión
          </button>
        )}

        <p className="policy">
          Proyecto personal de demostración — no afiliado a la SBS ni a ninguna entidad oficial.
          Tu email y consultas se usan solo para el funcionamiento de la app; no se comparten con terceros.
        </p>
      </div>
    </div>
  )
}
