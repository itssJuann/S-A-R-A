import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { inicioDe, useAuth } from '../auth.jsx'
import { Aviso } from '../components/ui.jsx'

const DEMO = [
  ['admin@uninorte.edu.co', 'Administrador'],
  ['coord.isc@uninorte.edu.co', 'Coordinadora de programa'],
  ['juan.isc@uninorte.edu.co', 'Consejero académico'],
  ['carlos.isc@uninorte.edu.co', 'Docente'],
  ['bienestar@uninorte.edu.co', 'Bienestar universitario'],
  ['daniela.0@uninorte.edu.co', 'Estudiante'],
]

export default function Login() {
  const { entrar } = useAuth()
  const navegar = useNavigate()
  const [correo, setCorreo] = useState('coord.isc@uninorte.edu.co')
  const [clave, setClave] = useState('sara2026')
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function enviar(e) {
    e.preventDefault()
    setError('')
    setEnviando(true)
    try {
      const usuario = await entrar(correo, clave)
      navegar(inicioDe(usuario))
    } catch (err) {
      setError(err.message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="login">
      <aside>
        <p style={{ color: 'var(--acc)', fontWeight: 700, letterSpacing: '.09em', fontSize: 13 }}>
          SISTEMA DE ALERTA TEMPRANA
        </p>
        <h1>SARA</h1>
        <p>
          Detecta a tiempo a los estudiantes en riesgo de deserción, abre el caso de
          acompañamiento y hace seguimiento hasta cerrarlo con un resultado verificable.
        </p>
      </aside>

      <form onSubmit={enviar}>
        <h2 style={{ fontSize: 26, margin: 0 }}>Iniciar sesión</h2>
        <p className="subtitle">Usa tu correo institucional.</p>

        <label className="field" htmlFor="correo">Correo</label>
        <input id="correo" type="email" value={correo} autoComplete="username"
          onChange={(e) => setCorreo(e.target.value)} required />

        <label className="field" htmlFor="clave">Contraseña</label>
        <input id="clave" type="password" value={clave} autoComplete="current-password"
          onChange={(e) => setClave(e.target.value)} required />

        <Aviso tipo="err">{error}</Aviso>

        <button className="btn" style={{ marginTop: 20 }} disabled={enviando}>
          {enviando ? 'Entrando…' : 'Entrar'}
        </button>

        <div className="demo">
          <b>Usuarios de demostración</b> (clave <code>sara2026</code>):
          {DEMO.map(([c, rol]) => (
            <div key={c}>
              <code onClick={() => setCorreo(c)}>{c}</code> — {rol}
            </div>
          ))}
        </div>
      </form>
    </div>
  )
}
