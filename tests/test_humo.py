"""Pruebas de humo de la interfaz con Streamlit simulado y una IA falsa."""
import json
import os
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "tests"))
os.chdir(RAIZ)
import fake_streamlit as fs  # noqa: E402  (instala el streamlit falso antes de importar la app)

import nucleo  # noqa: E402
from tm import config, ia, spaced  # noqa: E402
from ui import comun  # noqa: E402

APP = os.path.join(RAIZ, "app.py")
QUIZ_JSON = json.dumps({"preguntas": [
    {"pregunta": f"Pregunta {i}", "opciones": [f"A{i}", f"B{i}", f"C{i}", f"D{i}"], "correcta": 0, "explicacion": f"Porque {i}"}
    for i in range(3)]})
RESUMEN_JSON = json.dumps({"resumen": "Repasaste fracciones.", "dominados": ["sumas"], "dificultades": ["fracciones"],
                           "tarjetas": [{"pregunta": "¿Qué es el denominador?", "respuesta": "La parte de abajo"}],
                           "memoria": "Va bien con sumas, le cuestan fracciones."})
SISTEMAS = []


def falso_stream(mensajes, system, rol, estado, imagen=None, usar_codigo=False):
    SISTEMAS.append({"system": system, "imagen": bool(imagen), "codigo": usar_codigo})
    estado["tokens_in"], estado["tokens_out"] = 120, 40
    yield "Respuesta de prueba "
    yield "[F1]. ¿Qué piensas tú?"


def falso_generar(prompt, system=None, json_mode=False, max_tokens=2048, rol=None, temperatura=0.5):
    uso = {"tokens_in": 10, "tokens_out": 5}
    if "Resume esta sesión" in prompt:
        return RESUMEN_JSON, uso
    if "quiz de" in prompt or "mini reto" in prompt:
        return QUIZ_JSON, uso
    return "Reporte de prueba para la familia.", uso


ia.stream_chat, ia.generar = falso_stream, falso_generar
ia.transcribir = lambda audio, mime="audio/wav": "texto dictado de prueba"


class Base(unittest.TestCase):
    def setUp(self):
        fs.reiniciar()
        SISTEMAS.clear()
        self.tmp = tempfile.TemporaryDirectory()
        fs.SECRETS["DATOS_LOCALES"] = os.path.join(self.tmp.name, "datos.json")

    def tearDown(self):
        self.tmp.cleanup()

    def correr(self, clicks=(), **inputs):
        fs.CLICKS.update(clicks)
        fs.INPUTS.update(inputs)
        fs.ejecutar(APP)
        self.assertEqual(fs.ERRORES, [], f"La interfaz mostró errores: {fs.ERRORES}")

    def repo(self):
        return comun.obtener_repo()[0]

    def entrar(self, quien):
        self.correr(["Entrar"], **{"Entrar como": quien})
        self.assertIsNotNone(fs.session_state.usuario)
        self.correr(["Continuar"], acepto_aviso=True)   # consentimiento
        self.assertTrue(fs.session_state.usuario["consentimiento"])

    def ir(self, pagina, **inputs):
        self.correr(pagina_sel=pagina, **inputs)


class Acceso(Base):
    def test_login_pide_codigo(self):
        fs.SECRETS["ACCESS_CODE"] = "secreto"
        fs.CLICKS.add("Entrar")
        fs.INPUTS.update({"Código de acceso": "mal"})
        fs.ejecutar(APP)
        self.assertIsNone(fs.session_state.usuario)
        self.assertEqual(fs.ERRORES, ["Código incorrecto."])
        fs.ERRORES.clear()
        self.correr(["Entrar"], **{"Código de acceso": "secreto", "Entrar como": "Docente"})
        self.assertEqual(fs.session_state.usuario["rol"], "docente")

    def test_sin_aviso_de_demo_y_con_boton_del_creador(self):
        self.correr()
        self.assertFalse(any("datos no son reales" in str(a) for n, a in fs.LOG))
        self.assertFalse(any("Firebase" in str(a) for n, a in fs.LOG if n == "info"))
        self.correr(["creador_login"])
        self.assertTrue(any(n == "info" and "Maximiliano Ávila Castillo" in str(a) for n, a in fs.LOG))
        self.entrar("Alumno de Secundaria")
        fs.LOG.clear()
        self.correr(["creador_lateral"])
        self.assertTrue(any(n == "info" and "Maximiliano Ávila Castillo" in str(a) for n, a in fs.LOG))

    def test_tema_fuerza_letras_claras(self):
        self.correr()
        html = " ".join(str(a) for n, a in fs.LOG if n == "html")
        self.assertIn("color-scheme: dark", html)
        self.assertIn("#F4F8FF !important", html)

    def test_consentimiento_obligatorio(self):
        self.correr(["Entrar"], **{"Entrar como": "Alumno de Secundaria"})
        self.assertFalse(fs.session_state.usuario.get("consentimiento"))
        self.correr()   # sin aceptar sigue en el aviso
        self.assertFalse(self.repo().get_usuario("demo_alumno_sec")["consentimiento"])

    def test_firebase_admin_y_cuenta_inactiva(self):
        from unittest import mock
        from tm import auth
        repo = self.repo()
        fs.SECRETS.update({"ADMIN_EMAILS": "jefe@escuela.mx", "FIREBASE_API_KEY": "k"})
        falso = lambda k, e, p, http=None: {"uid": "uid_jefe" if "jefe" in e else "uid_x", "email": e.lower()}
        with mock.patch.object(comun, "obtener_repo", lambda: (repo, "firebase")), mock.patch.object(auth, "login", falso):
            self.correr(["Entrar"], **{"Correo de la escuela": "jefe@escuela.mx", "Contraseña": "x"})
            self.assertEqual(fs.session_state.usuario["rol"], "admin")   # el primer admin se crea solo
            fs.session_state.clear()
            fs.ERRORES.clear()
            fs.CLICKS.add("Entrar")
            fs.INPUTS.update({"Correo de la escuela": "otro@escuela.mx", "Contraseña": "x"})
            fs.ejecutar(APP)
            self.assertIsNone(fs.session_state.usuario)   # sin perfil: no entra
            self.assertTrue(fs.ERRORES)
            repo.crear_usuario("uid_x", "Otro", "otro@escuela.mx", activo=False)
            fs.ERRORES.clear()
            fs.CLICKS.add("Entrar")
            fs.ejecutar(APP)
            self.assertIsNone(fs.session_state.usuario)   # desactivada: no entra
            self.assertTrue(fs.ERRORES)

    def test_error_de_firebase_no_deja_entrar(self):
        from unittest import mock
        repo = self.repo()
        with mock.patch.object(comun, "obtener_repo", lambda: (repo, "firebase_error")):
            fs.ejecutar(APP)
            self.assertIsNone(fs.session_state.usuario)
            self.assertTrue(fs.ERRORES)


class Alumno(Base):
    def setUp(self):
        super().setUp()
        self.entrar("Alumno de Secundaria")

    def test_chat_completo(self):
        repo = self.repo()
        repo.guardar_material("Fracciones", "Una fracción tiene numerador y denominador.", ["demo"], "Matemáticas", "demo_docente")
        self.ir("💬 Tutor", materia="Matemáticas")
        self.correr(chat="¿Cómo sumo fracciones y el denominador?")
        m = fs.session_state.messages
        self.assertEqual([x["role"] for x in m], ["user", "assistant"])
        self.assertIn("Respuesta de prueba", m[1]["content"])
        self.assertEqual(m[1]["fuentes"][0]["titulo"], "Fracciones")
        self.assertIn("[F1]", SISTEMAS[-1]["system"])           # el material llegó al modelo
        self.assertIn("Matemáticas", SISTEMAS[-1]["system"])
        self.assertTrue(SISTEMAS[-1]["codigo"])                 # cálculo activado en matemáticas
        p = repo.get_progreso("demo_alumno_sec")
        self.assertEqual((p["xp"], p["mensajes"], p["racha"]), (1, 1, 1))
        u = repo.uso_diario("demo_alumno_sec")
        self.assertEqual((u["msgs"], u["tin"], u["tout"]), (1, 120, 40))
        self.assertEqual(len(repo.eventos_grupo("demo")), 1)
        # retroalimentación
        self.correr(["fb_1_-1"])
        self.assertEqual(repo.listar_feedback("demo")[0]["valor"], -1)
        self.assertEqual(fs.session_state.messages[1]["feedback"], -1)

    def test_limite_diario(self):
        repo = self.repo()
        repo.set_config(limite_alumno=2)
        fs.session_state.pop("_cache", None)
        for i in range(3):
            self.correr(chat=f"pregunta {i}")
        self.assertEqual(len([m for m in fs.session_state.messages if m["role"] == "user"]), 2)
        self.assertEqual(repo.uso_diario("demo_alumno_sec")["msgs"], 2)

    def test_bienestar_crea_alerta_y_orientador_la_atiende(self):
        self.correr(chat="a veces siento que me quiero morir")
        self.assertIsNotNone(fs.session_state.apoyo)
        self.assertIn("911", fs.session_state.apoyo)
        alertas = self.repo().listar_alertas("nueva")
        self.assertEqual(len(alertas), 1)
        fs.session_state.clear()
        self.entrar("Orientador")
        self.ir("🫶 Bienestar")
        self.correr([f"aten_{alertas[0]['id']}"])
        self.assertEqual(self.repo().listar_alertas("nueva"), [])

    def test_foto_y_voz(self):
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (400, 300), (10, 90, 200)).save(buf, "PNG")
        self.correr(chat="mira mi ejercicio", **{"foto_0": fs.FakeFile("ej.png", buf.getvalue())})
        self.assertTrue(SISTEMAS[-1]["imagen"])
        self.assertIn("foto", SISTEMAS[-1]["system"].lower())
        self.assertEqual(fs.session_state.foto_key, 1)
        self.correr(**{"audio_1": fs.FakeFile("a.wav", b"RIFFxxxx")})
        self.assertEqual(fs.session_state.messages[-2]["content"], "texto dictado de prueba")

    def test_terminar_sesion_guarda_memoria_y_tarjetas(self):
        self.correr(chat="primera pregunta")
        self.correr(chat="segunda pregunta")
        self.correr(["terminar"])
        repo = self.repo()
        p = repo.get_progreso("demo_alumno_sec")
        self.assertIn("fracciones", p["memoria"])
        self.assertEqual(len(repo.tarjetas_usuario("demo_alumno_sec")), 1)
        self.assertIn("Repasaste", fs.session_state.resumen_sesion["resumen"])
        self.correr(chat="otra")   # la memoria llega al modelo en la siguiente sesión
        self.assertIn("fracciones", SISTEMAS[-1]["system"])

    def test_quiz_completo_y_repaso(self):
        self.ir("🧠 Quiz", **{"¿Sobre qué tema?": "fracciones"})
        self.correr(["Crear mi quiz"], **{"¿Sobre qué tema?": "fracciones"})
        q = fs.session_state.quiz
        self.assertEqual(len(q["preguntas"]), 3)
        elegidas = {}
        for i, pr in enumerate(q["preguntas"]):
            correcta = pr["opciones"][pr["correcta"]]
            mala = next(o for o in pr["opciones"] if o != correcta)
            elegidas[f"quiz_{i}"] = correcta if i < 2 else mala     # 2 de 3
        self.correr(["Calificar"], **elegidas)
        r = fs.session_state.quiz["resultado"]
        self.assertEqual(r["aciertos"], 2)
        repo = self.repo()
        p = repo.get_progreso("demo_alumno_sec")
        self.assertEqual(p["xp"], 5 + 2 * 3)
        self.assertEqual(len(repo.tarjetas_usuario("demo_alumno_sec")), 1)        # la fallada
        self.assertEqual(len(repo.eventos_grupo("demo")), 1)
        self.correr(["otro_quiz"])
        self.assertIsNone(fs.session_state.quiz)
        # repaso: la tarjeta vence mañana, la adelantamos para probar
        t = repo.tarjetas_usuario("demo_alumno_sec")[0]
        t["proxima"] = config.hoy()
        repo.guardar_tarjeta(t["tid"], t)
        self.ir("🔁 Repaso")
        self.correr(["empezar_repaso"])
        cola = fs.session_state.repaso["cola"]
        self.assertEqual(len(cola), 1)
        self.correr(["rp_ok_0"], rp_0=cola[0]["opciones"][cola[0]["correcta"]])
        self.correr(["rp_sig_0"])
        self.assertEqual(fs.session_state.repaso["aciertos"], 1)
        self.assertEqual(repo.tarjetas_pendientes("demo_alumno_sec"), [])
        self.assertEqual(repo.tarjetas_usuario("demo_alumno_sec")[0]["caja"], 2)
        self.correr()   # termina y suma puntos
        self.assertTrue(fs.session_state.repaso["registrado"])

    def test_reto_del_dia(self):
        self.ir("⭐ Reto del día", reto_materia="Matemáticas")
        self.correr(["ver_reto"])
        self.assertEqual(self.repo().get_reto("demo", "Matemáticas")["preguntas"][0]["pregunta"], "Pregunta 0")
        qs = self.repo().get_reto("demo", "Matemáticas")["preguntas"]
        elegidas = {f"reto_Matemáticas_{i}": q["opciones"][q["correcta"]] for i, q in enumerate(qs)}
        self.correr(["Calificar"], **elegidas)
        self.assertTrue(self.repo().reto_hecho("demo_alumno_sec", "Matemáticas"))
        self.assertEqual(self.repo().get_progreso("demo_alumno_sec")["retos"], 1)
        self.correr()
        self.assertEqual(len(fs.ERRORES), 0)

    def test_progreso_y_avisos(self):
        repo = self.repo()
        repo.publicar_aviso("demo", "Mañana examen", "demo_docente", 3)
        fs.session_state.pop("_cache", None)
        self.correr(chat="hola")
        self.ir("🔥 Mi progreso")
        self.assertTrue(any(n == "metric" for n, _ in fs.LOG))
        self.ir("💬 Tutor")
        self.assertTrue(any(n == "info" and "Mañana examen" in str(a) for n, a in fs.LOG))

    def test_limpiar_y_cerrar_sesion(self):
        self.correr(chat="hola")
        self.correr(["limpiar"])
        self.assertEqual(fs.session_state.messages, [])
        self.correr(["salir"])
        self.assertIsNone(fs.session_state.get("usuario"))

    def test_accesibilidad(self):
        self.correr(acc_tam=130, acc_fuente=True, acc_contraste=True, acc_movimiento=True)
        from ui import accesibilidad
        css = accesibilidad.css()
        for esperado in ("130%", "Lexend", "#000", "animation: none"):
            self.assertIn(esperado, css)

    def test_prepa_usa_su_prompt(self):
        fs.session_state.clear()
        self.entrar("Alumno de Preparatoria")
        self.correr(chat="hola")
        self.assertIn("Preparatoria", SISTEMAS[-1]["system"])


class Docente(Base):
    def setUp(self):
        super().setUp()
        self.entrar("Docente")

    def test_asistente_con_documento(self):
        doc = fs.FakeFile("plan.txt", "Plan de clase sobre los cenotes de Yucatán.".encode("utf-8"))
        self.correr(**{"uploader_0": doc})
        self.assertTrue(fs.session_state.messages[0]["es_doc"])
        self.correr(chat="Genera 3 preguntas")
        self.assertNotIn("EXPLÍCAME", SISTEMAS[-1]["system"])
        self.assertEqual(len(fs.session_state.messages), 3)

    def test_panel_y_materiales(self):
        repo = self.repo()
        repo.crear_usuario("al1", "Ana", "ana@x.mx", "alumno", grupos=["demo"])
        repo.registrar_evento("al1", "demo", "quiz", "Matemáticas", "Fracciones")
        repo.registrar_actividad("al1", "quiz", xp=8)
        repo.anotar_resultado("al1", "Fracciones", 0, 3)
        repo.guardar_feedback("al1", "demo", -1, "Matemáticas", "¿Cómo?", "Respuesta confusa")
        self.ir("👩‍🏫 Mi grupo", alumno_reporte="Ana")
        self.correr(["gen_reporte"])
        self.assertIn("Reporte", fs.session_state.reporte_familia)
        self.correr(["ver_reto_doc"], reto_doc_materia="Matemáticas")
        self.assertIsNotNone(repo.get_reto("demo", "Matemáticas"))
        self.correr(["guardar_meta"], meta_sem=50)
        self.assertEqual(repo.get_grupo("demo")["meta_semanal"], 50)
        # materiales
        archivo = fs.FakeFile("lectura.txt", "Los cenotes son pozos naturales.".encode("utf-8"))
        self.ir("📚 Materiales")
        self.correr(["Guardar material"], **{"Archivo (PDF, DOCX o TXT)": archivo, "¿Para qué grupos?": ["Demo"],
                                              "Título (por ejemplo: Lectura 3 – Los cenotes)": "Cenotes"})
        self.assertEqual(repo.listar_materiales("demo")[0]["titulo"], "Cenotes")
        mid = repo.listar_materiales("demo")[0]["id"]
        self.correr([f"del_mat_{mid}"])
        self.assertEqual(repo.listar_materiales("demo"), [])

    def test_docente_sin_grupos(self):
        repo = self.repo()
        repo.actualizar_grupo("demo", docentes=[])
        self.ir("👩‍🏫 Mi grupo")


class Admin(Base):
    def setUp(self):
        super().setUp()
        self.entrar("Administrador")

    def test_panel_y_csv(self):
        self.ir("🛠️ Administración")
        csv_txt = "nombre,email,rol,nivel,grupo\nLuis Pérez,luis@x.mx,alumno,secundaria,1A Secundaria\nProfa Ruiz,ruiz@x.mx,docente,secundaria,1A Secundaria\n"
        self.correr(["crear_csv"], csv_usuarios=fs.FakeFile("u.csv", csv_txt.encode("utf-8")))
        repo = self.repo()
        self.assertEqual({u["email"] for u in repo.listar_usuarios(gid="1a_secundaria")}, {"luis@x.mx", "ruiz@x.mx"})
        self.assertEqual(len(repo.get_grupo("1a_secundaria")["docentes"]), 1)
        self.assertEqual(len(fs.session_state.credenciales), 2)
        self.correr(["toggle_activo"], usuario_gest="Luis Pérez (luis@x.mx)")
        self.assertFalse(repo.get_usuario("u_luis_x_mx")["activo"])
        # límites y privacidad
        self.correr(["Guardar límites"], cfg_alumno=15)
        self.assertEqual(repo.get_config()["limite_alumno"], 15)
        self.correr(["borrar_datos"], usuario_borrar="Luis Pérez (luis@x.mx)", seguro_borrar=True)
        self.assertIsNone(repo.get_usuario("u_luis_x_mx"))

    def test_todas_las_paginas_renderizan(self):
        for p in ("🛠️ Administración", "👩‍🏫 Mi grupo", "📚 Materiales", "🫶 Bienestar", "💬 Asistente"):
            self.ir(p)


if __name__ == "__main__":
    unittest.main()
