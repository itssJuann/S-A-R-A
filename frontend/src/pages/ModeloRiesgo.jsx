import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { Aviso, Barra, Cargando } from '../components/ui.jsx'

export default function ModeloRiesgo() {
  const [factores, setFactores] = useState(null)
  const [pesos, setPesos] = useState({})
  const [error, setError] = useState(''), [aviso, setAviso] = useState('')
  const [guardando, setGuardando] = useState(false)

  function cargar() {
    api.factores().then((f) => {
      setFactores(f)
      setPesos(Object.fromEntries(f.map((x) => [x.codigo, String(x.peso)])))
    }).catch((e) => setError(e.message))
  }
  useEffect(cargar, [])

  if (error && !factores) return <Aviso tipo="err">{error}</Aviso>
  if (!factores) return <Cargando />

  const version = factores[0]?.version_modelo ?? 1
  const suma = Object.values(pesos).reduce((s, v) => s + (parseFloat(String(v).replace(',', '.')) || 0), 0)
  const valida = Math.abs(suma - 100) < 0.001
  const cambio = factores.some((f) => Math.abs(parseFloat(String(pesos[f.codigo]).replace(',', '.')) - f.peso) > 0.001)

  async function guardar() {
    setError(''); setAviso(''); setGuardando(true)
    try {
      await api.configurarFactores(factores.map((f) => ({
        codigo: f.codigo, nombre: f.nombre,
        peso: parseFloat(String(pesos[f.codigo]).replace(',', '.')),
      })))
      setAviso(`Pesos guardados. El modelo pasó a la versión ${version + 1}; las evaluaciones anteriores conservan la versión con la que se calcularon.`)
      cargar()
    } catch (e) { setError(e.message) }
    finally { setGuardando(false) }
  }

  return (
    <>
      <p className="kicker">Configuración · RQF-02</p>
      <h1 className="title">Modelo de riesgo</h1>
      <p className="subtitle">
        Pesos vigentes (versión {version}). La suma debe ser exactamente 100 % [RN-01].
      </p>

      {error && <Aviso tipo="err">{error}</Aviso>}
      {aviso && <Aviso tipo="ok">{aviso}</Aviso>}

      <div className="split">
        <div className="card">
          <h3>Pesos de los factores</h3>
          <p className="hint">Cada factor aporta <code>valor × peso / 100</code> al índice 0–100.</p>
          {factores.map((f) => {
            const p = parseFloat(String(pesos[f.codigo]).replace(',', '.')) || 0
            return (
              <div key={f.codigo} style={{ display: 'flex', alignItems: 'center', gap: 16, margin: '20px 0' }}>
                <div style={{ width: 200 }}>
                  <b style={{ fontSize: 13.5 }}>{f.nombre}</b>
                  <div style={{ fontSize: 11, color: 'var(--mute)', letterSpacing: .4 }}>{f.codigo}</div>
                </div>
                <div style={{ flex: 1 }}><Barra valor={p} color="var(--teal)" /></div>
                <input style={{ width: 86, padding: '8px 10px', textAlign: 'center' }} inputMode="decimal"
                  value={pesos[f.codigo]}
                  onChange={(e) => setPesos({ ...pesos, [f.codigo]: e.target.value })} />
                <span style={{ color: 'var(--mute)' }}>%</span>
              </div>
            )
          })}
          <div style={{ borderTop: '1px solid var(--bd)', marginTop: 18, paddingTop: 18, display: 'flex', alignItems: 'center', gap: 16 }}>
            <b style={{ flex: 1 }}>Suma</b>
            <b style={{ fontSize: 22, color: valida ? 'var(--bajo)' : 'var(--crit)' }}>
              {suma.toFixed(2).replace('.', ',')} %
            </b>
          </div>
          {!valida && <Aviso tipo="err">
            La suma es {suma.toFixed(2).replace('.', ',')} %. El sistema rechaza cualquier configuración que no sume 100 %.
          </Aviso>}
          <button className="btn" style={{ marginTop: 18 }} disabled={!valida || !cambio || guardando} onClick={guardar}>
            {guardando ? 'Guardando…' : 'Guardar y crear versión ' + (version + 1)}
          </button>
        </div>

        <div>
          <div className="card" style={{ marginBottom: 20 }}>
            <h3>Umbrales de clasificación</h3>
            <p className="hint">Fijos en la configuración del sistema [RN-02]</p>
            <ul className="lista">
              <li><span className="chip bajo">Bajo</span> índice menor que 40</li>
              <li><span className="chip medio">Medio</span> entre 40 y 64</li>
              <li><span className="chip alto">Alto</span> entre 65 y 84</li>
              <li><span className="chip crit">Crítico</span> 85 o más</li>
            </ul>
          </div>
          <div className="card">
            <h3>Versionado</h3>
            <p className="hint">
              Al guardar, los factores actuales dejan de estar vigentes y se insertan nuevos con la
              versión siguiente. Las evaluaciones ya registradas guardan su propia versión, así que
              un índice histórico siempre se puede reproducir con los pesos con los que se calculó
              [RQNF-05].
            </p>
          </div>
        </div>
      </div>
    </>
  )
}
