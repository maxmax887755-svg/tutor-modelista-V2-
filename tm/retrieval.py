"""Búsqueda en el material de la escuela: troceo de texto y ranking BM25 (sin servicios externos)."""
import math
import re
import unicodedata
from collections import Counter

STOP = set("""de la el en y a los las un una unos unas que es se por con para del al lo como mas pero sus le ya o fue
este si porque esta son entre cuando muy sin sobre tambien me hasta hay donde quien desde todo nos durante todos uno
les ni contra otros ese eso ante ellos e esto mi antes algunos otro otras otra tanto esa estos mucho quienes nada
muchos cual poco ella estar estas algunas algo nosotros mis tu te ti tus ellas""".split())


def normalizar(t):
    t = unicodedata.normalize("NFD", str(t).lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def tokens(t):
    res = []
    for w in re.findall(r"[a-z0-9]+", normalizar(t)):
        if len(w) < 2 or w in STOP:
            continue
        if len(w) > 4 and w.endswith("es"):
            w = w[:-2]
        elif len(w) > 3 and w.endswith("s"):
            w = w[:-1]
        res.append(w)
    return res


def trocear(texto, max_chars=1100):
    """Divide un texto en fragmentos de hasta max_chars, respetando párrafos y oraciones."""
    texto = re.sub(r"[ \t]+", " ", str(texto).replace("\r", ""))
    parrafos = [p.strip() for p in re.split(r"\n\s*\n", texto) if p.strip()]
    frags, actual = [], ""
    for p in parrafos:
        while len(p) > max_chars:
            corte = p.rfind(". ", 0, max_chars)
            corte = corte + 1 if corte > max_chars // 2 else max_chars
            if actual:
                frags.append(actual)
                actual = ""
            frags.append(p[:corte].strip())
            p = p[corte:].strip()
        if not p:
            continue
        if len(actual) + len(p) + 2 <= max_chars:
            actual = (actual + "\n\n" + p).strip()
        else:
            if actual:
                frags.append(actual)
            actual = p
    if actual:
        frags.append(actual)
    return frags


def buscar(consulta, fragmentos, k=4):
    """fragmentos: lista de dicts con 'texto' (y opcional 'titulo'). Devuelve los k más relevantes."""
    q = tokens(consulta)
    if not q or not fragmentos:
        return []
    docs = [tokens(f.get("texto", "") + " " + f.get("titulo", "")) for f in fragmentos]
    n = len(docs)
    avgdl = (sum(len(d) for d in docs) / n) or 1
    df = Counter()
    for d in docs:
        df.update(set(d))
    k1, b = 1.5, 0.75
    res = []
    for f, d in zip(fragmentos, docs):
        tf = Counter(d)
        dl = len(d) or 1
        s = 0.0
        for t in set(q):
            if t in tf:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * dl / avgdl))
        if s > 0:
            res.append({**f, "puntaje": round(s, 3)})
    res.sort(key=lambda x: -x["puntaje"])
    return res[:k]


def formatear_contexto(frags, max_chars=1100):
    """Texto para el modelo: cada fragmento con su etiqueta [F1], [F2]..."""
    return "\n\n".join(f"[F{i}] ({f.get('titulo', 'material')}) {f['texto'][:max_chars]}"
                       for i, f in enumerate(frags, 1))


def ids_citados(respuesta):
    return sorted({int(x) for x in re.findall(r"\[F(\d+)\]", respuesta or "")})
