"""Estadísticas para el panel docente y reporte base para familias."""
from collections import Counter

from . import config


def resumen_grupo(repo, gid, dias=7):
    eventos = repo.eventos_grupo(gid, dias)
    alumnos = repo.listar_usuarios(rol="alumno", gid=gid)
    activos = {e["uid"] for e in eventos}
    tipos = Counter(e.get("tipo") for e in eventos)
    errores = sum(1 for e in eventos if not e.get("ok", True))
    dif = Counter()
    rachas = []
    por_alumno = []
    for a in alumnos:
        p = repo.get_progreso(a["uid"])
        dif.update(p.get("dificultades", {}))
        rachas.append(p.get("racha", 0))
        por_alumno.append({"nombre": a["nombre"], "uid": a["uid"], "xp": p["xp"], "racha": p.get("racha", 0),
                           "actividad": sum(1 for e in eventos if e["uid"] == a["uid"])})
    fb = repo.listar_feedback(gid)
    return {
        "alumnos": len(alumnos), "activos": len(activos), "mensajes": tipos.get("mensaje", 0),
        "quizzes": tipos.get("quiz", 0), "retos": tipos.get("reto", 0), "errores": errores,
        "racha_media": round(sum(rachas) / len(rachas), 1) if rachas else 0,
        "dificultades": dif.most_common(8), "por_alumno": sorted(por_alumno, key=lambda x: -x["actividad"]),
        "likes": sum(1 for f in fb if f.get("valor", 0) > 0), "dislikes": sum(1 for f in fb if f.get("valor", 0) < 0),
        "actividad_total": sum(tipos.get(t, 0) for t in ("mensaje", "quiz", "reto")),
    }


def datos_familia(repo, uid, dias=7):
    """Datos agregados (sin conversaciones) para el reporte a familias."""
    p = repo.get_progreso(uid)
    u = repo.get_usuario(uid) or {}
    eventos = []
    for g in u.get("grupos", []) or [""]:
        eventos += [e for e in repo.eventos_grupo(g, dias) if e["uid"] == uid]
    dias_activos = len({e["dia"] for e in eventos})
    return {"dias_activos": dias_activos, "mensajes": sum(1 for e in eventos if e["tipo"] == "mensaje"),
            "quizzes": sum(1 for e in eventos if e["tipo"] == "quiz"), "retos": sum(1 for e in eventos if e["tipo"] == "reto"),
            "racha": p.get("racha", 0), "temas_logrados": list(p.get("dominados", {}))[:5],
            "temas_por_reforzar": list(p.get("dificultades", {}))[:5],
            "precision": round(100 * p["aciertos"] / p["preguntas"]) if p.get("preguntas") else None}


def reporte_base(nombre, d):
    """Texto de respaldo si la IA no está disponible."""
    logros = ", ".join(d["temas_logrados"]) or "seguir practicando"
    refuerzo = ", ".join(d["temas_por_reforzar"]) or "ningún tema en particular"
    return (f"Reporte semanal de {nombre}\n\nEsta semana estudió con el tutor {d['dias_activos']} día(s) y "
            f"completó {d['quizzes']} quiz(es) y {d['retos']} reto(s) diario(s). Su racha actual es de {d['racha']} día(s).\n"
            f"Temas donde le fue bien: {logros}.\nTemas por reforzar: {refuerzo}.\n\n"
            "Sugerencias: 1) Pregúntele qué aprendió hoy y que se lo explique con sus palabras. "
            "2) Acompañe un ratito de estudio constante en lugar de sesiones largas. "
            "3) Celebre el esfuerzo, no solo los resultados.")
