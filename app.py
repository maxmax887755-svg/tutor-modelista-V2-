"""Tutor Modelista v2 · Escuela Modelo de Mérida, Yucatán
Accesos con Firebase, progreso por alumno, material de la escuela, quizzes, repaso, reto diario y panel docente."""
import streamlit as st

st.set_page_config(page_title="Tutor Modelista", page_icon="🎓", layout="wide", initial_sidebar_state="expanded")

import nucleo
from tm import config
from ui import accesibilidad, admin, comun, docente, login, orientador, progreso, pwa, quizzes, repaso, reto, tutor


def main():
    comun.iniciar_estado()
    repo, modo = comun.obtener_repo()
    usuario = st.session_state.usuario
    if usuario is None:
        login.pantalla(repo, modo)
        st.stop()
    ctx = comun.Ctx(repo, modo, usuario)
    if (usuario.get("consentimiento") or {}).get("version") != config.VERSION_AVISO:
        comun.pantalla_consentimiento(ctx)
        st.stop()
    accesibilidad.aplicar()
    pwa.inyectar()
    paginas = {
        "💬 Tutor": tutor.pagina_tutor, "💬 Asistente": tutor.pagina_tutor,
        "🧠 Quiz": quizzes.pagina_quiz, "🔁 Repaso": repaso.pagina_repaso, "⭐ Reto del día": reto.pagina_reto,
        "🔥 Mi progreso": progreso.pagina_progreso, "👩‍🏫 Mi grupo": docente.pagina_grupo,
        "📚 Materiales": docente.pagina_materiales, "🫶 Bienestar": orientador.pagina_bienestar,
        "🛠️ Administración": admin.pagina_admin,
    }
    pagina = comun.barra_lateral(ctx)
    try:
        paginas[pagina](ctx)
    except Exception:
        nucleo.logger.exception("Error en la pantalla %s", pagina)
        st.error("Algo salió mal en esta pantalla. Recarga la página; si sigue igual, avisa a tu docente o a la administración.")


if __name__ == "__main__":
    main()
