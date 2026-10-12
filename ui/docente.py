"""Panel docente: resumen del grupo, dificultades, calidad de respuestas, avisos, familias, reto y materiales."""
import csv
import io
import json

import streamlit as st

import nucleo
from tm import ia, prompts2, reports

from . import comun, reto


def _grupo_activo(ctx):
    grupos = ctx.repo.listar_grupos() if ctx.rol == "admin" else ctx.repo.grupos_de_docente(ctx.uid)
    if not grupos:
        st.info("Todavía no tienes grupos asignados. Pide a la administración que te asigne uno.")
        return None
    opciones = {g["nombre"]: g for g in grupos}
    return opciones[st.selectbox("Grupo", list(opciones), key="grupo_sel")]


def _tab_resumen(ctx, g):
    r = reports.resumen_grupo(ctx.repo, g["gid"], 7)
    a, b, c, d = st.columns(4)
    a.metric("Alumnos", r["alumnos"])
    b.metric("Activos (7 días)", r["activos"])
    c.metric("Quizzes y retos", r["quizzes"] + r["retos"])
    d.metric("Mensajes al tutor", r["mensajes"])
    if r["alumnos"] and r["activos"] < r["alumnos"]:
        st.info(f"{r['alumnos'] - r['activos']} alumno(s) no la usaron esta semana. Un recordatorio en clase suele ayudar.")
    if r["por_alumno"]:
        st.dataframe([{"Alumno": x["nombre"], "Actividad (7 días)": x["actividad"], "Racha": x["racha"], "Puntos": x["xp"]}
                      for x in r["por_alumno"]], use_container_width=True)
    st.caption("Aquí solo ves datos de uso y progreso, no las conversaciones de los alumnos.")


def _tab_dificultades(ctx, g):
    r = reports.resumen_grupo(ctx.repo, g["gid"], 7)
    if not r["dificultades"]:
        st.success("Aún no hay temas con dificultad registrada.")
        return
    st.subheader("Temas que más se les dificultan")
    st.bar_chart({t: n for t, n in r["dificultades"]})
    st.caption("Se calcula con los quizzes, retos y resúmenes de sesión. Úsalo para planear un repaso en clase.")


def _tab_calidad(ctx, g):
    fb = ctx.repo.listar_feedback(g["gid"])
    likes = sum(1 for f in fb if f.get("valor", 0) > 0)
    malos = [f for f in fb if f.get("valor", 0) < 0]
    a, b = st.columns(2)
    a.metric("👍 Respuestas útiles", likes)
    b.metric("👎 Respuestas por mejorar", len(malos))
    for f in malos[:15]:
        with st.expander(f"{f.get('dia', '')} · {f.get('materia', '')} · {f.get('pregunta', '')[:60]}"):
            st.markdown(f"**Pregunta:** {f.get('pregunta', '')}")
            st.markdown(f"**Respuesta:** {f.get('respuesta', '')}")
    if fb:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["dia", "materia", "valor", "pregunta", "respuesta"])
        for f in fb:
            w.writerow([f.get("dia"), f.get("materia"), f.get("valor"), f.get("pregunta"), f.get("respuesta")])
        st.download_button("⬇️ Descargar retroalimentación (CSV)", buf.getvalue(), file_name="retroalimentacion.csv", key="dl_fb")


def _tab_avisos(ctx, g):
    with st.form("form_aviso"):
        texto = st.text_area("Aviso para tu grupo (lo verán al abrir el tutor)", max_chars=300)
        dias = st.slider("Vigente por (días)", 1, 14, 5)
        if st.form_submit_button("Publicar aviso", use_container_width=True) and texto.strip():
            ctx.repo.publicar_aviso(g["gid"], texto.strip(), ctx.nombre, dias)
            st.success("Aviso publicado.")
    for a in ctx.repo.avisos_vigentes([g["gid"]]):
        st.markdown(f"- 📣 {a['texto']} _(hasta {a['hasta']})_")
    st.divider()
    meta = st.number_input("Meta semanal del grupo (quizzes y retos entre todos)", 10, 2000, int(g.get("meta_semanal", 100)), 10, key="meta_sem")
    if st.button("Guardar meta", key="guardar_meta"):
        ctx.repo.actualizar_grupo(g["gid"], meta_semanal=int(meta))
        st.success("Meta actualizada.")


def _tab_familias(ctx, g):
    alumnos = ctx.repo.listar_usuarios(rol="alumno", gid=g["gid"])
    if not alumnos:
        st.info("Este grupo aún no tiene alumnos.")
        return
    mapa = {a["nombre"]: a for a in alumnos}
    nombre = st.selectbox("Alumno", list(mapa), key="alumno_reporte")
    if st.button("Generar reporte para la familia", key="gen_reporte"):
        datos = reports.datos_familia(ctx.repo, mapa[nombre]["uid"])
        try:
            with st.spinner("Redactando…"):
                texto, _ = ia.generar(prompts2.prompt_reporte_familia(json.dumps(datos, ensure_ascii=False)),
                                      max_tokens=800, rol=nucleo.ES_DOCENTE)
        except ia.IAError:
            texto = reports.reporte_base(nombre, datos)
        st.session_state.reporte_familia = texto
    if st.session_state.get("reporte_familia"):
        st.text_area("Revisa y edita antes de compartir", st.session_state.reporte_familia, height=240, key="texto_reporte")
        st.download_button("⬇️ Descargar", st.session_state.get("texto_reporte") or st.session_state.reporte_familia,
                           file_name="reporte_familia.txt", key="dl_reporte")


def _tab_reto(ctx, g):
    materia = st.selectbox("Materia", comun.MATERIAS[1:], key="reto_doc_materia")
    if st.button("Ver / generar el reto de hoy", key="ver_reto_doc"):
        qs = reto.reto_del_dia(ctx, materia, g["gid"])
        if qs:
            for i, q in enumerate(qs, 1):
                st.markdown(f"**{i}. {q['pregunta']}**")
                for j, o in enumerate(q["opciones"]):
                    st.markdown(f"- {'✅ ' if j == q['correcta'] else ''}{o}")
                if q.get("explicacion"):
                    st.caption(q["explicacion"])


def pagina_grupo(ctx):
    nucleo.aplicar_tema(nucleo.ES_DOCENTE)
    st.header("👩‍🏫 Mi grupo")
    g = _grupo_activo(ctx)
    if not g:
        return
    pestañas = st.tabs(["📊 Resumen", "🧩 Dificultades", "👍 Calidad", "📣 Avisos y meta", "👨‍👩‍👧 Familias", "⭐ Reto"])
    for tab, fn in zip(pestañas, (_tab_resumen, _tab_dificultades, _tab_calidad, _tab_avisos, _tab_familias, _tab_reto)):
        with tab:
            fn(ctx, g)


def pagina_materiales(ctx):
    nucleo.aplicar_tema(nucleo.ES_DOCENTE)
    st.header("📚 Materiales de la escuela")
    st.caption("Lo que subas aquí lo usará el tutor para explicar con lo que se ve en clase y citar la fuente.")
    grupos = ctx.repo.listar_grupos() if ctx.rol == "admin" else ctx.repo.grupos_de_docente(ctx.uid)
    nombres = {g["nombre"]: g["gid"] for g in grupos}
    if ctx.rol == "admin":
        nombres = {"Toda la escuela": "*", **nombres}
    with st.form("form_material"):
        archivo = st.file_uploader("Archivo (PDF, DOCX o TXT)", type=["pdf", "docx", "txt"])
        titulo = st.text_input("Título (por ejemplo: Lectura 3 – Los cenotes)")
        materia = st.selectbox("Materia", comun.MATERIAS)
        destino = st.multiselect("¿Para qué grupos?", list(nombres))
        guardar = st.form_submit_button("Guardar material", use_container_width=True)
    if guardar:
        if archivo is None or not destino:
            st.warning("Elige un archivo y al menos un grupo.")
        else:
            try:
                texto = nucleo.extraer_texto(archivo.name, archivo.getvalue())
            except ValueError as e:
                texto = None
                st.warning(str(e))
            except Exception:
                nucleo.logger.exception("Error al leer material")
                texto = None
                st.warning("No pude leer el archivo.")
            if texto is not None and not texto:
                st.warning("No encontré texto en el archivo (¿es un escaneo?).")
            elif texto:
                _, n = ctx.repo.guardar_material(titulo.strip() or archivo.name, texto, [nombres[d] for d in destino], materia, ctx.uid)
                st.session_state.pop("_cache", None)
                st.success(f"Material guardado en {n} fragmento(s).")
    st.subheader("Materiales guardados")
    mats = ctx.repo.listar_materiales()
    if ctx.rol != "admin":
        propios = {g["gid"] for g in grupos}
        mats = [m for m in mats if m.get("autor") == ctx.uid or propios & set(m.get("gids", []))]
    if not mats:
        st.caption("Aún no hay materiales.")
    for m in mats:
        c1, c2 = st.columns([4, 1])
        c1.markdown(f"**{m['titulo']}** · {m.get('materia', '')} · {m.get('n', 0)} fragmento(s) · {'activo' if m.get('activo', True) else 'desactivado'}")
        if (ctx.rol == "admin" or m.get("autor") == ctx.uid) and c2.button("Eliminar", key=f"del_mat_{m['id']}"):
            ctx.repo.eliminar_material(m["id"])
            st.session_state.pop("_cache", None)
            st.rerun()
