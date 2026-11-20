// Piezas reutilizables de la interfaz.

export const COLOR_NIVEL = {
  BAJO: 'var(--bajo)', MEDIO: 'var(--medio)', ALTO: 'var(--alto)', CRITICO: 'var(--crit)',
}
export const TEXTO_NIVEL = { BAJO: 'Bajo', MEDIO: 'Medio', ALTO: 'Alto', CRITICO: 'Crítico' }
export const TEXTO_ESTADO = {
  ABIERTO: 'Abierto', ASIGNADO: 'Asignado', EN_SEGUIMIENTO: 'En seguimiento',
  EN_EVALUACION: 'En evaluación', CERRADO: 'Cerrado',
}
export const TEXTO_RESULTADO = {
  SUPERADO: 'Superado', PERSISTE: 'Persiste', DESERCION_CONFIRMADA: 'Deserción confirmada',
}
export const TEXTO_MOTIVO = {
  APERTURA_AUTOMATICA: 'apertura automática',
  ASIGNACION_AUTOMATICA: 'asignación automática por carga',
  PRIMERA_INTERVENCION: 'primera intervención',
  REASIGNACION: 'reasignación',
  APERTURA_MANUAL: 'apertura manual por el coordinador',
  ASIGNACION_MANUAL: 'asignación manual',
  REAPERTURA: 'reapertura por el coordinador',
  ESCALAMIENTO_ATENDIDO: 'escalamiento atendido',
  ESCALAMIENTO: 'escalamiento al coordinador',
  DEVOLUCION: 'devuelto a seguimiento',
  CIERRE: 'cierre del caso',
}
export const TEXTO_ACCION = {
  LECTURA: 'consultó', ESCRITURA: 'registró', APERTURA: 'abrió el caso',
  CAMBIO_ESTADO: 'cambió el estado', CIERRE: 'cerró el caso',
  REAPERTURA: 'reabrió el caso', REASIGNACION: 'reasignó el caso',
  ESCALAMIENTO: 'atendió el escalamiento', DERIVACION: 'gestionó una derivación',
}
export const COLOR_ACCION = {
  LECTURA: 'neutro', ESCRITURA: 'teal', APERTURA: 'teal', CAMBIO_ESTADO: 'teal',
  CIERRE: 'ok', REAPERTURA: 'alerta', REASIGNACION: 'alerta', ESCALAMIENTO: 'alerta',
  DERIVACION: 'teal',
}
export const ORDEN_ESTADOS = ['ABIERTO', 'ASIGNADO', 'EN_SEGUIMIENTO', 'EN_EVALUACION', 'CERRADO']

export function Nivel({ nivel }) {
  if (!nivel) return <span className="chip neutro">Sin evaluar</span>
  return <span className={`chip ${nivel}`}>{TEXTO_NIVEL[nivel]}</span>
}

export function Estado({ estado }) {
  const clase = estado === 'CERRADO' ? 'ok' : estado === 'ABIERTO' ? 'alerta' : 'teal'
  return <span className={`chip ${clase}`}>{TEXTO_ESTADO[estado]}</span>
}

export function Barra({ valor, max = 100, color = 'var(--teal)' }) {
  const crudo = max > 0 ? (valor / max) * 100 : 0
  // Un valor de 0 deja la barra vacía; cualquier valor positivo se ve, aunque sea mínimo.
  const pct = crudo <= 0 ? 0 : Math.max(2, Math.min(100, crudo))
  return (
    <div className="bar">{pct > 0 && <i style={{ width: `${pct}%`, background: color }} />}</div>
  )
}

export function Medidor({ indice, nivel, etiqueta = 'Índice de riesgo' }) {
  const r = 78, circ = 2 * Math.PI * r, pct = Math.min(100, Math.max(0, indice || 0))
  const avance = (circ * pct) / 100
  return (
    <div className="gauge">
      <p className="gauge-titulo">{etiqueta}</p>
      <div className="gauge-aro">
        <svg viewBox="0 0 190 190" role="img" aria-label={`Índice ${indice ?? 'sin calcular'} de 100`}>
          <circle cx="95" cy="95" r={r} fill="none" stroke="#2c3b5e" strokeWidth="16" />
          {pct > 0 && (
            <circle cx="95" cy="95" r={r} fill="none" stroke={COLOR_NIVEL[nivel] || 'var(--teal)'}
              strokeWidth="16" strokeLinecap="round" transform="rotate(-90 95 95)"
              strokeDasharray={`${avance} ${circ - avance}`} />
          )}
        </svg>
        <div className="gauge-centro">
          <b>{indice ?? '—'}</b>
          <span>de 100</span>
        </div>
      </div>
      <Nivel nivel={nivel} />
    </div>
  )
}

export function Aviso({ tipo = 'info', children }) {
  if (!children) return null
  return <div className={`aviso ${tipo}`}>{children}</div>
}

export function Cargando({ texto = 'Cargando…' }) {
  return <div className="loading">{texto}</div>
}

/** El índice siempre se muestra como entero, aquí y en el resto de la interfaz. */
export function indice(valor) {
  return valor === null || valor === undefined ? '—' : Math.round(Number(valor))
}

export function fecha(iso, conHora = false) {
  if (!iso) return '—'
  const d = new Date(iso)
  const base = d.toLocaleDateString('es-CO', { day: '2-digit', month: '2-digit', year: 'numeric' })
  return conHora ? `${base} ${d.toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' })}` : base
}
