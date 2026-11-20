# SARA — Sistema de Alerta Temprana y Retención Académica

Implementación de la Entrega 1 del proyecto de **Diseño de Software I** — Universidad del Norte.
Prof. Daniel Romero Martínez.

**Equipo:** Juan David de la Rosa · Samuel de la Valle · Camilo Acevedo

SARA detecta de forma temprana a los estudiantes en riesgo de deserción, abre un caso de
acompañamiento, lo asigna a un consejero, registra las intervenciones y mide la efectividad
de la retención. Cubre los **16 requerimientos funcionales (RQF-01 a RQF-16)**, los
**6 no funcionales (RQNF-01 a RQNF-06)** y las **10 reglas de negocio (RN-01 a RN-10)**
del documento de la entrega.

---

## 1. Arquitectura

```
                 React 18 + Vite            FastAPI + SQLAlchemy 2.0
   Navegador ───────────────────► /api ───────────────────► SQLite / PostgreSQL
                  (SPA, JWT)                   │
                                               ├── services/riesgo.py       motor de riesgo
                                               ├── services/casos.py        máquina de estados
                                               └── services/escalamiento.py APScheduler
```

Arquitectura en tres capas dentro del backend:

| Capa | Carpeta | Responsabilidad |
|---|---|---|
| Presentación | `app/routers/` | HTTP, validación de entrada, permisos por rol |
| Dominio | `app/services/`, `app/factores.py` | reglas de negocio; no sabe de HTTP |
| Persistencia | `app/models.py`, `app/db.py` | 16 tablas SQLAlchemy |

Los esquemas de entrada/salida (`app/schemas.py`) son Pydantic v2: el router nunca
devuelve un modelo de base de datos directamente.

---

## 2. Cómo ejecutarlo

Requisitos: **Python 3.11+** y **Node 18+**.

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app.seed                 # crea sara.db con datos de demostración
uvicorn app.main:app --reload      # http://127.0.0.1:8000
```

Documentación interactiva de la API: **http://127.0.0.1:8000/docs**

### Frontend

En otra terminal:

```bash
cd frontend
npm install
npm run dev                        # http://127.0.0.1:5173
```

Vite redirige `/api` al backend, así que no hay que configurar CORS ni URLs.

### Pruebas

```bash
cd backend && pytest               # 48 pruebas
```

---

## 3. Usuarios de demostración y alcance de cada rol

La clave de **todos** los usuarios es `sara2026`. El `seed` imprime esta misma lista al
terminar, así que siempre se puede consultar sin abrir el código.

| Rol | Correo | Qué ve exactamente |
|---|---|---|
| Administrador | `admin@uninorte.edu.co` | Toda la institución y la configuración del modelo de riesgo |
| Coordinador | `coord.isc@uninorte.edu.co` | Solo su programa: riesgo, casos, indicadores y bitácora |
| Consejero | `juan.isc@uninorte.edu.co` | Solo los estudiantes de los casos que tiene asignados |
| Bienestar | `bienestar@uninorte.edu.co` | Solo las derivaciones que le llegan; indicadores institucionales |
| Docente | `carlos.isc@uninorte.edu.co` | Solo las asignaturas que dicta |
| Estudiante | `daniela.0@uninorte.edu.co` | Solo su ficha, sus notas y sus compromisos |

Hay un coordinador y dos consejeros y dos docentes **por cada uno de los cuatro programas**:
cambia el sufijo del correo por `iin` (Ingeniería Industrial), `psi` (Psicología) o `der`
(Derecho). Los 30 estudiantes siguen el patrón `nombre.N@uninorte.edu.co`.

### Cómo se hace cumplir el alcance

El alcance **no** es esconder botones: vive en `app/alcance.py`, un solo módulo que decide
qué programas, estudiantes y casos alcanza cada rol, y que se aplica en todos los routers.
La interfaz es su espejo, de modo que el menú nunca ofrece algo que la API vaya a negar.

| Rol | `/riesgo/estudiantes` | `/casos` | `/reportes` | `/admin/bitacora` |
|---|---|---|---|---|
| Administrador | 30 | 9 | institucional | completa |
| Coordinador (ISC) | 8 | 3 | su programa | la de sus casos |
| Consejero | 2 (los suyos) | 2 | 403 | 403 |
| Bienestar | 403 | 1 (con derivación) | institucional | 403 |
| Docente | 403 | 403 | 403 | 403 |
| Estudiante | 403 | 403 | 403 | 403 |

Un consejero que pida por URL el caso de otro recibe **403**, no una pantalla vacía. Las
pruebas lo verifican.

## 4. Cortes del semestre

El periodo académico se divide en **4 cortes** de calificación. El número de cortes, el
periodo vigente y el corte en curso están en `app/config.py` y se pueden cambiar sin tocar
código, con variables de entorno:

```bash
export SARA_CORTES=4          # cortes por semestre
export SARA_PERIODO=2026-2    # periodo vigente
export SARA_CORTE_VIGENTE=4   # corte en curso (por defecto, el último)
```

La interfaz no los tiene escritos a mano: los lee de `GET /api/configuracion`, así que al
cambiar la variable se actualizan las pestañas del docente, el encabezado y el boletín.

Cada asignatura guarda una nota por corte (`UNIQUE(matricula_id, corte)`), y
`GET /api/desempeno/boletin/{estudiante_id}` devuelve la rejilla completa de asignaturas
por cortes con el promedio de cada una. El estudiante ve la suya en su portal; un
estudiante no puede consultar el boletín de otro.

## 5. El motor de riesgo

El índice va de **0 a 100** y es una suma ponderada de cinco factores
(`app/factores.py`), cada uno normalizado a 0–100 con su propia evidencia textual:

| Código | Factor | Peso v1 | Cómo se calcula |
|---|---|---|---|
| `RENDIMIENTO` | Rendimiento del corte | 35 % | notas del corte entre 1,5 (piso) y 3,5 (techo) |
| `INASISTENCIA` | Inasistencia | 25 % | % de faltas; 30 % de inasistencia ya es crítico |
| `REPETIDAS` | Asignaturas repetidas | 20 % | 3 repeticiones saturan el factor |
| `FINANCIERA` | Situación financiera | 10 % | deuda pendiente y ausencia de apoyo |
| `HISTORICO` | Rendimiento histórico | 10 % | promedio acumulado |

**Clasificación (RN-02):** Bajo < 40 · Medio 40–64 · Alto 65–84 · Crítico ≥ 85.
Los umbrales están en `app/config.py`.

**La suma de los pesos debe ser exactamente 100 % (RN-01).** Esta regla abarca varias
filas de la tabla `factor_riesgo`, así que **no se puede expresar como un `CHECK` de SQL**:
se valida en `services/riesgo.py::factores_vigentes` y en el endpoint
`PUT /api/admin/factores`, que rechaza cualquier configuración que no sume 100.

**Versionado del modelo (RQNF-05):** al cambiar los pesos, las filas vigentes se marcan
`vigente = False` y se insertan nuevas con `version_modelo + 1`. Cada `evaluacion_riesgo`
guarda la versión con la que se calculó, de modo que un índice histórico siempre se puede
reproducir con los pesos de su época. La pantalla *Modelo de riesgo* muestra esto en vivo.

---

## 6. Ciclo de vida de un caso

```
ABIERTO ──► ASIGNADO ──► EN_SEGUIMIENTO ──► EN_EVALUACION ──► CERRADO
                                ▲                  │
                                └──── devolución ──┘
```

Transiciones permitidas en `services/casos.py::TRANSICIONES`; cualquier otra lanza un error
de dominio. Cada cambio deja una fila en `historial_estado_caso` con usuario, motivo y fecha
(RQF-12).

- **Apertura automática (RN-03):** al registrar una nota o una inasistencia se recalcula el
  índice; si queda en Alto o Crítico y el estudiante no tiene caso activo, el caso se abre solo.
- **Asignación por carga (RN-04):** se asigna al consejero del programa con menos casos
  activos, con tope de 20 (`MAX_CASOS_ACTIVOS_POR_CONSEJERO`).
- **Escalamiento (RN-06):** un caso Crítico sin primera intervención en **3 días hábiles**
  (descontando fines de semana y los festivos colombianos de 2026) se escala al coordinador.
  Lo ejecuta APScheduler y también se puede disparar a mano desde el tablero.
- **Cierre (RN-08):** solo desde `EN_EVALUACION` y solo si no quedan derivaciones abiertas.

---

## 7. Trazabilidad requerimiento → código

| Req. | Qué exige | Dónde está |
|---|---|---|
| RQF-01 | Autenticación por rol | `routers/auth.py`, `security.py::exige_rol` |
| RQF-02 | Configurar pesos del modelo | `PUT /api/admin/factores`, página *Modelo de riesgo* |
| RQF-03 | Registrar notas por corte | `POST /api/desempeno/notas`, `GET /api/desempeno/boletin/{id}` |
| RQF-04 | Registrar inasistencias | `POST /api/desempeno/inasistencias` |
| RQF-05 | Calcular el índice de riesgo | `services/riesgo.py::calcular_indice` |
| RQF-06 | Listar y filtrar estudiantes en riesgo | `GET /api/riesgo/estudiantes` |
| RQF-07 | Ver el detalle de un índice | `GET /api/riesgo/estudiantes/{id}/simular` |
| RQF-08 | Abrir caso de acompañamiento | `services/casos.py::abrir_o_adjuntar` |
| RQF-09 | Asignar consejero | `services/casos.py::asignar_automaticamente`, `/reasignar` |
| RQF-10 | Registrar intervenciones y citas | `routers/intervenciones.py` |
| RQF-11 | Derivar a bienestar | `routers/derivaciones.py` |
| RQF-12 | Historial de estados | `models.HistorialEstadoCaso`, `POST /casos/{id}/estado` |
| RQF-13 | Notificaciones al responsable | `routers/notificaciones.py`, `services/escalamiento.py` |
| RQF-14 | Cerrar el caso con resultado | `POST /api/casos/{id}/cerrar` |
| RQF-15 | Indicadores de retención y efectividad | `routers/reportes.py` |
| RQF-16 | Portal del estudiante | `GET /api/portal/mi-estado` |
| RQNF-01 | Respuesta rápida | consultas con `select()` e índices; sin N+1 en los listados |
| RQNF-02 | Contraseñas protegidas | bcrypt (12 rondas) en `security.py` |
| RQNF-03 | Auditoría de datos sensibles | tabla `bitacora_acceso`, página *Bitácora* |
| RQNF-04 | Sesión expira a los 30 min | `MINUTOS_EXPIRACION_SESION`, JWT |
| RQNF-05 | Índices reproducibles | `version_modelo` en cada evaluación |
| RQNF-06 | Portabilidad de la BD | SQLAlchemy; cambiar `SARA_DB_URL` basta |

---

## 8. Publicar la aplicación en internet

El proyecto trae un `Dockerfile` que compila el frontend y lo sirve desde el mismo
backend, así que la aplicación entera es **un solo contenedor**. Funciona igual en
Render, Railway, Fly.io o cualquier servidor con Docker.

### Opción recomendada: Render

El archivo `render.yaml` describe el servicio y la base de datos, de modo que Render
los crea y los conecta solo:

1. Sube el repositorio a GitHub.
2. En Render: **New → Blueprint**, elige el repositorio y confirma.
3. Render construye la imagen, crea el PostgreSQL gratuito y publica la URL.

El primer arranque carga los datos de demostración (`SARA_SEMBRAR=1`) y la clave de
firma de los JWT la genera Render. El plan gratuito duerme el servicio tras unos
minutos sin tráfico: la primera visita después tarda unos segundos en responder.

### Probarlo localmente igual que en producción

```bash
docker build -t sara .
docker run -p 8000:8000 -e SARA_SEMBRAR=1 sara
```

### Variables de entorno

| Variable | Para qué sirve | Valor por defecto |
|---|---|---|
| `SARA_DATABASE_URL` | Conexión a la base. Acepta la URL tal como la entregan Render, Railway o Heroku | `sqlite:///./sara.db` |
| `SARA_SECRET_KEY` | Clave de firma de los JWT. **Obligatorio cambiarla en producción** | valor de desarrollo |
| `SARA_SEMBRAR` | `1` carga los datos de demostración en el primer arranque | `0` |
| `SARA_PERIODO` · `SARA_CORTES` · `SARA_CORTE_VIGENTE` | Periodo y cortes del semestre | `2026-2` · `4` · `4` |
| `SARA_CORS` | Orígenes permitidos, si el frontend se sirve aparte | `localhost:5173` |

Como el backend sirve el frontend compilado, en producción **no hace falta configurar
CORS**: ambos salen del mismo origen.

## 9. Cambiar a PostgreSQL

No hay que tocar código. Se instala el driver y se define la variable de entorno:

```bash
pip install "psycopg[binary]"
export SARA_DB_URL="postgresql+psycopg://usuario:clave@localhost:5432/sara"
python -m app.seed
uvicorn app.main:app
```

Otras variables: `SARA_SECRETO` (clave de firma del JWT),
`SARA_BCRYPT_ROUNDS` (las pruebas usan 4 para ir rápido).

---

## 10. Estructura

```
sara-app/
├── backend/
│   ├── app/
│   │   ├── main.py            arranque, routers, planificador
│   │   ├── config.py          umbrales y parámetros del negocio
│   │   ├── models.py          16 tablas
│   │   ├── schemas.py         entrada/salida Pydantic
│   │   ├── security.py        JWT, bcrypt, permisos por rol
│   │   ├── factores.py        los 5 cálculos de factores
│   │   ├── seed.py            datos de demostración
│   │   ├── services/          riesgo · casos · escalamiento
│   │   └── routers/           11 routers
│   ├── tests/                 48 pruebas
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── api.js             cliente HTTP
    │   ├── auth.jsx           sesión y permisos por rol
    │   ├── App.jsx            rutas protegidas
    │   ├── components/        Layout y componentes de UI
    │   └── pages/             14 pantallas
    └── package.json
```
