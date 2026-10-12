"""Detección sencilla de mensajes de riesgo (primera persona) para mostrar apoyo y avisar al orientador.
Es una ayuda, no sustituye el protocolo de la escuela: puede fallar en ambos sentidos."""
import re
from .retrieval import normalizar

PATRONES = {
    "autolesion": [
        r"\bme quiero (morir|matar|suicidar|hacer dano)", r"\bquiero (morir|matarme|suicidarme|desaparecer para siempre)",
        r"\bno quiero (seguir )?(vivir|vivo)", r"\bpienso en (suicidarme|matarme|quitarme la vida)",
        r"\bquitarme la vida", r"\bhacerme dano", r"\bcortarme\b", r"\bacabar con mi vida",
    ],
    "violencia": [
        r"\bvoy a (matar|golpear|lastimar) a", r"\b(traer|llevar) (un |una )?(arma|pistola|cuchillo) a (la |el )?(escuela|prepa|secundaria|salon)",
        r"\bamenaza de (muerte|bomba)",
    ],
    "abuso": [r"\bme (abusa|abusan|abuso|violaron|violo)\b", r"\bme tocan?\b.*\b(no quiero|me incomoda|me da miedo)"],
    "acoso": [
        r"\bme (hacen|hace) bullying", r"\bme (acosan|acosa|pegan|golpean|amenazan)\b",
        r"\bme molestan todos los dias", r"\bsufro (de )?(bullying|acoso)",
    ],
}
NIVEL = {"autolesion": "alta", "violencia": "alta", "abuso": "alta", "acoso": "media"}


def revisar(texto):
    """Devuelve {'alerta': bool, 'categorias': [...], 'nivel': 'alta'|'media'|None}."""
    t = normalizar(texto or "")
    cats = [c for c, pats in PATRONES.items() if any(re.search(p, t) for p in pats)]
    if not cats:
        return {"alerta": False, "categorias": [], "nivel": None}
    nivel = "alta" if any(NIVEL[c] == "alta" for c in cats) else "media"
    return {"alerta": True, "categorias": cats, "nivel": nivel}


def mensaje_apoyo(categorias, linea):
    base = ("Gracias por contármelo. Lo que sientes o te pasa es importante y no tienes que cargarlo solo. "
            "Habla hoy mismo con un adulto de confianza: tu familia, un profesor o tu orientador.")
    if "autolesion" in categorias:
        return base + f" Si sientes que puedes hacerte daño, pide ayuda ahora. {linea}. En una emergencia llama al 911."
    if "violencia" in categorias or "abuso" in categorias:
        return base + f" Si estás en peligro, llama al 911. {linea}."
    return base + " Tu orientador puede ayudarte con esto."
