"""Autenticación: Firebase Authentication (REST para iniciar sesión, Admin SDK para crear cuentas)."""
import secrets
import string

import requests

URL = "https://identitytoolkit.googleapis.com/v1/accounts:{}?key={}"
ERRORES = {
    "EMAIL_NOT_FOUND": "Correo o contraseña incorrectos.",
    "INVALID_PASSWORD": "Correo o contraseña incorrectos.",
    "INVALID_LOGIN_CREDENTIALS": "Correo o contraseña incorrectos.",
    "USER_DISABLED": "Esta cuenta está desactivada. Habla con el administrador.",
    "TOO_MANY_ATTEMPTS_TRY_LATER": "Demasiados intentos. Espera unos minutos e inténtalo de nuevo.",
    "INVALID_EMAIL": "El correo no es válido.",
}


class AuthError(Exception):
    pass


def _mensaje(resp):
    try:
        codigo = resp.json()["error"]["message"].split(" ")[0]
    except Exception:
        return "No pude conectar con el servicio de acceso. Intenta de nuevo."
    return ERRORES.get(codigo, "No pude iniciar sesión. Revisa tus datos o avisa al administrador.")


def login(api_key, email, password, http=requests):
    """Inicia sesión con correo y contraseña. Devuelve {'uid', 'email'}."""
    if not api_key:
        raise AuthError("Falta FIREBASE_API_KEY en la configuración.")
    try:
        r = http.post(URL.format("signInWithPassword", api_key),
                      json={"email": email.strip(), "password": password, "returnSecureToken": True}, timeout=15)
    except Exception:
        raise AuthError("No pude conectar con el servicio de acceso. Intenta de nuevo.")
    if r.status_code != 200:
        raise AuthError(_mensaje(r))
    d = r.json()
    return {"uid": d["localId"], "email": d.get("email", email).lower()}


def enviar_restablecer(api_key, email, http=requests):
    """Envía el correo para crear/cambiar contraseña. Siempre responde True (no revela si el correo existe)."""
    try:
        http.post(URL.format("sendOobCode", api_key), json={"requestType": "PASSWORD_RESET", "email": email.strip()}, timeout=15)
    except Exception:
        pass
    return True


def contrasena_temporal(n=12):
    alfabeto = string.ascii_letters + string.digits
    return "".join(secrets.choice(alfabeto) for _ in range(n)) + "!7"


def crear_cuenta(email, nombre):
    """Crea la cuenta en Firebase Auth (Admin SDK). Devuelve (uid, contraseña_temporal o None si ya existía)."""
    from firebase_admin import auth
    try:
        u = auth.get_user_by_email(email)
        return u.uid, None
    except auth.UserNotFoundError:
        pass
    clave = contrasena_temporal()
    u = auth.create_user(email=email, password=clave, display_name=nombre)
    return u.uid, clave


def desactivar_cuenta(uid, desactivar=True):
    from firebase_admin import auth
    auth.update_user(uid, disabled=desactivar)


def eliminar_cuenta(uid):
    from firebase_admin import auth
    auth.delete_user(uid)
