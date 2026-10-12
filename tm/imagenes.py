"""Prepara fotos de ejercicios: reduce el tamaño y elimina metadatos (ubicación, etc.) antes de enviarlas a la IA."""
import io

MAX_BYTES = 8 * 1024 * 1024
MAX_LADO = 1280


def preparar(datos):
    from PIL import Image
    if len(datos) > MAX_BYTES:
        raise ValueError("La foto pesa demasiado (máximo 8 MB).")
    im = Image.open(io.BytesIO(datos))
    im = im.convert("RGB")
    im.thumbnail((MAX_LADO, MAX_LADO))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82)   # al reguardar se pierden los metadatos EXIF
    return {"bytes": buf.getvalue(), "mime": "image/jpeg"}
