"""Administración: usuarios (alta, CSV, baja), grupos, uso y costos, límites y privacidad."""
import csv
import io

import streamlit as st

import nucleo
from tm import auth, config, csvimport, quotas
from tm.repo import slug

from . import comun

ROLES = ["alumno", "docente", "orientador", "admin"]
NIVELES = ["secundaria", "preparatoria"]


def _asegurar_grupo(repo, nombre, nivel, docente_uid=None):
    if not nombre:
        return None
    gid = slug(nombre)
    if repo.get_grupo(gid) is None:
        repo.crear_grupo(nombre, nivel)
    if docente_uid:
        g = repo.get_grupo(gid)
        if docente_uid not in g.get("docentes", []):
            repo.actualizar_grupo(gid, docentes=g.get("docentes", []) + [docente_uid])
    return gid


def alta_usuario(ctx, fila):
    """Crea la cuenta y el perfil. Devuelve {'email', 'clave'|None, 'ok', 'detalle'}."""
    repo = ctx.repo
    email = fila["email"]
    try:
        if ctx.modo == "firebase":
            uid, clave = auth.crear_cuenta(email, fila["nombre"])
        else:
            uid, clave = "u_" + slug(email), None
        existente = repo.get_usuario(uid)
        gid = _asegurar_grupo(repo, fila.get("grupo"), fila["nivel"], uid if fila["rol"] == "docente" else None)
        grupos = [gid] if gid else []
        if existente:
            repo.actualizar_usuario(uid, nombre=fila["nombre"], rol=fila["rol"], nivel=fila["nivel"],
                                    grupos=sorted(set(existente.get("grupos", [])) | set(grupos)), activo=True)
        else:
            repo.crear_usuario(uid, fila["nombre"], email, fila["rol"], fila["nivel"], grupos)
        if ctx.modo == "firebase" and clave and config.api_key_firebase():
            auth.enviar_restablecer(config.api_key_firebase(), email)
        return {"email": email, "clave": clave, "ok": True, "detalle": "creado" if clave or ctx.modo != "firebase" else "ya existía"}
    except Exception:
        nucleo.logger.exception("No pude dar de alta a %s", email)
        return {"email": email, "clave": None, "ok": False, "detalle": "error al crear"}


def _csv_credenciales(resultados):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["email", "estado", "contraseña_temporal"])
    for r in resultados:
        w.writerow([r["email"], r["detalle"], r["clave"] or ""])
    return buf.getvalue()


def _tab_usuarios(ctx):
    usuarios = ctx.repo.listar_usuarios()
    st.caption(f"{len(usuarios)} usuario(s) en total.")
    if usuarios:
        st.dataframe([{"Nombre": u["nombre"], "Correo": u.get("email"), "Rol": u["rol"], "Nivel": u.get("nivel"),
                       "Grupos": ", ".join(u.get("grupos", [])), "Activo": u.get("activo", True)} for u in usuarios],
                     use_container_width=True)
    with st.expander("➕ Crear un usuario"):
        with st.form("alta_uno"):
            nombre = st.text_input("Nombre completo")
            email = st.text_input("Correo")
            c1, c2, c3 = st.columns(3)
            rol, nivel, grupo = c1.selectbox("Rol", ROLES), c2.selectbox("Nivel", NIVELES), c3.text_input("Grupo (ej. 1A Secundaria)")
            ok = st.form_submit_button("Crear", use_container_width=True)
        if ok:
            filas, errores = csvimport.parsear_csv(f"nombre,email,rol,nivel,grupo\n\"{nombre}\",{email},{rol},{nivel},\"{grupo}\"")
            if errores:
                st.warning(errores[0])
            else:
                r = alta_usuario(ctx, filas[0])
                st.session_state.credenciales = [r]
                (st.success if r["ok"] else st.error)(f"{r['email']}: {r['detalle']}. Se envió un correo para crear contraseña." if r["ok"] else "No pude crearlo.")
    with st.expander("📥 Importar desde CSV"):
        st.caption("Columnas: nombre,email,rol,nivel,grupo (rol y nivel opcionales). Máximo 500 filas.")
        archivo = st.file_uploader("Archivo CSV", type=["csv"], key="csv_usuarios")
        if archivo is not None:
            filas, errores = csvimport.parsear_csv(archivo.getvalue().decode("utf-8-sig", errors="replace"))
            for e in errores[:10]:
                st.warning(e)
            st.write(f"{len(filas)} fila(s) válidas.")
            if filas and st.button("Crear estos usuarios", key="crear_csv"):
                with st.spinner("Creando cuentas…"):
                    st.session_state.credenciales = [alta_usuario(ctx, f) for f in filas]
                st.success("Listo.")
    creds = st.session_state.get("credenciales")
    if creds:
        st.download_button("⬇️ Descargar lista (contraseñas temporales, se muestran una sola vez)", _csv_credenciales(creds),
                           file_name="usuarios_nuevos.csv", key="dl_creds")
    if usuarios:
        st.subheader("Gestionar un usuario")
        mapa = {f"{u['nombre']} ({u.get('email')})": u for u in usuarios}
        u = mapa[st.selectbox("Usuario", list(mapa), key="usuario_gest")]
        c1, c2 = st.columns(2)
        activo = u.get("activo", True)
        if c1.button("Desactivar" if activo else "Activar", use_container_width=True, key="toggle_activo"):
            ctx.repo.actualizar_usuario(u["uid"], activo=not activo)
            if ctx.modo == "firebase":
                try:
                    auth.desactivar_cuenta(u["uid"], activo)
                except Exception:
                    nucleo.logger.exception("No pude cambiar el estado de la cuenta")
            st.rerun()
        if ctx.modo == "firebase" and u.get("email") and c2.button("Enviar correo de contraseña", use_container_width=True, key="reset_usuario"):
            auth.enviar_restablecer(config.api_key_firebase(), u["email"])
            st.success("Correo enviado.")


def _tab_grupos(ctx):
    grupos = ctx.repo.listar_grupos()
    docentes = ctx.repo.listar_usuarios(rol="docente")
    st.dataframe([{"Grupo": g["nombre"], "Nivel": g.get("nivel"), "Docentes": len(g.get("docentes", [])),
                   "Meta semanal": g.get("meta_semanal")} for g in grupos], use_container_width=True)
    with st.form("nuevo_grupo"):
        nombre = st.text_input("Nombre del grupo (ej. 2B Preparatoria)")
        nivel = st.selectbox("Nivel", NIVELES)
        if st.form_submit_button("Crear grupo", use_container_width=True) and nombre.strip():
            _asegurar_grupo(ctx.repo, nombre.strip(), nivel)
            st.rerun()
    if grupos and docentes:
        st.subheader("Asignar docentes")
        mapa_g = {g["nombre"]: g for g in grupos}
        g = mapa_g[st.selectbox("Grupo", list(mapa_g), key="grupo_asig")]
        mapa_d = {f"{d['nombre']} ({d.get('email')})": d["uid"] for d in docentes}
        previos = [k for k, v in mapa_d.items() if v in g.get("docentes", [])]
        elegidos = st.multiselect("Docentes del grupo", list(mapa_d), default=previos, key="docentes_grupo")
        if st.button("Guardar docentes", key="guardar_docentes"):
            ctx.repo.actualizar_grupo(g["gid"], docentes=[mapa_d[k] for k in elegidos])
            for k in elegidos:
                ctx.repo.asignar_grupo(mapa_d[k], g["gid"])
            st.success("Docentes asignados.")
    alumnos = ctx.repo.listar_usuarios(rol="alumno")
    if grupos and alumnos:
        st.subheader("Asignar alumnos")
        g2 = mapa_g[st.selectbox("Grupo", list(mapa_g), key="grupo_asig_al")]
        mapa_a = {f"{a['nombre']} ({a.get('email')})": a["uid"] for a in alumnos}
        sel = st.multiselect("Alumnos a agregar a este grupo", list(mapa_a), key="alumnos_grupo")
        if st.button("Agregar alumnos", key="agregar_alumnos"):
            for k in sel:
                ctx.repo.asignar_grupo(mapa_a[k], g2["gid"])
            st.success("Alumnos agregados.")


def _tab_uso(ctx):
    cfg = ctx.repo.get_config()
    p_in, p_out = config.leer_float("COSTO_ENTRADA_POR_MILLON", 0.0), config.leer_float("COSTO_SALIDA_POR_MILLON", 0.0)
    filas = []
    for d in config.dias_atras(7):
        u = ctx.repo.uso_global(d)
        filas.append({"Día": d, "Mensajes": u.get("msgs", 0), "Generaciones": u.get("gen", 0),
                      "Tokens entrada": u.get("tin", 0), "Tokens salida": u.get("tout", 0),
                      "Costo estimado USD": quotas.costo_estimado(u.get("tin", 0), u.get("tout", 0), p_in, p_out)})
    hoy = filas[0]
    st.metric("Mensajes hoy", f"{hoy['Mensajes']} / {cfg['tope_global_mensajes']}")
    if hoy["Mensajes"] >= cfg["tope_global_mensajes"] * 0.8:
        st.warning("Estás cerca del tope diario de mensajes de la escuela. Revisa los límites o la cuota de la API.")
    st.dataframe(filas, use_container_width=True)
    if not (p_in or p_out):
        st.caption("Para ver costos en dinero, define COSTO_ENTRADA_POR_MILLON y COSTO_SALIDA_POR_MILLON en los secretos "
                   "(precios por millón de tokens, según la página de precios de Google).")


def _tab_config(ctx):
    cfg = ctx.repo.get_config()
    with st.form("form_cfg"):
        valores = {}
        for rol in ROLES:
            valores[f"limite_{rol}"] = st.number_input(f"Mensajes por día ({rol})", 1, 1000,
                                                       int(cfg.get(f"limite_{rol}", quotas.LIMITES_DEFECTO[rol])), key=f"cfg_{rol}")
        valores["tope_global_mensajes"] = st.number_input("Tope global de mensajes por día", 100, 100000, int(cfg["tope_global_mensajes"]), key="cfg_tope")
        if st.form_submit_button("Guardar límites", use_container_width=True):
            ctx.repo.set_config(**{k: int(v) for k, v in valores.items()})
            st.session_state.pop("_cache", None)
            st.success("Guardado.")


def _tab_privacidad(ctx):
    st.markdown("**Derecho de supresión.** Borra los datos de un usuario (progreso, tarjetas, retroalimentación, alertas, "
                "uso y perfil). La cuenta de acceso en Firebase no se elimina aquí.")
    usuarios = ctx.repo.listar_usuarios()
    if not usuarios:
        return
    mapa = {f"{u['nombre']} ({u.get('email')})": u["uid"] for u in usuarios}
    elegido = st.selectbox("Usuario", list(mapa), key="usuario_borrar")
    seguro = st.checkbox("Entiendo que esto no se puede deshacer", key="seguro_borrar")
    if st.button("Borrar sus datos", disabled=not seguro, key="borrar_datos"):
        ctx.repo.eliminar_datos_usuario(mapa[elegido])
        st.success("Datos borrados.")


def pagina_admin(ctx):
    nucleo.aplicar_tema(nucleo.ES_DOCENTE)
    st.header("🛠️ Administración")
    if ctx.modo == "local":
        st.warning("Estás en modo demo: los datos se guardan en un archivo local y no son permanentes en la nube.")
    pestañas = st.tabs(["👥 Usuarios", "🏫 Grupos", "💰 Uso y costos", "⚙️ Límites", "🔒 Privacidad"])
    for tab, fn in zip(pestañas, (_tab_usuarios, _tab_grupos, _tab_uso, _tab_config, _tab_privacidad)):
        with tab:
            fn(ctx)
