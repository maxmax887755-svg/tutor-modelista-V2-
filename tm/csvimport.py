"""Importación masiva de usuarios desde CSV: nombre,email,rol,nivel,grupo"""
import csv
import io
import re

ROLES_VALIDOS = {"alumno", "docente", "orientador", "admin"}
NIVELES_VALIDOS = {"secundaria", "preparatoria"}
MAX_FILAS = 500
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def parsear_csv(texto):
    """Devuelve (filas_validas, errores[str])."""
    filas, errores, vistos = [], [], set()
    lector = csv.DictReader(io.StringIO(texto.lstrip("\ufeff")))
    campos = {(c or "").strip().lower() for c in (lector.fieldnames or [])}
    if not {"nombre", "email"} <= campos:
        return [], ["El CSV debe tener al menos las columnas: nombre,email (y opcional rol,nivel,grupo)."]
    for i, fila in enumerate(lector, start=2):
        if len(filas) >= MAX_FILAS:
            errores.append(f"Se ignoraron filas después de {MAX_FILAS}.")
            break
        f = {(k or "").strip().lower(): (v or "").strip() for k, v in fila.items()}
        email = f.get("email", "").lower()
        rol = (f.get("rol") or "alumno").lower()
        nivel = (f.get("nivel") or "secundaria").lower()
        if not f.get("nombre") or not EMAIL.match(email):
            errores.append(f"Fila {i}: falta el nombre o el correo es inválido.")
        elif rol not in ROLES_VALIDOS or nivel not in NIVELES_VALIDOS:
            errores.append(f"Fila {i}: rol o nivel inválido ({rol}/{nivel}).")
        elif email in vistos:
            errores.append(f"Fila {i}: correo repetido ({email}).")
        else:
            vistos.add(email)
            filas.append({"nombre": f["nombre"], "email": email, "rol": rol, "nivel": nivel, "grupo": f.get("grupo", "")})
    return filas, errores
