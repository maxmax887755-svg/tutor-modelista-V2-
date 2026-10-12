"""Pantalla de acceso: Firebase (correo y contraseña) o modo demo con código opcional."""
import hmac

import streamlit as st

import nucleo
from tm import auth, config

from . import comun

MAX_INTENTOS = 5
DEMOS = {
    "Alumno de Secundaria": ("demo_alumno_sec", "alumno", "secundaria"),
    "Alumno de Preparatoria": ("demo_alumno_prepa", "alumno", "preparatoria"),
    "Docente": ("demo_docente", "docente", "secundaria"),
    "Orientador": ("demo_orientador", "orientador", "secundaria"),
    "Administrador": ("demo_admin", "admin", "secundaria"),
}


def _entrar(usuario):
    st.session_state.usuario = usuario
    st.rerun()


def _login_firebase(repo):
    if st.session_state.intentos_login >= MAX_INTENTOS:
        st.error("Demasiados intentos. Recarga la página e inténtalo de nuevo.")
        return
    with st.form("acceso"):
        email = st.text_input("Correo de la escuela")
        clave = st.text_input("Contraseña", type="password")
        enviar = st.form_submit_button("Entrar", use_container_width=True)
    if enviar:
        try:
            cuenta = auth.login(config.api_key_firebase(), email, clave)
        except auth.AuthError as e:
            st.session_state.intentos_login += 1
            st.error(str(e))
            return
        perfil = repo.get_usuario(cuenta["uid"])
        es_admin = cuenta["email"] in config.admin_emails()
        if perfil is None and es_admin:
            perfil = repo.crear_usuario(cuenta["uid"], cuenta["email"].split("@")[0], cuenta["email"], rol="admin")
        elif perfil is not None and es_admin and perfil.get("rol") != "admin":
            repo.actualizar_usuario(cuenta["uid"], rol="admin")
            perfil["rol"] = "admin"
        if perfil is None or not perfil.get("activo", True):
            st.error("Tu cuenta aún no está activada. Avisa a la administración de la escuela.")
            return
        _entrar(perfil)
    with st.expander("¿Olvidaste tu contraseña o es tu primera vez?"):
        correo = st.text_input("Tu correo", key="correo_reset")
        if st.button("Enviarme un correo para crear/cambiar contraseña", key="btn_reset"):
            auth.enviar_restablecer(config.api_key_firebase(), correo)
            st.success("Si el correo está registrado, recibirás un mensaje en unos minutos.")


def _login_demo(repo):
    codigo = config.leer("ACCESS_CODE")
    with st.form("acceso_demo"):
        if codigo:
            entrada = st.text_input("Código de acceso", type="password")
        quien = st.selectbox("Entrar como", list(DEMOS))
        enviar = st.form_submit_button("Entrar", use_container_width=True)
    if not enviar:
        return
    if st.session_state.intentos_login >= MAX_INTENTOS:
        st.error("Demasiados intentos. Recarga la página.")
        return
    if codigo and not hmac.compare_digest(entrada.encode("utf-8"), codigo.encode("utf-8")):
        st.session_state.intentos_login += 1
        st.error("Código incorrecto.")
        return
    uid, rol, nivel = DEMOS[quien]
    if repo.get_grupo("demo") is None:
        repo.crear_grupo("Demo", "secundaria", docentes=["demo_docente"])
    perfil = repo.get_usuario(uid)
    if perfil is None:
        perfil = repo.crear_usuario(uid, quien, f"{uid}@demo.local", rol, nivel, grupos=["demo"])
    _entrar(perfil)


def pantalla(repo, modo):
    nucleo.aplicar_tema(nucleo.ROLES[0])
    _, c, _ = st.columns([1, 2, 1])
    with c:
        if nucleo.existe(nucleo.LOGO):
            st.image(nucleo.LOGO, width=140)
        st.title("Tutor Modelista")
        st.caption("Escuela Modelo · Asistente educativo con IA")
        if modo == "firebase":
            _login_firebase(repo)
        elif modo == "firebase_error":
            st.error("No pude conectar con la base de datos de la escuela. Avisa a la persona responsable.")
        else:
            _login_demo(repo)
        comun.boton_creador("creador_login")
