import { COLOR_NIVEL } from './ui.jsx'

/** Color de una nota según si aprueba, está en el límite o pierde. */
function colorNota(valor) {
  if (valor === null || valor === undefined) return 'var(--mute-d)'
  if (valor < 3) return COLOR_NIVEL.CRITICO
  if (valor < 3.5) return COLOR_NIVEL.MEDIO
  return COLOR_NIVEL.BAJO
}

function texto(valor) {
  return valor === null || valor === undefined ? '—' : valor.toFixed(1).replace('.', ',')
}

/**
 * Notas de cada asignatura corte por corte.
 * `compacto` quita la columna de inasistencias, para el portal del estudiante.
 */
export default function Boletin({ boletin, compacto = false }) {
  if (!boletin || boletin.asignaturas.length === 0) {
    return <p className="hint">No hay asignaturas matriculadas en este periodo.</p>
  }
  const { cortes, corte_vigente: vigente, asignaturas, promedio_periodo: promedio } = boletin

  return (
    <div className="boletin">
      <table>
        <thead>
          <tr>
            <th>Asignatura</th>
            {cortes.map((c) => (
              <th key={c} className={'corte' + (c === vigente ? ' on' : '')}>
                Corte {c}
              </th>
            ))}
            <th className="corte">Promedio</th>
            {!compacto && <th className="corte">Faltas</th>}
          </tr>
        </thead>
        <tbody>
          {asignaturas.map((a) => (
            <tr key={a.matricula_id}>
              <td>
                <b>{a.asignatura}</b>
                <div className="meta">
                  {a.codigo} · {a.creditos} créditos
                  {a.docente && ` · ${a.docente}`}
                  {a.repetida && <span className="chip alerta repetida">repetida</span>}
                </div>
              </td>
              {a.notas.map((n) => (
                <td key={n.corte} className={'corte' + (n.corte === vigente ? ' on' : '')}
                  style={{ color: colorNota(n.valor), fontWeight: 700 }}>
                  {texto(n.valor)}
                </td>
              ))}
              <td className="corte" style={{ color: colorNota(a.promedio), fontWeight: 800 }}>
                {texto(a.promedio)}
              </td>
              {!compacto && (
                <td className="corte" style={{ color: 'var(--mute)' }}>
                  {a.inasistencias}/{a.sesiones}
                </td>
              )}
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td><b>Promedio del periodo</b></td>
            <td colSpan={cortes.length} />
            <td className="corte" style={{ color: colorNota(promedio), fontWeight: 800 }}>
              {texto(promedio)}
            </td>
            {!compacto && <td />}
          </tr>
        </tfoot>
      </table>
    </div>
  )
}
