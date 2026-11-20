"""Esquemas Pydantic: lo que entra y sale por la API."""
from __future__ import annotations

from datetime import date, datetime

from .config import CORTES_POR_SEMESTRE
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import (
    AccionAuditoria, EstadoCaso, EstadoDerivacion, EstadoMatricula, NivelRiesgo,
    ResultadoCaso, RolNombre, TipoApoyo, TipoIntervencion,
)

ORM = ConfigDict(from_attributes=True)


# ----------------------------- Autenticación -----------------------------
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expira_en_minutos: int
    usuario: "UsuarioOut"


class UsuarioOut(BaseModel):
    model_config = ORM
    id: int
    documento: str
    nombre: str
    correo: EmailStr
    rol: RolNombre
    programa_id: int | None = None
    activo: bool


class UsuarioCrear(BaseModel):
    documento: str = Field(min_length=5, max_length=20)
    nombre: str = Field(min_length=3, max_length=100)
    correo: EmailStr
    password: str = Field(min_length=8, max_length=72)
    rol: RolNombre
    programa_id: int | None = None


# ----------------------------- Académico -----------------------------
class ProgramaOut(BaseModel):
    model_config = ORM
    id: int
    codigo: str
    nombre: str
    coordinador_id: int | None = None
    semestres_totales: int


class ProgramaCrear(BaseModel):
    codigo: str = Field(max_length=15)
    nombre: str = Field(max_length=100)
    coordinador_id: int | None = None
    semestres_totales: int = Field(default=10, gt=0)


class AsignaturaOut(BaseModel):
    model_config = ORM
    id: int
    codigo: str
    nombre: str
    programa_id: int
    creditos: int


class AsignaturaCrear(BaseModel):
    codigo: str = Field(max_length=15)
    nombre: str = Field(max_length=100)
    programa_id: int
    creditos: int = Field(gt=0)


class EstudianteCrear(BaseModel):
    """RQF-01: crea el usuario y el estudiante en una sola operación."""
    documento: str = Field(min_length=5, max_length=20)
    nombre: str = Field(min_length=3, max_length=100)
    correo: EmailStr
    password: str = Field(min_length=8, max_length=72)
    programa_id: int
    semestre: int = Field(gt=0)
    promedio_acumulado: float = Field(default=0, ge=0, le=5)
    estado_matricula: EstadoMatricula = EstadoMatricula.ACTIVA
    tiene_apoyo_financiero: bool = False
    tiene_deuda_vigente: bool = False


class EstudianteActualizar(BaseModel):
    semestre: int | None = Field(default=None, gt=0)
    promedio_acumulado: float | None = Field(default=None, ge=0, le=5)
    estado_matricula: EstadoMatricula | None = None
    tiene_apoyo_financiero: bool | None = None
    tiene_deuda_vigente: bool | None = None


class EstudianteOut(BaseModel):
    model_config = ORM
    id: int
    usuario_id: int
    nombre: str
    documento: str
    programa_id: int
    programa: str
    semestre: int
    promedio_acumulado: float
    estado_matricula: EstadoMatricula
    tiene_apoyo_financiero: bool
    tiene_deuda_vigente: bool


class EstudianteRiesgoOut(EstudianteOut):
    indice: float | None = None
    nivel: NivelRiesgo | None = None
    factor_principal: str | None = None
    caso_id: int | None = None
    caso_estado: EstadoCaso | None = None


class MatriculaCrear(BaseModel):
    estudiante_id: int
    asignatura_id: int
    docente_id: int
    periodo: str = Field(max_length=10)
    numero_intento: int = Field(default=1, gt=0)
    sesiones_programadas: int = Field(default=0, ge=0)


class MatriculaOut(BaseModel):
    model_config = ORM
    id: int
    estudiante_id: int
    asignatura_id: int
    docente_id: int
    periodo: str
    numero_intento: int
    sesiones_programadas: int


# ----------------------------- Desempeño -----------------------------
class NotaCrear(BaseModel):
    matricula_id: int
    corte: int = Field(ge=1, le=CORTES_POR_SEMESTRE)
    valor: float = Field(ge=0, le=5)


class NotaOut(BaseModel):
    model_config = ORM
    id: int
    matricula_id: int
    corte: int
    valor: float
    fecha: datetime


class InasistenciaCrear(BaseModel):
    matricula_id: int
    fecha_sesion: date
    justificada: bool = False


class InasistenciaOut(BaseModel):
    model_config = ORM
    id: int
    matricula_id: int
    fecha_sesion: date
    justificada: bool


class ResultadoRegistro(BaseModel):
    """Lo que devuelve registrar una nota o una inasistencia."""
    mensaje: str
    indice: float
    nivel: NivelRiesgo
    alerta_generada: bool
    caso_id: int | None = None
    caso_nuevo: bool = False


class FilaCurso(BaseModel):
    """Una fila de la pantalla de captura de desempeño del docente."""
    matricula_id: int
    estudiante_id: int
    estudiante: str
    documento: str
    semestre: int
    nota: float | None = None
    inasistencias: int
    sesiones: int
    nivel: NivelRiesgo | None = None
    indice: float | None = None


# ----------------------------- Riesgo -----------------------------
class FactorOut(BaseModel):
    model_config = ORM
    id: int
    codigo: str
    nombre: str
    peso: float
    version_modelo: int
    vigente: bool


class PesoFactor(BaseModel):
    codigo: str
    nombre: str | None = None
    peso: float = Field(gt=0, le=100)


class ConfigurarModelo(BaseModel):
    """RQF-02: la suma de los pesos debe ser exactamente 100."""
    factores: list[PesoFactor] = Field(min_length=1)


class DetalleFactor(BaseModel):
    codigo: str
    nombre: str
    valor: float
    peso: float
    aporte: float
    evidencia: str


class EvaluacionOut(BaseModel):
    model_config = ORM
    id: int
    estudiante_id: int
    indice: float
    nivel: NivelRiesgo
    detalle_factores: list[DetalleFactor]
    version_modelo: int
    corte: int | None = None
    fecha: datetime


class ResumenReevaluacion(BaseModel):
    evaluados: int
    alertas: int
    casos_nuevos: int
    por_nivel: dict[str, int]


# ----------------------------- Casos -----------------------------
class CasoOut(BaseModel):
    model_config = ORM
    id: int
    estudiante_id: int
    estudiante: str
    programa: str
    programa_id: int
    consejero_id: int | None = None
    consejero: str | None = None
    estado: EstadoCaso
    nivel_apertura: NivelRiesgo
    escalado: bool
    resultado: ResultadoCaso | None = None
    indice_actual: float | None = None
    indice_cierre: float | None = None
    fecha_apertura: datetime
    fecha_cierre: datetime | None = None
    intervenciones: int = 0
    derivaciones_abiertas: int = 0


class HistorialOut(BaseModel):
    model_config = ORM
    id: int
    estado_anterior: EstadoCaso | None = None
    estado_nuevo: EstadoCaso
    motivo: str | None = None
    usuario: str | None = None
    fecha: datetime


class CasoDetalleOut(CasoOut):
    historial: list[HistorialOut] = []
    evaluacion: EvaluacionOut | None = None
    acciones: list["AccionCasoOut"] = []


class CambiarEstado(BaseModel):
    estado: EstadoCaso
    motivo: str | None = Field(default=None, max_length=40)


class AbrirCaso(BaseModel):
    """Apertura manual por parte del coordinador (RQF-08)."""
    estudiante_id: int
    motivo: str = Field(min_length=10, max_length=300)
    consejero_id: int | None = None


class ReabrirCaso(BaseModel):
    motivo: str = Field(min_length=10, max_length=300)


class AccionCasoOut(BaseModel):
    model_config = ORM
    id: int
    usuario: str
    accion: AccionAuditoria
    detalle: str | None = None
    fecha: datetime


class CerrarCaso(BaseModel):
    resultado: ResultadoCaso


class Reasignar(BaseModel):
    consejero_id: int


# ----------------------------- Intervenciones -----------------------------
class IntervencionCrear(BaseModel):
    tipo: TipoIntervencion
    descripcion: str = Field(min_length=10, max_length=2000)
    compromisos: str | None = Field(default=None, max_length=2000)
    fecha_cita: datetime | None = None


class RegistrarAsistencia(BaseModel):
    asistio: bool


class IntervencionOut(BaseModel):
    model_config = ORM
    id: int
    caso_id: int
    consejero: str
    tipo: TipoIntervencion
    descripcion: str
    compromisos: str | None = None
    fecha_cita: datetime | None = None
    asistio: bool | None = None
    fecha: datetime


# ----------------------------- Derivaciones -----------------------------
class DerivacionCrear(BaseModel):
    tipo_apoyo: TipoApoyo
    observacion: str | None = Field(default=None, max_length=2000)


class AtenderDerivacion(BaseModel):
    estado: EstadoDerivacion
    observacion: str | None = Field(default=None, max_length=2000)


class DerivacionOut(BaseModel):
    model_config = ORM
    id: int
    caso_id: int
    estudiante: str
    tipo_apoyo: TipoApoyo
    estado: EstadoDerivacion
    solicitante: str
    observacion: str | None = None
    fecha: datetime


# ----------------------------- Notificaciones -----------------------------
class NotificacionOut(BaseModel):
    model_config = ORM
    id: int
    tipo: str
    mensaje: str
    caso_id: int | None = None
    leida: bool
    atendida: bool
    fecha: datetime


# ----------------------------- Portal del estudiante -----------------------------
class CompromisoOut(BaseModel):
    intervencion_id: int
    texto: str
    fecha: datetime


class CitaOut(BaseModel):
    intervencion_id: int
    fecha_cita: datetime
    consejero: str
    asistio: bool | None = None


class MiEstadoOut(BaseModel):
    """RQF-15 + RQNF-03: el estudiante NO ve las notas de intervención."""
    estudiante: str
    programa: str
    semestre: int
    nivel: NivelRiesgo | None = None
    caso_id: int | None = None
    caso_estado: EstadoCaso | None = None
    consejero: str | None = None
    proxima_cita: CitaOut | None = None
    compromisos: list[CompromisoOut] = []
    boletin: "BoletinOut | None" = None


# ----------------------------- Boletín por corte -----------------------------
class NotaDeCorte(BaseModel):
    corte: int
    valor: float | None = None
    fecha: datetime | None = None


class FilaBoletin(BaseModel):
    """Una asignatura con la nota de cada corte del semestre."""
    matricula_id: int
    asignatura: str
    codigo: str
    creditos: int
    docente: str | None = None
    repetida: bool = False
    notas: list[NotaDeCorte]
    promedio: float | None = None
    inasistencias: int = 0
    sesiones: int = 0


class BoletinOut(BaseModel):
    estudiante: str
    programa: str
    semestre: int
    periodo: str
    cortes: list[int]
    corte_vigente: int
    asignaturas: list[FilaBoletin]
    promedio_periodo: float | None = None


# ----------------------------- Reportes -----------------------------
class ConteoNivel(BaseModel):
    nivel: NivelRiesgo
    cantidad: int


class ConteoResultado(BaseModel):
    resultado: ResultadoCaso
    cantidad: int


class RetencionPrograma(BaseModel):
    programa: str
    activos: int
    desertores: int
    tasa_retencion: float


class ReporteGeneral(BaseModel):
    estudiantes_evaluados: int
    en_riesgo: int
    casos_activos: int
    casos_escalados: int
    distribucion: list[ConteoNivel]
    resultados: list[ConteoResultado]
    retencion_por_programa: list[RetencionPrograma]
    tasa_retencion_global: float


class EfectividadNivel(BaseModel):
    nivel_apertura: NivelRiesgo
    cerrados: int
    superados: int
    efectividad: float


class BitacoraOut(BaseModel):
    model_config = ORM
    id: int
    usuario: str
    recurso: str
    recurso_id: int
    accion: AccionAuditoria
    detalle: str | None = None
    fecha: datetime


Token.model_rebuild()
MiEstadoOut.model_rebuild()
CasoDetalleOut.model_rebuild()
