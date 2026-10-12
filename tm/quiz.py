"""Quizzes: lectura segura del JSON del modelo, mezcla de opciones y calificación."""
import json
import random
import re


def extraer_json(texto):
    t = (texto or "").strip()
    t = re.sub(r"^```(?:json)?|```$", "", t, flags=re.M).strip()
    ini, fin = t.find("{"), t.rfind("}")
    if ini == -1 or fin <= ini:
        raise ValueError("La respuesta no trae JSON.")
    return json.loads(t[ini:fin + 1])


def _indice(c, n):
    if isinstance(c, int) and 0 <= c < n:
        return c
    if isinstance(c, str):
        c = c.strip()
        if c.isdigit() and 0 <= int(c) < n:
            return int(c)
        if len(c) == 1 and c.upper() in "ABCD"[:n]:
            return "ABCD".index(c.upper())
    return None


def parsear_quiz(texto, semilla=None):
    """Devuelve lista de preguntas válidas: {pregunta, opciones[4], correcta(idx), explicacion}."""
    datos = extraer_json(texto)
    crudas = datos.get("preguntas") if isinstance(datos, dict) else datos
    rnd = random.Random(semilla)
    res = []
    for q in crudas or []:
        try:
            ops = [str(o).strip() for o in q["opciones"]]
            idx = _indice(q["correcta"], len(ops))
            pregunta = str(q["pregunta"]).strip()
            if len(ops) < 2 or idx is None or not pregunta or len(set(ops)) != len(ops):
                continue
            orden = list(range(len(ops)))
            rnd.shuffle(orden)
            res.append({"pregunta": pregunta, "opciones": [ops[i] for i in orden],
                        "correcta": orden.index(idx), "explicacion": str(q.get("explicacion", "")).strip()})
        except (KeyError, TypeError):
            continue
    if not res:
        raise ValueError("No se pudo armar ninguna pregunta válida.")
    return res


def calificar(preguntas, respuestas):
    """respuestas: lista de índices elegidos (o None). Devuelve (aciertos, detalle[bool])."""
    detalle = [r is not None and r == q["correcta"] for q, r in zip(preguntas, respuestas)]
    return sum(detalle), detalle
