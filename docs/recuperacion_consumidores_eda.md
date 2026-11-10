# Recuperación de consumidores EDA — 9 de noviembre de 2026

**Resultado: usuarios y empleados habilitados, mensajes pendientes procesados y 25 alarmas en OK.**

Verificación final: `2026-11-09T23:06:19.321590+00:00`.

## Recuperación

AWS registraba ambos mappings como `Disabled` con razón `USER_INITIATED`. La consulta de CloudTrail no devolvió un evento que permitiera identificar el motivo concreto o el autor de la desactivación. Se habilitaron mediante `UpdateEventSourceMapping`:

| Consumidor | Mapping | Mensajes pendientes antes | Estado final |
|---|---|---:|---|
| `ms-usuarios-dev-procesarEventos` | `b4e74f30-1c53-4422-9672-5fc2b481d049` | 2 | Enabled |
| `ms-empleados-dev-procesarEventos` | `e5b2843e-1250-4be1-a2f8-7d828ac43947` | 5 | Enabled |

Se verificó en AWS:

- Las dos colas principales tienen 0 mensajes visibles, 0 en procesamiento y 0 diferidos.
- Las dos DLQ tienen 0 mensajes en esas mismas categorías.
- CloudWatch SQS registra 2 y 5 mensajes eliminados por la integración tras procesarlos; los logs muestran invocaciones completadas sin errores.
- El monitor ejecutado en Lambda devuelve `{"canales_no_habilitados": []}`.
- Las 25 alarmas están en `OK`; la recuperación ocurrió con las métricas reales, sin forzar manualmente el estado.
- Las comprobaciones con curl de login admin y consulta del empleado `emp-000002` pasaron en Andina y Pacífico, verificando el tenant de la respuesta.

No se purgaron colas ni se borraron mensajes manualmente. No se modificó el código de los consumidores para esta recuperación.

Evidencia original: [recuperacion_consumidores_eda.json](recuperacion_consumidores_eda.json).

## Efecto de los ceses pendientes

Los dos eventos de usuarios eran `EmpleadoCesado` para `emp-000003` y `emp-000004` de Andina. Al procesarlos, el consumidor dejó inactivas `usr-000003` (gerente) y `usr-000004` (reclutador). Sus registros de empleados figuran `ACTIVO`.

Las cuentas equivalentes de Pacífico y Sierra siguen activas. Después, el usuario solicitó activar las dos cuentas. Se reactivaron mediante la API administrativa de usuarios y ambos logins respondieron HTTP 200. Evidencia: [reactivacion_cuentas_demo.json](reactivacion_cuentas_demo.json).

Esta diferencia entre el estado de empleado y la cuenta no debe confundirse con un fallo de SQS: el consumidor procesó los eventos de cese según su lógica vigente. Ambas cuentas están activas tras la instrucción del usuario.
