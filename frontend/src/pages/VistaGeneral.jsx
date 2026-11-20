import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { Aviso, Barra, Cargando, COLOR_NIVEL, TEXTO_NIVEL } from '../components/ui.jsx'

export default function VistaGeneral() {
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.reporteGeneral().then(setDatos).catch((e) => setError(e.message))
  }, [])

  if (error) return <Aviso tipo="err">{error}</Aviso>
  if (!datos) return <Cargando />

  const maximo = Math.max(...datos.distribucion.map((d) => d.cantidad), 1)
  const kpis = [
    ['Estudiantes evaluados', datos.estudiantes_evaluados, 'Población con índice calculado', 'var(--ink)'],
    ['En riesgo Alto o Crítico', datos.en_riesgo, 'Requieren acompañamiento', 'var(--crit)'],
    ['Casos activos', datos.casos_activos, 'Abiertos, asignados o en seguimiento', 'var(--ink)'],
    ['Casos escalados', datos.casos_escalados, 'Sin atención en 3 días hábiles', 'var(--acc)'],
  ]

  return (
    <>
      <p className="kicker">Centro de permanencia</p>
      <h1 className="title">Vista general</h1>
      <p className="subtitle">El estado de la permanencia estudiantil, en un solo lugar.</p>

      <div className="banner">
        <p className="kicker">Alerta temprana, no reacción tardía</p>
        <h2>{datos.en_riesgo} estudiantes necesitan acompañamiento</h2>
        <p>El sistema ya abrió un caso para cada uno y asignó consejero.</p>
      </div>

      <div className="grid g4" style={{ marginTop: 20 }}>
        {kpis.map(([label, valor, sub, color]) => (
          <div className="card kpi" key={label}>
            <label>{label}</label>
            <b style={{ color }}>{valor}</b>
            <span>{sub}</span>
          </div>
        ))}
      </div>

      <div className="split" style={{ marginTop: 20 }}>
        <div className="card">
          <h3>Distribución del índice de riesgo</h3>
          <p className="hint">Última evaluación de cada estudiante</p>
          {datos.distribucion.map((d) => (
            <div key={d.nivel} style={{ display: 'flex', alignItems: 'center', gap: 16, margin: '16px 0' }}>
              <span style={{ width: 70, fontWeight: 600, fontSize: 13.5 }}>{TEXTO_NIVEL[d.nivel]}</span>
              <div style={{ flex: 1 }}>
                <Barra valor={d.cantidad} max={maximo} color={COLOR_NIVEL[d.nivel]} />
              </div>
              <b style={{ width: 44, textAlign: 'right', fontSize: 14 }}>{d.cantidad}</b>
            </div>
          ))}
          <p className="hint" style={{ marginTop: 18, marginBottom: 0 }}>
            La atención se concentra en los niveles Alto y Crítico.
          </p>
        </div>

        <div className="card">
          <h3>Retención por programa</h3>
          <p className="hint">Matriculados activos frente a retirados</p>
          {datos.retencion_por_programa.map((p) => (
            <div key={p.programa} style={{ margin: '16px 0' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 7 }}>
                <span style={{ fontWeight: 600 }}>{p.programa}</span>
                <b>{p.tasa_retencion.toLocaleString('es-CO')}%</b>
              </div>
              <Barra valor={p.tasa_retencion} />
            </div>
          ))}
          <p className="hint" style={{ marginTop: 20, marginBottom: 0 }}>
            Global: <b>{datos.tasa_retencion_global.toLocaleString('es-CO')}%</b>
          </p>
          <Link to="/indicadores" style={{ color: 'var(--teal)', fontWeight: 600, fontSize: 13 }}>
            Ver todos los indicadores →
          </Link>
        </div>
      </div>
    </>
  )
}
