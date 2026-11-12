# Prueba EDA en dev — 9 de noviembre de 2026

Resultado: **APROBADA** mediante las APIs desplegadas, con usuarios de demo de Andina y Pacífico.

Flujo: API de desempeño → SNS → SQS → Lambda de notificaciones → API de notificaciones.

- Evaluación creada: `eva-9a79ce8a`.
- Identificador de prueba: `E2E-6ee3d9c648b6`.
- Creación de evaluación: HTTP 201; actualización a `COMPLETADA`: HTTP 200.
- Se encontró una notificación `EvaluacionCompletada` asociada a esa evaluación, al evaluador y al tenant `andina`, inicialmente sin leer.
- Intento de marcarla leída desde Pacífico: rechazado (el script acepta HTTP 403 o 404).
- Consulta sin token: HTTP 401.
- Lectura desde Andina: HTTP 200 y `leida=true`.

Durante la prueba se detectó que la conexión SQS → Lambda estaba deshabilitada, con 5 mensajes pendientes. Se habilitó el event source mapping `7a152209-8817-45b0-90d0-8ec530eb3bef` y el flujo terminó correctamente.

Comprobación final a las `21:20:39 UTC`: conexión en estado `Enabled`. SQS aún reportaba aproximadamente 5 mensajes visibles; no se verificó el vaciado de la cola ni el contenido de esos mensajes.

La evaluación y sus notificaciones se conservan en dev como evidencia. La prueba crea datos identificados con `E2E`; no utiliza una evaluación laboral real.

## Repetir

Desde la raíz del repositorio:

```bash
python3 scripts/probar_eda.py
```

El script solicita las credenciales de ambos tenants y lee las URLs de las colecciones Postman. Usar un administrador de RR. HH. de prueba de Andina con identificador `usr-` y un usuario de prueba de Pacífico.

Comprobaciones locales ejecutadas: 3 pruebas del script (`python3 -m unittest discover -s scripts -p 'test_*.py'`) y 5 pruebas del consumidor (`npm test` en `ms-notificaciones`), todas aprobadas.

Alcance: este resultado valida el flujo de evaluación y los controles HTTP indicados. No verifica entrega de correo, carga concurrente ni todos los eventos del catálogo.

## Comprobación posterior de SNS

Consulta realizada el mismo día, desde las `21:23 UTC`, sobre la última hora:

- `hcm-eventos`: CloudWatch registra 1 publicación, 1 entrega y 0 fallos de entrega.
- `hcm-notificaciones-email-dev`: CloudWatch registra 6 publicaciones, sin datos de entregas. El listado de suscripciones SNS no contiene ninguna suscripción al topic de correo; por tanto, actualmente no hay destinatarios configurados para esos avisos.
- La cola `ms-notificaciones-eventos` reporta 0 mensajes visibles y 0 en procesamiento.
- Los logs del consumidor muestran tres invocaciones completadas a las `21:20 UTC`, sin errores registrados en la ventana consultada.

SNS funciona para el flujo entre servicios. Para recibir correos falta suscribir una dirección al topic de correo y confirmar la suscripción desde esa bandeja. No se envió ningún correo de prueba en esta comprobación.

## Prueba con suscripción de correo confirmada — 21:30 UTC

Después de crear y confirmar la suscripción de correo solicitada, se repitió el flujo HTTP completo:

- Evaluación `eva-e0ca8585`, etiqueta `E2E-baa71632d2f6`.
- Creación, finalización, aparición de notificación y lectura correctas; acceso cruzado y anónimo rechazados.
- Lambda consumidora completó la invocación a las `21:30:06 UTC`; la cola quedó con 0 mensajes visibles y 0 en procesamiento.
- CloudWatch, para el minuto `21:30 UTC`, registra 2 publicaciones y 2 entregas en `hcm-notificaciones-email-dev`: corresponden a los avisos del empleado ficticio y del evaluador generados por la prueba.

La entrega registrada por SNS no verifica la ubicación en la bandeja de entrada o spam. También se ejecutaron las 14 pruebas locales de nóminas, todas aprobadas.
