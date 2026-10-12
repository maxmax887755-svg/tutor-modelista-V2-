"""Pantalla del tutor: chat con Antorchita, con material de la escuela, foto, voz, retroalimentación y memoria."""
import hashlib
import json
import re
import time

import streamlit as st
import streamlit.components.v1 as components

import nucleo
from nucleo import MSG_ERROR
from tm import config, ia, imagenes, moderation, prompts2, quiz, quotas, retrieval, spaced

from . import comun

MAX_FRAGS = 4


# ---------- documento (modo docente) ----------
def _subir_documento():
    archivo = st.file_uploader("Sube un documento (PDF, DOCX o TXT)", type=["pdf", "docx", "txt"],
                               key=f"uploader_{st.session_state.uploader_key}")
    if archivo is None:
        return
    id_doc = f"{archivo.name}-{archivo.size}"
    if st.session_state.doc_procesado == id_doc:
        return
    try:
        texto = nucleo.extraer_texto(archivo.name, archivo.getvalue())
    except ValueError as e:
        st.warning(str(e))
        return
    except Exception:
        nucleo.logger.exception("Error al procesar el documento")
        st.warning("No pude leer el archivo. Intenta pegar el contenido en el chat.")
        return
    if not texto:
        st.warning("No encontré texto en el documento (¿es un escaneo?). Pega el contenido en el chat.")
        return
    truncado = len(texto) > nucleo.MAX_CHARS_DOC
    texto = texto[:nucleo.MAX_CHARS_DOC]
    st.session_state.doc_procesado = id_doc
    st.session_state.messages = [m for m in st.session_state.messages if not m.get("es_doc")]
    st.session_state.messages.append({"role": "user", "content": f"[DOCUMENTO ADJUNTO: {archivo.name}]\n\n{texto}",
                                      "mostrar": f"📎 Documento cargado: **{archivo.name}**", "es_doc": True})
    if truncado:
        st.warning(f"El documento es largo: solo se analizarán los primeros {nucleo.MAX_CHARS_DOC:,} caracteres.")
    else:
        st.success("Documento agregado al contexto. Ahora puedes hacer preguntas sobre él.")


# ---------- historial ----------
def _fuentes(m):
    fs = m.get("fuentes") or []
    if not fs:
        return
    citados = retrieval.ids_citados(m["content"])
    usados = [f for f in fs if f["n"] in citados]
    if usados:
        st.caption("📚 Fuentes: " + " · ".join(f"[F{f['n']}] {f['titulo']}" for f in usados))
    else:
        st.caption("📚 Material consultado: " + ", ".join(sorted({f["titulo"] for f in fs})))


def _feedback(ctx, i, m, materia):
    if m.get("feedback") is not None:
        st.caption("Gracias por tu opinión 💙")
        return
    c1, c2, _ = st.columns([1, 1, 8])
    for col, valor, icono in ((c1, 1, "👍"), (c2, -1, "👎")):
        if col.button(icono, key=f"fb_{i}_{valor}"):
            previos = [x for x in st.session_state.messages[:i] if x["role"] == "user" and not x.get("es_doc")]
            pregunta = previos[-1]["content"] if previos else ""
            ctx.repo.guardar_feedback(ctx.uid, ctx.gid, valor, materia, pregunta, m["content"],
                                      config.leer_bool("GUARDAR_TEXTO_FEEDBACK", True))
            m["feedback"] = valor
            st.rerun()


def _historial(ctx, materia):
    for i, m in enumerate(st.session_state.messages):
        avatar = nucleo.avatar_asistente() if m["role"] == "assistant" else None
        with st.chat_message(m["role"], avatar=avatar):
            st.markdown(m.get("mostrar", m["content"]))
            if m.get("tiene_imagen"):
                st.caption("📷 con foto")
            if m["role"] == "assistant" and not m.get("error"):
                _fuentes(m)
                _feedback(ctx, i, m, materia)


# ---------- avisos y apoyo ----------
def _avisos(ctx):
    if not ctx.grupos:
        return
    for a in comun.cacheado("avisos", lambda: ctx.repo.avisos_vigentes(ctx.grupos), 180)[:2]:
        st.info(f"📣 {a['texto']}")


def _apoyo():
    texto = st.session_state.get("apoyo")
    if texto:
        st.warning("🫶 " + texto)
        if st.button("Entendido", key="cerrar_apoyo"):
            st.session_state.apoyo = None
            st.rerun()


# ---------- foto y voz ----------
def _extras():
    """Foto del ejercicio y dictado por voz. Devuelve la imagen preparada (o None)."""
    imagen = None
    with st.expander("📷 Foto del ejercicio  ·  🎤 Dictar tu pregunta"):
        k = st.session_state.foto_key
        archivo = st.file_uploader("Foto del ejercicio o apunte (JPG o PNG)", type=["jpg", "jpeg", "png"], key=f"foto_{k}")
        if archivo is None and st.toggle("Usar la cámara", key=f"usar_cam_{k}"):
            archivo = st.camera_input("Toma la foto", key=f"cam_{k}")
        if archivo is not None:
            try:
                imagen = imagenes.preparar(archivo.getvalue())
                st.image(imagen["bytes"], width=160, caption="Se enviará con tu siguiente mensaje")
            except Exception:
                st.warning("No pude leer la foto. Prueba con otra.")
        if hasattr(st, "audio_input"):
            audio = st.audio_input("Dicta tu pregunta", key=f"audio_{k}")
            if audio is not None:
                datos = audio.getvalue()
                h = hashlib.md5(datos).hexdigest()
                if h != st.session_state.hash_audio:
                    st.session_state.hash_audio = h
                    texto = None
                    try:
                        with st.spinner("Escuchando…"):
                            texto = ia.transcribir(datos)
                    except ia.IAError as e:
                        st.warning(str(e))
                    if texto:
                        st.session_state.pendiente = texto
                        st.rerun()
    return imagen


def _hablar(texto):
    limpio = re.sub(r"[*_`#\[\]]", "", texto)[:1500]
    js = json.dumps(limpio).replace("</", "<\\/")
    components.html("<script>const u=new SpeechSynthesisUtterance(" + js + ");u.lang='es-MX';u.rate=0.95;"
                    "window.speechSynthesis.cancel();window.speechSynthesis.speak(u);</script>", height=0)


# ---------- responder ----------
def _responder(ctx, prompt, imagen, materia, modo):
    es_doc = not ctx.es_alumno
    uso = comun.uso_hoy(ctx)
    if not quotas.puede_enviar(uso, ctx.limite_diario):
        st.warning("Llegaste al límite de mensajes de hoy. ¡Mañana seguimos! 🔥")
        return
    mod = moderation.revisar(prompt)
    if mod["alerta"]:
        st.session_state.apoyo = moderation.mensaje_apoyo(mod["categorias"], config.linea_ayuda())
        if ctx.es_alumno and config.leer_bool("ALERTAS_BIENESTAR", True):
            try:
                ctx.repo.crear_alerta(ctx.uid, ctx.nombre, ctx.gid, mod["categorias"], prompt)
            except Exception:
                nucleo.logger.exception("No pude registrar la alerta de bienestar")

    frags, contexto = [], ""
    material = comun.fragmentos(ctx)
    if material:
        frags = retrieval.buscar(f"{prompt} {'' if materia == 'General' else materia}", material, MAX_FRAGS)
        contexto = retrieval.formatear_contexto(frags)
    prog = comun.progreso(ctx)
    dif = sorted(prog.get("dificultades", {}), key=prog["dificultades"].get, reverse=True)[:5]
    system = prompts2.instruccion_tutor(nucleo.PROMPTS[ctx.rol_nucleo], materia, modo, prog.get("memoria", ""), dif,
                                        contexto, bool(imagen), es_doc)

    nuevo = {"role": "user", "content": prompt}
    if imagen:
        nuevo["tiene_imagen"] = True
    st.session_state.messages.append(nuevo)
    with st.chat_message("user"):
        st.markdown(prompt)
        if imagen:
            st.caption("📷 con foto")
    with st.chat_message("assistant", avatar=nucleo.avatar_asistente()):
        placeholder = st.empty()
        with placeholder.container():
            espera = "Generando respuesta…" if es_doc else "Antorchita está pensando…"
            if not nucleo.mostrar_mascota("pensando", 140, "antorchita_pensando.json", key="pensando", etiqueta=espera):
                st.markdown(f"_{espera}_")
        estado = {"error": False}
        usar_codigo = materia in ("Matemáticas", "Ciencias") and config.leer_bool("CODIGO_EJECUCION", True)
        flujo = ia.stream_chat(st.session_state.messages, system, ctx.rol_nucleo, estado, imagen, usar_codigo)
        respuesta = st.write_stream(nucleo.con_animacion_hasta_primer_fragmento(flujo, placeholder))
        respuesta = (respuesta or "").strip() or MSG_ERROR
        if respuesta == MSG_ERROR:
            estado["error"] = True
    st.session_state.messages.append({"role": "assistant", "content": respuesta, "error": estado["error"],
                                      "fuentes": [{"n": i, "titulo": f["titulo"]} for i, f in enumerate(frags, 1)]})
    tin, tout = estado.get("tokens_in", 0), estado.get("tokens_out", 0)
    primero = next((m["content"] for m in st.session_state.messages if m["role"] == "user" and not m.get("es_doc")), prompt)
    tema = f"{materia}: {primero[:40]}"
    try:
        if not estado["error"]:
            ctx.repo.sumar_uso(ctx.uid, msgs=1, tin=tin, tout=tout)
            comun.uso_hoy(ctx, refrescar=True)
        ctx.repo.registrar_evento(ctx.uid, ctx.gid, "mensaje", materia, tema, not estado["error"], tin, tout)
        if ctx.es_alumno and not estado["error"]:
            ctx.repo.registrar_actividad(ctx.uid, "mensaje", tema=tema)
            comun.progreso(ctx, refrescar=True)
    except Exception:
        nucleo.logger.exception("No pude guardar el registro de uso")
    st.session_state.n_mensajes += 1
    st.session_state.celebrar = (not estado["error"]) and (ctx.es_alumno or nucleo.CELEBRAR_DOCENTE)
    if imagen:
        st.session_state.foto_key += 1   # vacía la foto ya enviada
    st.rerun()


# ---------- cierre de sesión de estudio ----------
def _terminar(ctx, materia):
    msgs = [m for m in st.session_state.messages if not m.get("es_doc") and not m.get("error")]
    if sum(1 for m in msgs if m["role"] == "user") < 2:
        st.warning("Conversa un poco más con Antorchita antes de guardar tu resumen.")
        return
    if not quotas.puede_generar(comun.uso_hoy(ctx)):
        st.warning("Llegaste al límite de resúmenes de hoy.")
        return
    conv = "\n".join(f"{'Alumno' if m['role'] == 'user' else 'Tutor'}: {m['content'][:400]}" for m in msgs[-14:])
    try:
        with st.spinner("Preparando tu resumen…"):
            texto, uso = ia.generar(prompts2.prompt_resumen(conv, materia), json_mode=True, max_tokens=1500)
            datos = quiz.extraer_json(texto)
    except (ia.IAError, ValueError):
        st.warning("No pude preparar el resumen ahora. Intenta de nuevo en un momento.")
        return
    hoy = config.hoy()
    tarjetas = [spaced.nueva(t["pregunta"], t["respuesta"], hoy, materia=materia)
                for t in datos.get("tarjetas", []) if isinstance(t, dict) and t.get("pregunta") and t.get("respuesta")][:4]
    ctx.repo.agregar_tarjetas(ctx.uid, tarjetas)
    ctx.repo.actualizar_memoria(ctx.uid, datos.get("memoria", ""), datos.get("dominados", []), datos.get("dificultades", []))
    ctx.repo.sumar_uso(ctx.uid, gen=1, tin=uso["tokens_in"], tout=uso["tokens_out"])
    comun.progreso(ctx, refrescar=True)
    comun.uso_hoy(ctx, refrescar=True)
    st.session_state.resumen_sesion = {"resumen": datos.get("resumen", ""), "tarjetas": len(tarjetas), "materia": materia}


def _mostrar_resumen():
    r = st.session_state.get("resumen_sesion")
    if not r:
        return
    st.success(f"**Resumen de hoy ({r['materia']}):** {r['resumen']}")
    st.caption(f"Se guardaron {r['tarjetas']} tarjetas en tu sección de Repaso.")
    st.download_button("⬇️ Descargar mi resumen", f"Resumen de estudio ({r['materia']})\n\n{r['resumen']}\n",
                       file_name="resumen_estudio.txt", key="descargar_resumen")
    if st.button("Cerrar resumen", key="cerrar_resumen"):
        st.session_state.resumen_sesion = None
        st.rerun()


# ---------- página ----------
def pagina_tutor(ctx):
    rol = ctx.rol_nucleo
    es_doc = not ctx.es_alumno
    nucleo.aplicar_tema(rol)
    comun.chip_rol(ctx)
    _avisos(ctx)

    if st.session_state.mostrar_adios:
        st.session_state.mostrar_adios = False
        ph = st.empty()
        with ph.container():
            if nucleo.mostrar_mascota("adios", 250, "antorchita_adios.json", key="adios"):
                time.sleep(2.5)
            else:
                st.info("¡Hasta pronto! Conversación limpiada. 👋")
                time.sleep(1.5)
        ph.empty()

    c1, c2 = st.columns(2)
    materia = c1.selectbox("Materia", comun.MATERIAS, key="materia")
    modo = None
    if es_doc:
        _subir_documento()
    else:
        modo = c2.radio("¿Cómo quieres trabajar?", list(prompts2.MODOS), horizontal=True, key="modo")

    _apoyo()
    _mostrar_resumen()
    _historial(ctx, materia)

    nivel_nuevo = st.session_state.pop("celebrar_nivel", None)
    if nivel_nuevo or st.session_state.get("celebrar", False):
        celebracion = nucleo.html_celebracion_fija(nivel_nuevo)
        if celebracion:
            nucleo._html(celebracion)

    limite = not quotas.puede_enviar(comun.uso_hoy(ctx), ctx.limite_diario)
    prompt = st.chat_input("Escribe tu mensaje..." if not limite else "Llegaste al límite de mensajes de hoy",
                           max_chars=nucleo.MAX_CHARS_MENSAJE, disabled=limite)
    imagen = _extras()
    if st.session_state.pendiente:
        prompt = st.session_state.pendiente
        st.session_state.pendiente = None
    if limite:
        prompt = None
        st.info("Alcanzaste el límite de mensajes de hoy. ¡Mañana puedes seguir! 🔥")

    if not st.session_state.messages and not prompt:
        prog = comun.progreso(ctx) if ctx.es_alumno else {}
        with st.container(key="hero"):
            _, centro, _ = st.columns([1, 2, 1])
            with centro:
                if not nucleo.mostrar_mascota("saludo", 340, "antorchita_saludo.json", key="saludo"):
                    if nucleo.existe(nucleo.LOGO):
                        st.image(nucleo.LOGO, width=220)
                if es_doc:
                    titulo, sub = ("Asistente Docente de la Escuela Modelo",
                                   "Planeación, material didáctico y análisis de documentos. Sube un archivo o elige una sugerencia.")
                else:
                    titulo, sub = (f"¡Hola, {ctx.nombre.split(' ')[0]}! Soy Antorchita 🎓",
                                   "No te doy las respuestas directas: te guío con preguntas para que descubras el camino.")
                st.markdown(f"<h2 class='hero-titulo'>{titulo}</h2>", unsafe_allow_html=True)
                st.markdown(f"<p class='hero-sub'>{sub}</p>", unsafe_allow_html=True)
                if prog.get("ultimo_tema"):
                    if st.button(f"↩️ Continuar con: {prog['ultimo_tema']}", use_container_width=True, key="continuar"):
                        st.session_state.pendiente = (f"Quiero seguir con {prog['ultimo_tema']}. "
                                                      "Recuérdame dónde nos quedamos y hazme una pregunta para retomar.")
                        st.rerun()
                for i, sug in enumerate(nucleo.SUGERENCIAS[rol]):
                    if st.button(sug, use_container_width=True, key=f"sug_{i}"):
                        st.session_state.pendiente = sug
                        st.rerun()

    ultimo = st.session_state.messages[-1] if st.session_state.messages else None
    if (not prompt and not limite and ultimo and ultimo["role"] == "assistant" and not ultimo.get("error")):
        with st.container(key="chips"):
            acciones = nucleo.ACCIONES_RAPIDAS[rol]
            cols = st.columns(len(acciones))
            for i, (etiqueta, texto) in enumerate(acciones):
                if cols[i].button(etiqueta, use_container_width=True, key=f"chip_{i}"):
                    st.session_state.pendiente = texto
                    st.rerun()
        b1, b2 = st.columns(2)
        if b1.button("🔊 Escuchar la respuesta", use_container_width=True, key="escuchar"):
            _hablar(ultimo["content"])
        if ctx.es_alumno and b2.button("✅ Terminar y guardar lo aprendido", use_container_width=True, key="terminar"):
            _terminar(ctx, materia)
            st.rerun()

    if prompt:
        _responder(ctx, prompt, imagen, materia, modo)

    if st.session_state.pop("celebrar", False) and nucleo.mascota_disponible() and not nucleo.usa_imagenes_fijas():
        nucleo._html(nucleo.html_celebracion())
