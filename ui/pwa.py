"""Instalable en el celular (mejor esfuerzo): agrega el manifiesto y el ícono a la página.
Requiere 'enableStaticServing = true' en .streamlit/config.toml y la carpeta static/."""
import streamlit as st
import streamlit.components.v1 as components

from tm import config

_JS = """<script>
try {
  const d = window.parent.document;
  if (!d.querySelector('link[rel=manifest]')) {
    const l = d.createElement('link'); l.rel = 'manifest'; l.href = '/app/static/manifest.json'; d.head.appendChild(l);
    const i = d.createElement('link'); i.rel = 'apple-touch-icon'; i.href = '/app/static/icono-192.png'; d.head.appendChild(i);
    const m = d.createElement('meta'); m.name = 'theme-color'; m.content = '#061A66'; d.head.appendChild(m);
  }
} catch (e) {}
</script>"""


def inyectar():
    if config.leer_bool("PWA", True) and not st.session_state.get("_pwa"):
        st.session_state["_pwa"] = True
        components.html(_JS, height=0)
