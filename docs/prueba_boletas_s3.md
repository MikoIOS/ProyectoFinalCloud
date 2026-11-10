# Boletas privadas en S3 — 9 de noviembre de 2026

**Resultado: implementado, desplegado y verificado en dev.**

`ms-nominas-dev` terminó en `UPDATE_COMPLETE`. El bucket `hcm-boletas-dev-851725431647` queda administrado por su `serverless.yml` y se conserva al eliminar o reemplazar el recurso.

## Comportamiento

La ruta existente `GET /nominas/{nomina_id}/boleta` valida tenant y permisos, genera el PDF y lo archiva antes de responder. Sigue admitiendo PDF y `?formato=json`, sin agregar URLs públicas ni cambiar las respuestas existentes.

La clave S3 se construye como `<tenant>/boletas/<periodo>/<nomina_id>.pdf`. El tenant proviene del contexto autenticado. Los parámetros de consulta no pueden dirigir el archivo a otro tenant o bucket.

El bucket bloquea acceso público, usa propiedad `BucketOwnerEnforced`, cifra con AES256, conserva versiones y exige HTTPS. Los objetos guardan `tenant_id` y `nomina_id` como metadata para auditoría.

## Verificación

Pasaron **19 pruebas locales** de nóminas, incluidas las nuevas comprobaciones de permisos previos al archivado, PDF/JSON compatibles y errores de S3 visibles.

Pasaron **22 comprobaciones de integración** mediante curl y las APIs AWS:

- Bloqueo de acceso público, versionado, cifrado y política HTTPS verificados en el bucket desplegado.
- Login y descarga PDF del empleado demo de Andina y Pacífico: HTTP 200.
- Los bytes descargados por API coinciden exactamente con los leídos en S3.
- Los objetos están cifrados y tienen metadata del tenant correcto.
- PDF y JSON/base64 devuelven el mismo documento.
- Las descargas sucesivas conservan versiones del archivo.
- Solicitar `tenant_id=andina` con un token de Pacífico sigue produciendo la boleta de Pacífico; las claves y los hashes de los dos documentos son distintos.
- Descargar la boleta de otro empleado: HTTP 403 en ambos tenants.
- Descargar por API sin token: HTTP 401.
- Acceder al objeto de S3 mediante HTTPS sin credenciales: HTTP 403.

Se archivaron las boletas demo de noviembre de 2026 del empleado `emp-000002` en ambos tenants. No se recalculó ninguna planilla ni se cambiaron importes.

Datos originales: [prueba_boletas_s3.json](prueba_boletas_s3.json).

## Alcance

Los PDFs se archivan al descargarlos. No se generaron anticipadamente todas las boletas históricas ni se probaron cargas concurrentes. El frontend y su despliegue en Amplify siguen pendientes.

Referencias: [configuración de buckets en CloudFormation](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-s3-bucket.html), [cifrado en tránsito en S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingEncryptionInTransit.html).
