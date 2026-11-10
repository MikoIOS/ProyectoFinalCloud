# Prueba de alarmas EDA — 9 de noviembre de 2026

Resultado: **despliegue y canal de avisos verificados en AWS dev**.

- Stack `hcm-monitorizacion-dev`: `UPDATE_COMPLETE`.
- **25 alarmas** creadas; las acciones están conectadas al topic `hcm-alarmas-dev`.
- Suscripción SNS confirmada al consumidor `hcm-monitorizacion-dev-avisarAlarma`.
- Invocación del monitor de conexiones: HTTP 200, sin `FunctionError`; detectó dos consumidores deshabilitados.
- **16 pruebas locales** del monitor, recursos y script de alarmas aprobadas; también pasaron las 3 pruebas existentes del script EDA.

## Prueba controlada

Se ejecutó `python3 scripts/probar_alarmas.py --stage dev` contra CloudWatch. La prueba usa una métrica sintética y no modifica datos del negocio ni introduce mensajes defectuosos en las colas.

Se comprobó `OK → ALARM → OK`. El script terminó a las `22:48:29 UTC` y guardó [prueba_alarmas.json](prueba_alarmas.json).

El historial de acciones de `hcm-dev-eda-prueba` registra ejecuciones correctas hacia SNS:

| Hora UTC | Acción |
|---|---|
| 22:47:21 | Publicación de la alerta |
| 22:48:21 | Publicación de la recuperación |

Las métricas SNS de la ventana de 15 minutos consultada registraron:

| Topic | Publicaciones | Entregas | Fallos |
|---|---:|---:|---:|
| `hcm-alarmas-dev` | 26 | 26 | 0 |
| `hcm-notificaciones-email-dev` | 5 | 5 | 0 |

El topic de alarmas también recibió estados iniciales de CloudWatch. El formateador omitió los OK iniciales y publicó cinco correos: avisos de problemas reales y la prueba con su recuperación. Los correos usan texto en español; el aviso de respaldo por fallo del formateador usa el formato nativo de CloudWatch.

Datos originales de la verificación: [verificacion_alarmas_aws.json](verificacion_alarmas_aws.json). Una entrega registrada por SNS no comprueba la ubicación en la bandeja de entrada o spam del suscriptor.

## Problemas reales detectados

| Consumidor | Estado | Motivo de transición | Mensajes visibles en su cola |
|---|---|---|---:|
| `ms-usuarios-dev-procesarEventos` | Disabled | USER_INITIATED | 2 |
| `ms-empleados-dev-procesarEventos` | Disabled | USER_INITIATED | 5 |

Las alarmas de retraso de ambas colas y de conexiones deshabilitadas están en `ALARM`. Las otras 22 alarmas estaban en `OK` al finalizar la verificación. No se modificaron esas conexiones ni se borraron mensajes: atenderlas queda pendiente.

## Alcance

Se verificaron el despliegue, la revisión de conexiones, la evaluación real de la alarma sintética, sus acciones SNS, el consumidor de avisos y las métricas de entrega de correo. Los permisos SNS usan acciones explícitas y el canal de avisos se crea antes de las alarmas para evitar perder avisos al desplegar.

No se provocaron fallos reales de negocio ni se hizo una prueba de carga. Las alarmas detectan problemas; no realizan recuperación automática ni extienden la retención del stream de asistencia.

## Recuperación posterior

Las conexiones de usuarios y empleados se habilitaron después de esta prueba. Se procesaron los siete mensajes pendientes, las colas principales y DLQ quedaron vacías y las 25 alarmas volvieron a OK. Ver [recuperacion_consumidores_eda.md](recuperacion_consumidores_eda.md) para la evidencia y la reactivación posterior de las dos cuentas demo afectadas por ceses.
