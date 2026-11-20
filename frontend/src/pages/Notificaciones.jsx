import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { Aviso, Cargando, fecha } from '../components/ui.jsx'

export default function Notificaciones() {
  const [lista, setLista] = useState(null)
  const [error, setError] = useState('')
  function cargar() { api.notificaciones().then(setLista).catch((e) => setError(e.message)) }
  useEffect(cargar, [])

  if (error) return <Aviso tipo="err">{error}</Aviso>
  if (!lista) return <Cargando />

  return (
    <>
      <p className="kicker">Bandeja</p>
      <h1 className="title">Notificaciones</h1>
      <p className="subtitle">{lista.filter((n) => !n.atendida).length} sin atender.</p>
      <div className="card pad0">
        <table>
          <thead><tr><th>Tipo</th><th>Mensaje</th><th>Caso</th><th>Fecha</th><th></th></tr></thead>
          <tbody>
            {lista.map((n) => (
              <tr key={n.id} style={{ opacity: n.atendida ? .55 : 1 }}>
                <td><span className="chip teal">{n.tipo.toLowerCase().replace(/_/g, ' ')}</span></td>
                <td>{n.mensaje}</td>
                <td>{n.caso_id ? <Link to={`/casos/${n.caso_id}`} style={{ color: 'var(--teal)', fontWeight: 600 }}>CA-{n.caso_id}</Link> : '—'}</td>
                <td style={{ color: 'var(--mute)' }}>{fecha(n.fecha, true)}</td>
                <td>{!n.atendida && <button className="btn sm ghost"
                  onClick={() => api.atenderNotificacion(n.id).then(cargar)}>Marcar atendida</button>}</td>
              </tr>
            ))}
            {lista.length === 0 && <tr><td colSpan={5} style={{ textAlign: 'center', color: 'var(--mute)' }}>Sin notificaciones.</td></tr>}
          </tbody>
        </table>
      </div>
    </>
  )
}
