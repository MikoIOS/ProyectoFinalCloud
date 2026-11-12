# Mimo · Portal HCM

Frontend React + Vite del proyecto HCM. Diseño kawaii en tonos crema, rosa, azul y menta, con personajes originales dibujados en CSS y esqueletos suaves en el espacio de las tarjetas y tablas mientras llegan los datos. Respeta la preferencia de movimiento reducido.

Sitio: https://main.d2d9bbvg1i7lcp.amplifyapp.com

## Desarrollo

Requiere Node >=22.12. Desde `frontend/`:

```sh
npm ci
npm run dev
npm test
npm run build
```

Las URLs públicas de las siete APIs están en `src/api.js`. Se pueden sustituir en la compilación con las variables `VITE_USUARIOS_URL`, `VITE_EMPLEADOS_URL`, `VITE_NOMINAS_URL`, `VITE_ASISTENCIA_URL`, `VITE_RECLUTAMIENTO_URL`, `VITE_DESEMPENO_URL` y `VITE_NOTIFICACIONES_URL`. No colocar contraseñas ni claves AWS en variables VITE: se incluyen en el JavaScript público.

## Funcionalidad

Desde el login, **¿Tu empresa es nueva? Crear cuenta** abre el registro de empresa y administrador (empresa, RUC de 11 dígitos, nombre, correo y contraseña). `POST /auth/register` genera la empresa y devuelve la sesión inicial; el nombre de la empresa se muestra en el portal. Publicado en AWS y Amplify; [evidencia del deployment](../docs/deployment_registro_empresa.json). Los próximos cambios de la ruta requieren un despliegue completo de `ms-usuarios` y publicar nuevamente este frontend.

Login con correo y contraseña (la empresa se obtiene de la cuenta), dashboard, empleados y ficha personal, nóminas y boletas PDF, marcaciones y ausencias, vacantes y postulaciones con CV, evaluaciones y notificaciones. Las acciones visibles dependen del rol; las APIs siguen siendo responsables de autorizar cada operación. Las contrataciones requieren confirmación.

El JWT permanece en memoria. Recargar la página o salir requiere iniciar sesión otra vez; no se almacena en localStorage/sessionStorage. La navegación usa hashes, sin depender de reglas de reescritura. Los errores de API se muestran y permiten reintentar. La carga de CV admite PDF de hasta 10 MB mediante la URL firmada emitida por la API, sin enviarle el JWT a S3.

## Verificación

`npm test`: seis pruebas del cliente API. `tests/browser_smoke.py`: ocho comprobaciones de Chromium con APIs simuladas, incluyendo esqueletos, reintentos, validación de documento, asociación del CV, acceso sin selector de empresa, sesión y menú móvil. Requiere Python Playwright y Chromium; ejecutar con el servidor local activo. `HCM_UI_URL` permite cambiar el destino.

Las comprobaciones reales de AWS y Amplify están descritas en [la evidencia](../docs/frontend_verificacion.md); se distinguen de las pruebas simuladas.

## Amplify

App `d2d9bbvg1i7lcp`, región `us-east-1`, rama `main`. Este despliegue sube manualmente el contenido de `dist/` a Amplify Hosting usando `create_deployment`, PUT del ZIP y `start_deployment`. Los enlaces firmados de subida no se guardan en el repositorio.

**Subir commits a GitHub no vuelve a desplegar automáticamente esta app.** No se vinculó un token de GitHub a AWS. El archivo raíz `amplify.yml` deja definido el build para conectar el repositorio posteriormente. Los encabezados de seguridad configurados en la app están en `customHttp.yml`.


Las solicitudes de ausencia requieren al menos 15 días calendario de anticipación respecto de la fecha actual de Lima. Los campos de fecha muestran el mínimo permitido y la API vuelve a validar la regla, para todos los tipos y roles.
