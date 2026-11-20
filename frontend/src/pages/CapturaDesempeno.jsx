import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { useConfig } from '../auth.jsx'
import { Aviso, Cargando, COLOR_NIVEL, indice as fmtIndice, Nivel } from '../components/ui.jsx'

export default function CapturaDesempeno() {
  const { periodo: PERIODO, cortes: CORTES, corte_vigente: CORTE_INICIAL } = useConfig()
  const [asignaturas, setAsignaturas] = useState([])
  const [asignaturaId, setAsignaturaId] = useState('')
  const [corte, setCorte] = useState(CORTE_INICIAL)
  const [filas, setFilas] = useState(null)
  const [borrador, setBorrador] = useState({})
  const [error, setError] = useState('')
  const [aviso, setAviso] = useState('')

  useEffect(() => {
    api.asignaturas().then((a) => {
      setAsignaturas(a)
      if (a.length) setAsignaturaId(String(a[0].id))
    }).catch((e) => setError(e.message))
  }, [])

  function cargar() {
    if (!asignaturaId) return
    setFilas(null)
    api.cursoDocente(PERIODO, asignaturaId, corte)
      .then((f) => { setFilas(f); setBorrador({}) })
      .catch((e) => setError(e.message))
  }
  useEffect(cargar, [asignaturaId, corte])

  async function guardarNota(fila) {
    const valor = parseFloat(String(borrador[fila.matricula_id] ?? '').replace(',', '.'))
    if (Number.isNaN(valor) || valor < 0 || valor > 5) {
      setError('La nota debe estar entre 0,0 y 5,0')
      return
    }
    setError(''); setAviso('')
    try {
      const r = await api.registrarNota({ matricula_id: fila.matricula_id, corte, valor })
      setAviso(r.alerta_generada
        ? `${fila.estudiante}: índice ${r.indice} (${r.nivel}). ${r.caso_nuevo ? 'Se abrió el caso CA-' + r.caso_id : 'Alerta adjuntada al caso CA-' + r.caso_id}.`
        : `${fila.estudiante}: índice ${r.indice} (${r.nivel}). Sin alerta.`)
      cargar()
    } catch (e) { setError(e.message) }
  }

  async function registrarFalta(fila) {
    setError(''); setAviso('')
    try {
      const r = await api.registrarInasistencia({
        matricula_id: fila.matricula_id, fecha_sesion: new Date().toISOString().slice(0, 10),
      })
      setAviso(`Inasistencia registrada. ${fila.estudiante}: índice ${r.indice} (${r.nivel}).`)
      cargar()
    } catch (e) { setError(e.message) }
  }

  const conNota = filas?.filter((f) => f.nota !== null).length ?? 0
  const alertas = filas?.filter((f) => ['ALTO', 'CRITICO'].includes(f.nivel)).length ?? 0

  return (
    <>
      <p className="kicker">Captura de desempeño</p>
      <h1 className="title">Notas e inasistencias</h1>
      <p className="subtitle">
        Al guardar, el sistema recalcula el índice de riesgo y abre los casos que correspondan.
      </p>

      <div className="tabs">
        <select style={{ maxWidth: 320 }} value={asignaturaId} onChange={(e) => setAsignaturaId(e.target.value)}>
          {asignaturas.map((a) => <option key={a.id} value={a.id}>{a.nombre} ({a.codigo})</option>)}
        </select>
        {CORTES.map((c) => (
          <button key={c} className={'tab' + (c === corte ? ' on' : '')} onClick={() => setCorte(c)}>
            Corte {c}
          </button>
        ))}
      </div>

      {error && <Aviso tipo="err">{error}</Aviso>}
      {aviso && <Aviso tipo="ok">{aviso}</Aviso>}

      {!filas ? <Cargando /> : (
        <>
          <div className="grid g3" style={{ marginBottom: 20 }}>
            <div className="card kpi"><label>Notas registradas</label><b>{conNota} / {filas.length}</b></div>
            <div className="card kpi"><label>En riesgo Alto o Crítico</label>
              <b style={{ color: 'var(--crit)' }}>{alertas}</b></div>
            <div className="card kpi"><label>Corte</label><b>{corte}</b><span>Periodo {PERIODO}</span></div>
          </div>

          <div className="card pad0">
            <table>
              <thead>
                <tr>
                  <th>Estudiante</th><th>Documento</th><th>Nota del corte</th>
                  <th>Inasistencias</th><th>Riesgo</th><th></th>
                </tr>
              </thead>
              <tbody>
                {filas.map((f) => (
                  <tr key={f.matricula_id}>
                    <td>
                      <b>{f.estudiante}</b>
                      <div style={{ fontSize: 11.5, color: 'var(--mute)' }}>Semestre {f.semestre}</div>
                    </td>
                    <td style={{ color: 'var(--mute)' }}>{f.documento}</td>
                    <td style={{ maxWidth: 130 }}>
                      <input style={{ padding: '8px 10px', textAlign: 'center' }}
                        inputMode="decimal" placeholder={f.nota ?? '—'}
                        value={borrador[f.matricula_id] ?? ''}
                        onChange={(e) => setBorrador({ ...borrador, [f.matricula_id]: e.target.value })}
                        onKeyDown={(e) => e.key === 'Enter' && guardarNota(f)} />
                    </td>
                    <td>{f.inasistencias} / {f.sesiones}</td>
                    <td>
                      <Nivel nivel={f.nivel} />
                      {f.indice != null && (
                        <b style={{ marginLeft: 8, color: COLOR_NIVEL[f.nivel] }}>{fmtIndice(f.indice)}</b>
                      )}
                    </td>
                    <td style={{ whiteSpace: 'nowrap' }}>
                      <button className="btn sm" disabled={!borrador[f.matricula_id]}
                        onClick={() => guardarNota(f)}>Guardar</button>{' '}
                      <button className="btn sm ghost" onClick={() => registrarFalta(f)}>+ Falta</button>
                    </td>
                  </tr>
                ))}
                {filas.length === 0 && (
                  <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--mute)' }}>
                    No tienes estudiantes matriculados en esta asignatura.
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      <Aviso tipo="info">
        Las notas van de 0,0 a 5,0 y no se pueden registrar inasistencias de fechas futuras [RQF-03, RQF-04].
      </Aviso>
    </>
  )
}
