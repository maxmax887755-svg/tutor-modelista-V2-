import json
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "tests"))
os.chdir(RAIZ)
import fake_streamlit  # noqa: E402,F401

import evaluar_calidad as ec  # noqa: E402
from tm import ia  # noqa: E402


class Calidad(unittest.TestCase):
    def test_casos_validos(self):
        casos = json.load(open(os.path.join(RAIZ, "datos", "preguntas_prueba.json"), encoding="utf-8"))
        self.assertGreaterEqual(len(casos), 35)
        for c in casos:
            self.assertIn(c["rol"], ec.ROLES)
            self.assertIn(c["tipo"], ec.CRITERIOS_DEBEN)
        self.assertEqual(len({c["id"] for c in casos}), len(casos))

    def test_juez_y_resumen(self):
        bueno = '{"no_da_respuesta_directa": true, "guia_con_preguntas": true, "tono_adecuado": true, "seguro": true, "claridad": 4, "correccion": 5, "comentario": "ok"}'
        malo = '```json\n{"no_da_respuesta_directa": false, "tono_adecuado": true, "seguro": true, "claridad": 9, "correccion": 4}\n```'
        j1, j2 = ec.parsear_juicio(bueno), ec.parsear_juicio(malo)
        self.assertEqual(j2["claridad"], 5)
        caso = {"tipo": "tarea"}
        self.assertTrue(ec.aprobado(caso, j1))
        self.assertFalse(ec.aprobado(caso, j2))
        self.assertTrue(ec.aprobado({"tipo": "explicar"}, j2))
        res = ec.resumen([{"tipo": "tarea", "aprobado": True}, {"tipo": "tarea", "aprobado": False}])
        self.assertEqual(res["tarea"]["porcentaje"], 50)

    def test_evaluar_caso_con_ia_falsa(self):
        llamadas = []

        def falso(prompt, system=None, json_mode=False, max_tokens=0, rol=None, temperatura=0.5):
            llamadas.append(json_mode)
            if json_mode:
                return '{"no_da_respuesta_directa": true, "guia_con_preguntas": true, "tono_adecuado": true, "seguro": true, "claridad": 4, "correccion": 4}', {}
            return "¿Qué crees que es el primer paso?", {}

        original = ia.generar
        ia.generar = falso
        try:
            r = ec.evaluar_caso({"id": 1, "rol": "secundaria", "materia": "Matemáticas", "tipo": "tarea", "pregunta": "Resuelve 2x=4", "esperado": "x"})
        finally:
            ia.generar = original
        self.assertTrue(r["aprobado"])
        self.assertEqual(llamadas, [False, True])


if __name__ == "__main__":
    unittest.main()
