"""Configuración, lectura de secretos y fechas (zona horaria de Mérida, UTC-6 todo el año)."""
import json
import os
from datetime import datetime, timedelta, timezone

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None

TZ = timezone(timedelta(hours=-6))
VERSION_APP = "2.0"
VERSION_AVISO = "2026-10"


def ahora():
    return datetime.now(TZ)


def hoy():
    return ahora().strftime("%Y-%m-%d")


def iso():
    return ahora().isoformat(timespec="seconds")


def dias_atras(n):
    """Lista de las últimas n fechas (hoy primero)."""
    return [(ahora() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n)]


def secretos():
    """Devuelve st.secrets solo si existe un secrets.toml. Sin archivo, Streamlit muestra un cuadro rojo de error
    (y rompe set_page_config si ocurre antes), así que en ese caso no lo tocamos."""
    if st is None:
        return None
    try:
        existe = getattr(st.secrets, "load_if_toml_exists", None)
        if existe is not None and not existe():
            return None
        return st.secrets
    except Exception:
        return None


def leer(nombre, defecto=None):
    """Busca en los secretos de Streamlit y luego en variables de entorno/.env."""
    sec = secretos()
    if sec is not None:
        try:
            v = sec[nombre]
            if v not in (None, ""):
                return str(v)
        except Exception:
            pass
    v = os.getenv(nombre)
    return v if v else defecto


def leer_int(nombre, defecto):
    try:
        return int(float(leer(nombre, defecto)))
    except (TypeError, ValueError):
        return defecto


def leer_float(nombre, defecto):
    try:
        return float(leer(nombre, defecto))
    except (TypeError, ValueError):
        return defecto


def leer_bool(nombre, defecto):
    v = leer(nombre)
    if v is None:
        return defecto
    return str(v).strip().lower() in ("1", "true", "si", "sí", "yes", "on")


def cuenta_firebase():
    """Credenciales de la cuenta de servicio (tabla [firebase_cuenta] en secretos o FIREBASE_CUENTA_JSON)."""
    cuenta = None
    sec = secretos()
    if sec is not None:
        try:
            t = sec["firebase_cuenta"]
            cuenta = {k: t[k] for k in t}
        except Exception:
            cuenta = None
    if not cuenta:
        crudo = os.getenv("FIREBASE_CUENTA_JSON")
        if crudo:
            try:
                cuenta = json.loads(crudo)
            except ValueError:
                cuenta = None
    if cuenta and cuenta.get("private_key"):
        cuenta["private_key"] = str(cuenta["private_key"]).replace("\\n", "\n")
    if cuenta and cuenta.get("project_id") and cuenta.get("private_key"):
        return cuenta
    return None


def api_key_firebase():
    return leer("FIREBASE_API_KEY")


def admin_emails():
    return {e.strip().lower() for e in (leer("ADMIN_EMAILS", "") or "").split(",") if e.strip()}


LINEA_AYUDA = "Línea de la Vida: 800 911 2000 (gratuita, 24 horas)"


def linea_ayuda():
    return leer("LINEA_AYUDA", LINEA_AYUDA)
