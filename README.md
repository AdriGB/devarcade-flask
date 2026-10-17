# DevArcade — Flask + SQLite

Portfolio con estética arcade, tres juegos, cuentas de usuario y panel de administración.
Proyecto armado a partir del frontend original y los archivos de `Gemini 4 Argon`.
El backend anterior en Express queda fuera de esta carpeta y no se necesita para ejecutar.

## Inicio rápido en Windows

Necesitás Python 3.10 o superior. Abrí `iniciar.bat` con doble clic.
El primer arranque instala las dependencias en `.venv`, crea una base nueva y carga
las cuentas y los tres juegos. Se necesita Internet para esa instalación inicial.
La ventana debe quedar abierta mientras usás el sitio. Para detenerlo, presioná Ctrl+C.

Abrí **http://localhost:5000**. No abras los HTML con doble clic.
Si el puerto está ocupado, configurá otro en `.env` y usá ese número en la URL.

También podés arrancarlo desde PowerShell, ubicado en esta carpeta:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe seed.py
.\.venv\Scripts\python.exe app.py
```

No hace falta activar el entorno virtual ni cambiar la política de ejecución de Windows.

## Cuentas locales de demostración

| Rol | Email | Contraseña |
|---|---|---|
| Administrador | admin@devarcade.dev | admin1234 |
| Jugador | lucia@mail.com | jugadora1 |

El administrador entra a `/admin.html` o usa el enlace Admin de la navegación.
En celular, abrí el menú de navegación para ver los enlaces.
Las cuentas son para demostrar el proyecto localmente. `seed.py` no cambia cuentas
existentes y no agrega visitas, partidas ni consultas ficticias.

## Funciones

- Portfolio, servicios dinámicos y formulario de consulta.
- Registro, login/logout, contraseña hasheada con Werkzeug y sesión firmada.
- Juegos y administración protegidos desde Flask; roles consultados en SQLite.
- Token CSRF para operaciones que modifican datos.
- CRUD de proyectos/demos y servicios, incluyendo borradores e inactivos.
- Gestión de roles, suspensión y eliminación de usuarios; preservación del historial de respuestas.
- Bandeja de consultas, respuestas e historial con estado de correo simulado, enviado o fallido.
- Contadores históricos y gráficos de visitas, registros, accesos y consultas.
- Filtros por período y juego; ranking e historial de partidas.
- Snake: teclado/deslizamiento táctil y pausa. Memory: parejas con reinicio.
  Ta-Te-Ti: dos dificultades y cancelación de jugadas pendientes al cambiar de ronda.
- Reintento de guardado de resultados sin duplicar la misma partida en la base.
- Subida de imágenes con límites de tamaño, revisión de formato y archivo con Pillow.

Los puntajes se calculan en el navegador. Las validaciones de rango y juego no son
un sistema antitrampas para una competición pública.

## Correo y configuración

Copiá `.env.example` como `.env` si necesitás cambiar las opciones.
Sin SMTP, la app guarda consultas y respuestas e indica claramente **modo simulado**.
Para mandar correo real, configurá SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS y SMTP_FROM.
El correo real requiere conexión. Un envío aceptado por SMTP no garantiza recepción en la bandeja final.

La clave de sesión se genera en `.secret_key` si no definís FLASK_SECRET_KEY.
No compartas `.env`, `.secret_key` ni la base poblada. La base nueva está en
`db/devarcade.db`; la base del proyecto Express original no se modifica ni importa.
Si quisieras migrar datos anteriores, hacé un respaldo y una migración específica:
los hashes bcrypt anteriores no son los hashes Werkzeug de este proyecto.

Bootstrap y Chart.js están incluidos en `prototipo/vendor/`. Las fuentes de Google
son opcionales: sin Internet se usan las fuentes de respaldo del CSS.
Las licencias de las bibliotecas se conservan en sus distribuciones.

## Probar desde un celular

Poné `HOST=0.0.0.0` en `.env`, reiniciá Flask y conectá ambos dispositivos a la misma
red Wi-Fi. Desde el teléfono abrí `http://IP-DE-LA-PC:5000` (por ejemplo,
`http://192.168.1.20:5000`). Consultá la IPv4 con `ipconfig`.
El firewall puede requerir permitir Python en la red privada. No se modifica automáticamente.
El host predeterminado es `127.0.0.1`, accesible solo desde la propia computadora.
El servidor de desarrollo se usa para la demostración local.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_app
```

Las pruebas usan bases y carpetas temporales. Cubren permisos y CSRF, partidas,
CRUD, imágenes, eliminación de administradores con respuestas, filtros, fallos SMTP,
suspensión de cuentas, reintentos y seed idempotente. No envían correo real.

La comprobación manual en navegador incluyó login, consulta y respuesta simulada,
panel con datos reales, guardado
desde el editor, pausa de Snake, reinicio de Memory y cambio de dificultad de Ta-Te-Ti.
No sustituye una prueba exhaustiva de todos los juegos en teléfonos físicos.

Para crear un ZIP de fuentes, ejecutá `python empaquetar.py`. Excluye la base poblada,
las imágenes subidas, secretos y entorno virtual.

## Estructura

```text
app.py             Rutas y Blueprints de la API, sesiones y páginas protegidas
database.py        Conexión SQLite por petición y esquema
validators.py      Validaciones compartidas
seed.py            Inicialización idempotente de datos de demostración
test_app.py        Pruebas de integración
db/schema.sql      Modelo de datos
prototipo/         HTML, CSS, JavaScript y recursos locales
uploads/           Imágenes cargadas desde el panel
```

## Pendientes de contenido para entregar

Reemplazar el nombre ficticio Luca Ferrari, avatar, correo y enlaces de ejemplo del
portfolio por los datos que el grupo quiera presentar. Completar manual de marca y
documentación académica, configurar y comprobar SMTP real si se exige en la exposición,
y ensayar la demostración en los dispositivos del grupo. DOOM no se incluyó en este alcance.
