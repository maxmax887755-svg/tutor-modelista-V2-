# Conectar Firebase (cuentas y base de datos)

Sin Firebase la app funciona en **modo demo** (datos de prueba, sin cuentas reales). Con Firebase tienes cuentas por alumno/docente, progreso permanente y panel docente.

## 1. Crear el proyecto
1. Entra a https://console.firebase.google.com con una cuenta de Google (mejor una institucional).
2. **Crear un proyecto** → ponle nombre (ej. `tutor-modelista`) → puedes desactivar Google Analytics.

## 2. Activar el acceso con correo
**Compilación → Authentication → Comenzar → Método de acceso → Correo electrónico/contraseña → Habilitar → Guardar.**

## 3. Crear la base de datos
**Compilación → Firestore Database → Crear base de datos** → elige una ubicación → **modo producción**.
En la pestaña **Reglas** pega el contenido de `firestore.rules` (bloquea todo acceso directo; la app entra por el servidor) y publica.

## 4. Copiar las dos llaves
- **Web API Key**: Configuración del proyecto (⚙️) → General → "Clave de API web". Va en `FIREBASE_API_KEY`.
- **Cuenta de servicio**: Configuración → Cuentas de servicio → **Generar nueva clave privada** → se descarga un `.json`. Su contenido va en la tabla `[firebase_cuenta]` de los secretos (ver `.streamlit/secrets.toml.example`; copia cada campo del JSON). **Ese archivo es una llave maestra: no lo subas a GitHub ni lo compartas.**

## 5. Poner los secretos
- **En tu computadora:** copia `.streamlit/secrets.toml.example` a `.streamlit/secrets.toml` y llénalo.
- **En Streamlit Cloud:** Manage app → Settings → Secrets → pega el contenido.

## 6. Crear el primer administrador
1. En Firebase: **Authentication → Usuarios → Agregar usuario** (tu correo y una contraseña).
2. En los secretos pon `ADMIN_EMAILS = "tu_correo@..."` (el mismo correo).
3. Abre la app e inicia sesión: se crea tu perfil de administrador automáticamente.

## 7. Dar de alta a la escuela
En **🛠️ Administración**:
1. **Grupos** → crea los grupos (ej. `1A Secundaria`).
2. **Usuarios** → crea docentes y alumnos uno por uno o importa un CSV con columnas `nombre,email,rol,nivel,grupo`.
3. Cada persona recibe un correo para crear su contraseña (si no llega, revisa spam o usa "¿Olvidaste tu contraseña?" en la pantalla de acceso).
4. **Grupos → Asignar docentes** para que cada profesor vea su grupo.

## Costos y límites
Firebase tiene un plan gratuito con cuotas diarias de lecturas/escrituras (revisa las cifras vigentes en https://firebase.google.com/pricing). La app lee poco (guarda datos unos minutos en memoria), pero con muchos alumnos puede crecer. En **💰 Uso y costos** ves el consumo de la IA; Gemini se cobra aparte.
