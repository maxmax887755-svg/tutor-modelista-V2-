import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tm import auth, config, csvimport, moderation, progress, prompts2, quiz, quotas, reports, retrieval, spaced
from tm.repo import Repo, clave
from tm.store import LocalStore


class FakeResp:
    def __init__(self, status, data):
        self.status_code, self._d = status, data

    def json(self):
        return self._d


class FakeHttp:
    def __init__(self, resp):
        self.resp = resp

    def post(self, *a, **k):
        return self.resp


class Secretos(unittest.TestCase):
    def test_no_toca_secrets_sin_archivo(self):
        class Boom:
            def load_if_toml_exists(self):
                return False

            def __getitem__(self, k):
                raise AssertionError("no debía leer st.secrets sin secrets.toml")

        class FakeSt:
            secrets = Boom()

        original = config.st
        config.st = FakeSt()
        os.environ["PRUEBA_X"] = "valor"
        try:
            self.assertEqual(config.leer("PRUEBA_X"), "valor")
            self.assertIsNone(config.leer("NO_EXISTE"))
            self.assertIsNone(config.cuenta_firebase())
        finally:
            config.st = original
            os.environ.pop("PRUEBA_X", None)

    def test_lee_secrets_cuando_existe(self):
        class Ok(dict):
            def load_if_toml_exists(self):
                return True

        class FakeSt:
            secrets = Ok(A="1")

        original = config.st
        config.st = FakeSt()
        try:
            self.assertEqual(config.leer("A"), "1")
        finally:
            config.st = original


class Retrieval(unittest.TestCase):
    def test_trocear_respeta_limite(self):
        texto = ("Frase de prueba número uno. " * 60 + "\n\n") * 3
        frags = retrieval.trocear(texto, 400)
        self.assertTrue(all(len(f) <= 400 for f in frags))
        self.assertGreater(len(frags), 3)

    def test_busca_lo_relevante(self):
        frags = [{"texto": "Los cenotes de Yucatán son depósitos de agua dulce.", "titulo": "Geografía"},
                 {"texto": "La fotosíntesis convierte luz en energía química en las plantas.", "titulo": "Ciencias"},
                 {"texto": "Las ecuaciones de primer grado tienen una incógnita.", "titulo": "Matemáticas"}]
        r = retrieval.buscar("¿cómo hacen las plantas la fotosíntesis?", frags, k=2)
        self.assertEqual(r[0]["titulo"], "Ciencias")
        self.assertEqual(retrieval.buscar("xyz", frags), [])
        self.assertEqual(retrieval.ids_citados("según [F2] y [F1], también [F2]"), [1, 2])
        self.assertIn("[F1]", retrieval.formatear_contexto(r))


class Spaced(unittest.TestCase):
    def test_leitner(self):
        t = spaced.nueva("¿2+2?", "4", "2026-10-10")
        self.assertEqual(t["proxima"], "2026-10-11")
        t = spaced.actualizar(t, True, "2026-10-11")
        self.assertEqual((t["caja"], t["proxima"]), (2, "2026-10-13"))
        t = spaced.actualizar(t, False, "2026-10-13")
        self.assertEqual((t["caja"], t["proxima"], t["fallos"]), (1, "2026-10-14", 1))
        for _ in range(8):
            t = spaced.actualizar(t, True, "2026-10-14")
        self.assertEqual(t["caja"], 5)
        self.assertEqual(len(spaced.pendientes([t, {"proxima": "2026-10-01", "caja": 1}], "2026-10-10")), 1)


class Progreso(unittest.TestCase):
    def test_nivel_y_racha(self):
        self.assertEqual(progress.nivel(0)[1], "Chispa")
        self.assertEqual(progress.nivel(120)[1], "Llama")
        self.assertEqual(progress.nivel(9999)[3], None)
        self.assertEqual(progress.actualizar_racha(None, "2026-10-10", 0), 1)
        self.assertEqual(progress.actualizar_racha("2026-10-10", "2026-10-10", 3), 3)
        self.assertEqual(progress.actualizar_racha("2026-10-09", "2026-10-10", 3), 4)
        self.assertEqual(progress.actualizar_racha("2026-10-08", "2026-10-10", 3), 4)   # día de gracia
        self.assertEqual(progress.actualizar_racha("2026-10-05", "2026-10-10", 3), 1)


class Moderacion(unittest.TestCase):
    def test_detecta_y_no_exagera(self):
        self.assertTrue(moderation.revisar("A veces siento que me quiero morir")["alerta"])
        self.assertEqual(moderation.revisar("Me hacen bullying en el salón")["nivel"], "media")
        self.assertEqual(moderation.revisar("Voy a traer un arma a la escuela")["nivel"], "alta")
        self.assertFalse(moderation.revisar("Explícame el suicidio en la obra de Romeo y Julieta")["alerta"])
        self.assertFalse(moderation.revisar("¿Cómo se resuelve 2x+3=7?")["alerta"])
        self.assertIn("911", moderation.mensaje_apoyo(["autolesion"], config.linea_ayuda()))


class Quiz(unittest.TestCase):
    def test_parsear(self):
        txt = '```json\n{"preguntas":[{"pregunta":"¿Capital de México?","opciones":["CDMX","Mérida","Puebla","Oaxaca"],"correcta":"A","explicacion":"Es CDMX"},{"pregunta":"mala","opciones":["a"],"correcta":5}]}\n```'
        qs = quiz.parsear_quiz(txt, semilla=1)
        self.assertEqual(len(qs), 1)
        q = qs[0]
        self.assertEqual(q["opciones"][q["correcta"]], "CDMX")
        self.assertEqual(quiz.calificar(qs, [q["correcta"]])[0], 1)
        self.assertEqual(quiz.calificar(qs, [None])[0], 0)
        with self.assertRaises(ValueError):
            quiz.parsear_quiz("no es json")
        with self.assertRaises(ValueError):
            quiz.parsear_quiz('{"preguntas":[]}')


class Cuotas(unittest.TestCase):
    def test_limites(self):
        self.assertTrue(quotas.puede_enviar({"msgs": 39}, 40))
        self.assertFalse(quotas.puede_enviar({"msgs": 40}, 40))
        self.assertEqual(quotas.limite_mensajes("alumno", {"limite_alumno": 10}), 10)
        self.assertEqual(quotas.costo_estimado(1_000_000, 500_000, 0.5, 2.0), 1.5)


class Csv(unittest.TestCase):
    def test_importacion(self):
        t = "nombre,email,rol,nivel,grupo\nAna,ana@x.mx,alumno,secundaria,1A\nMal,correo,alumno,,\nAna2,ana@x.mx,alumno,,\nLuis,l@x.mx,rey,,\n"
        filas, errs = csvimport.parsear_csv(t)
        self.assertEqual([f["email"] for f in filas], ["ana@x.mx"])
        self.assertEqual(len(errs), 3)
        self.assertTrue(csvimport.parsear_csv("a,b\n1,2")[1])


class Auth(unittest.TestCase):
    def test_login(self):
        ok = FakeHttp(FakeResp(200, {"localId": "u1", "email": "A@x.mx"}))
        self.assertEqual(auth.login("k", "a@x.mx", "pw", http=ok), {"uid": "u1", "email": "a@x.mx"})
        mal = FakeHttp(FakeResp(400, {"error": {"message": "INVALID_LOGIN_CREDENTIALS"}}))
        with self.assertRaises(auth.AuthError) as cm:
            auth.login("k", "a@x.mx", "pw", http=mal)
        self.assertIn("incorrectos", str(cm.exception))
        with self.assertRaises(auth.AuthError):
            auth.login("", "a", "b")
        self.assertTrue(auth.enviar_restablecer("k", "a@x.mx", http=mal))
        self.assertGreaterEqual(len(auth.contrasena_temporal()), 12)


class Prompts(unittest.TestCase):
    def test_instruccion(self):
        s = prompts2.instruccion_tutor("BASE", "Matemáticas", "Explícame", "le cuestan fracciones", ["fracciones"], "[F1] x", True)
        for esperado in ("BASE", "Matemáticas", "EXPLÍCAME", "PRIVADO".lower() if False else "privado", "fracciones", "[F1]", "foto"):
            self.assertIn(esperado, s)
        d = prompts2.instruccion_tutor("BASE", es_docente=True)
        self.assertNotIn("EXPLÍCAME", d)


class RepoTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repo(LocalStore())
        self.gid = self.repo.crear_grupo("1°A Secundaria", "secundaria", ["doc1"])
        self.repo.crear_usuario("a1", "Ana", "ana@x.mx", "alumno", "secundaria", [self.gid])
        self.repo.crear_usuario("doc1", "Prof", "p@x.mx", "docente", grupos=[self.gid])

    def test_usuarios_y_grupos(self):
        self.assertEqual([u["uid"] for u in self.repo.listar_usuarios(rol="alumno", gid=self.gid)], ["a1"])
        self.assertEqual(len(self.repo.listar_usuarios(gid=self.gid)), 2)
        self.assertEqual(self.repo.grupos_de_docente("doc1")[0]["gid"], self.gid)
        self.repo.registrar_consentimiento("a1")
        self.assertEqual(self.repo.get_usuario("a1")["consentimiento"]["version"], config.VERSION_AVISO)

    def test_progreso_y_tope_xp(self):
        for _ in range(25):
            r = self.repo.registrar_actividad("a1", "mensaje", tema="Fracciones")
        p = self.repo.get_progreso("a1")
        self.assertEqual(p["xp"], progress.MAX_XP_MSG_DIA)
        self.assertEqual((p["mensajes"], p["racha"]), (25, 1))
        r = self.repo.registrar_actividad("a1", "reto", xp=progress.XP_RETO)
        self.assertTrue(r["subio"])   # 20 + 20 = 40 -> Brasa
        self.repo.anotar_resultado("a1", "Fracciones", 1, 5)
        self.repo.anotar_resultado("a1", "Geometría", 5, 5)
        p = self.repo.get_progreso("a1")
        self.assertIn("Fracciones", p["dificultades"])
        self.assertIn("Geometría", p["dominados"])

    def test_uso_y_eventos(self):
        self.repo.sumar_uso("a1", msgs=1, tin=100, tout=50)
        self.repo.sumar_uso("a1", msgs=1, gen=1, tin=10, tout=5)
        u = self.repo.uso_diario("a1")
        self.assertEqual((u["msgs"], u["gen"], u["tin"], u["tout"]), (2, 1, 110, 55))
        self.assertEqual(self.repo.uso_global()["msgs"], 2)
        self.repo.registrar_evento("a1", self.gid, "mensaje", "Matemáticas", "Fracciones")
        self.repo.registrar_evento("a1", self.gid, "quiz", "Matemáticas", "Fracciones")
        self.assertEqual(len(self.repo.eventos_grupo(self.gid)), 2)

    def test_material_y_busqueda(self):
        mid, n = self.repo.guardar_material("Cenotes", "Los cenotes son pozos naturales de Yucatán.\n\nSe formaron por disolución de la roca caliza.", [self.gid], "Ciencias", "doc1")
        self.assertGreaterEqual(n, 1)
        self.repo.guardar_material("General", "Aviso para toda la escuela sobre el reglamento.", [], "General", "doc1")
        frags = self.repo.fragmentos_de_grupo(self.gid)
        self.assertEqual({f["titulo"] for f in frags}, {"Cenotes", "General"})
        self.assertEqual(retrieval.buscar("cenotes de Yucatán", frags)[0]["titulo"], "Cenotes")
        self.repo.desactivar_material(mid)
        self.assertEqual({f["titulo"] for f in self.repo.fragmentos_de_grupo(self.gid)}, {"General"})
        self.repo.eliminar_material(mid)
        self.assertEqual(self.repo.s.query("fragmentos", [("mid", "==", mid)]), [])

    def test_tarjetas_alertas_avisos_reto(self):
        t = spaced.nueva("¿2+2?", "4", config.hoy())
        t["proxima"] = config.hoy()
        self.assertEqual(self.repo.agregar_tarjetas("a1", [t, dict(t)]), 1)
        pend = self.repo.tarjetas_pendientes("a1")
        self.assertEqual(len(pend), 1)
        nueva = spaced.actualizar(pend[0], True, config.hoy())
        self.repo.guardar_tarjeta(pend[0]["tid"], nueva)
        self.assertEqual(self.repo.tarjetas_pendientes("a1"), [])
        self.repo.crear_alerta("a1", "Ana", self.gid, ["acoso"], "me hacen bullying")
        self.assertEqual(len(self.repo.listar_alertas("nueva")), 1)
        aid = self.repo.listar_alertas()[0]["id"]
        self.repo.marcar_alerta(aid, "orientador1")
        self.assertEqual(self.repo.listar_alertas("nueva"), [])
        self.repo.publicar_aviso(self.gid, "Mañana examen de Español", "doc1", 3)
        self.assertEqual(len(self.repo.avisos_vigentes([self.gid])), 1)
        self.repo.guardar_reto(self.gid, "Matemáticas", [{"pregunta": "x"}])
        self.assertEqual(self.repo.get_reto(self.gid, "Matemáticas")["preguntas"][0]["pregunta"], "x")
        self.assertFalse(self.repo.reto_hecho("a1", "Matemáticas"))
        self.repo.registrar_evento("a1", self.gid, "reto", "Matemáticas")
        self.assertTrue(self.repo.reto_hecho("a1", "Matemáticas"))

    def test_feedback_reportes_y_borrado(self):
        self.repo.guardar_feedback("a1", self.gid, -1, "Matemáticas", "¿Cómo?", "Respuesta")
        self.repo.guardar_feedback("a1", self.gid, 1, "Matemáticas", "p", "r", guardar_texto=False)
        self.repo.registrar_evento("a1", self.gid, "mensaje")
        self.repo.registrar_actividad("a1", "mensaje")
        self.repo.anotar_resultado("a1", "Fracciones", 0, 3)
        r = reports.resumen_grupo(self.repo, self.gid)
        self.assertEqual((r["alumnos"], r["activos"], r["likes"], r["dislikes"]), (1, 1, 1, 1))
        self.assertEqual(r["dificultades"][0][0], "Fracciones")
        d = reports.datos_familia(self.repo, "a1")
        self.assertEqual(d["dias_activos"], 1)
        self.assertIn("Ana", reports.reporte_base("Ana", d))
        self.repo.eliminar_datos_usuario("a1")
        self.assertIsNone(self.repo.get_usuario("a1"))
        self.assertEqual(self.repo.s.query("feedback", [("uid", "==", "a1")]), [])
        self.assertEqual(self.repo.get_progreso("a1")["xp"], 0)

    def test_persistencia_local(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "datos.json")
            r1 = Repo(LocalStore(ruta))
            r1.crear_usuario("x", "Xavier", "x@x.mx")
            r2 = Repo(LocalStore(ruta))
            self.assertEqual(r2.get_usuario("x")["nombre"], "Xavier")

    def test_clave(self):
        self.assertEqual(clave("Fracciones: ¿qué son?"), "Fracciones qué son")


class Imagenes(unittest.TestCase):
    def test_preparar_quita_exif_y_reduce(self):
        import io
        from PIL import Image
        from tm import imagenes
        im = Image.new("RGB", (3000, 2000), (200, 30, 30))
        exif = Image.Exif()
        exif[0x010F] = "Camara"
        buf = io.BytesIO()
        im.save(buf, "JPEG", exif=exif)
        r = imagenes.preparar(buf.getvalue())
        out = Image.open(io.BytesIO(r["bytes"]))
        self.assertLessEqual(max(out.size), imagenes.MAX_LADO)
        self.assertEqual(len(out.getexif()), 0)
        with self.assertRaises(Exception):
            imagenes.preparar(b"no es una imagen")


if __name__ == "__main__":
    unittest.main()
