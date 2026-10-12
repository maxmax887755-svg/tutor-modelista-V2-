"""Almacenamiento genérico de documentos: LocalStore (demo/pruebas) y FirestoreStore (producción).
Regla de diseño: cada consulta usa filtros de igualdad (o UN solo array_contains/in) para no exigir índices."""
import copy
import json
import os
import threading
import uuid


def _coincide(doc, filtros):
    for campo, op, valor in filtros:
        v = doc.get(campo)
        if op == "==":
            ok = v == valor
        elif op == "in":
            ok = v in valor
        elif op == "array_contains":
            ok = isinstance(v, list) and valor in v
        else:
            raise ValueError(f"Operador no soportado: {op}")
        if not ok:
            return False
    return True


def _fusionar(base, nuevo):
    """Mezcla profunda de diccionarios (las listas se reemplazan, igual que en Firestore)."""
    for k, v in nuevo.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _fusionar(base[k], v)
        else:
            base[k] = copy.deepcopy(v)
    return base


class LocalStore:
    def __init__(self, ruta=None):
        self._d = {}
        self._ruta = ruta
        self._lock = threading.RLock()
        if ruta and os.path.exists(ruta):
            try:
                with open(ruta, "r", encoding="utf-8") as f:
                    self._d = json.load(f)
            except (OSError, ValueError):
                self._d = {}

    def _guardar(self):
        if not self._ruta:
            return
        try:
            with open(self._ruta, "w", encoding="utf-8") as f:
                json.dump(self._d, f, ensure_ascii=False, default=str)
        except OSError:
            pass

    def get(self, col, id):
        with self._lock:
            d = self._d.get(col, {}).get(id)
            return copy.deepcopy(d) if d is not None else None

    def set(self, col, id, data, merge=True):
        with self._lock:
            tabla = self._d.setdefault(col, {})
            if merge and id in tabla:
                _fusionar(tabla[id], data)
            else:
                tabla[id] = copy.deepcopy(data)
            self._guardar()

    def add(self, col, data):
        id = uuid.uuid4().hex[:20]
        self.set(col, id, data, merge=False)
        return id

    def delete(self, col, id):
        with self._lock:
            self._d.get(col, {}).pop(id, None)
            self._guardar()

    def query(self, col, filtros=(), limite=None):
        with self._lock:
            res = []
            for id, doc in self._d.get(col, {}).items():
                if _coincide(doc, filtros):
                    d = copy.deepcopy(doc)
                    d["id"] = id
                    res.append(d)
                    if limite and len(res) >= limite:
                        break
            return res

    def incr(self, col, id, deltas):
        with self._lock:
            doc = self._d.setdefault(col, {}).setdefault(id, {})
            for k, v in deltas.items():
                doc[k] = doc.get(k, 0) + v
            self._guardar()


class FirestoreStore:
    def __init__(self, cuenta):
        import firebase_admin
        from firebase_admin import credentials, firestore
        self._firestore = firestore
        if not firebase_admin._apps:
            firebase_admin.initialize_app(credentials.Certificate(cuenta))
        self.db = firestore.client()

    def get(self, col, id):
        d = self.db.collection(col).document(id).get()
        return d.to_dict() if d.exists else None

    def set(self, col, id, data, merge=True):
        self.db.collection(col).document(id).set(data, merge=merge)

    def add(self, col, data):
        _, ref = self.db.collection(col).add(data)
        return ref.id

    def delete(self, col, id):
        self.db.collection(col).document(id).delete()

    def query(self, col, filtros=(), limite=None):
        from google.cloud.firestore_v1.base_query import FieldFilter
        q = self.db.collection(col)
        for campo, op, valor in filtros:
            q = q.where(filter=FieldFilter(campo, op, valor))
        if limite:
            q = q.limit(limite)
        res = []
        for d in q.stream():
            x = d.to_dict() or {}
            x["id"] = d.id
            res.append(x)
        return res

    def incr(self, col, id, deltas):
        inc = {k: self._firestore.Increment(v) for k, v in deltas.items()}
        self.db.collection(col).document(id).set(inc, merge=True)


def crear_store(cuenta=None, ruta=None):
    return FirestoreStore(cuenta) if cuenta else LocalStore(ruta)
