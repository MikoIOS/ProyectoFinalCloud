# Prueba EDA real en dev

Resultado: **APROBADO**, ejecución `E2E-7a5bc01873`, con dos empresas ficticias nuevas y recursos exclusivos de dev. [Evidencia JSON](eda_dev_real_verificacion.json).

Se ejercitaron los seis consumidores con mensajes de negocio reales:

| Flujo | Resultado comprobado |
|---|---|
| Contratar postulante → SNS → SQS → empleados | Empleado creado con ID derivado de la postulación. |
| EmpleadoCreado → SNS → SQS → usuarios | Cuenta creada automáticamente; login del empleado correcto. |
| EmpleadoCreado → notificaciones | Bienvenida visible para ese empleado. |
| Solicitar y aprobar ausencia → DynamoDB Streams → SNS → SQS | Avisos de solicitud y aprobación; concepto SIN_GOCE de dos días creado en nómina. Solicitud con solo 14 días de anticipación rechazada. |
| Generar planilla HTTP 202 → SQS → worker → DynamoDB → SNS → notificaciones | Planilla GENERADA con un empleado; nómina y aviso disponibles. |
| EvaluacionCompletada → SNS → SQS → notificaciones | Notificación visible para el empleado evaluado. |

Sueldo de prueba: 3 000; bono manual: 100; descuento manual: 50; dos días sin goce: 200; pensión ONP sobre 2 800: 364. Neto comprobado: **2 486**. El PDF descargado comienza con `%PDF` y su objeto S3 está cifrado con AES256.

Se reenvió por SNS el mismo evento AusenciaAprobada con idéntico timestamp. CloudWatch confirmó dos mensajes eliminados de la cola de eventos de nómina durante la ejecución. Tras esas entregas: al terminar continuaban existiendo un único concepto asociado a la ausencia y un único aviso de aprobación. SQS reportó cero mensajes visibles, en vuelo y demorados en las cinco colas y sus cinco DLQs, en dos muestras separadas. El monitor confirmó los seis mappings habilitados.

La segunda empresa recibió HTTP 404 al intentar leer el empleado, la nómina y marcar la notificación de la primera. El acceso anónimo a notificaciones recibió HTTP 401. El empleado propietario pudo marcar su aviso leído.

## Regresión detectada y corregida

La primera ejecución encontró que el descuento sin goce se registraba, pero el cálculo de nómina no lo aplicaba. DynamoDB distingue `tipo=CONCEPTO` de `tipo_concepto=BONO/DESCUENTO/SIN_GOCE`; el calculador leía solo `tipo`. La corrección utiliza `tipo_concepto` cuando está presente y conserva el formato anterior como alternativa. No se modifican tablas ni registros para convertir formatos.

Se añadió `test_conceptos_con_formato_persistido_en_dynamodb`: falló antes del arreglo y pasó después. Las 24 pruebas de nómina pasan. Tras desplegar dev, el EDA completo comprobó los tres tipos de concepto con registros persistidos reales y el neto esperado.

## Alcance

Los datos ficticios, incluidos los de la ejecución que detectó el fallo, se conservan en sus empresas de pruebas. Las credenciales aleatorias permanecen en archivos privados ignorados por Git. No se generaron ni recalcularon planillas de producción durante estas pruebas. El topic de correo de dev no tiene suscriptores: se probó la cadena de notificaciones, **sin verificar entrega en una bandeja de correo**. No se ejecutaron pruebas de carga.

La corrección se desplegó después en prod, conservando las planillas existentes. Se verificó que las tres funciones de nómina tienen el ZIP corregido; las 17 Lambdas están activas y el monitor no detecta canales deshabilitados. Las 17 consultas del cliente para Andina volvieron a pasar.
