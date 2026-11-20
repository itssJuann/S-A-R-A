import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import {
  Aviso, Cargando, COLOR_ACCION, Estado, fecha, indice as fmtIndice, Nivel, ORDEN_ESTADOS,
  TEXTO_ACCION, TEXTO_ESTADO, TEXTO_MOTIVO, TEXTO_RESULTADO,
} from '../components/ui.jsx'

const TIPOS = [['TUTORIA', 'Tutoría'], ['ENTREVISTA', 'Entrevista'], ['LLAMADA', 'Llamada'], ['TALLER', 'Taller']]
const APOYOS = [['PSICOLOGICO', 'Apoyo psicológico'], ['FINANCIERO', 'Apoyo financiero'],
                ['ACADEMICO', 'Apoyo académico'], ['SALUD', 'Salud']]

export default function Caso() {
  const { id } = useParams()
  const { usuario } = useAuth()
  const [caso, setCaso] = useState(null)
  const [intervenciones, setIntervenciones] = useState([])
  const [derivaciones, setDerivaciones] = useState([])
  const [error, setError] = useState('')
  const [aviso, setAviso] = useState('')
  const [form, setForm] = useState({ tipo: 'ENTREVISTA', descripcion: '', compromisos: '', fecha_cita: '' })
  const [apoyo, setApoyo] = useState('FINANCIERO')
  const [consejeros, setConsejeros] = useState([])
  const [motivoReapertura, setMotivoReapertura] = useState('')
  const [nuevoConsejero, setNuevoConsejero] = useState('')

  function cargar() {
    setError('')
    api.caso(id).then(setCaso).catch((e) => setError(e.message))
    api.intervenciones(id).then(setIntervenciones).catch(() => {})
    api.derivaciones().then((d) => setDerivaciones(d.filter((x) => String(x.caso_id) === String(id)))).catch(() => {})
  }
  useEffect(cargar, [id])

  // La lista de consejeros solo la necesita quien puede reasignar.
  useEffect(() => {
    if (['COORDINADOR', 'ADMINISTRADOR'].includes(usuario.rol)) {
      api.usuarios({ rol: 'CONSEJERO' }).then(setConsejeros).catch(() => {})
    }
  }, [usuario.rol])

  async function accion(fn, mensaje) {
    setError(''); setAviso('')
    try { await fn(); setAviso(mensaje); cargar() } catch (e) { setError(e.message) }
  }

  if (error && !caso) return <Aviso tipo="err">{error}</Aviso>
  if (!caso) return <Cargando />

  const cerrado = caso.estado === 'CERRADO'
  const siguiente = { ABIERTO: 'ASIGNADO', ASIGNADO: 'EN_SEGUIMIENTO', EN_SEGUIMIENTO: 'EN_EVALUACION' }[caso.estado]
  const puedeCerrar = caso.estado === 'EN_EVALUACION'
  const esConsejero = ['CONSEJERO', 'COORDINADOR', 'ADMINISTRADOR'].includes(usuario.rol)
  const esCoordinador = ['COORDINADOR', 'ADMINISTRADOR'].includes(usuario.rol)

  return (
    <>
      <p className="kicker">Casos · CA-{caso.id}</p>
      <h1 className="title">{caso.estudiante}</h1>
      <p className="subtitle">
        {caso.programa} · abierto el {fecha(caso.fecha_apertura)} · consejero: {caso.consejero || 'sin asignar'}
      </p>

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 20 }}>
        <Estado estado={caso.estado} />
        <Nivel nivel={caso.nivel_apertura} />
        {caso.escalado && <span className="chip alerta">Escalado al coordinador</span>}
        {caso.resultado && <span className="chip ok">{TEXTO_RESULTADO[caso.resultado]}</span>}
        <span className="chip neutro">Índice actual: {fmtIndice(caso.indice_actual)}</span>
      </div>

      {error && <Aviso tipo="err">{error}</Aviso>}
      {aviso && <Aviso tipo="ok">{aviso}</Aviso>}

      {/* Línea de estados */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          {ORDEN_ESTADOS.map((e, i) => (
            <span key={e} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span className="chip" style={{
                background: e === caso.estado ? 'var(--dk)' : 'var(--lt)',
                color: e === caso.estado ? '#fff' : 'var(--mute)',
              }}>{TEXTO_ESTADO[e]}</span>
              {i < ORDEN_ESTADOS.length - 1 && <span style={{ color: 'var(--mute-d)' }}>→</span>}
            </span>
          ))}
        </div>
        {!cerrado && esConsejero && (
          <div style={{ marginTop: 18, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            {siguiente && (
              <button className="btn sm" onClick={() => accion(
                () => api.cambiarEstado(caso.id, siguiente), `Caso movido a ${TEXTO_ESTADO[siguiente]}.`)}>
                Pasar a {TEXTO_ESTADO[siguiente]}
              </button>
            )}
            {caso.estado === 'EN_EVALUACION' && (
              <button className="btn sm ghost" onClick={() => accion(
                () => api.cambiarEstado(caso.id, 'EN_SEGUIMIENTO', 'DEVOLUCION'),
                'Caso devuelto a seguimiento.')}>
                Devolver a seguimiento
              </button>
            )}
            {puedeCerrar && Object.entries(TEXTO_RESULTADO).map(([valor, texto]) => (
              <button key={valor} className={'btn sm ' + (valor === 'SUPERADO' ? 'ok' : 'danger')}
                onClick={() => accion(() => api.cerrarCaso(caso.id, valor), `Caso cerrado: ${texto}.`)}>
                Cerrar · {texto}
              </button>
            ))}
          </div>
        )}

        {/* Acciones reservadas al coordinador */}
        {esCoordinador && (
          <div className="acciones-coord">
            <p className="kicker">Acciones del coordinador</p>
            <div className="fila">
              {caso.escalado && (
                <button className="btn sm" onClick={() => accion(
                  () => api.atenderEscalamiento(caso.id),
                  'Tomaste el escalamiento: el caso deja de figurar como pendiente.')}>
                  Tomar el escalamiento
                </button>
              )}
              {!cerrado && consejeros.length > 0 && (
                <>
                  <select style={{ maxWidth: 230 }} value={nuevoConsejero}
                    onChange={(e) => setNuevoConsejero(e.target.value)}>
                    <option value="">Reasignar a…</option>
                    {consejeros
                      .filter((c) => c.id !== caso.consejero_id
                                     && c.programa_id === caso.programa_id)
                      .map((c) => (
                        <option key={c.id} value={c.id}>{c.nombre}</option>
                      ))}
                  </select>
                  <button className="btn sm ghost" disabled={!nuevoConsejero}
                    onClick={() => accion(async () => {
                      await api.reasignar(caso.id, Number(nuevoConsejero))
                      setNuevoConsejero('')
                    }, 'Caso reasignado.')}>
                    Reasignar
                  </button>
                </>
              )}
              {cerrado && (
                <>
                  <input style={{ maxWidth: 330 }} value={motivoReapertura}
                    placeholder="Motivo de la reapertura (mínimo 10 caracteres)"
                    onChange={(e) => setMotivoReapertura(e.target.value)} />
                  <button className="btn sm" disabled={motivoReapertura.trim().length < 10}
                    onClick={() => accion(async () => {
                      await api.reabrirCaso(caso.id, motivoReapertura.trim())
                      setMotivoReapertura('')
                    }, 'Caso reabierto y devuelto a seguimiento.')}>
                    Reabrir caso
                  </button>
                </>
              )}
            </div>
            <p className="hint" style={{ margin: '12px 0 0' }}>
              Cada una de estas acciones queda registrada con tu nombre en el historial
              del caso y en la bitácora [RQNF-03].
            </p>
          </div>
        )}

        {caso.derivaciones_abiertas > 0 && (
          <Aviso tipo="info">
            El caso tiene {caso.derivaciones_abiertas} derivación(es) abierta(s): no se puede cerrar
            hasta que bienestar las atienda [RQF-11].
          </Aviso>
        )}
      </div>

      <div className="split">
        <div>
          {/* Registrar intervención */}
          {!cerrado && esConsejero && (
            <div className="card" style={{ marginBottom: 20 }}>
              <h3>Registrar intervención</h3>
              <p className="hint">
                La descripción es confidencial: solo la ven el consejero, el coordinador y bienestar [RQNF-03].
              </p>
              <label className="field">Tipo</label>
              <select value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value })}>
                {TIPOS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
              </select>

              <label className="field">Descripción</label>
              <textarea value={form.descripcion} placeholder="Qué se habló y qué se observó…"
                onChange={(e) => setForm({ ...form, descripcion: e.target.value })} />

              <label className="field">Compromisos acordados (los ve el estudiante)</label>
              <textarea style={{ minHeight: 70 }} value={form.compromisos}
                placeholder="Asistir a todas las clases del corte…"
                onChange={(e) => setForm({ ...form, compromisos: e.target.value })} />

              <label className="field">Próxima cita (opcional)</label>
              <input type="datetime-local" value={form.fecha_cita}
                onChange={(e) => setForm({ ...form, fecha_cita: e.target.value })} />

              <button className="btn" style={{ marginTop: 18 }}
                disabled={form.descripcion.trim().length < 10}
                onClick={() => accion(async () => {
                  await api.crearIntervencion(caso.id, {
                    tipo: form.tipo, descripcion: form.descripcion,
                    compromisos: form.compromisos || null,
                    fecha_cita: form.fecha_cita ? new Date(form.fecha_cita).toISOString() : null,
                  })
                  setForm({ tipo: 'ENTREVISTA', descripcion: '', compromisos: '', fecha_cita: '' })
                }, 'Intervención registrada.')}>
                Guardar intervención
              </button>
            </div>
          )}

          <div className="card">
            <h3>Intervenciones ({intervenciones.length})</h3>
            {intervenciones.length === 0 && <p className="hint">Todavía no hay intervenciones registradas.</p>}
            {intervenciones.map((i) => (
              <div key={i.id} style={{ borderTop: '1px solid var(--bd)', padding: '16px 0' }}>
                <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 8 }}>
                  <span className="chip teal">{TIPOS.find(([v]) => v === i.tipo)?.[1] || i.tipo}</span>
                  <span style={{ fontSize: 12, color: 'var(--mute)' }}>
                    {fecha(i.fecha, true)} · {i.consejero}
                  </span>
                </div>
                <p style={{ margin: '0 0 8px', fontSize: 13.5 }}>{i.descripcion}</p>
                {i.compromisos && (
                  <p style={{ margin: 0, fontSize: 13, color: 'var(--mute)' }}>
                    <b>Compromisos:</b> {i.compromisos}
                  </p>
                )}
                {i.fecha_cita && (
                  <p style={{ margin: '8px 0 0', fontSize: 12.5, color: 'var(--teal)' }}>
                    Cita: {fecha(i.fecha_cita, true)}
                    {i.asistio === true && ' · asistió'}
                    {i.asistio === false && ' · no asistió'}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>

        <div>
          {!cerrado && esConsejero && (
            <div className="card" style={{ marginBottom: 20 }}>
              <h3>Derivar a bienestar</h3>
              <p className="hint">El caso no se cierra mientras la derivación siga abierta.</p>
              <select value={apoyo} onChange={(e) => setApoyo(e.target.value)}>
                {APOYOS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
              </select>
              <button className="btn sm" style={{ marginTop: 14 }} onClick={() => accion(
                () => api.crearDerivacion(caso.id, { tipo_apoyo: apoyo }), 'Derivación enviada a bienestar.')}>
                Enviar derivación
              </button>
            </div>
          )}

          <div className="card" style={{ marginBottom: 20 }}>
            <h3>Derivaciones ({derivaciones.length})</h3>
            {derivaciones.length === 0 && <p className="hint">Sin derivaciones.</p>}
            {derivaciones.map((d) => (
              <div key={d.id} style={{ borderTop: '1px solid var(--bd)', padding: '12px 0', fontSize: 13 }}>
                <b>{APOYOS.find(([v]) => v === d.tipo_apoyo)?.[1]}</b>
                <span className={'chip ' + (d.estado === 'ABIERTA' ? 'alerta' : 'ok')} style={{ float: 'right' }}>
                  {d.estado.toLowerCase()}
                </span>
                <div style={{ color: 'var(--mute)', fontSize: 12, marginTop: 6 }}>
                  {fecha(d.fecha)} · {d.solicitante}
                </div>
                {usuario.rol === 'BIENESTAR' && d.estado === 'ABIERTA' && (
                  <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                    <button className="btn sm ok" onClick={() => accion(
                      () => api.atenderDerivacion(d.id, { estado: 'ATENDIDA' }), 'Derivación atendida.')}>
                      Atender
                    </button>
                    <button className="btn sm danger" onClick={() => accion(
                      () => api.atenderDerivacion(d.id, { estado: 'RECHAZADA' }), 'Derivación rechazada.')}>
                      Rechazar
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="card" style={{ marginBottom: 20 }}>
            <h3>Acciones registradas ({caso.acciones?.length ?? 0})</h3>
            <p className="hint">Quién hizo qué sobre este caso [RQNF-03]</p>
            {(caso.acciones ?? []).length === 0 && (
              <p className="hint">Todavía no hay acciones manuales sobre el caso.</p>
            )}
            <ul className="timeline">
              {(caso.acciones ?? []).map((a) => (
                <li key={a.id}>
                  <span className="when">{fecha(a.fecha, true)}</span>
                  <span>
                    <span className={'chip ' + (COLOR_ACCION[a.accion] || 'neutro')}>
                      {TEXTO_ACCION[a.accion] || a.accion.toLowerCase()}
                    </span>
                    <div style={{ fontSize: 12.5, marginTop: 5 }}>{a.detalle}</div>
                    <div style={{ fontSize: 11.5, color: 'var(--mute)' }}>{a.usuario}</div>
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <div className="card">
            <h3>Historial del caso</h3>
            <p className="hint">Cada transición queda registrada [RQF-12]</p>
            <ul className="timeline">
              {caso.historial.map((h) => (
                <li key={h.id}>
                  <span className="when">{fecha(h.fecha, true)}</span>
                  <span>
                    <b>{TEXTO_ESTADO[h.estado_nuevo]}</b>
                    {h.motivo && (
                      <span style={{ color: 'var(--mute)' }}>
                        {' · '}{TEXTO_MOTIVO[h.motivo] || h.motivo.toLowerCase().replace(/_/g, ' ')}
                      </span>
                    )}
                    <div style={{ fontSize: 11.5, color: 'var(--mute)' }}>{h.usuario}</div>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </>
  )
}
