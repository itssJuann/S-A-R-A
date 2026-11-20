import { createContext, useContext, useEffect, useState } from 'react'
import { api, guardarToken, leerToken } from './api.js'

const Ctx = createContext(null)

/** Valores por defecto mientras llega la configuración del servidor. */
const CONFIG_INICIAL = { periodo: '2026-2', cortes: [1, 2, 3, 4], corte_vigente: 4 }

export function ProveedorAuth({ children }) {
  const [usuario, setUsuario] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [config, setConfig] = useState(CONFIG_INICIAL)

  useEffect(() => {
    // El periodo y los cortes vienen del backend, no están fijos en la interfaz.
    api.configuracion().then(setConfig).catch(() => {})
    if (!leerToken()) { setCargando(false); return }
    api.yo().then(setUsuario).catch(() => guardarToken(null)).finally(() => setCargando(false))
  }, [])

  async function entrar(correo, clave) {
    const r = await api.login(correo, clave)
    guardarToken(r.access_token)
    setUsuario(r.usuario)
    return r.usuario
  }

  function salir() {
    guardarToken(null)
    setUsuario(null)
  }

  return (
    <Ctx.Provider value={{ usuario, cargando, entrar, salir, config }}>{children}</Ctx.Provider>
  )
}

export function useAuth() {
  return useContext(Ctx)
}

/** Atajo para las pantallas que solo necesitan el periodo y los cortes. */
export function useConfig() {
  return useContext(Ctx)?.config ?? CONFIG_INICIAL
}

// Qué ve cada rol. Es el espejo de app/alcance.py y de las dependencias
// `exige_rol` del backend: el menú no muestra nada que la API vaya a negar.
export const PERMISOS = {
  ADMINISTRADOR: ['general', 'riesgo', 'casos', 'citas', 'derivaciones', 'desempeno',
                  'indicadores', 'modelo', 'bitacora'],
  COORDINADOR: ['general', 'riesgo', 'casos', 'citas', 'derivaciones', 'indicadores', 'bitacora'],
  CONSEJERO: ['riesgo', 'casos', 'citas'],
  BIENESTAR: ['derivaciones', 'casos', 'indicadores'],
  DOCENTE: ['desempeno'],
  ESTUDIANTE: ['mi-estado'],
}

/** Lo que cada rol alcanza a ver, en una frase, para mostrarlo en la interfaz. */
export const ALCANCE = {
  ADMINISTRADOR: 'Toda la institución',
  COORDINADOR: 'Tu programa',
  CONSEJERO: 'Los casos que tienes asignados',
  BIENESTAR: 'Las derivaciones que te llegan',
  DOCENTE: 'Las asignaturas que dictas',
  ESTUDIANTE: 'Tu propia información',
}

export function puede(usuario, seccion) {
  if (!usuario) return false
  return (PERMISOS[usuario.rol] || []).includes(seccion)
}

export function inicioDe(usuario) {
  if (!usuario) return '/login'
  if (usuario.rol === 'ESTUDIANTE') return '/mi-estado'
  if (usuario.rol === 'DOCENTE') return '/desempeno'
  if (usuario.rol === 'CONSEJERO') return '/casos'
  if (usuario.rol === 'BIENESTAR') return '/derivaciones'
  return '/'
}
