import { useEffect, useState } from 'react'
import Logo from './Logo'
import Login from './Login'
import Chat from './Chat'
import Survey from './Survey'
import type { User, Mensaje } from './api'

const SESION_KEY = 'sbs_sesion'
const ADMIN_KEY = 'sbs_admin_token'

// Restaura la sesión guardada (perfil no sensible: id/email/nombre/estado; nunca el PIN).
function cargarSesion(): User | null {
  try {
    const raw = localStorage.getItem(SESION_KEY)
    return raw ? (JSON.parse(raw) as User) : null
  } catch {
    return null
  }
}

export default function App() {
  const [user, setUser] = useState<User | null>(cargarSesion)
  const [adminToken, setAdminToken] = useState<string>(() => localStorage.getItem(ADMIN_KEY) || '')
  const [, setMemoria] = useState<Mensaje[]>([])
  const [salida, setSalida] = useState<null | 'manual' | 'timeout'>(null)

  // Persiste / limpia la sesión cuando cambia el usuario.
  useEffect(() => {
    try {
      if (user) localStorage.setItem(SESION_KEY, JSON.stringify(user))
      else {
        localStorage.removeItem(SESION_KEY)
        localStorage.removeItem(ADMIN_KEY)
      }
    } catch {
      /* almacenamiento no disponible */
    }
  }, [user])

  useEffect(() => {
    try {
      if (adminToken) localStorage.setItem(ADMIN_KEY, adminToken)
      else localStorage.removeItem(ADMIN_KEY)
    } catch {
      /* noop */
    }
  }, [adminToken])

  if (!user) {
    return (
      <Login
        onAuth={(u, mem, token) => {
          setUser(u)
          setMemoria(mem)
          if (token) setAdminToken(token)
        }}
      />
    )
  }
  if (user.status !== 'approved') {
    return (
      <div className="login-wrap">
        <div className="login-card" style={{ textAlign: 'center' }}>
          <div style={{ marginBottom: 16, display: 'inline-flex' }}><Logo size={52} variant="light" /></div>
          <div className="brand-title">Solicitud enviada</div>
          <p className="brand-sub" style={{ marginTop: 10 }}>
            Tu acceso quedó pendiente de aprobación por un administrador.
          </p>
          <button className="btn-primary" style={{ marginTop: 18 }} onClick={() => setUser(null)}>
            Volver
          </button>
        </div>
      </div>
    )
  }
  return (
    <>
      <Chat user={user} adminToken={adminToken} onExit={() => setSalida('manual')} onTimeout={() => setSalida('timeout')} />
      {salida && (
        <Survey
          user={user}
          reason={salida}
          onDone={() => {
            setSalida(null)
            setUser(null)
          }}
        />
      )}
    </>
  )
}
