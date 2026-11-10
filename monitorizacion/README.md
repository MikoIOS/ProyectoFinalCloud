# Alarmas del flujo EDA — dev

**Estado: desplegado y verificado en AWS dev el 9 de noviembre de 2026.** Stack `hcm-monitorizacion-dev` en `UPDATE_COMPLETE`, 25 alarmas creadas y prueba `OK → ALARM → OK` completada. SNS registró 5 entregas de correo y 0 fallos en la ventana de verificación. [Evidencia](../docs/prueba_alarmas.md).

## Cobertura

Se definen 25 alarmas:

| Señal | Cantidad | Condición |
|---|---:|---|
| Errores de consumidores, publicador de asistencia y calendario | 7 | Al menos 1 error Lambda en un minuto |
| Errores capturados con respuesta parcial | 1 | Al menos 1 error registrado por los 6 procesadores |
| Mensajes en DLQ | 5 | Al menos 1 mensaje visible |
| Retraso en colas de eventos | 4 | Mensaje de al menos 5 minutos durante 2 periodos de un minuto |
| Retraso en trabajos de planillas | 1 | Mensaje de al menos 30 minutos durante 2 periodos de un minuto |
| Retraso del stream de asistencia | 1 | IteratorAge de al menos 5 minutos durante 2 periodos |
| Fallos de entrega SNS | 2 | Al menos 1 fallo en eventos o correo |
| Conexiones EDA deshabilitadas o monitor sin reportar | 1 | Problema en 2 revisiones de 5 minutos; datos ausentes también disparan la alarma |
| Error del monitor de conexiones | 1 | Al menos 1 error Lambda |
| Error del formateador de avisos | 1 | Al menos 1 error Lambda; aviso directo de respaldo |
| Prueba controlada | 1 | Métrica sintética independiente de los datos del negocio |

Las colas cubiertas son usuarios, empleados, notificaciones, eventos de nóminas y trabajos de planillas. Los nombres actuales de esas colas no contienen stage: este stack está previsto para el **dev existente**, no para desplegar otro ambiente sobre las mismas colas.

Los fallos parciales se detectan mediante filtros de logs: los consumidores capturan excepciones y devuelven `batchItemFailures`, por lo que mirar únicamente `AWS/Lambda Errors` dejaría esos fallos sin cubrir. Los filtros apuntan a los mensajes de error existentes, sin cambiar los consumidores.

El monitor comprueba cada cinco minutos los seis event source mappings SQS/Streams. No habilita conexiones ni modifica mensajes. Publica la cantidad de funciones con conexiones ausentes o cuyo estado no es `Enabled`; si la consulta a AWS falla, la invocación falla y no publica un estado saludable.

## Correo

CloudWatch → `hcm-alarmas-dev` → Lambda de formato → `hcm-notificaciones-email-dev` → suscripción de correo ya confirmada.

Los avisos son texto en español con estado, nombre de alarma, explicación y enlace a CloudWatch. Se envían alertas y recuperaciones; los estados OK iniciales se omiten. Si falla el formateador, una alarma de respaldo publica directamente en el topic de correo con el formato nativo de CloudWatch.

La política del nuevo topic permite publicaciones de CloudWatch únicamente desde esta cuenta y desde alarmas `hcm-dev-eda-*`. La política del topic de correo mantiene el acceso del propietario y agrega el permiso específico para la alarma de respaldo. Antes de desplegar se debe revisar la política actual del topic de correo para preservar cualquier permiso adicional que se haya agregado fuera de este repositorio.

## Pruebas locales

Desde esta carpeta:

```bash
python3 -m unittest discover -s tests -v
node --test tests/recursos.test.cjs
serverless print --stage dev
```

Desde la raíz:

```bash
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

Se aprobaron 6 pruebas Python del monitor/formato, 6 pruebas de recursos y 4 pruebas del script de alarmas. También pasaron las 3 pruebas existentes del script EDA. Serverless resolvió la configuración para dev y completó el despliegue. Se verificaron la suscripción SNS, la ejecución del monitor en AWS y las acciones de alerta y recuperación.

## Desplegar y verificar

Requisitos: servicios existentes desplegados, export `ms-notificaciones-dev-EmailTopicArn`, credenciales vigentes y `LabRole` del laboratorio.

Desde esta carpeta, comprobar primero las conexiones reales y publicar la primera muestra del monitor. Esto evita evaluar como ausentes datos anteriores al despliegue:

```bash
STAGE=dev python3 canales.py
serverless deploy --stage dev
```

Si la comprobación inicial detecta una conexión deshabilitada, corregir su causa antes de habilitarla; no se habilita automáticamente. Verificar la ejecución del monitor en AWS y que la alarma de conexiones quede en OK.

Desde la raíz, probar la evaluación sin introducir errores en el negocio:

```bash
python3 scripts/probar_alarmas.py --stage dev
```

El script espera OK, publica una muestra sintética, verifica ALARM con acciones habilitadas y espera la recuperación a OK. Restablece el valor de prueba a cero incluso si la validación de acciones falla. Guarda `docs/prueba_alarmas.json` únicamente después de verificar la secuencia completa.

Esta prueba verifica la evaluación de la alarma y su configuración de acciones. La entrega se verifica por separado mediante historial de acciones, logs de `hcm-monitorizacion-dev-avisarAlarma`, métricas SNS y recepción del suscriptor. No se debe confundir una prueba local o un estado ALARM con una entrega confirmada.

## Responder a una alerta

1. Abrir el enlace del correo y comprobar la métrica y las fechas.
2. Revisar el log del procesador, el estado del mapping y los permisos de SNS/SQS/DynamoDB.
3. Si hay DLQ, inspeccionar mensajes sin purgar ni borrar. Corregir la causa y comprobar que reintentar sea seguro antes de reenviar.
4. Comprobar la recuperación del servicio y el cambio de la alarma a OK.

Las alarmas detectan problemas; no hacen recuperación automática ni amplían las 24 horas de retención de DynamoDB Streams. Si falla la entrega al mismo topic de correo no hay un canal alternativo de notificación. No se incluyen pruebas de carga ni alarmas de todas las APIs HTTP. Los recursos están sujetos a las tarifas normales de CloudWatch, SNS y Lambda.

Referencias: [métricas SQS](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-available-cloudwatch-metrics.html), [respuestas parciales de SQS](https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-errorhandling.html), [notificaciones y permisos de CloudWatch](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Notify_Users_Alarm_Changes.html).

## Estado después de recuperar los consumidores

Se habilitaron las conexiones de usuarios y empleados, se procesaron sus 2 y 5 mensajes pendientes, y las colas principales y DLQ quedaron vacías. El monitor devuelve cero conexiones deshabilitadas y las 25 alarmas volvieron a OK. [Evidencia de recuperación](../docs/recuperacion_consumidores_eda.md).

Los dos eventos de usuarios eran ceses de cuentas demo de Andina. Las cuentas gerente y reclutador quedaron inactivas por esos eventos; después se reactivaron por instrucción del usuario y ambos logins se verificaron con HTTP 200. [Evidencia](../docs/reactivacion_cuentas_demo.json).
