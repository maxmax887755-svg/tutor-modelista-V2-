"""Piezas compartidas por quiz, reto del día y repaso: formulario de preguntas, resultados y tarjetas."""
import streamlit as st

from tm import config, spaced


def formulario(preguntas, clave):
    """Muestra las preguntas. Devuelve la lista de índices elegidos al calificar, o None."""
    with st.form(f"form_{clave}"):
        elegidas = []
        for i, q in enumerate(preguntas):
            e = st.radio(f"{i + 1}. {q['pregunta']}", q["opciones"], index=None, key=f"{clave}_{i}")
            elegidas.append(q["opciones"].index(e) if e in q["opciones"] else None)
        enviar = st.form_submit_button("Calificar", use_container_width=True)
    if not enviar:
        return None
    if any(e is None for e in elegidas):
        st.warning("Responde todas las preguntas antes de calificar.")
        return None
    return elegidas


def resultado(preguntas, elegidas, detalle):
    for i, (q, e, ok) in enumerate(zip(preguntas, elegidas, detalle), 1):
        with st.expander(f"{'✅' if ok else '❌'} Pregunta {i}", expanded=not ok):
            st.markdown(f"**{q['pregunta']}**")
            st.markdown(f"Tu respuesta: {q['opciones'][e] if e is not None else '—'}")
            if not ok:
                st.markdown(f"Respuesta correcta: **{q['opciones'][q['correcta']]}**")
            if q.get("explicacion"):
                st.caption(q["explicacion"])


def tarjetas_de_fallos(preguntas, detalle, materia, tema):
    """Convierte las preguntas falladas en tarjetas de repaso espaciado."""
    hoy = config.hoy()
    return [spaced.nueva(q["pregunta"], q["opciones"][q["correcta"]], hoy, q["opciones"], q["correcta"],
                         q.get("explicacion", ""), materia, tema)
            for q, ok in zip(preguntas, detalle) if not ok]
