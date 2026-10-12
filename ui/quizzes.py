"""Quiz: el alumno elige tema y dificultad; la IA crea las preguntas y se califican aquí."""
import streamlit as st

import nucleo
from tm import ia, progress, prompts2, quiz, quotas, retrieval

from . import comun, preguntas

DIFICULTADES = ["Fácil", "Medio", "Reto"]


def _crear(ctx):
    with st.form("crear_quiz"):
        materia = st.selectbox("Materia", comun.MATERIAS[1:], key="quiz_materia")
        tema = st.text_input("¿Sobre qué tema?", max_chars=80, placeholder="Por ejemplo: fracciones, la Revolución, el ciclo del agua")
        c1, c2 = st.columns(2)
        n = c1.selectbox("Preguntas", [3, 5, 8], index=1)
        dificultad = c2.selectbox("Dificultad", DIFICULTADES, index=1)
        crear = st.form_submit_button("Crear mi quiz", use_container_width=True)
    if not crear:
        return
    if not tema.strip():
        st.warning("Escribe un tema para armar tu quiz.")
        return
    if not quotas.puede_generar(comun.uso_hoy(ctx)):
        st.warning("Llegaste al límite de quizzes de hoy. ¡Mañana hay más!")
        return
    nivel = "preparatoria" if ctx.usuario.get("nivel") == "preparatoria" else "secundaria"
    material = comun.fragmentos(ctx)
    contexto = retrieval.formatear_contexto(retrieval.buscar(f"{tema} {materia}", material, 3)) if material else ""
    try:
        with st.spinner("Antorchita está preparando tu quiz…"):
            texto, uso = ia.generar(prompts2.prompt_quiz(materia, tema.strip(), n, dificultad, nivel, contexto),
                                    json_mode=True, max_tokens=3500)
            qs = quiz.parsear_quiz(texto)
    except (ia.IAError, ValueError):
        st.warning("No pude armar el quiz ahora. Intenta de nuevo o cambia el tema.")
        return
    ctx.repo.sumar_uso(ctx.uid, gen=1, tin=uso["tokens_in"], tout=uso["tokens_out"])
    comun.uso_hoy(ctx, refrescar=True)
    st.session_state.quiz = {"materia": materia, "tema": tema.strip(), "preguntas": qs, "resultado": None}
    st.rerun()


def _calificar(ctx, q, elegidas):
    aciertos, detalle = quiz.calificar(q["preguntas"], elegidas)
    xp = progress.XP_QUIZ_COMPLETO + aciertos * progress.XP_QUIZ_ACIERTO
    info = ctx.repo.registrar_actividad(ctx.uid, "quiz", xp=xp, tema=q["tema"])
    ctx.repo.anotar_resultado(ctx.uid, q["tema"], aciertos, len(detalle))
    nuevas = ctx.repo.agregar_tarjetas(ctx.uid, preguntas.tarjetas_de_fallos(q["preguntas"], detalle, q["materia"], q["tema"]))
    ctx.repo.registrar_evento(ctx.uid, ctx.gid, "quiz", q["materia"], q["tema"], True)
    comun.progreso(ctx, refrescar=True)
    q["resultado"] = {"elegidas": elegidas, "detalle": detalle, "aciertos": aciertos, "xp": xp, "nuevas": nuevas,
                      "racha": info["racha"]}
    st.rerun()


def pagina_quiz(ctx):
    nucleo.aplicar_tema(ctx.rol_nucleo)
    comun.chip_rol(ctx)
    st.header("🧠 Quiz")
    q = st.session_state.quiz
    if q is None:
        st.caption("Pon a prueba lo que sabes. Lo que falles se guarda para repasarlo después.")
        _crear(ctx)
        return
    st.subheader(f"{q['materia']} · {q['tema']}")
    r = q["resultado"]
    if r is None:
        elegidas = preguntas.formulario(q["preguntas"], "quiz")
        if elegidas is not None:
            _calificar(ctx, q, elegidas)
        if st.button("Cancelar quiz", key="cancelar_quiz"):
            st.session_state.quiz = None
            st.rerun()
        return
    total = len(r["detalle"])
    st.metric("Tu resultado", f"{r['aciertos']} de {total}")
    if r["aciertos"] == total:
        st.success("¡Perfecto! Dominas este tema 🔥")
    elif r["aciertos"] / total >= 0.6:
        st.info("¡Muy bien! Repasa lo que fallaste y quedará firme.")
    else:
        st.info("Este tema todavía es un reto, y está bien. Con el repaso mejorarás.")
    st.caption(f"+{r['xp']} puntos · racha de {r['racha']} día(s)")
    if r["nuevas"]:
        st.caption(f"Guardamos {r['nuevas']} tarjeta(s) en tu sección de Repaso.")
    preguntas.resultado(q["preguntas"], r["elegidas"], r["detalle"])
    if st.button("Hacer otro quiz", use_container_width=True, key="otro_quiz"):
        st.session_state.quiz = None
        st.rerun()
