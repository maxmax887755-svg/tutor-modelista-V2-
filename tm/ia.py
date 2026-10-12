"""Llamadas a Gemini: chat en streaming (con foto y cálculo opcional), JSON, texto y transcripción de voz."""
import nucleo
from nucleo import MSG_ERROR, MSG_SIN_CONFIG, logger

from . import prompts2


class IAError(Exception):
    pass


def _cliente():
    clave = nucleo.cargar_api_key()
    if not clave or nucleo.genai is None:
        raise IAError(MSG_SIN_CONFIG)
    return nucleo.obtener_cliente(clave)


def _config(system, max_tokens, nivel=None, tools=None, json_mode=False, temperatura=0.7):
    t = nucleo.types
    kw = dict(system_instruction=system, temperature=temperatura, max_output_tokens=max_tokens)
    if nivel:
        valor = getattr(getattr(t, "ThinkingLevel", None), nivel, nivel.lower())
        kw["thinking_config"] = t.ThinkingConfig(thinking_level=valor)
    if tools:
        kw["tools"] = tools
    if json_mode:
        kw["response_mime_type"] = "application/json"
    return t.GenerateContentConfig(**kw)


def _texto(frag):
    try:
        return getattr(frag, "text", None)
    except Exception:
        return None


def _uso(um):
    if um is None:
        return {"tokens_in": 0, "tokens_out": 0}
    return {"tokens_in": getattr(um, "prompt_token_count", 0) or 0,
            "tokens_out": (getattr(um, "candidates_token_count", 0) or 0) + (getattr(um, "thoughts_token_count", 0) or 0)}


def _contenidos(mensajes, imagen=None):
    t = nucleo.types
    hist = nucleo.preparar_historial(mensajes)
    salida = []
    for i, m in enumerate(hist):
        partes = [t.Part.from_text(text=m["content"])]
        if imagen and i == len(hist) - 1 and m["role"] == "user":
            partes.append(t.Part.from_bytes(data=imagen["bytes"], mime_type=imagen["mime"]))
        salida.append(t.Content(role=m["role"], parts=partes))
    return salida


def stream_chat(mensajes, system, rol, estado, imagen=None, usar_codigo=False):
    """Generador de texto. Reintenta sin razonamiento/herramientas y luego con el modelo de respaldo.
    Deja en 'estado' el error y los tokens usados."""
    try:
        client = _cliente()
    except IAError:
        estado["error"] = True
        yield MSG_SIN_CONFIG
        return
    contenido = _contenidos(mensajes, imagen)
    principal, nivel, respaldo = nucleo.modelos_para(rol)
    herramientas = [nucleo.types.Tool(code_execution=nucleo.types.ToolCodeExecution())] if usar_codigo else None
    intentos = [(principal, nivel, herramientas), (principal, None, None)]
    if respaldo and respaldo != principal:
        intentos.append((respaldo, None, None))
    for modelo, nivel_i, tools in intentos:
        emitido = False
        ultimo = None
        try:
            cfg = _config(system, nucleo.MAX_TOKENS[rol], nivel_i, tools)
            for frag in client.models.generate_content_stream(model=modelo, contents=contenido, config=cfg):
                if getattr(frag, "usage_metadata", None) is not None:
                    ultimo = frag.usage_metadata
                texto = _texto(frag)
                if texto:
                    emitido = True
                    yield texto
            if emitido:
                u = _uso(ultimo)
                estado["tokens_in"], estado["tokens_out"] = u["tokens_in"], u["tokens_out"]
                return
            logger.warning("Respuesta vacía del modelo %s", modelo)
        except Exception:
            logger.exception("Fallo al generar con %s (nivel=%s)", modelo, nivel_i)
            if emitido:
                yield "\n\n_(La respuesta se interrumpió. Intenta de nuevo.)_"
                return
    estado["error"] = True
    yield MSG_ERROR


def generar(prompt, system=None, json_mode=False, max_tokens=2048, rol=None, temperatura=0.5):
    """Respuesta completa (no streaming). Devuelve (texto, uso). Lanza IAError si todo falla."""
    rol = rol or nucleo.ROLES[0]
    client = _cliente()
    principal, nivel, respaldo = nucleo.modelos_para(rol)
    intentos = [(principal, nivel, json_mode), (principal, None, False)]
    if respaldo and respaldo != principal:
        intentos.append((respaldo, None, False))
    for modelo, nv, jm in intentos:
        try:
            cfg = _config(system, max_tokens, nv, None, json_mode=jm, temperatura=temperatura)
            r = client.models.generate_content(model=modelo, contents=prompt, config=cfg)
            texto = (getattr(r, "text", None) or "").strip()
            if texto:
                return texto, _uso(getattr(r, "usage_metadata", None))
        except Exception:
            logger.exception("Fallo al generar (no streaming) con %s", modelo)
    raise IAError(MSG_ERROR)


def transcribir(audio, mime="audio/wav"):
    """Pasa voz a texto con Gemini. 'audio' son los bytes de la grabación."""
    client = _cliente()
    t = nucleo.types
    modelo = nucleo.modelos_para(nucleo.ROLES[0])[0]
    try:
        r = client.models.generate_content(
            model=modelo, contents=[t.Part.from_bytes(data=audio, mime_type=mime), prompts2.PROMPT_TRANSCRIBIR])
        return (getattr(r, "text", None) or "").strip()
    except Exception:
        logger.exception("Fallo al transcribir")
        raise IAError("No pude entender el audio. Intenta de nuevo o escribe tu pregunta.")
