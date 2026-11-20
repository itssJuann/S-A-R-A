import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import { Aviso, Cargando, COLOR_NIVEL, indice as fmtIndice, Nivel } from '../components/ui.jsx'

const FILTROS = [
  ['Todos', {}], ['Crítico', { nivel: 'CRITICO' }], ['Alto', { nivel: 'ALTO' }],
  ['Medio', { nivel: 'MEDIO' }], ['Sin caso abierto', { sin_caso: true }],
]

export default function EstudiantesRiesgo() {
  const navegar = useNavigate()
  const [filtro, setFiltro] = useState(0)
  const [buscar, setBuscar] = useState('')
  const [filas, setFilas] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setFilas(null)
    const t = setTimeout(() => {
      api.estudiantesEnRiesgo({ ...FILTROS[filtro][1], buscar })
        .then(setFilas).catch((e) => setError(e.message))
    }, buscar ? 300 : 0)
    return () => clearTimeout(t)
  }, [filtro, buscar])

  return (
    <>
      <p className="kicker">Motor de riesgo</p>
      <h1 className="title">Estudiantes en riesgo</h1>
      <p className="subtitle">Índice calculado con los factores vigentes del modelo.</p>

      <div className="tabs">
        {FILTROS.map(([texto], i) => (
          <button key={texto} className={'tab' + (i === filtro ? ' on' : '')} onClick={() => setFiltro(i)}>
            {texto}
          </button>
        ))}
        <input style={{ maxWidth: 280, marginLeft: 'auto' }} placeholder="Buscar por nombre o documento…"
          value={buscar} onChange={(e) => setBuscar(e.target.value)} />
      </div>

      {error && <Aviso tipo="err">{error}</Aviso>}
      {!filas ? <Cargando /> : (
        <div className="card pad0">
          <table>
            <thead>
              <tr>
                <th>Estudiante</th><th>Programa</th><th>Índice</th><th>Nivel</th>
                <th>Factor principal</th><th>Caso</th>
              </tr>
            </thead>
            <tbody>
              {filas.map((f) => (
                <tr key={f.id} className="click" onClick={() => navegar(`/estudiantes/${f.id}`)}>
                  <td>
                    <b>{f.nombre}</b>
                    <div style={{ fontSize: 11.5, color: 'var(--mute)' }}>{f.documento}</div>
                  </td>
                  <td>{f.programa}</td>
                  <td className="num" style={{ color: COLOR_NIVEL[f.nivel], fontSize: 19 }}>
                    {fmtIndice(f.indice)}
                  </td>
                  <td><Nivel nivel={f.nivel} /></td>
                  <td style={{ color: 'var(--mute)', fontSize: 12.5 }}>{f.factor_principal || '—'}</td>
                  <td>
                    {f.caso_id
                      ? <span style={{ color: 'var(--teal)', fontWeight: 600 }}>CA-{f.caso_id}</span>
                      : <span style={{ color: 'var(--mute-d)' }}>Sin caso</span>}
                  </td>
                </tr>
              ))}
              {filas.length === 0 && (
                <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--mute)' }}>
                  No hay estudiantes con ese filtro.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      <Aviso tipo="info">
        El índice se recalcula al registrar una nota o una inasistencia y al iniciar cada corte [RN-07].
      </Aviso>
    </>
  )
}
