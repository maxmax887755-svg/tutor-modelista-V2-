"""Mi progreso: llama, racha, temas y meta del grupo."""
import streamlit as st

import nucleo
from tm import progress

from . import comun


def pagina_progreso(ctx):
    nucleo.aplicar_tema(ctx.rol_nucleo)
    comun.chip_rol(ctx)
    st.header("🔥 Mi progreso")
    p = comun.progreso(ctx, refrescar=True)
    idx, nombre, base, sig = progress.nivel(p["xp"])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tu llama", nombre)
    c2.metric("Puntos", p["xp"])
    c3.metric("Racha", f"{p.get('racha', 0)} día(s)")
    c4.metric("Mejor racha", f"{p.get('mejor_racha', 0)} día(s)")
    if sig:
        st.progress(min(max((p["xp"] - base) / (sig - base), 0.0), 1.0), text=f"{p['xp']} de {sig} puntos para el siguiente nivel")
    else:
        st.caption("¡Llegaste al nivel máximo!")
    if p.get("preguntas"):
        st.metric("Aciertos en quizzes y retos", f"{round(100 * p['aciertos'] / p['preguntas'])}%")
    a, b = st.columns(2)
    with a:
        st.subheader("💪 Lo que dominas")
        dom = sorted(p.get("dominados", {}), key=p["dominados"].get, reverse=True)[:6]
        st.markdown("\n".join(f"- {t}" for t in dom) if dom else "Aún no hay temas. ¡Haz un quiz!")
    with b:
        st.subheader("🌱 Para reforzar")
        dif = sorted(p.get("dificultades", {}), key=p["dificultades"].get, reverse=True)[:6]
        st.markdown("\n".join(f"- {t}" for t in dif) if dif else "Nada por ahora. ¡Sigue así!")
    pend = len(ctx.repo.tarjetas_pendientes(ctx.uid, 50))
    if pend:
        st.info(f"Tienes {pend} tarjeta(s) esperando en **Repaso**.")
    if ctx.gid:
        g = comun.cacheado(f"grupo_{ctx.gid}", lambda: ctx.repo.get_grupo(ctx.gid), 120)
        eventos = comun.cacheado(f"ev_{ctx.gid}", lambda: ctx.repo.eventos_grupo(ctx.gid, 7), 120)
        hechos = sum(1 for e in eventos if e["tipo"] in ("quiz", "reto"))
        meta = (g or {}).get("meta_semanal", 100)
        st.subheader("🤝 Meta de tu grupo esta semana")
        st.progress(min(hechos / meta, 1.0) if meta else 0.0, text=f"{hechos} de {meta} quizzes y retos entre todos")
