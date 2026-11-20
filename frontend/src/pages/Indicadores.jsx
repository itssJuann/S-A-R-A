import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { Aviso, Barra, Cargando, COLOR_NIVEL, TEXTO_NIVEL, TEXTO_RESULTADO } from '../components/ui.jsx'

const COLOR_RESULTADO = {
  SUPERADO: 'var(--bajo)', PERSISTE: 'var(--medio)', DESERCION_CONFIRMADA: 'var(--crit)',
}

export default function Indicadores() {
  const [g, setG] = useState(null)
  const [ef, setEf] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([api.reporteGeneral(), api.efectividad()])
      .then(([a, b]) => { setG(a); setEf(b) })
      .catch((e) => setError(e.message))
  }, [])

  if (error) return <Aviso tipo="err">{error}</Aviso>
  if (!g) return <Cargando />

  const totalResultados = g.resultados.reduce((n, r) => n + r.cantidad, 0)
  const superados = g.resultados.find((r) => r.resultado === 'SUPERADO')?.cantidad ?? 0

  return (
    <>
      <p className="kicker">Indicadores</p>
      <h1 className="title">Indicadores de retención</h1>
      <p className="subtitle">Efectividad del acompañamiento y permanencia por programa.</p>

      <div className="grid g4">
        <div className="card kpi"><label>Tasa de retención</label>
          <b style={{ color: 'var(--bajo)' }}>{g.tasa_retencion_global.toLocaleString('es-CO')}%</b>
          <span>Global del periodo</span></div>
        <div className="card kpi"><label>Casos cerrados</label><b>{totalResultados}</b>
          <span>En lo corrido del periodo</span></div>
        <div className="card kpi"><label>Resultado Superado</label>
          <b style={{ color: 'var(--bajo)' }}>
            {totalResultados ? Math.round((superados / totalResultados) * 100) : 0}%
          </b><span>De los casos cerrados</span></div>
        <div className="card kpi"><label>Casos escalados</label>
          <b style={{ color: 'var(--acc)' }}>{g.casos_escalados}</b>
          <span>Activos sin atención</span></div>
      </div>

      <div className="split" style={{ marginTop: 20 }}>
        <div className="card">
          <h3>Resultado de los casos cerrados</h3>
          <p className="hint">{totalResultados} casos cerrados</p>
          {g.resultados.map((r) => (
            <div key={r.resultado} style={{ display: 'flex', alignItems: 'center', gap: 16, margin: '16px 0' }}>
              <span style={{ width: 170, fontWeight: 600, fontSize: 13.5 }}>{TEXTO_RESULTADO[r.resultado]}</span>
              <div style={{ flex: 1 }}>
                <Barra valor={r.cantidad} max={Math.max(totalResultados, 1)} color={COLOR_RESULTADO[r.resultado]} />
              </div>
              <b style={{ width: 40, textAlign: 'right' }}>{r.cantidad}</b>
            </div>
          ))}
          {totalResultados === 0 && <p className="hint">Todavía no hay casos cerrados en el periodo.</p>}

          <h3 style={{ marginTop: 26 }}>Efectividad según el nivel de apertura</h3>
          <p className="hint">Proporción de casos cerrados que terminaron en Superado</p>
          {ef.map((e) => (
            <div key={e.nivel_apertura} style={{ display: 'flex', alignItems: 'center', gap: 16, margin: '16px 0' }}>
              <span style={{ width: 170, fontWeight: 600, fontSize: 13.5 }}>
                Apertura en {TEXTO_NIVEL[e.nivel_apertura]}
              </span>
              <div style={{ flex: 1 }}>
                <Barra valor={e.efectividad} color={COLOR_NIVEL[e.nivel_apertura]} />
              </div>
              <b style={{ width: 90, textAlign: 'right', fontSize: 13 }}>
                {e.efectividad.toLocaleString('es-CO')}% ({e.superados}/{e.cerrados})
              </b>
            </div>
          ))}
        </div>

        <div className="card">
          <h3>Distribución actual del riesgo</h3>
          <p className="hint">{g.estudiantes_evaluados} estudiantes evaluados</p>
          {g.distribucion.map((d) => (
            <div key={d.nivel} style={{ margin: '16px 0' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 7 }}>
                <span style={{ fontWeight: 600 }}>{TEXTO_NIVEL[d.nivel]}</span><b>{d.cantidad}</b>
              </div>
              <Barra valor={d.cantidad} max={Math.max(g.estudiantes_evaluados, 1)} color={COLOR_NIVEL[d.nivel]} />
            </div>
          ))}

          <h3 style={{ marginTop: 26 }}>Retención por programa</h3>
          <table style={{ fontSize: 13 }}>
            <thead><tr><th>Programa</th><th>Activos</th><th>Retirados</th><th>Tasa</th></tr></thead>
            <tbody>
              {g.retencion_por_programa.map((p) => (
                <tr key={p.programa}>
                  <td>{p.programa}</td><td>{p.activos}</td><td>{p.desertores}</td>
                  <td className="num">{p.tasa_retencion.toLocaleString('es-CO')}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}
