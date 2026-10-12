"""Reto del día: 3 preguntas por materia, un mismo reto para todo el grupo (se genera una sola vez al día)."""
import streamlit as st

import nucleo
from tm import ia, progress, prompts2, quiz, quotas, retrieval

from . import comun, preguntas


def reto_del_dia(ctx, materia, gid):
    """Devuelve el reto guardado o lo genera (una vez por grupo, materia y día). None si falla."""
    existente = ctx.repo.get_reto(gid, materia)
    if existente:
        return existente["preguntas"]
    if not quotas.puede_generar(comun.uso_hoy(ctx)):
        st.warning("Llegaste al límite de generaciones de hoy.")
        return None
    nivel = "preparatoria" if ctx.usuario.get("nivel") == "preparatoria" else "secundaria"
    material = comun.fragmentos(ctx)
    contexto = retrieval.formatear_contexto(retrieval.buscar(materia, material, 3)) if material else ""
    try:
        with st.spinner("Preparando el reto de hoy…"):
            texto, uso = ia.generar(prompts2.prompt_reto(materia, nivel, contexto), json_mode=True, max_tokens=2500)
            qs = quiz.parsear_quiz(texto)
    except (ia.IAError, ValueError):
        st.warning("No pude preparar el reto ahora. Intenta de nuevo en un momento.")
        return None
    ctx.repo.guardar_reto(gid, materia, qs)
    ctx.repo.sumar_uso(ctx.uid, gen=1, tin=uso["tokens_in"], tout=uso["tokens_out"])
    comun.uso_hoy(ctx, refrescar=True)
    return qs


def pagina_reto(ctx):
    nucleo.aplicar_tema(ctx.rol_nucleo)
    comun.chip_rol(ctx)
    st.header("⭐ Reto del día")
    materia = st.selectbox("Materia", comun.MATERIAS[1:], key="reto_materia")
    gid = ctx.gid or "general"
    res = st.session_state.reto_resultado
    if res and res["materia"] == materia:
        st.success(f"¡Reto completado! Acertaste {res['aciertos']} de {len(res['detalle'])} · +{res['xp']} puntos · "
                   f"racha de {res['racha']} día(s) 🔥")
        preguntas.resultado(res["preguntas"], res["elegidas"], res["detalle"])
        return
    if ctx.repo.reto_hecho(ctx.uid, materia):
        st.success("¡Ya hiciste el reto de hoy en esta materia! Vuelve mañana 🔥")
        return
    st.caption("3 preguntas, unos 5 minutos. Sumas puntos y mantienes tu racha.")
    if not st.session_state.get("reto_abierto") == materia:
        if st.button("🚀 Ver el reto de hoy", use_container_width=True, key="ver_reto"):
            st.session_state.reto_abierto = materia
            st.rerun()
        return
    qs = reto_del_dia(ctx, materia, gid)
    if not qs:
        return
    elegidas = preguntas.formulario(qs, f"reto_{materia}")
    if elegidas is None:
        return
    aciertos, detalle = quiz.calificar(qs, elegidas)
    xp = progress.XP_RETO + aciertos * progress.XP_QUIZ_ACIERTO
    info = ctx.repo.registrar_actividad(ctx.uid, "reto", xp=xp, tema=f"Reto {materia}")
    ctx.repo.anotar_resultado(ctx.uid, f"Reto {materia}", aciertos, len(detalle))
    ctx.repo.agregar_tarjetas(ctx.uid, preguntas.tarjetas_de_fallos(qs, detalle, materia, f"Reto {materia}"))
    ctx.repo.registrar_evento(ctx.uid, ctx.gid, "reto", materia, f"Reto {materia}", True)
    comun.progreso(ctx, refrescar=True)
    st.session_state.reto_resultado = {"materia": materia, "preguntas": qs, "elegidas": elegidas, "detalle": detalle,
                                       "aciertos": aciertos, "xp": xp, "racha": info["racha"]}
    st.session_state.celebrar = True
    st.session_state.reto_abierto = None
    st.rerun()
