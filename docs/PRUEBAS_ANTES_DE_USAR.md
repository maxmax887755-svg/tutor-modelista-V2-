# Lista de pruebas antes de usar con alumnos

Las pruebas automáticas (`python -m unittest discover -s tests -t .`) revisan la lógica y la interfaz con un Streamlit y una IA simulados. **No prueban Firebase, Gemini ni el navegador reales.** Haz esto tú, en este orden:

## A. Modo demo (sin Firebase)
- [ ] `streamlit run app.py` abre sin errores y se ve el tema oscuro y la mascota.
- [ ] Entrar como **Alumno**: aceptar aviso, chatear, ver 👍/👎, ver que la llama/racha cambia.
- [ ] **Quiz**: crear uno, responder, ver resultado y que lo fallado aparece en **Repaso** (la tarjeta vence mañana).
- [ ] **Reto del día**, **Mi progreso**.
- [ ] Entrar como **Docente**: Mi grupo (todas las pestañas), Materiales (subir un TXT/PDF), y luego, como alumno, preguntar sobre ese tema: debe citar `[F1]`.
- [ ] Escribir "me quiero morir" como alumno → aparece el mensaje de apoyo; como **Orientador** → aparece la alerta.
- [ ] Foto de un ejercicio (la IA guía sin resolver) y dictado por voz (permite el micrófono).
- [ ] Accesibilidad: letra grande, Lexend, alto contraste.

## B. Con Firebase
- [ ] El primer admin entra con su correo (`ADMIN_EMAILS`).
- [ ] Crear un grupo, un docente y un alumno de prueba; que les llegue el correo para crear contraseña.
- [ ] El alumno entra, chatea, cierra sesión y vuelve a entrar: su progreso sigue ahí.
- [ ] En la consola de Firebase (Firestore) aparecen `usuarios`, `progreso`, `eventos`.
- [ ] Desactivar al alumno: ya no puede entrar. Borrar sus datos: desaparecen.

## C. Calidad de la IA
- [ ] `python evaluar_calidad.py --max 10`, y luego completo. Revisa `resultados_calidad.csv`, sobre todo los casos de tipo `tarea`, `bienestar` e `inyeccion`.
- [ ] Un docente revisa 20 respuestas reales y confirma que son correctas y adecuadas a la edad.

## D. Antes del piloto
- [ ] Aviso de privacidad revisado y aprobado por la escuela; autorizaciones recogidas.
- [ ] Definido quién atiende las alertas de bienestar y con qué protocolo.
- [ ] Límites diarios y cuota/facturación de Gemini configurados (🛠️ Administración → ⚙️ Límites).
- [ ] Probado en los celulares y la red de la escuela.
