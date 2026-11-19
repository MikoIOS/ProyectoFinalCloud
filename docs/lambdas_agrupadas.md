# Agrupación de Lambdas — verificación AWS (17-Nov-2026, Lima)

Estado: **desplegado en dev y prod, con 17 Lambdas por entorno**. Dev terminó su verificación antes de iniciar la actualización de prod. Ambos stacks están en `UPDATE_COMPLETE` y conservan sus URLs.

## Resultado

- 17 funciones activas y actualizadas en cada stack: siete routers HTTP, seis consumidores SQS/Streams, calendario, authorizer y dos monitores.
- 58 rutas HTTP conservadas; 13 consultas autenticadas de los siete módulos aprobadas en cada entorno.
- Integración del cliente contra prod: Administración Andina **17/17**, Empleado Pacífico **9/9**, sin modificar registros de negocio.
- Seis mappings habilitados y 25 alarmas con acciones activas por entorno. Monitor sin canales deshabilitados.
- Dev utiliza siete tablas, buckets, colas y topics propios; solo se creó una empresa ficticia para las consultas de prueba. Prod conserva los recursos originales y el secreto JWT anterior.
- Frontend publicado accesible y apuntando a la misma API de prod.

## Dependencias y pruebas locales

Dependencias instaladas en `/tmp/hcm-build`: requirements de construcción y de usuarios, empleados y asistencia, incluyendo pytest y moto con soporte DynamoDB/SNS/SQS. Notificaciones se instaló con `npm ci`.

**177 pruebas Python y 13 Node aprobadas en el despliegue inicial**, sin omitir las pruebas de plantillas. Tras corregir el cálculo se repitieron las 30 pruebas HCM y las 24 de nómina (incluida la nueva regresión), además del EDA real. Desglose de la ejecución inicial:

| Suite Python | Aprobadas |
|---|---:|
| HCM, rutas, artefactos y plantillas | 30 |
| Usuarios | 55 |
| Empleados | 46 |
| Asistencia | 13 |
| Nóminas | 23 |
| Reclutamiento | 3 |
| Monitorización | 7 |

Node: siete pruebas de notificaciones y seis de recursos de monitorización. Los tests de agrupación recorren las 58 rutas y ejecutan las 17 funciones desde sus ZIPs con handlers reales y AWS simulado.

## Revisión y operación

Los change sets de dev y prod se revisaron antes de desplegar: sin eliminación o reemplazo de recursos de datos y conservando el secreto JWT. Los prototipos vacíos de dev, respaldados y fuera del stack, se retiraron tras comprobar que las siete tablas no tenían registros y los dos buckets no tenían objetos, versiones ni cargas pendientes. CloudFormation creó los recursos definitivos de pruebas. No se borraron bases originales ni respaldos.

La verificación de prod encontró sus seis mappings deshabilitados fuera de CloudFormation. El stream registraba un error de permisos del laboratorio anterior. Se reactivaron tras descartar consumidores duplicados; el monitor quedó sano. Al renovar el laboratorio, revisar el estado efectivo de estos mappings además del estado del stack.

## Límites

Las siete funciones HTTP se ejercitaron mediante API Gateway con credenciales reales. La comprobación inicial de consumidores con lotes vacíos se amplió con el [EDA completo de dev](eda_dev_real.md), con mensajes reales y resultados persistidos de los seis consumidores. En prod se mantienen las comprobaciones de lectura y lotes vacíos. El formateador se invocó sin mensajes, sin enviar correo. El calendario se ejecutó sobre datos de dev; en prod se comprobó mediante `DryRun` para evitar cambios manuales de ausencias. No se generaron nóminas reales ni se ejecutó una restauración del respaldo en esta validación.

[Evidencia conjunta](hcm_unificado_verificacion.json) · [Dev](lambdas_dev_verificacion.json) · [Prod](lambdas_prod_verificacion.json).

## Ampliación EDA y corrección de nómina

El EDA real encontró y permitió corregir que el calculador ignoraba `tipo_concepto` de los registros DynamoDB. La nueva regresión falló antes del cambio y las 24 pruebas de nómina pasan después. Las 30 pruebas HCM también se repitieron sin omisiones. El EDA de dev confirmó bono 100, descuento 50, ausencia sin goce 200 y neto 2 486 con sueldo 3 000. [Evidencia de las cadenas y controles](eda_dev_real_verificacion.json). No se recalcularon planillas históricas.
