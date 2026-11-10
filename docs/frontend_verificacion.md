# Verificación del frontend Mimo

Frontend React/Vite integrado con los siete microservicios dev. Publicado en:

https://main.d2d9bbvg1i7lcp.amplifyapp.com

## Comprobaciones ejecutadas

- Build de producción correcto; cinco pruebas unitarias del cliente API aprobadas.
- Siete pruebas Chromium con APIs simuladas: esqueletos en escritorio y móvil, error/reintento, documento de ocho dígitos, CV asociado a la vacante, acceso solo con correo y contraseña, con empresa obtenida de la cuenta, menú móvil accesible y ausencia de tokens persistidos o errores de JavaScript.
- Navegador contra APIs reales: administrador de Andina recorre equipo, nóminas, asistencia, reclutamiento, desempeño y notificaciones sin alertas de error; empleado de Andina descarga su PDF; empleado de Pacífico accede a su empresa. Vista móvil de 375 px sin desbordamiento horizontal. No se cambiaron contraseñas ni se contrataron personas para probar la interfaz.
- Revisión independiente del frontend: se corrigieron la asociación del CV al cambiar de vacante, la validación del documento antes de crear postulaciones, la visibilidad/cierre del menú móvil y la asignación de empresa al iniciar sesión.
- Tres pruebas del backend de postulaciones aprobadas para documento inválido, documento opcional y conservación de ceros iniciales. La validación fue desplegada en `crearPostulacion` dev.

La evidencia del despliegue y de la última comprobación en el dominio público está en `frontend_amplify.json`.

## Skills y límites

Se aplicaron las guías locales de Sites, web-design-enhancer y Ponytail. Se usó AWS Amplify según la petición del usuario. No se creó un sitio adicional en Cloudflare/Sites.

El verificador WDE **no certifica READY**: sus hipótesis iniciales proponían otra estética y su comprobación automática de trazas sigue esperando esa propuesta descartada; también marca espaciados de las ilustraciones y texto en mayúsculas. Se conserva la dirección kawaii pedida por el usuario. Las pruebas reales de navegador y la revisión independiente descritas arriba no equivalen a aprobar todos los gates de WDE.

No se comprobaron Safari, Firefox ni pruebas de carga del frontend. Los listados mantienen las capacidades de paginación de cada API existente; algunos endpoints antiguos devuelven colecciones completas. El despliegue de Amplify es manual y no está conectado a redeploy automático desde GitHub. Los datos de los tenants son datos de demostración del proyecto.


## Actualización: cuenta vinculada al correo

El login ya no pide seleccionar empresa. La cuenta se localiza por correo en `login-email-index` y el JWT recibe el tenant del registro persistido. La empresa se muestra como texto en el encabezado. Para entrar con otra cuenta hay que cerrar sesión. El cliente anterior que envía `tenant_id` sigue siendo compatible; un correo repetido entre cuentas se rechaza en el nuevo flujo.

La evidencia de esta actualización está en `login_correo_verificacion.json`. Las pruebas de usuarios cubren correo con dominio externo, normalización, empresa correcta, ambigüedad, contraseña incorrecta, cuenta desactivada y lectura consistente del usuario frente a un índice desactualizado.
