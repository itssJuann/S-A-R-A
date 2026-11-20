import { Navigate, Route, Routes } from 'react-router-dom'
import { ProveedorAuth, useAuth, inicioDe, puede } from './auth.jsx'
import Layout from './components/Layout.jsx'
import { Cargando } from './components/ui.jsx'

import Login from './pages/Login.jsx'
import VistaGeneral from './pages/VistaGeneral.jsx'
import EstudiantesRiesgo from './pages/EstudiantesRiesgo.jsx'
import DetalleEstudiante from './pages/DetalleEstudiante.jsx'
import Casos from './pages/Casos.jsx'
import Caso from './pages/Caso.jsx'
import CapturaDesempeno from './pages/CapturaDesempeno.jsx'
import Indicadores from './pages/Indicadores.jsx'
import MiEstado from './pages/MiEstado.jsx'
import Citas from './pages/Citas.jsx'
import Derivaciones from './pages/Derivaciones.jsx'
import Notificaciones from './pages/Notificaciones.jsx'
import ModeloRiesgo from './pages/ModeloRiesgo.jsx'
import Bitacora from './pages/Bitacora.jsx'

/** Ruta protegida: exige sesión y, si se indica, un permiso concreto. */
function Privada({ permiso, children }) {
  const { usuario, cargando } = useAuth()
  if (cargando) return <Cargando />
  if (!usuario) return <Navigate to="/login" replace />
  if (permiso && !puede(usuario, permiso)) return <Navigate to={inicioDe(usuario)} replace />
  return <Layout>{children}</Layout>
}

const RUTAS = [
  ['/', 'general', <VistaGeneral />],
  ['/riesgo', 'riesgo', <EstudiantesRiesgo />],
  ['/estudiantes/:id', 'riesgo', <DetalleEstudiante />],
  ['/casos', 'casos', <Casos />],
  ['/casos/:id', 'casos', <Caso />],
  ['/desempeno', 'desempeno', <CapturaDesempeno />],
  ['/indicadores', 'indicadores', <Indicadores />],
  ['/citas', 'citas', <Citas />],
  ['/derivaciones', 'derivaciones', <Derivaciones />],
  ['/modelo', 'modelo', <ModeloRiesgo />],
  ['/bitacora', 'bitacora', <Bitacora />],
  ['/mi-estado', 'mi-estado', <MiEstado />],
  ['/notificaciones', null, <Notificaciones />],
]

function Raiz() {
  const { usuario, cargando } = useAuth()
  if (cargando) return <Cargando />
  if (!usuario) return <Navigate to="/login" replace />
  const inicio = inicioDe(usuario)
  if (inicio !== '/') return <Navigate to={inicio} replace />
  return <Privada permiso="general"><VistaGeneral /></Privada>
}

export default function App() {
  return (
    <ProveedorAuth>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<Raiz />} />
        {RUTAS.filter(([ruta]) => ruta !== '/').map(([ruta, permiso, elemento]) => (
          <Route key={ruta} path={ruta} element={<Privada permiso={permiso}>{elemento}</Privada>} />
        ))}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ProveedorAuth>
  )
}
