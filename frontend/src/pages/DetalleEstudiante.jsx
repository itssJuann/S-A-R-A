import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import Boletin from '../components/Boletin.jsx'
import {
  Aviso, Barra, Cargando, COLOR_NIVEL, fecha, indice as fmtIndice, Medidor,
} from '../components/ui.jsx'

export default function DetalleEstudiante() {
  const { id } = useParams()
  const navegar = useNavigate()
  const { usuario } = useAuth()
  const [sim, setSim] = useState(null)
  const [motivo, setMotivo] = useState('')
  const [abriendo, setAbriendo] = useState(false)
  const [boletin, setBoletin] = useState(null)
  const [historial, setHistorial] = useState([])
  const [estudiante, setEstudiante] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.boletin(id).then(setBoletin).catch(() => {})
    Promise.all([api.simular(id), api.evaluaciones(id), api.estudiantesEnRiesgo({})])
      .then(([s, h, lista]) => {
        setSim(s)
        setHistorial(h.slice().reverse())
        setEstudiante(lista.find((e) => String(e.id) === String(id)))
      })
      .catch((e) => setError(e.message))
  }, [id])

  if (error) return <Aviso tipo="err">{error}</Aviso>
  if (!sim) return <Cargando />

  const esCoordinador = ['COORDINADOR', 'ADMINISTRADOR'].includes(usuario.rol)

  async function abrirCaso() {
    setError(''); setAbriendo(true)
    try {
      const caso = await api.abrirCaso({ estudiante_id: Number(id), motivo: motivo.trim() })
      navegar(`/casos/${caso.id}`)
    } catch (e) { setError(e.message) }
    finally { setAbriendo(false) }
  }

  return (
    <>
      <p className="kicker">Estudiantes en riesgo · Detalle</p>
      <h1 className="title">{estudiante?.nombre ?? `Estudiante ${id}`}</h1>
      <p className="subtitle">
        {estudiante && `${estudiante.documento} · ${estudiante.programa} · Semestre ${estudiante.semestre}`}
      </p>

      <div className="split">
        <div className="card">
          <h3>Cómo se compone el índice</h3>
          <p className="hint">Aporte de cada factor según los pesos vigentes (modelo v{sim.version_modelo})</p>
          {sim.detalle_factores.map((f) => (
            <div key={f.codigo} style={{ display: 'flex', alignItems: 'center', gap: 16, margin: '18px 0' }}>
              <div style={{ width: 190 }}>
                <b style={{ fontSize: 13.5 }}>{f.nombre}</b>
                <div style={{ fontSize: 11.5, color: 'var(--mute)' }}>{f.evidencia}</div>
              </div>
              <div style={{ flex: 1 }}>
                <Barra valor={f.valor} color={COLOR_NIVEL[nivelDe(f.valor)]} />
              </div>
              <span style={{ width: 44, textAlign: 'right', fontSize: 13, color: 'var(--mute)' }}>
                {f.peso}%
              </span>
              <b style={{ width: 44, textAlign: 'right', color: COLOR_NIVEL[nivelDe(f.valor)] }}>
                {f.aporte}
              </b>
            </div>
          ))}
          <p className="hint" style={{ textAlign: 'right', marginBottom: 0 }}>
            Índice total: <b style={{ color: 'var(--ink)' }}>{fmtIndice(sim.indice)} / 100</b>
          </p>
        </div>

        <div className="card oscuro">
          <Medidor indice={sim.indice} nivel={sim.nivel} />
          <p style={{ textAlign: 'center', margin: '22px 0 0' }}>
            {estudiante?.caso_id ? (
              <Link to={`/casos/${estudiante.caso_id}`} className="btn sm claro">
                Ver caso CA-{estudiante.caso_id}
              </Link>
            ) : (
              <span style={{ fontSize: 12.5, color: 'var(--mute-d)' }}>
                Sin caso de acompañamiento abierto
              </span>
            )}
          </p>
        </div>
      </div>

      {esCoordinador && !estudiante?.caso_id && (
        <div className="card" style={{ marginTop: 20 }}>
          <h3>Abrir un caso de acompañamiento</h3>
          <p className="hint">
            El sistema abre casos solo cuando el índice llega a Alto o Crítico. Como coordinador
            puedes abrir uno por lo que el modelo no ve: un reporte de un docente, una situación
            familiar, una señal en clase [RQF-08].
          </p>
          {error && <Aviso tipo="err">{error}</Aviso>}
          <label className="field">Motivo de la apertura</label>
          <textarea style={{ minHeight: 70 }} value={motivo}
            placeholder="La profesora de Cálculo reportó que dejó de asistir tras…"
            onChange={(e) => setMotivo(e.target.value)} />
          <button className="btn" style={{ marginTop: 14 }}
            disabled={motivo.trim().length < 10 || abriendo} onClick={abrirCaso}>
            {abriendo ? 'Abriendo…' : 'Abrir caso y asignar consejero'}
          </button>
        </div>
      )}

      <div className="card" style={{ marginTop: 20 }}>
        <h3>Notas por corte</h3>
        <p className="hint">
          {boletin
            ? `Periodo ${boletin.periodo} · ${boletin.cortes.length} cortes · el corte ${boletin.corte_vigente} es el vigente`
            : 'Cargando el boletín…'}
        </p>
        <Boletin boletin={boletin} />
      </div>

      <div className="card" style={{ marginTop: 20 }}>
        <h3>Historial del índice</h3>
        <p className="hint">Cada evaluación guarda la versión del modelo con la que se calculó</p>
        {historial.length === 0 ? <p className="hint">Sin evaluaciones registradas.</p> : (
          <div className="historial">
            {historial.map((e) => (
              <div className="punto" key={e.id}>
                <b style={{ color: COLOR_NIVEL[e.nivel] }}>{fmtIndice(e.indice)}</b>
                <div className="pista">
                  <i style={{
                    height: `${Math.max(4, Number(e.indice) * 1.2)}px`,
                    background: COLOR_NIVEL[e.nivel],
                  }} />
                </div>
                <span>
                  {fecha(e.fecha)}<br />Corte {e.corte ?? '—'} · v{e.version_modelo}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  )
}

function nivelDe(valor) {
  if (valor >= 85) return 'CRITICO'
  if (valor >= 65) return 'ALTO'
  if (valor >= 40) return 'MEDIO'
  return 'BAJO'
}
