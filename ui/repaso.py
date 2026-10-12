"""Repaso espaciado: tarjetas que vuelven justo cuando conviene recordarlas."""
import streamlit as st

import nucleo
from tm import config, progress, spaced

from . import comun


def _guardar(ctx, e, t, acerto):
    ctx.repo.guardar_tarjeta(t["tid"], spaced.actualizar(t, acerto, config.hoy()))
    e["resultado"] = acerto
    e["aciertos"] += 1 if acerto else 0


def _siguiente(e):
    e["i"] += 1
    e["resultado"], e["revelada"] = None, False
    st.rerun()


def pagina_repaso(ctx):
    nucleo.aplicar_tema(ctx.rol_nucleo)
    comun.chip_rol(ctx)
    st.header("🔁 Repaso")
    e = st.session_state.repaso
    if e is None:
        cola = ctx.repo.tarjetas_pendientes(ctx.uid, 10)
        total = len(ctx.repo.tarjetas_usuario(ctx.uid))
        if not cola:
            st.success("No tienes tarjetas por repasar hoy 🎉")
            st.caption(f"Tienes {total} tarjeta(s) guardadas. Se crean con tus quizzes y al terminar una sesión con el tutor.")
            return
        st.caption(f"Tienes {len(cola)} tarjeta(s) para hoy. ¡Son pocas y te ayudan a no olvidar!")
        if st.button("Empezar repaso", use_container_width=True, key="empezar_repaso"):
            st.session_state.repaso = {"cola": cola, "i": 0, "revelada": False, "resultado": None, "aciertos": 0}
            st.rerun()
        return

    cola, i = e["cola"], e["i"]
    if i >= len(cola):
        xp = e["aciertos"] * progress.XP_REPASO_ACIERTO
        if not e.get("registrado"):
            ctx.repo.registrar_actividad(ctx.uid, "repaso", xp=xp)
            comun.progreso(ctx, refrescar=True)
            e["registrado"] = True
        st.success(f"¡Repaso terminado! Acertaste {e['aciertos']} de {len(cola)} (+{xp} puntos).")
        if st.button("Volver", key="fin_repaso"):
            st.session_state.repaso = None
            st.rerun()
        return

    t = cola[i]
    st.progress(i / len(cola), text=f"Tarjeta {i + 1} de {len(cola)}")
    st.markdown(f"### {t['pregunta']}")
    if t.get("opciones"):
        elegido = st.radio("Elige tu respuesta", t["opciones"], index=None, key=f"rp_{i}", disabled=e["resultado"] is not None)
        if e["resultado"] is None:
            if st.button("Comprobar", key=f"rp_ok_{i}"):
                if elegido is None:
                    st.warning("Elige una opción.")
                else:
                    _guardar(ctx, e, t, t["opciones"].index(elegido) == t["correcta"])
                    st.rerun()
        else:
            if e["resultado"]:
                st.success("¡Correcto!")
            else:
                st.error(f"La respuesta era: {t['respuesta']}")
            if t.get("explicacion"):
                st.caption(t["explicacion"])
            if st.button("Siguiente", key=f"rp_sig_{i}"):
                _siguiente(e)
    else:
        if not e["revelada"]:
            if st.button("Mostrar la respuesta", key=f"rp_rev_{i}"):
                e["revelada"] = True
                st.rerun()
        else:
            st.info(t["respuesta"])
            c1, c2 = st.columns(2)
            if c1.button("😅 No la sabía", use_container_width=True, key=f"rp_no_{i}"):
                _guardar(ctx, e, t, False)
                _siguiente(e)
            if c2.button("😎 La sabía", use_container_width=True, key=f"rp_si_{i}"):
                _guardar(ctx, e, t, True)
                _siguiente(e)
