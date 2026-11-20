import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { Aviso, Cargando, fecha } from '../components/ui.jsx'

export default function Citas() {
  const [citas, setCitas] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.citas().then(setCitas).catch((e) => setError(e.message)) }, [])

  if (error) return <Aviso tipo="err">{error}</Aviso>
  if (!citas) return <Cargando />

  const ahora = new Date()
  const futuras = citas.filter((c) => new Date(c.fecha_cita) >= ahora)
  const pasadas = citas.filter((c) => new Date(c.fecha_cita) < ahora)

  return (
    <>
      <p className="kicker">Acompañamiento</p>
      <h1 className="title">Citas agendadas</h1>
      <p className="subtitle">{futuras.length} próximas · {pasadas.length} realizadas.</p>
      {[['Próximas', futuras], ['Anteriores', pasadas]].map(([titulo, lista]) => (
        <div className="card pad0" key={titulo} style={{ marginBottom: 20 }}>
          <div style={{ padding: '18px 24px 0' }}><h3>{titulo}</h3></div>
          <table>
            <thead><tr><th>Fecha y hora</th><th>Caso</th><th>Tipo</th><th>Asistencia</th></tr></thead>
            <tbody>
              {lista.map((c) => (
                <tr key={c.id}>
                  <td><b>{fecha(c.fecha_cita, true)}</b></td>
                  <td><Link to={`/casos/${c.caso_id}`} style={{ color: 'var(--teal)', fontWeight: 600 }}>CA-{c.caso_id}</Link></td>
                  <td>{c.tipo}</td>
                  <td>{c.asistio === true ? <span className="chip ok">Asistió</span>
                    : c.asistio === false ? <span className="chip alerta">No asistió</span>
                    : <span className="chip neutro">Sin registrar</span>}</td>
                </tr>
              ))}
              {lista.length === 0 && <tr><td colSpan={4} style={{ textAlign: 'center', color: 'var(--mute)' }}>Nada por aquí.</td></tr>}
            </tbody>
          </table>
        </div>
      ))}
    </>
  )
}
