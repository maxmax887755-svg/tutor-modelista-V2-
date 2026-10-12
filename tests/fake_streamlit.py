"""Simulador mínimo de Streamlit para probar la interfaz sin navegador.
No sustituye una prueba real, pero atrapa errores de nombres, flujos y datos."""
import runpy
import sys
import types


class Signal(BaseException):
    pass


class RerunSignal(Signal):
    pass


class StopSignal(Signal):
    pass


class Estado(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k)

    def __setattr__(self, k, v):
        self[k] = v

    def __delattr__(self, k):
        del self[k]


CLICKS, INPUTS, LOG, ERRORES = set(), {}, [], []
SECRETS = {}
session_state = Estado()


class Ctx:
    def __init__(self, st):
        self._st = st

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __getattr__(self, name):
        return getattr(self._st, name)


class FakeFile:
    def __init__(self, name, datos, tipo="application/octet-stream"):
        self.name, self._d, self.type = name, datos, tipo
        self.size = len(datos)

    def getvalue(self):
        return self._d


def _valor(key, label, defecto):
    k = key if key is not None else label
    if k in INPUTS:
        v = INPUTS[k]
    elif key is not None and key in session_state:
        v = session_state[key]
    else:
        v = defecto
    if key is not None:
        session_state[key] = v
    return v


def _click(key, label):
    for k in (key, label):
        if k is not None and k in CLICKS:
            CLICKS.discard(k)
            return True
    return False


class CacheRes:
    def __init__(self):
        self.memo = {}

    def __call__(self, *a, **k):
        def deco(f):
            def w(*args):
                clave = (f.__qualname__, args)
                if clave not in self.memo:
                    self.memo[clave] = f(*args)
                return self.memo[clave]
            return w
        if a and callable(a[0]):
            return deco(a[0])
        return deco

    def clear(self):
        self.memo.clear()


st = types.ModuleType("streamlit")
st.session_state = session_state
st.secrets = SECRETS
st.cache_resource = CacheRes()
st.cache_data = lambda *a, **k: (a[0] if a and callable(a[0]) else (lambda f: f))
st.set_page_config = lambda **k: None


def _registro(nombre):
    def f(*a, **k):
        LOG.append((nombre, a[0] if a else None))
        if nombre == "error":
            ERRORES.append(a[0] if a else None)
        return None
    return f


for _n in ("markdown", "html", "title", "header", "subheader", "caption", "write", "text", "info", "warning", "error",
           "success", "toast", "divider", "image", "logo", "audio", "progress", "metric", "dataframe", "bar_chart",
           "code", "json", "table", "balloons"):
    setattr(st, _n, _registro(_n))
st.button = lambda label, key=None, **k: _click(key, label)
st.form_submit_button = lambda label="Submit", key=None, **k: _click(key, label)
st.download_button = lambda *a, **k: False
st.text_input = lambda label, value="", key=None, **k: _valor(key, label, value)
st.text_area = lambda label, value="", height=None, key=None, **k: _valor(key, label, value)
st.number_input = lambda label, min_value=None, max_value=None, value=0, step=None, key=None, **k: _valor(key, label, value)
st.slider = lambda label, min_value=None, max_value=None, value=None, step=None, key=None, **k: _valor(key, label, value)
st.select_slider = lambda label, options=(), value=None, key=None, **k: _valor(key, label, value if value is not None else options[0])
st.checkbox = lambda label, value=False, key=None, **k: _valor(key, label, value)
st.toggle = st.checkbox
st.radio = lambda label, options, index=0, key=None, **k: _valor(key, label, options[index] if index is not None and options else None)
st.selectbox = lambda label, options, index=0, key=None, **k: _valor(key, label, options[index] if index is not None and options else None)
st.multiselect = lambda label, options=(), default=None, key=None, **k: _valor(key, label, list(default or []))
st.file_uploader = lambda label, type=None, key=None, **k: INPUTS.get(key if key is not None else label)
st.camera_input = lambda label, key=None, **k: INPUTS.get(key if key is not None else label)
st.audio_input = lambda label, key=None, **k: INPUTS.get(key if key is not None else label)


def _chat_input(placeholder="", max_chars=None, disabled=False, key=None, **k):
    return None if disabled else INPUTS.pop("chat", None)


st.chat_input = _chat_input
st.columns = lambda spec, **k: [Ctx(st) for _ in range(spec if isinstance(spec, int) else len(spec))]
st.tabs = lambda labels, **k: [Ctx(st) for _ in labels]
for _n in ("container", "expander", "form", "spinner", "status", "chat_message", "empty"):
    setattr(st, _n, lambda *a, **k: Ctx(st))
st.sidebar = Ctx(st)
st.write_stream = lambda gen: "".join(x for x in gen if isinstance(x, str))


def _rerun():
    raise RerunSignal()


def _stop():
    raise StopSignal()


st.rerun, st.stop = _rerun, _stop
comp = types.ModuleType("streamlit.components")
comp1 = types.ModuleType("streamlit.components.v1")
comp1.html = _registro("components_html")
comp.v1 = comp1
st.components = comp
sys.modules.update({"streamlit": st, "streamlit.components": comp, "streamlit.components.v1": comp1})


def reiniciar():
    CLICKS.clear(); INPUTS.clear(); LOG.clear(); ERRORES.clear(); SECRETS.clear()
    session_state.clear()
    st.cache_resource.clear()


def ejecutar(app, max_reruns=10):
    """Ejecuta app.py como lo haría Streamlit, repitiendo mientras haya st.rerun()."""
    for _ in range(max_reruns):
        try:
            runpy.run_path(app, run_name="__main__")
            return
        except RerunSignal:
            continue
        except StopSignal:
            return
    raise RuntimeError("Demasiados reruns seguidos (posible bucle).")
