import { useEffect, useState } from 'react'
import { api } from '../api.js'
import Boletin from '../components/Boletin.jsx'
import { Aviso, Cargando, fecha, Nivel, TEXTO_ESTADO } from '../components/ui.jsx'

export default function MiEstado() {
  const [d, setD] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => { api.miEstado().then(setD).catch((e) => setError(e.message)) }, [])

  if (error) return <Aviso tipo="err">{error}</Aviso>
  if (!d) return <Cargando />

  return (
    <>
      <p className="kicker">Mi acompañamiento</p>
      <h1 className="title">Hola, {d.estudiante.split(' ')[0]}</h1>
      <p className="subtitle">{d.programa} · Semestre {d.semestre}</p>

      <div className="banner">
        <p className="kicker">Tu acompañamiento</p>
        <h2>{d.caso_id ? `Estás ${TEXTO_ESTADO[d.caso_estado].toLowerCase()}` : 'No tienes acompañamiento activo'}</h2>
        <p>
          {d.caso_id
            ? `Tu consejero es ${d.consejero || 'por asignar'}. Caso CA-${d.caso_id}.`
            : 'Sigue así: no hay alertas activas sobre tu desempeño.'}
        </p>
      </div>

      <div className="card" style={{ marginTop: 20 }}>
        <h3>Tus notas por corte</h3>
        <p className="hint">
          {d.boletin
            ? `Periodo ${d.boletin.periodo} · el semestre tiene ${d.boletin.cortes.length} cortes y vas en el ${d.boletin.corte_vigente}`
            : 'Sin notas registradas en este periodo.'}
        </p>
        <Boletin boletin={d.boletin} compacto />
      </div>

      <div className="split" style={{ marginTop: 20 }}>
        <div className="card">
          <h3>Tus compromisos</h3>
          <p className="hint">Lo que acordaste con tu consejero</p>
          {d.compromisos.length === 0 && <p className="hint">Todavía no hay compromisos registrados.</p>}
          {d.compromisos.map((c) => (
            <div key={c.intervencion_id} style={{ borderTop: '1px solid var(--bd)', padding: '14px 0' }}>
              <p style={{ margin: 0, fontSize: 14 }}>{c.texto}</p>
              <span style={{ fontSize: 11.5, color: 'var(--mute)' }}>Acordado el {fecha(c.fecha)}</span>
            </div>
          ))}
        </div>

        <div>
          <div className="card" style={{ marginBottom: 20 }}>
            <h3>Próxima cita</h3>
            {d.proxima_cita ? (
              <>
                <p style={{ fontSize: 19, fontWeight: 700, margin: '10px 0 4px' }}>
                  {fecha(d.proxima_cita.fecha_cita, true)}
                </p>
                <p className="hint" style={{ margin: 0 }}>Con {d.proxima_cita.consejero}</p>
              </>
            ) : <p className="hint">No tienes citas agendadas.</p>}
          </div>

          <div className="card">
            <h3>Tu situación</h3>
            <p className="hint">Nivel de riesgo académico</p>
            <Nivel nivel={d.nivel} />
            <Aviso tipo="info">
              Las notas que tu consejero registra sobre las sesiones son confidenciales
              y no se muestran aquí.
            </Aviso>
          </div>
        </div>
      </div>
    </>
  )
}
