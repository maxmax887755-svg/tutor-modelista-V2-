"""Repaso espaciado (cajas de Leitner): lo que se falla vuelve pronto; lo que se sabe, cada vez más tarde."""
from datetime import datetime, timedelta

INTERVALOS = [1, 2, 4, 8, 16]   # días por caja (1 a 5)


def sumar_dias(dia, n):
    return (datetime.strptime(dia, "%Y-%m-%d") + timedelta(days=n)).strftime("%Y-%m-%d")


def nueva(pregunta, respuesta, hoy, opciones=None, correcta=None, explicacion="", materia="", tema=""):
    return {"pregunta": pregunta, "respuesta": respuesta, "opciones": opciones, "correcta": correcta,
            "explicacion": explicacion, "materia": materia, "tema": tema, "caja": 1,
            "proxima": sumar_dias(hoy, 1), "aciertos": 0, "fallos": 0, "creada": hoy}


def actualizar(tarjeta, acerto, hoy):
    t = dict(tarjeta)
    caja = int(t.get("caja", 1))
    caja = min(caja + 1, len(INTERVALOS)) if acerto else 1
    t["caja"] = caja
    t["proxima"] = sumar_dias(hoy, INTERVALOS[caja - 1])
    t["aciertos"] = t.get("aciertos", 0) + (1 if acerto else 0)
    t["fallos"] = t.get("fallos", 0) + (0 if acerto else 1)
    t["ultima"] = hoy
    return t


def pendientes(tarjetas, hoy, limite=10):
    due = [t for t in tarjetas if t.get("proxima", "9999") <= hoy]
    due.sort(key=lambda t: (t.get("caja", 1), t.get("proxima", "")))
    return due[:limite]
