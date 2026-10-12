"""Límites diarios de uso (cuida la cuota y el gasto de la API)."""

LIMITES_DEFECTO = {"alumno": 40, "docente": 120, "orientador": 60, "admin": 200}
LIMITE_GENERACIONES = 12   # quizzes/retos/resúmenes generados por usuario y día


def limite_mensajes(rol, cfg=None):
    cfg = cfg or {}
    return int(cfg.get(f"limite_{rol}", LIMITES_DEFECTO.get(rol, 40)))


def puede_enviar(uso, limite):
    return int((uso or {}).get("msgs", 0)) < limite


def puede_generar(uso, limite=LIMITE_GENERACIONES):
    return int((uso or {}).get("gen", 0)) < limite


def costo_estimado(tokens_in, tokens_out, precio_in_millon, precio_out_millon):
    """Costo en USD según los precios que tú configures (consúltalos en la página de precios de Google)."""
    return round(tokens_in / 1e6 * precio_in_millon + tokens_out / 1e6 * precio_out_millon, 6)
