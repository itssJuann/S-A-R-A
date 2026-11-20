// Cliente de la API de SARA. Guarda el token en memoria + localStorage.
const CLAVE_TOKEN = 'sara.token'

export function guardarToken(t) {
  if (t) localStorage.setItem(CLAVE_TOKEN, t)
  else localStorage.removeItem(CLAVE_TOKEN)
}
export function leerToken() {
  return localStorage.getItem(CLAVE_TOKEN)
}

export class ErrorApi extends Error {
  constructor(mensaje, status) {
    super(mensaje)
    this.status = status
  }
}

async function pedir(ruta, { metodo = 'GET', cuerpo, form } = {}) {
  const cabeceras = {}
  const token = leerToken()
  if (token) cabeceras.Authorization = `Bearer ${token}`
  let body
  if (form) {
    body = new URLSearchParams(form)
    cabeceras['Content-Type'] = 'application/x-www-form-urlencoded'
  } else if (cuerpo !== undefined) {
    body = JSON.stringify(cuerpo)
    cabeceras['Content-Type'] = 'application/json'
  }

  const r = await fetch(`/api${ruta}`, { method: metodo, headers: cabeceras, body })
  if (r.status === 401) {
    guardarToken(null)
    throw new ErrorApi('Tu sesión expiró. Vuelve a iniciar sesión.', 401)
  }
  if (!r.ok) {
    let detalle = `Error ${r.status}`
    try {
      const j = await r.json()
      if (typeof j.detail === 'string') detalle = j.detail
      else if (Array.isArray(j.detail)) detalle = j.detail.map((d) => d.msg).join(' · ')
    } catch { /* respuesta sin cuerpo JSON */ }
    throw new ErrorApi(detalle, r.status)
  }
  if (r.status === 204) return null
  return r.json()
}

export const api = {
  configuracion: () => pedir('/configuracion'),
  boletin: (estudianteId) => pedir(`/desempeno/boletin/${estudianteId}`),
  login: (correo, clave) => pedir('/auth/login', { metodo: 'POST', form: { username: correo, password: clave } }),
  yo: () => pedir('/auth/me'),

  estudiantesEnRiesgo: (q = {}) => pedir(`/riesgo/estudiantes${qs(q)}`),
  evaluaciones: (id) => pedir(`/riesgo/estudiantes/${id}/evaluaciones`),
  simular: (id) => pedir(`/riesgo/estudiantes/${id}/simular`),
  evaluar: (id) => pedir(`/riesgo/estudiantes/${id}/evaluar`, { metodo: 'POST' }),
  reevaluar: (corte) => pedir(`/riesgo/reevaluar?corte=${corte}`, { metodo: 'POST' }),

  casos: (q = {}) => pedir(`/casos${qs(q)}`),
  abrirCaso: (datos) => pedir('/casos', { metodo: 'POST', cuerpo: datos }),
  reabrirCaso: (id, motivo) => pedir(`/casos/${id}/reabrir`, { metodo: 'POST', cuerpo: { motivo } }),
  atenderEscalamiento: (id) => pedir(`/casos/${id}/atender-escalamiento`, { metodo: 'POST' }),
  tablero: () => pedir('/casos/tablero'),
  caso: (id) => pedir(`/casos/${id}`),
  cambiarEstado: (id, estado, motivo) => pedir(`/casos/${id}/estado`, { metodo: 'POST', cuerpo: { estado, motivo } }),
  cerrarCaso: (id, resultado) => pedir(`/casos/${id}/cerrar`, { metodo: 'POST', cuerpo: { resultado } }),
  reasignar: (id, consejero_id) => pedir(`/casos/${id}/reasignar`, { metodo: 'POST', cuerpo: { consejero_id } }),
  revisarEscalamientos: () => pedir('/casos/revisar-escalamientos', { metodo: 'POST' }),

  intervenciones: (casoId) => pedir(`/casos/${casoId}/intervenciones`),
  crearIntervencion: (casoId, datos) => pedir(`/casos/${casoId}/intervenciones`, { metodo: 'POST', cuerpo: datos }),
  citas: () => pedir('/citas'),

  derivaciones: (q = {}) => pedir(`/derivaciones${qs(q)}`),
  crearDerivacion: (casoId, datos) => pedir(`/casos/${casoId}/derivaciones`, { metodo: 'POST', cuerpo: datos }),
  atenderDerivacion: (id, datos) => pedir(`/derivaciones/${id}/atender`, { metodo: 'POST', cuerpo: datos }),

  cursoDocente: (periodo, asignaturaId, corte) => pedir(`/desempeno/cursos/${periodo}?asignatura_id=${asignaturaId}&corte=${corte}`),
  registrarNota: (datos) => pedir('/desempeno/notas', { metodo: 'POST', cuerpo: datos }),
  registrarInasistencia: (datos) => pedir('/desempeno/inasistencias', { metodo: 'POST', cuerpo: datos }),

  asignaturas: (programaId) => pedir(`/admin/asignaturas${qs({ programa_id: programaId })}`),
  programas: () => pedir('/admin/programas'),
  usuarios: (q = {}) => pedir(`/admin/usuarios${qs(q)}`),
  factores: () => pedir('/admin/factores'),
  configurarFactores: (factores) => pedir('/admin/factores', { metodo: 'PUT', cuerpo: { factores } }),
  bitacora: (q = {}) => pedir(`/admin/bitacora${qs(q)}`),

  notificaciones: () => pedir('/notificaciones'),
  pendientes: () => pedir('/notificaciones/pendientes'),
  atenderNotificacion: (id) => pedir(`/notificaciones/${id}/atender`, { metodo: 'POST' }),

  miEstado: () => pedir('/portal/mi-estado'),
  reporteGeneral: () => pedir('/reportes/general'),
  efectividad: () => pedir('/reportes/efectividad'),
}

function qs(objeto) {
  const partes = Object.entries(objeto).filter(([, v]) => v !== undefined && v !== null && v !== '')
  return partes.length ? '?' + new URLSearchParams(Object.fromEntries(partes)) : ''
}
