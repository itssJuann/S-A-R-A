import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { Aviso, Cargando, COLOR_ACCION, fecha, TEXTO_ACCION } from '../components/ui.jsx'

export default function Bitacora() {
  const [lista, setLista] = useState(null)
  const [recurso, setRecurso] = useState('')
  const [error, setError] = useState('')
  useEffect(() => { api.bitacora().then(setLista).catch((e) => setError(e.message)) }, [])

  if (error) return <Aviso tipo="err">{error}</Aviso>
  if (!lista) return <Cargando />

  const recursos = [...new Set(lista.map((b) => b.recurso))]
  const filas = recurso ? lista.filter((b) => b.recurso === recurso) : lista

  return (
    <>
      <p className="kicker">Auditoría · RQNF-03</p>
      <h1 className="title">Bitácora de accesos</h1>
      <p className="subtitle">
        Todo acceso a información sensible de un estudiante queda registrado con usuario, recurso y fecha.
      </p>

      <div className="tabs">
        <button className={'tab' + (recurso === '' ? ' on' : '')} onClick={() => setRecurso('')}>
          Todos ({lista.length})
        </button>
        {recursos.map((r) => (
          <button key={r} className={'tab' + (recurso === r ? ' on' : '')} onClick={() => setRecurso(r)}>
            {r} ({lista.filter((b) => b.recurso === r).length})
          </button>
        ))}
      </div>

      <div className="card pad0">
        <table>
          <thead><tr><th>Fecha</th><th>Usuario</th><th>Acción</th><th>Qué hizo</th><th>Recurso</th></tr></thead>
          <tbody>
            {filas.map((b) => (
              <tr key={b.id}>
                <td style={{ whiteSpace: 'nowrap' }}>{fecha(b.fecha, true)}</td>
                <td><b>{b.usuario}</b></td>
                <td>
                  <span className={'chip ' + (COLOR_ACCION[b.accion] || 'neutro')}>
                    {TEXTO_ACCION[b.accion] || b.accion.toLowerCase().replace(/_/g, ' ')}
                  </span>
                </td>
                <td style={{ fontSize: 12.5 }}>{b.detalle || '—'}</td>
                <td style={{ color: 'var(--mute)' }}>
                  {b.recurso} #{b.recurso_id}
                </td>
              </tr>
            ))}
            {filas.length === 0 && <tr><td colSpan={5} style={{ textAlign: 'center', color: 'var(--mute)' }}>Sin registros.</td></tr>}
          </tbody>
        </table>
      </div>
      <Aviso tipo="info">
        Cada apertura, cambio de estado, cierre, reapertura y reasignación queda aquí con su
        responsable. Los registros no se pueden editar ni borrar desde la aplicación.
      </Aviso>
    </>
  )
}
