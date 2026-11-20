import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import { Aviso, Cargando, fecha } from '../components/ui.jsx'

const APOYOS = { PSICOLOGICO: 'Apoyo psicológico', FINANCIERO: 'Apoyo financiero', ACADEMICO: 'Apoyo académico', SALUD: 'Salud' }

export default function Derivaciones() {
  const { usuario } = useAuth()
  const [lista, setLista] = useState(null)
  const [error, setError] = useState(''), [aviso, setAviso] = useState('')

  function cargar() { api.derivaciones().then(setLista).catch((e) => setError(e.message)) }
  useEffect(cargar, [])

  async function atender(id, estado) {
    setError(''); setAviso('')
    try { await api.atenderDerivacion(id, { estado }); setAviso(`Derivación ${estado.toLowerCase()}.`); cargar() }
    catch (e) { setError(e.message) }
  }

  if (error && !lista) return <Aviso tipo="err">{error}</Aviso>
  if (!lista) return <Cargando />
  const abiertas = lista.filter((d) => d.estado === 'ABIERTA').length

  return (
    <>
      <p className="kicker">Bienestar universitario</p>
      <h1 className="title">Derivaciones</h1>
      <p className="subtitle">{abiertas} abiertas · un caso no se cierra mientras tenga derivaciones abiertas.</p>
      {error && <Aviso tipo="err">{error}</Aviso>}
      {aviso && <Aviso tipo="ok">{aviso}</Aviso>}
      <div className="card pad0">
        <table>
          <thead><tr><th>Caso</th><th>Estudiante</th><th>Tipo de apoyo</th><th>Solicitada por</th><th>Fecha</th><th>Estado</th><th></th></tr></thead>
          <tbody>
            {lista.map((d) => (
              <tr key={d.id}>
                <td><Link to={`/casos/${d.caso_id}`} style={{ color: 'var(--teal)', fontWeight: 600 }}>CA-{d.caso_id}</Link></td>
                <td><b>{d.estudiante}</b></td>
                <td>{APOYOS[d.tipo_apoyo]}</td>
                <td style={{ color: 'var(--mute)' }}>{d.solicitante}</td>
                <td style={{ color: 'var(--mute)' }}>{fecha(d.fecha)}</td>
                <td><span className={'chip ' + (d.estado === 'ABIERTA' ? 'alerta' : d.estado === 'ATENDIDA' ? 'ok' : 'neutro')}>
                  {d.estado.toLowerCase()}</span></td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  {usuario.rol === 'BIENESTAR' && d.estado === 'ABIERTA' && (
                    <>
                      <button className="btn sm ok" onClick={() => atender(d.id, 'ATENDIDA')}>Atender</button>{' '}
                      <button className="btn sm danger" onClick={() => atender(d.id, 'RECHAZADA')}>Rechazar</button>
                    </>
                  )}
                </td>
              </tr>
            ))}
            {lista.length === 0 && <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--mute)' }}>No hay derivaciones.</td></tr>}
          </tbody>
        </table>
      </div>
    </>
  )
}
