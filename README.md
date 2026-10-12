# Tutor Modelista v2 · Escuela Modelo, Mérida

Tutor con IA (Gemini) que **guía sin dar las respuestas**, para secundaria, preparatoria y docentes, con cuentas, progreso y panel para el docente.

## Qué incluye
| Para el alumno | Para el docente | Para la escuela |
|---|---|---|
| Tutor con memoria del alumno y diagnóstico inicial | Resumen del grupo y quién la usa | Cuentas con Firebase (alumno, docente, orientador, admin) |
| Modos *Explícame* / *Practica conmigo* | Temas que más se les dificultan | Alta masiva por CSV |
| Explica con **el material de la escuela** y cita la fuente | Calidad: 👍/👎 y respuestas por mejorar | Límites diarios y control de gasto |
| Foto del ejercicio · dictado y lectura en voz alta | Subir materiales (PDF/DOCX/TXT) | Alertas de bienestar para orientación |
| Quiz, **repaso espaciado** y reto del día | Avisos, meta del grupo, reporte para familias | Borrado de datos de un usuario |
| Llama que crece, racha amable y meta de grupo | Reto del día por materia | Instalable en celular (mejor esfuerzo) |
| Accesibilidad: letra grande, Lexend, alto contraste | | Evaluador de calidad de la IA |

## Cómo correrlo
```
python -m venv venv
venv\Scripts\activate            # Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env           # pon tu GEMINI_API_KEY
streamlit run app.py
```
Sin Firebase arranca en **modo demo** (eliges un rol de prueba). Para cuentas reales sigue `docs/FIREBASE_PASO_A_PASO.md`.

## Despliegue
Igual que la v1: sube el proyecto a GitHub (sin `.env` ni `secrets.toml`), crea la app en https://share.streamlit.io y pega los secretos (ver `.streamlit/secrets.toml.example`). Copia también tu carpeta `assets/` de la v1 (los `.webp` de la mascota) junto a los PNG incluidos. **Despliega la v2 como app aparte para no tocar la v1 que ya funciona.**

## Pruebas
```
python -m unittest discover -s tests -t .      # lógica e interfaz simuladas (42 pruebas)
python evaluar_calidad.py --max 10              # calidad real de la IA (usa tu clave de Gemini)
```
Antes de usarla con alumnos, haz `docs/PRUEBAS_ANTES_DE_USAR.md`.

## Cómo está organizado
- `app.py` · enruta por rol. `nucleo.py` · mascota, tema y prompts heredados de la v1.
- `tm/` · lógica sin pantalla: datos (`store.py`, `repo.py`), IA (`ia.py`, `prompts2.py`), búsqueda en material (`retrieval.py`), repaso (`spaced.py`), bienestar (`moderation.py`), cuotas, quizzes, accesos (`auth.py`).
- `ui/` · pantallas. `datos/preguntas_prueba.json` · 35 casos para evaluar la IA.

## Límites que debes conocer
- **No se ha probado contra Firebase, Gemini ni un navegador reales** (solo con simuladores). Haz la lista de pruebas.
- El material se busca con una técnica de texto (BM25), sin embeddings: funciona bien con cientos de páginas, no con bibliotecas enormes.
- La detección de bienestar es por frases y puede fallar; no sustituye el protocolo de la escuela.
- "Instalable en celular" es de mejor esfuerzo: en Android/iPhone siempre puedes usar *Agregar a pantalla de inicio*.
- No se guardan las conversaciones: el "recuerdo" del alumno es un resumen corto que se genera al pulsar *Terminar y guardar lo aprendido*.
- Streamlit Cloud gratuito es para pilotos; para toda la escuela conviene un hosting propio.
