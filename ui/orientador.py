"""Bienestar: alertas de mensajes que indican riesgo. Información sensible: solo para orientación y administración."""
import streamlit as st

import nucleo

from . import comun


def pagina_bienestar(ctx):
    nucleo.aplicar_tema(nucleo.ES_DOCENTE)
    st.header("🫶 Bienestar")
    st.caption("Alertas generadas cuando un mensaje de un alumno sugiere riesgo (autolesión, violencia, acoso, abuso). "
               "Es una ayuda automática y puede fallar: sigue siempre el protocolo de la escuela. Información confidencial.")
    estado = st.radio("Mostrar", ["Nuevas", "Atendidas", "Todas"], horizontal=True, key="alertas_filtro")
    filtro = {"Nuevas": "nueva", "Atendidas": "atendida", "Todas": None}[estado]
    alertas = ctx.repo.listar_alertas(filtro)
    if not alertas:
        st.success("No hay alertas en esta vista.")
        return
    for a in alertas:
        with st.expander(f"{a.get('dia', '')} · {a.get('nombre', '—')} · {', '.join(a.get('categorias', []))}",
                         expanded=a.get("estado") == "nueva"):
            st.markdown(f"**Mensaje:** “{a.get('fragmento', '')}”")
            st.caption(f"Grupo: {a.get('gid') or '—'} · Estado: {a.get('estado')}")
            if a.get("estado") == "nueva" and st.button("Marcar como atendida", key=f"aten_{a['id']}"):
                ctx.repo.marcar_alerta(a["id"], ctx.nombre)
                st.rerun()
