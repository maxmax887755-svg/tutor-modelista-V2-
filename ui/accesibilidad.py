"""Opciones de accesibilidad: letra grande, tipografía amigable (dislexia), alto contraste y menos movimiento."""
import streamlit as st


def controles():
    with st.expander("♿ Accesibilidad"):
        st.select_slider("Tamaño de letra", options=[100, 115, 130, 150], value=100, key="acc_tam",
                         format_func=lambda v: f"{v}%")
        st.checkbox("Tipografía fácil de leer (Lexend)", key="acc_fuente")
        st.checkbox("Alto contraste", key="acc_contraste")
        st.checkbox("Reducir animaciones", key="acc_movimiento")


def css():
    s = st.session_state
    reglas = []
    tam = s.get("acc_tam", 100)
    if tam != 100:
        reglas.append(f"html {{ font-size: {tam}% !important; }}")
    if s.get("acc_fuente"):
        reglas.append("@import url('https://fonts.googleapis.com/css2?family=Lexend:wght@400;600&display=swap');"
                      ".stApp, .stMarkdown, p, li, label, h1, h2, h3, h4, input, textarea, button p "
                      "{ font-family: 'Lexend', sans-serif !important; letter-spacing: .02em; line-height: 1.7; }")
    if s.get("acc_contraste"):
        reglas.append(".stApp { background: #000 !important; color: #fff !important; }"
                      ".stApp p, .stApp li, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp span { color: #fff !important; }"
                      "button, input, textarea { border: 2px solid #fff !important; }")
    if s.get("acc_movimiento"):
        reglas.append("*, *::before, *::after { animation: none !important; transition: none !important; }")
    return "\n".join(reglas)


def aplicar():
    estilos = css()
    if estilos:
        st.markdown(f"<style>{estilos}</style>", unsafe_allow_html=True)
