import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import { Aviso, Cargando, Nivel, ORDEN_ESTADOS, TEXTO_ESTADO } from '../components/ui.jsx'

export default function Casos() {
  const navegar = useNavigate()
  const { usuario } = useAuth()
  const [columnas, setColumnas] = useState(null)
  const [error, setError] = useState('')
  const [aviso, setAviso] = useState('')

  function cargar() {
    api.tablero().then(setColumnas).catch((e) => setError(e.message))
  }
  useEffect(cargar, [])

  async function revisar() {
    try {
      const r = await api.revisarEscalamientos()
      setAviso(`Revisión ejecutada: ${r.revisados} casos críticos revisados, ${r.escalados} escalados.`)
      cargar()
    } catch (e) { setError(e.message) }
  }

  if (error) return <Aviso tipo="err">{error}</Aviso>
  if (!columnas) return <Cargando />

  const total = ORDEN_ESTADOS.reduce((n, e) => n + (columnas[e]?.length || 0), 0)
  const escalados = ORDEN_ESTADOS.flatMap((e) => columnas[e] || []).filter((c) => c.escalado).length

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
        <div>
          <p className="kicker">Casos</p>
          <h1 className="title">Casos de acompañamiento</h1>
          <p className="subtitle">
            {total} casos · {escalados} escalados · los estados siguen el flujo de RN-05.
          </p>
        </div>
        {['COORDINADOR', 'ADMINISTRADOR'].includes(usuario.rol) && (
          <button className="btn" onClick={revisar}>Revisar escalamientos</button>
        )}
      </div>

      {aviso && <Aviso tipo="ok">{aviso}</Aviso>}

      <div className="board">
        {ORDEN_ESTADOS.map((estado) => (
          <section className="col" key={estado}>
            <header>
              <span style={{
                width: 9, height: 9, borderRadius: '50%',
                background: estado === 'ABIERTO' ? 'var(--acc)' : estado === 'CERRADO' ? 'var(--bajo)' : 'var(--teal)',
              }} />
              <b>{TEXTO_ESTADO[estado]}</b>
              <span>{columnas[estado]?.length || 0}</span>
            </header>
            {(columnas[estado] || []).map((c) => (
              <article key={c.id} className={'minicard' + (c.escalado ? ' esc' : '')}
                onClick={() => navegar(`/casos/${c.id}`)}>
                <div className="id">
                  CA-{c.id}
                  {c.escalado && <b style={{ color: 'var(--crit)', float: 'right', fontSize: 10 }}>ESCALADO</b>}
                </div>
                <div className="nom">{c.estudiante}</div>
                <Nivel nivel={c.nivel_apertura} />
                <div className="who">{c.consejero || 'Sin consejero'}</div>
              </article>
            ))}
          </section>
        ))}
      </div>

      <Aviso tipo="info">
        Un caso Crítico sin primera intervención en 3 días hábiles se escala al coordinador [RN-06].
      </Aviso>
    </>
  )
}
