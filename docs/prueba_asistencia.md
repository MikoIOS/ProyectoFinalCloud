# Evidencia de ms-asistencia — 9 de noviembre de 2026

Servicio desplegado en `dev`: https://p79musr10g.execute-api.us-east-1.amazonaws.com/dev

CloudFormation: `ms-asistencia-dev`, estado `CREATE_COMPLETE`. Publicación de eventos desde DynamoDB Streams habilitada; el mapping reportó `OK`.

## Pruebas

- **11 pruebas locales de asistencia**, con DynamoDB/SNS simulados mediante moto: marcaciones, validaciones, saldo, solapamientos, permisos, aislamiento, paginación, transacciones concurrentes, calendario, seed y reintentos del publicador.
- **46 pruebas de empleados** aprobadas, incluidas las nuevas comprobaciones para no activar vacaciones futuras ni finalizar vacaciones al terminar un permiso.
- **6 pruebas de notificaciones** aprobadas, incluida la conservación de `ausencia_id` en metadata.
- **34 comprobaciones mediante curl contra AWS** aprobadas. Las peticiones reales y sus códigos esperados están registrados en [prueba_asistencia_curl.json](prueba_asistencia_curl.json).

La prueba curl creó una entrada a las 09:25 y una salida a las 17:55: 15 minutos de tardanza y 8.5 horas. Comprobó historial, resumen y CSV, y rechazó duplicados, salida anterior a la entrada, modificación de hora por empleados y consulta de datos ajenos.

También comprobó solicitud, solapamientos, aprobación por RR. HH., prohibición de autoaprobación, rechazo de doble aprobación y finalización anticipada. Un permiso histórico se aprobó y finalizó correctamente.

Pacífico no pudo obtener ni aprobar la ausencia de Andina: HTTP 404. La consulta de marcaciones desde Pacífico devolvió una lista vacía. Sin token: HTTP 401.

## Integración EDA

Ausencia sin goce de prueba: `aus-f42475c6470d4fb7b52e0e2c3ada3138`, empleado demo `emp-000002`, fecha `2035-07-14`.

Se verificó por HTTP:

1. Notificación `AusenciaAprobada` dirigida al usuario del empleado demo, con `metadata.ausencia_id` coincidente.
2. Concepto de nómina con referencia `AUSENCIA-aus-f42475c6470d4fb7b52e0e2c3ada3138` para el periodo `2035-07`.

La cola de notificaciones quedó con 0 mensajes visibles y 0 en procesamiento. La Lambda de calendario se invocó correctamente en AWS: HTTP de invocación 200, sin `FunctionError`, resultado `{"actualizadas": 0}`; la activación y finalización en distintas fechas se verificaron localmente con reloj controlado.

## Volumen

La auditoría final contó **30 004 registros** en `hcm-asistencia-dev`: 10 004 de Andina, 10 000 de Pacífico y 10 000 de Sierra. Incluye 30 000 marcaciones ficticias y los registros E2E/control del empleado demo. Los siete microservicios superan los 30 000 registros; detalle en [metricas_bd.md](metricas_bd.md).

## Repetir y límites

```bash
python3 ms-asistencia/scripts/probar_curl.py \
  --base-url https://p79musr10g.execute-api.us-east-1.amazonaws.com/dev
```

Solicita la clave de las cuentas demo. Conserva registros E2E y conceptos de nómina de años futuros; no modifica la nómina actual ni incluye tokens en el archivo de evidencia.

No se hicieron pruebas de carga concurrente contra AWS ni se esperó al siguiente disparo diario del calendario. El saldo es una simplificación de 30 días por año calendario; el stream retiene cambios durante 24 horas. Las alarmas ya están desplegadas y verificadas en [prueba_alarmas.md](prueba_alarmas.md); la recuperación no es automática.

## Correo legible — 22:00 UTC

Se desplegó el formato de correo en español para solicitudes, aprobaciones y finalizaciones, con asunto descriptivo, nombre del empleado, tipo, fechas y duración. Pasaron las 7 pruebas de notificaciones y las 11 de asistencia.

Se creó por API el permiso de prueba `aus-2d75ff09fa154a879f78ee45077d0fc9` para `Empleado Demo`, fecha `2040-03-18`. El consumidor de notificaciones completó la ejecución sin errores a las `22:00:53 UTC`. La solicitud se canceló después de generar el aviso para no dejar un permiso pendiente. No se comprobó la bandeja de entrada del suscriptor.
