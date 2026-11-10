# Verificación del frontend Mimo

Frontend React/Vite integrado con los siete microservicios dev. Publicado en:

https://main.d2d9bbvg1i7lcp.amplifyapp.com

## Comprobaciones ejecutadas

- Build de producción correcto; cinco pruebas unitarias del cliente API aprobadas.
- Siete pruebas Chromium con APIs simuladas: esqueletos en escritorio y móvil, error/reintento, documento de ocho dígitos, CV asociado a la vacante, empresa conservada al salir, menú móvil accesible y ausencia de tokens persistidos o errores de JavaScript.
- Navegador contra APIs reales: administrador de Andina recorre equipo, nóminas, asistencia, reclutamiento, desempeño y notificaciones sin alertas de error; empleado de Andina descarga su PDF; empleado de Pacífico accede a su empresa. Vista móvil de 375 px sin desbordamiento horizontal. No se cambiaron contraseñas ni se contrataron personas para probar la interfaz.
- Revisión independiente del frontend: se corrigieron la asociación del CV al cambiar de vacante, la validación del documento antes de crear postulaciones, la visibilidad/cierre del menú móvil y la empresa recordada tras el login.
- Tres pruebas del backend de postulaciones aprobadas para documento inválido, documento opcional y conservación de ceros iniciales. La validación fue desplegada en `crearPostulacion` dev.

La evidencia del despliegue y de la última comprobación en el dominio público está en `frontend_amplify.json`.

## Skills y límites

Se aplicaron las guías locales de Sites, web-design-enhancer y Ponytail. Se usó AWS Amplify según la petición del usuario. No se creó un sitio adicional en Cloudflare/Sites.

El verificador WDE **no certifica READY**: sus hipótesis iniciales proponían otra estética y su comprobación automática de trazas sigue esperando esa propuesta descartada; también marca espaciados de las ilustraciones y texto en mayúsculas. Se conserva la dirección kawaii pedida por el usuario. Las pruebas reales de navegador y la revisión independiente descritas arriba no equivalen a aprobar todos los gates de WDE.

No se comprobaron Safari, Firefox ni pruebas de carga del frontend. Los listados mantienen las capacidades de paginación de cada API existente; algunos endpoints antiguos devuelven colecciones completas. El despliegue de Amplify es manual y no está conectado a redeploy automático desde GitHub. Los datos de los tenants son datos de demostración del proyecto.
