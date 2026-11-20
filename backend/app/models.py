"""Modelo de datos de SARA — 16 tablas.

Corresponde uno a uno con el diagrama entidad-relación de la Entrega 1
(03_Artefactos/3_Base_de_datos/bd_sara.png).
"""
from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, Enum, ForeignKey, Integer,
    JSON, Numeric, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .config import CORTES_POR_SEMESTRE
from .database import Base


# --------------------------------------------------------------------------
# Enumeraciones (reflejan los CHECK del script SQL)
# --------------------------------------------------------------------------
class RolNombre(str, enum.Enum):
    ESTUDIANTE = "ESTUDIANTE"
    DOCENTE = "DOCENTE"
    CONSEJERO = "CONSEJERO"
    COORDINADOR = "COORDINADOR"
    BIENESTAR = "BIENESTAR"
    ADMINISTRADOR = "ADMINISTRADOR"


class EstadoMatricula(str, enum.Enum):
    ACTIVA = "ACTIVA"
    APLAZADA = "APLAZADA"
    RETIRADA = "RETIRADA"


class NivelRiesgo(str, enum.Enum):
    """RN-02. El orden importa: se usa para comparar gravedad."""
    BAJO = "BAJO"
    MEDIO = "MEDIO"
    ALTO = "ALTO"
    CRITICO = "CRITICO"


class EstadoCaso(str, enum.Enum):
    """RN-05. El orden de la lista es el flujo permitido."""
    ABIERTO = "ABIERTO"
    ASIGNADO = "ASIGNADO"
    EN_SEGUIMIENTO = "EN_SEGUIMIENTO"
    EN_EVALUACION = "EN_EVALUACION"
    CERRADO = "CERRADO"


class ResultadoCaso(str, enum.Enum):
    """RN-08."""
    SUPERADO = "SUPERADO"
    PERSISTE = "PERSISTE"
    DESERCION_CONFIRMADA = "DESERCION_CONFIRMADA"


class TipoIntervencion(str, enum.Enum):
    TUTORIA = "TUTORIA"
    ENTREVISTA = "ENTREVISTA"
    LLAMADA = "LLAMADA"
    TALLER = "TALLER"


class TipoApoyo(str, enum.Enum):
    PSICOLOGICO = "PSICOLOGICO"
    FINANCIERO = "FINANCIERO"
    ACADEMICO = "ACADEMICO"
    SALUD = "SALUD"


class EstadoDerivacion(str, enum.Enum):
    ABIERTA = "ABIERTA"
    ATENDIDA = "ATENDIDA"
    RECHAZADA = "RECHAZADA"


class AccionAuditoria(str, enum.Enum):
    """Qué hizo el usuario sobre el recurso (RQNF-03)."""
    LECTURA = "LECTURA"
    ESCRITURA = "ESCRITURA"
    APERTURA = "APERTURA"
    CAMBIO_ESTADO = "CAMBIO_ESTADO"
    CIERRE = "CIERRE"
    REAPERTURA = "REAPERTURA"
    REASIGNACION = "REASIGNACION"
    ESCALAMIENTO = "ESCALAMIENTO"
    DERIVACION = "DERIVACION"


# --------------------------------------------------------------------------
# Tablas
# --------------------------------------------------------------------------
class Rol(Base):
    __tablename__ = "rol"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[RolNombre] = mapped_column(Enum(RolNombre), unique=True, nullable=False)

    usuarios: Mapped[list["Usuario"]] = relationship(back_populates="rol")


class Usuario(Base):
    __tablename__ = "usuario"
    id: Mapped[int] = mapped_column(primary_key=True)
    documento: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    correo: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    rol_id: Mapped[int] = mapped_column(ForeignKey("rol.id"), nullable=False)
    programa_id: Mapped[int | None] = mapped_column(ForeignKey("programa.id"))
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    rol: Mapped[Rol] = relationship(back_populates="usuarios")
    programa: Mapped["Programa | None"] = relationship(foreign_keys=[programa_id])
    estudiante: Mapped["Estudiante | None"] = relationship(back_populates="usuario", uselist=False)

    @property
    def rol_nombre(self) -> RolNombre:
        return self.rol.nombre


class Programa(Base):
    __tablename__ = "programa"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(15), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    coordinador_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", use_alter=True, name="fk_programa_coordinador"))
    semestres_totales: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    __table_args__ = (CheckConstraint("semestres_totales > 0", name="ck_programa_semestres"),)

    coordinador: Mapped["Usuario | None"] = relationship(foreign_keys=[coordinador_id])


class Estudiante(Base):
    __tablename__ = "estudiante"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), unique=True, nullable=False)
    programa_id: Mapped[int] = mapped_column(ForeignKey("programa.id"), nullable=False)
    semestre: Mapped[int] = mapped_column(Integer, nullable=False)
    promedio_acumulado: Mapped[float] = mapped_column(Numeric(3, 2), default=0, nullable=False)
    estado_matricula: Mapped[EstadoMatricula] = mapped_column(
        Enum(EstadoMatricula), default=EstadoMatricula.ACTIVA, nullable=False)
    tiene_apoyo_financiero: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tiene_deuda_vigente: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    __table_args__ = (
        CheckConstraint("semestre > 0", name="ck_estudiante_semestre"),
        CheckConstraint("promedio_acumulado >= 0 AND promedio_acumulado <= 5",
                        name="ck_estudiante_promedio"),
    )

    usuario: Mapped[Usuario] = relationship(back_populates="estudiante")
    programa: Mapped[Programa] = relationship()
    matriculas: Mapped[list["Matricula"]] = relationship(back_populates="estudiante")
    evaluaciones: Mapped[list["EvaluacionRiesgo"]] = relationship(back_populates="estudiante")
    casos: Mapped[list["CasoAcompanamiento"]] = relationship(back_populates="estudiante")


class Asignatura(Base):
    __tablename__ = "asignatura"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(15), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    programa_id: Mapped[int] = mapped_column(ForeignKey("programa.id"), nullable=False)
    creditos: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (CheckConstraint("creditos > 0", name="ck_asignatura_creditos"),)

    programa: Mapped[Programa] = relationship()


class Matricula(Base):
    __tablename__ = "matricula"
    id: Mapped[int] = mapped_column(primary_key=True)
    estudiante_id: Mapped[int] = mapped_column(ForeignKey("estudiante.id"), nullable=False)
    asignatura_id: Mapped[int] = mapped_column(ForeignKey("asignatura.id"), nullable=False)
    docente_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), nullable=False)
    periodo: Mapped[str] = mapped_column(String(10), nullable=False)
    numero_intento: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    sesiones_programadas: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    __table_args__ = (
        UniqueConstraint("estudiante_id", "asignatura_id", "periodo", name="uq_matricula"),
        CheckConstraint("numero_intento > 0", name="ck_matricula_intento"),
    )

    estudiante: Mapped[Estudiante] = relationship(back_populates="matriculas")
    asignatura: Mapped[Asignatura] = relationship()
    docente: Mapped[Usuario] = relationship(foreign_keys=[docente_id])
    notas: Mapped[list["Nota"]] = relationship(back_populates="matricula")
    inasistencias: Mapped[list["Inasistencia"]] = relationship(back_populates="matricula")


class Nota(Base):
    __tablename__ = "nota"
    id: Mapped[int] = mapped_column(primary_key=True)
    matricula_id: Mapped[int] = mapped_column(ForeignKey("matricula.id"), nullable=False)
    corte: Mapped[int] = mapped_column(Integer, nullable=False)
    valor: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    registrada_por: Mapped[int] = mapped_column(ForeignKey("usuario.id"), nullable=False)
    fecha: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    __table_args__ = (
        UniqueConstraint("matricula_id", "corte", name="uq_nota_matricula_corte"),
        CheckConstraint(f"corte >= 1 AND corte <= {CORTES_POR_SEMESTRE}", name="ck_nota_corte"),
        CheckConstraint("valor >= 0 AND valor <= 5", name="ck_nota_valor"),
    )

    matricula: Mapped[Matricula] = relationship(back_populates="notas")


class Inasistencia(Base):
    __tablename__ = "inasistencia"
    id: Mapped[int] = mapped_column(primary_key=True)
    matricula_id: Mapped[int] = mapped_column(ForeignKey("matricula.id"), nullable=False)
    fecha_sesion: Mapped[date] = mapped_column(Date, nullable=False)
    justificada: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    registrada_por: Mapped[int] = mapped_column(ForeignKey("usuario.id"), nullable=False)
    __table_args__ = (UniqueConstraint("matricula_id", "fecha_sesion", name="uq_inasistencia"),)

    matricula: Mapped[Matricula] = relationship(back_populates="inasistencias")


class FactorRiesgo(Base):
    """RQF-02. Los pesos de los factores vigentes deben sumar 100."""
    __tablename__ = "factor_riesgo"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), nullable=False)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    peso: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    version_modelo: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    vigente: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    __table_args__ = (
        CheckConstraint("peso > 0 AND peso <= 100", name="ck_factor_peso"),
        UniqueConstraint("codigo", "version_modelo", name="uq_factor_version"),
    )


class EvaluacionRiesgo(Base):
    __tablename__ = "evaluacion_riesgo"
    id: Mapped[int] = mapped_column(primary_key=True)
    estudiante_id: Mapped[int] = mapped_column(ForeignKey("estudiante.id"), nullable=False)
    indice: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    nivel: Mapped[NivelRiesgo] = mapped_column(Enum(NivelRiesgo), nullable=False)
    detalle_factores: Mapped[list] = mapped_column(JSON, nullable=False)
    version_modelo: Mapped[int] = mapped_column(Integer, nullable=False)
    corte: Mapped[int | None] = mapped_column(Integer)
    fecha: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    __table_args__ = (
        CheckConstraint("indice >= 0 AND indice <= 100", name="ck_evaluacion_indice"),
    )

    estudiante: Mapped[Estudiante] = relationship(back_populates="evaluaciones")


class CasoAcompanamiento(Base):
    __tablename__ = "caso_acompanamiento"
    id: Mapped[int] = mapped_column(primary_key=True)
    estudiante_id: Mapped[int] = mapped_column(ForeignKey("estudiante.id"), nullable=False)
    evaluacion_id: Mapped[int] = mapped_column(ForeignKey("evaluacion_riesgo.id"), nullable=False)
    consejero_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    estado: Mapped[EstadoCaso] = mapped_column(Enum(EstadoCaso), default=EstadoCaso.ABIERTO, nullable=False)
    nivel_apertura: Mapped[NivelRiesgo] = mapped_column(Enum(NivelRiesgo), nullable=False)
    escalado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resultado: Mapped[ResultadoCaso | None] = mapped_column(Enum(ResultadoCaso))
    indice_cierre: Mapped[float | None] = mapped_column(Numeric(5, 2))
    fecha_apertura: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    fecha_cierre: Mapped[datetime | None] = mapped_column(DateTime)

    estudiante: Mapped[Estudiante] = relationship(back_populates="casos")
    evaluacion: Mapped[EvaluacionRiesgo] = relationship()
    consejero: Mapped["Usuario | None"] = relationship(foreign_keys=[consejero_id])
    historial: Mapped[list["HistorialEstadoCaso"]] = relationship(
        back_populates="caso", order_by="HistorialEstadoCaso.id")
    intervenciones: Mapped[list["Intervencion"]] = relationship(
        back_populates="caso", order_by="Intervencion.id")
    derivaciones: Mapped[list["Derivacion"]] = relationship(back_populates="caso")


class HistorialEstadoCaso(Base):
    __tablename__ = "historial_estado_caso"
    id: Mapped[int] = mapped_column(primary_key=True)
    caso_id: Mapped[int] = mapped_column(ForeignKey("caso_acompanamiento.id"), nullable=False)
    estado_anterior: Mapped[EstadoCaso | None] = mapped_column(Enum(EstadoCaso))
    estado_nuevo: Mapped[EstadoCaso] = mapped_column(Enum(EstadoCaso), nullable=False)
    motivo: Mapped[str | None] = mapped_column(String(40))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    fecha: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    caso: Mapped[CasoAcompanamiento] = relationship(back_populates="historial")
    usuario: Mapped["Usuario | None"] = relationship()


class Intervencion(Base):
    __tablename__ = "intervencion"
    id: Mapped[int] = mapped_column(primary_key=True)
    caso_id: Mapped[int] = mapped_column(ForeignKey("caso_acompanamiento.id"), nullable=False)
    consejero_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), nullable=False)
    tipo: Mapped[TipoIntervencion] = mapped_column(Enum(TipoIntervencion), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)   # confidencial (RQNF-03)
    compromisos: Mapped[str | None] = mapped_column(Text)
    fecha_cita: Mapped[datetime | None] = mapped_column(DateTime)    # RQF-10
    asistio: Mapped[bool | None] = mapped_column(Boolean)
    fecha: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    caso: Mapped[CasoAcompanamiento] = relationship(back_populates="intervenciones")
    consejero: Mapped[Usuario] = relationship()


class Derivacion(Base):
    __tablename__ = "derivacion"
    id: Mapped[int] = mapped_column(primary_key=True)
    caso_id: Mapped[int] = mapped_column(ForeignKey("caso_acompanamiento.id"), nullable=False)
    tipo_apoyo: Mapped[TipoApoyo] = mapped_column(Enum(TipoApoyo), nullable=False)
    solicitada_por: Mapped[int] = mapped_column(ForeignKey("usuario.id"), nullable=False)
    atendida_por: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    estado: Mapped[EstadoDerivacion] = mapped_column(
        Enum(EstadoDerivacion), default=EstadoDerivacion.ABIERTA, nullable=False)
    observacion: Mapped[str | None] = mapped_column(Text)            # confidencial (RQNF-03)
    fecha: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    caso: Mapped[CasoAcompanamiento] = relationship(back_populates="derivaciones")
    solicitante: Mapped[Usuario] = relationship(foreign_keys=[solicitada_por])


class Notificacion(Base):
    __tablename__ = "notificacion"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    mensaje: Mapped[str] = mapped_column(String(255), nullable=False)
    caso_id: Mapped[int | None] = mapped_column(ForeignKey("caso_acompanamiento.id"))
    leida: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    atendida: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fecha: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BitacoraAcceso(Base):
    """RQNF-03: todo acceso a información sensible queda registrado."""
    __tablename__ = "bitacora_acceso"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), nullable=False)
    recurso: Mapped[str] = mapped_column(String(40), nullable=False)
    recurso_id: Mapped[int] = mapped_column(Integer, nullable=False)
    accion: Mapped[AccionAuditoria] = mapped_column(Enum(AccionAuditoria), nullable=False)
    # Qué se hizo, en palabras, para que la bitácora se lea sin consultar otras tablas.
    detalle: Mapped[str | None] = mapped_column(String(200))
    fecha: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    usuario: Mapped["Usuario"] = relationship()
