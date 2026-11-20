import { useEffect, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import { ALCANCE, puede, useAuth, useConfig } from '../auth.jsx'

const SECCIONES = [
  ['Vista general', '/', 'general'],
  ['Estudiantes en riesgo', '/riesgo', 'riesgo'],
  ['Casos de acompañamiento', '/casos', 'casos'],
  ['Citas', '/citas', 'citas'],
  ['Derivaciones', '/derivaciones', 'derivaciones'],
  ['Captura de desempeño', '/desempeno', 'desempeno'],
  ['Indicadores', '/indicadores', 'indicadores'],
  ['Mi estado', '/mi-estado', 'mi-estado'],
]
// Algunos rótulos cambian según el rol, para que digan la verdad de lo que hay detrás.
const ROTULOS = {
  CONSEJERO: { '/riesgo': 'Mis estudiantes', '/casos': 'Mis casos', '/citas': 'Mis citas' },
  BIENESTAR: { '/casos': 'Casos derivados' },
}
const ADMIN = [
  ['Modelo de riesgo', '/modelo', 'modelo'],
  ['Bitácora de accesos', '/bitacora', 'bitacora'],
]

export default function Layout({ children }) {
  const config = useConfig()
  const { usuario, salir } = useAuth()
  const navegar = useNavigate()
  const [pendientes, setPendientes] = useState(0)

  useEffect(() => {
    api.pendientes().then((r) => setPendientes(r.pendientes)).catch(() => {})
  }, [])

  const principales = SECCIONES.filter(([, , s]) => puede(usuario, s))
  const administrativas = ADMIN.filter(([, , s]) => puede(usuario, s))

  return (
    <div className="app">
      <nav className="sidebar">
        <div className="brand">
          <div className="brand-mark">S</div>
          <div>
            <div className="brand-name">SARA</div>
            <div className="brand-sub">ALERTA TEMPRANA</div>
          </div>
        </div>
        <div className="workspace">
          <b>Universidad del Norte</b>
          <span>Periodo {config.periodo}</span>
        </div>

        <div className="nav-group">PRINCIPAL</div>
        {principales.map(([texto, ruta]) => (
          <NavLink key={ruta} to={ruta} end={ruta === '/'}
            className={({ isActive }) => 'nav-item' + (isActive ? ' on' : '')}>
            {ROTULOS[usuario?.rol]?.[ruta] || texto}
          </NavLink>
        ))}

        {administrativas.length > 0 && <div className="nav-group">ADMINISTRACIÓN</div>}
        {administrativas.map(([texto, ruta]) => (
          <NavLink key={ruta} to={ruta}
            className={({ isActive }) => 'nav-item' + (isActive ? ' on' : '')}>
            {texto}
          </NavLink>
        ))}

        <div className="user-card">
          <div className="avatar">{iniciales(usuario?.nombre)}</div>
          <div>
            <b>{usuario?.nombre}</b>
            <span>{etiquetaRol(usuario?.rol)}</span>
          </div>
        </div>
        <button className="logout" onClick={() => { salir(); navegar('/login') }}>Cerrar sesión</button>
      </nav>

      <div className="main">
        <header className="topbar">
          <span className="periodo">Periodo {config.periodo} · Corte {config.corte_vigente}</span>
          <span className="alcance">Ves: {ALCANCE[usuario?.rol] || '—'}</span>
          <NavLink to="/notificaciones" className="bell">
            Notificaciones
            {pendientes > 0 && <span className="dot">{pendientes}</span>}
          </NavLink>
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  )
}

function iniciales(nombre = '') {
  return nombre.split(' ').filter(Boolean).slice(0, 2).map((p) => p[0]).join('').toUpperCase() || '—'
}

export function etiquetaRol(rol) {
  return {
    ADMINISTRADOR: 'Administrador', COORDINADOR: 'Coordinador de programa',
    CONSEJERO: 'Consejero académico', BIENESTAR: 'Bienestar universitario',
    DOCENTE: 'Docente', ESTUDIANTE: 'Estudiante',
  }[rol] || rol
}
