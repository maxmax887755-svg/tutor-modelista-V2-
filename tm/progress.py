"""Puntos (XP), nivel de la llama y racha de días."""
from datetime import datetime

NIVELES = [(0, "Chispa"), (30, "Brasa"), (100, "Llama"), (250, "Fogata"), (500, "Antorcha")]
XP_MENSAJE, MAX_XP_MSG_DIA = 1, 20
XP_QUIZ_ACIERTO, XP_QUIZ_COMPLETO = 3, 5
XP_RETO, XP_REPASO_ACIERTO = 20, 2


def nivel(xp):
    """(índice, nombre, xp base, xp del siguiente o None)."""
    idx = 0
    for i, (umbral, _) in enumerate(NIVELES):
        if xp >= umbral:
            idx = i
    sig = NIVELES[idx + 1][0] if idx + 1 < len(NIVELES) else None
    return idx, NIVELES[idx][1], NIVELES[idx][0], sig


def actualizar_racha(ultimo_dia, hoy, racha):
    """Racha amable: se permite faltar un día sin perderla; si faltan más, vuelve a 1."""
    if not ultimo_dia:
        return 1
    if ultimo_dia == hoy:
        return max(racha, 1)
    gap = (datetime.strptime(hoy, "%Y-%m-%d") - datetime.strptime(ultimo_dia, "%Y-%m-%d")).days
    return racha + 1 if gap <= 2 else 1
