import { useState } from 'react'
import Login from './Login'
import Chat from './Chat'
import type { User, Mensaje } from './api'

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [, setMemoria] = useState<Mensaje[]>([])

  if (!user) {
    return (
      <Login
        onAuth={(u, mem) => {
          setUser(u)
          setMemoria(mem)
        }}
      />
    )
  }
  if (user.status !== 'approved') {
    return (
      <div className="login-wrap">
        <div className="login-card" style={{ textAlign: 'center' }}>
          <div className="badge" style={{ marginBottom: 16 }}>
            SBS
          </div>
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
  return <Chat user={user} onExit={() => setUser(null)} />
}
