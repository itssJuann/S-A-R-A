"""Boletín del estudiante: las notas de cada asignatura corte por corte.

El semestre se divide en `CORTES_POR_SEMESTRE` cortes de calificación
(configurable con SARA_CORTES). Esta vista consolida, para un periodo,
todas las asignaturas matriculadas con la nota de cada corte, el promedio
de la asignatura y las inasistencias acumuladas.
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import CORTE_VIGENTE, CORTES_POR_SEMESTRE, PERIODO_VIGENTE
from ..models import Estudiante, Inasistencia, Matricula, Nota


def cortes_del_semestre() -> list[int]:
    return list(range(1, CORTES_POR_SEMESTRE + 1))


def boletin_de(db: Session, estudiante: Estudiante, periodo: str = PERIODO_VIGENTE) -> dict:
    """Arma el boletín de un estudiante para un periodo académico."""
    cortes = cortes_del_semestre()
    matriculas = db.scalars(
        select(Matricula).where(Matricula.estudiante_id == estudiante.id,
                                Matricula.periodo == periodo)
    ).all()

    asignaturas, promedios = [], []
    for m in matriculas:
        notas = {n.corte: n for n in m.notas}
        valores = [float(notas[c].valor) for c in cortes if c in notas]
        promedio = round(sum(valores) / len(valores), 2) if valores else None
        if promedio is not None:
            promedios.append(promedio)

        faltas = db.scalar(select(func.count(Inasistencia.id)).where(
            Inasistencia.matricula_id == m.id, Inasistencia.justificada.is_(False))) or 0

        asignaturas.append({
            "matricula_id": m.id,
            "asignatura": m.asignatura.nombre,
            "codigo": m.asignatura.codigo,
            "creditos": m.asignatura.creditos,
            "docente": m.docente.nombre if m.docente else None,
            "repetida": m.numero_intento > 1,
            "notas": [
                {
                    "corte": c,
                    "valor": float(notas[c].valor) if c in notas else None,
                    "fecha": notas[c].fecha if c in notas else None,
                }
                for c in cortes
            ],
            "promedio": promedio,
            "inasistencias": faltas,
            "sesiones": m.sesiones_programadas,
        })

    asignaturas.sort(key=lambda a: a["asignatura"])
    return {
        "estudiante": estudiante.usuario.nombre,
        "programa": estudiante.programa.nombre,
        "semestre": estudiante.semestre,
        "periodo": periodo,
        "cortes": cortes,
        "corte_vigente": CORTE_VIGENTE,
        "asignaturas": asignaturas,
        "promedio_periodo": round(sum(promedios) / len(promedios), 2) if promedios else None,
    }
