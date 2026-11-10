# EXPERIENCE-CONTRACT.md

## Product goal

Primary user action: iniciar sesión en su empresa y completar una tarea de RRHH o autoservicio.
Success looks like: login real, datos del tenant correcto, formularios funcionales, marcación y descarga de boleta verificables.

## Pages & objectives

| Page / route | User objective | Primary CTA |
|---|---|---|
| / | Revisar resumen real y pendientes | Ver mi asistencia |
| /empleados | Buscar y consultar personal | Nuevo empleado para RRHH |
| /nominas | Consultar planillas y descargar PDF privado | Descargar boleta |
| /asistencia | Marcar entrada/salida y gestionar ausencias | Registrar marcación |
| /reclutamiento | Vacantes, candidatos y contratación | Nueva vacante |
| /desempeno | Evaluaciones del empleado y actualización | Nueva evaluación |
| /notificaciones | Revisar avisos y marcar lectura | Marcar como leída |

## Critical journeys

1. Ingresar correo y contraseña, obtener automáticamente la empresa de la cuenta, ver datos reales y cerrar sesión sin conservar datos del tenant anterior.
2. Registrar entrada/salida, solicitar ausencia y aprobarla desde RRHH; refrescar lista tras éxito.
3. Consultar nómina propia, descargar PDF con autorización y recibir errores legibles.
4. Crear evaluación y completarla; consultar notificaciones publicadas por EDA.

## Navigation

- Global: barra lateral de módulos, empresa activa y usuario autenticado.
- Mobile: menú plegable con botón etiquetado y misma navegación por rol.

## Interaction states

| Surface | Empty | Loading | Error | Success | Permission denied |
|---|---|---|---|---|---|
| Tarjetas, tablas, perfiles | Texto útil con acción permitida | Skeleton que mantiene dimensiones, aria-busy | Error con reintento | Datos reales | Ocultar acción y explicar 403 |
| Formularios | Campos etiquetados | Botón ocupado sin doble envío | Validación y mensaje del servidor | Confirmación y recarga | Roles revisados también por backend |

## Forms

| Form | Fields | Validation | Error strategy | Success |
|---|---|---|---|---|
| Login | Correo, contraseña | required, email | No registrar credenciales | Sesión solo en memoria |
| Empleado | Nombres, apellidos, correo, documento, área, cargo, fecha, sueldo | required y tipos nativos | Error API | Actualizar listado |
| Ausencia | Tipo, desde, hasta, motivo | Fechas y texto requeridos | Error API | Recarga |
| Reclutamiento | Vacante y candidato con PDF opcional | Campos requeridos | Error API o subida | Listado actualizado |
| Evaluación | Empleado, evaluador, periodo, comentarios | required | Error API | Registro y completar |

## Responsive behaviour

| Breakpoint | Priority content | Nav | Grid / tables |
|---|---|---|---|
| ≤375 | Tarea y mensajes | Menú desplegable | Una columna, tabla con scroll local |
| 768 | Resumen y listado | Menú compacto | Dos columnas |
| ≥1280 | Resumen completo | Lateral fija | Tres estadísticas y dos paneles |

## Accessibility requirements

- Keyboard: botones y campos nativos; foco visible y enlace a contenido.
- Focus / modals: formularios en página; cambio de módulo anunciado con encabezado.
- Labels / live regions: etiquetas reales, alertas role=alert y skeletons role=status; reduced-motion.

## Content & data policy

- Real data sources: siete APIs dev de las colecciones Postman del repositorio.
- Forbidden inventions (metrics, logos, testimonials): ninguna cifra inventada o credencial embebida.
- Placeholder policy: skeletons y estados vacíos explícitos; datos simulados solo en pruebas aisladas.

## Acceptance criteria

- [ ] Login, logout y aislamiento de empresa verificados en navegador.
- [ ] Skeletons visibles con red demorada y accesibles con movimiento reducido.
- [ ] Compilación, pruebas, vista móvil y despliegue Amplify verificados.
