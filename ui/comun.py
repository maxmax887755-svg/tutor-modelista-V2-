"""Piezas comunes: conexión a datos, contexto del usuario, estado de sesión, barra lateral y consentimiento."""
import time
from dataclasses import dataclass

import streamlit as st

import nucleo
from tm import config, progress, quotas
from tm.repo import Repo
from tm.store import crear_store

MATERIAS = ["General", "Matemáticas", "Español", "Ciencias", "Historia", "Inglés", "Formación Cívica"]
PAGINAS_POR_ROL = {
    "alumno": ["💬 Tutor", "🧠 Quiz", "🔁 Repaso", "⭐ Reto del día", "🔥 Mi progreso"],
    "docente": ["💬 Asistente", "👩‍🏫 Mi grupo", "📚 Materiales"],
    "orientador": ["🫶 Bienestar", "💬 Asistente"],
    "admin": ["🛠️ Administración", "👩‍🏫 Mi grupo", "📚 Materiales", "🫶 Bienestar", "💬 Asistente"],
}
NOMBRE_ROL = {"alumno": "Estudiante", "docente": "Docente", "orientador": "Orientación", "admin": "Administración"}
TEXTO_PRIVACIDAD = (
    "**Aviso de privacidad (resumen).** El Tutor Modelista guarda tu nombre, tu grupo, tu progreso (puntos, racha, "
    "temas) y los resultados de tus quizzes para ayudarte a aprender y para que tu docente vea cómo va el grupo. "
    "Tus conversaciones **no se guardan** en la plataforma; los mensajes se procesan con el servicio Gemini de Google "
    "para generar la respuesta. No escribas datos personales (apellidos, domicilio, teléfono). Si escribes algo que "
    "indique que estás en riesgo, la escuela puede avisar a orientación para apoyarte. Puedes pedir que se borren tus "
    "datos a la administración de la escuela. Las respuestas de la IA pueden tener errores: verifica con tu docente."
)


@st.cache_resource(show_spinner=False)
def obtener_repo():
    """Un solo repositorio de datos para toda la app. Devuelve (repo, modo): firebase | local | firebase_error."""
    cuenta = config.cuenta_firebase()
    if cuenta:
        try:
            return Repo(crear_store(cuenta=cuenta)), "firebase"
        except Exception:
            nucleo.logger.exception("No pude conectar con Firebase")
            return Repo(crear_store()), "firebase_error"
    return Repo(crear_store(ruta=config.leer("DATOS_LOCALES", "datos_locales.json"))), "local"


def iniciar_estado():
    por_defecto = {"usuario": None, "messages": [], "pendiente": None, "uploader_key": 0, "foto_key": 0,
                   "doc_procesado": None, "mostrar_adios": False, "audio_reproducido": False, "intentos_login": 0,
                   "apoyo": None, "hash_audio": None, "nivel_mostrado": None, "quiz": None, "repaso": None,
                   "celebrar": False, "n_mensajes": 0, "resumen_sesion": None, "reto_resultado": None}
    for k, v in por_defecto.items():
        st.session_state.setdefault(k, v)


def cacheado(clave, fn, ttl=300):
    """Guarda un resultado unos minutos en la sesión (evita leer la base de datos en cada interacción)."""
    c = st.session_state.setdefault("_cache", {})
    e = c.get(clave)
    if e and time.time() - e[0] < ttl:
        return e[1]
    v = fn()
    c[clave] = (time.time(), v)
    return v


@dataclass
class Ctx:
    repo: Repo
    modo: str
    usuario: dict

    @property
    def uid(self):
        return self.usuario["uid"]

    @property
    def nombre(self):
        return self.usuario.get("nombre", "")

    @property
    def rol(self):
        return self.usuario.get("rol", "alumno")

    @property
    def grupos(self):
        return self.usuario.get("grupos", []) or []

    @property
    def gid(self):
        return self.grupos[0] if self.grupos else None

    @property
    def es_alumno(self):
        return self.rol == "alumno"

    @property
    def rol_nucleo(self):
        if self.es_alumno:
            return nucleo.ROLES[1] if self.usuario.get("nivel") == "preparatoria" else nucleo.ROLES[0]
        return nucleo.ES_DOCENTE

    @property
    def limite_diario(self):
        return quotas.limite_mensajes(self.rol, cacheado("cfg", self.repo.get_config, 120))


def progreso(ctx, refrescar=False):
    if refrescar or st.session_state.get("progreso_uid") != ctx.uid or "progreso" not in st.session_state:
        st.session_state.progreso = ctx.repo.get_progreso(ctx.uid)
        st.session_state.progreso_uid = ctx.uid
    return st.session_state.progreso


def uso_hoy(ctx, refrescar=False):
    c = st.session_state.get("uso")
    if refrescar or not c or c["dia"] != config.hoy() or c["uid"] != ctx.uid:
        c = {"dia": config.hoy(), "uid": ctx.uid, "datos": ctx.repo.uso_diario(ctx.uid)}
        st.session_state.uso = c
    return c["datos"]


def fragmentos(ctx):
    """Material de la escuela disponible para este usuario (se renueva cada 5 minutos)."""
    gid = ctx.gid or "*"
    return cacheado(f"frags_{gid}", lambda: ctx.repo.fragmentos_de_grupo(gid), 300)


def chip_rol(ctx):
    st.markdown(f"<span class='rol-chip'>{nucleo.NOMBRE_CORTO_ROL[ctx.rol_nucleo]}</span>", unsafe_allow_html=True)


def pantalla_consentimiento(ctx):
    nucleo.aplicar_tema(nucleo.ROLES[0])
    _, c, _ = st.columns([1, 2, 1])
    with c:
        if nucleo.existe(nucleo.LOGO):
            st.image(nucleo.LOGO, width=120)
        st.title(f"¡Hola, {ctx.nombre.split(' ')[0] or 'bienvenido'}!")
        st.markdown(TEXTO_PRIVACIDAD)
        ok = st.checkbox("He leído el aviso. Si soy menor de edad, mi familia fue informada por la escuela.", key="acepto_aviso")
        if st.button("Continuar", use_container_width=True, disabled=not ok):
            ctx.repo.registrar_consentimiento(ctx.uid)
            st.session_state.usuario["consentimiento"] = {"version": config.VERSION_AVISO}
            st.rerun()


def boton_creador(clave="creador"):
    """Botón con el crédito del creador de la app."""
    if st.button("👨‍💻 Creador de esta app: Maximiliano Ávila Castillo", use_container_width=True, key=clave):
        st.session_state[f"{clave}_abierto"] = not st.session_state.get(f"{clave}_abierto", False)
    if st.session_state.get(f"{clave}_abierto"):
        st.info("Esta app fue creada por **Maximiliano Ávila Castillo** para la Escuela Modelo de Mérida, Yucatán. 💙🔥")


def cerrar_sesion():
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()


def barra_lateral(ctx):
    """Dibuja la barra lateral y devuelve la página elegida."""
    from . import accesibilidad
    with st.sidebar:
        if nucleo.existe(nucleo.LOGO):
            st.image(nucleo.LOGO, width=110)
        st.title("Tutor Modelista")
        st.caption(f"Hola, {ctx.nombre} · {NOMBRE_ROL.get(ctx.rol, ctx.rol)}")
        if ctx.es_alumno:
            p = progreso(ctx)
            idx, nombre_nivel, base, sig = progress.nivel(p["xp"])
            if st.session_state.nivel_mostrado is None:
                st.session_state.nivel_mostrado = idx
            elif idx > st.session_state.nivel_mostrado:
                st.session_state.nivel_mostrado = idx
                st.toast(f"¡Tu llama creció! Ahora eres {nombre_nivel} 🔥")
                nucleo.mostrar_lottie("antorchita_celebrando.json", 140, loop=False, key=f"celebra_{idx}")
                st.session_state.celebrar_nivel = nombre_nivel
            st.markdown(f"<div class='llama-nivel' style='height:{36 + idx * 16}px'></div>", unsafe_allow_html=True)
            st.markdown(f"**Tu llama: {nombre_nivel}** · racha de {p.get('racha', 0)} día(s)")
            if sig:
                st.progress(min(max((p["xp"] - base) / (sig - base), 0.0), 1.0), text=f"{p['xp']} de {sig} puntos")
            else:
                st.caption("¡Llegaste al nivel máximo!")
        opciones = PAGINAS_POR_ROL.get(ctx.rol, PAGINAS_POR_ROL["alumno"])
        pagina = st.radio("Ir a", opciones, key="pagina_sel")
        if ctx.es_alumno or ctx.rol in ("docente", "orientador"):
            uso = uso_hoy(ctx)
            st.caption(f"Mensajes de hoy: {uso.get('msgs', 0)}/{ctx.limite_diario}")
        if st.button("🗑️ Limpiar conversación", use_container_width=True, key="limpiar"):
            st.session_state.messages = []
            st.session_state.doc_procesado = None
            st.session_state.uploader_key += 1
            st.session_state.mostrar_adios = True
            st.rerun()
        accesibilidad.controles()
        with st.expander("🔒 Aviso de privacidad"):
            st.caption(TEXTO_PRIVACIDAD.replace("**", ""))
        if ctx.modo == "firebase" and config.api_key_firebase():
            if st.button("🔑 Cambiar mi contraseña", use_container_width=True, key="cambiar_clave"):
                from tm import auth
                auth.enviar_restablecer(config.api_key_firebase(), ctx.usuario.get("email", ""))
                st.success("Te enviamos un correo para crear una contraseña nueva.")
        if st.button("Cerrar sesión", use_container_width=True, key="salir"):
            cerrar_sesion()
        boton_creador("creador_lateral")
        st.caption(f"v{config.VERSION_APP} · Escuela Modelo")
    return pagina
