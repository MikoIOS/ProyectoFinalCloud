# Respaldos DynamoDB directamente en S3

`dynamodb_backup.py` solicita una exportación completa y nativa de cada tabla a S3. **Los datos no pasan por el dispositivo ni por la VM**; AWS ejecuta la copia y el script consulta su avance. El disco local solo guarda un manifiesto de estado. Por defecto selecciona todas las tablas `hcm-*` de la región, incluidas las originales y las de pruebas.

La exportación usa una instantánea consistente por tabla, requiere PITR y no consume capacidad de lectura de la tabla. Si PITR está deshabilitado, el script lo habilita. **PITR, exportaciones y almacenamiento S3 tienen costos.** No hay una instantánea atómica conjunta de las siete tablas. [Documentación AWS](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/S3DataExport_Requesting.html).

## Ejecutar desde tu dispositivo

Desde la raíz del proyecto, con boto3 instalado y credenciales AWS válidas:

```sh
python3 backup/dynamodb_backup.py \
  --bucket hcm-backups-851725431647-us-east-1
```

Si el bucket no existe, se crea en la región seleccionada (por defecto `us-east-1`). Debe pertenecer a tu cuenta. El script bloquea el acceso público del bucket y exige cifrado SSE-S3 (`AES256`) para sus objetos. Usar un bucket dedicado a respaldos; no reutilizar un bucket que deba ser público. No se borran copias ni se cambian políticas de retención automáticamente.

Para respaldar una tabla concreta, añadir `--table hcm-usuarios`; se puede repetir `--table`. `--destination` sigue disponible, pero ahora selecciona **solo el directorio del estado local**; por defecto `~/hcm-backup-status`. Ya no se escriben exportaciones de datos `.jsonl.gz` en el dispositivo.

Cada ejecución usa un prefijo nuevo:

```text
s3://hcm-backups-851725431647-us-east-1/dynamodb/<ejecucion>/
  manifest.json
  <tabla>/schema.json
  <tabla>/AWSDynamoDB/<export-id>/...
```

AWS genera archivos de datos comprimidos y sus propios manifiestos/checksums. `schema.json` conserva la descripción de la tabla para ayudar en la recuperación. `manifest.json` guarda los ARN de exportación, los tokens de solicitud y el resultado; solo indica `COMPLETE` cuando todas las exportaciones están `COMPLETED` en AWS.

## Si presionas Ctrl+C

El script marca la espera como `INTERRUPTED`, conserva el manifiesto local y trata de actualizar el de S3. **Las exportaciones que ya aceptó AWS siguen ejecutándose.** Las tablas que todavía no se enviaron no se exportarán con esa ejecución. Si una solicitud se interrumpe mientras se envía, su estado puede quedar `SUBMITTING`; revisar las exportaciones de la tabla antes de iniciar otra copia.

Para consultar un trabajo ya enviado:

```sh
aws dynamodb describe-export --export-arn '<export_arn-del-manifiesto>' --region us-east-1
aws s3 ls s3://hcm-backups-851725431647-us-east-1/dynamodb/ --recursive
```

No hace falta reiniciar la copia para consultar su estado. Si cierras el proceso, el manifiesto no se actualizará automáticamente aunque AWS termine: consultar `describe-export`. Cada nueva ejecución inicia nuevos trabajos y puede generar nuevos cargos. El script deja de esperar a las seis horas; tampoco cancela los trabajos en ese caso.

Los backups nativos o archivos locales creados por la versión anterior **no se eliminan ni se suben automáticamente**. La nueva versión hace exportaciones nuevas. Un `KeyboardInterrupt` del script anterior no confirma que se haya terminado ningún respaldo.

## Ejecutar diariamente desde una VM Linux

La VM solo necesita solicitar y supervisar las exportaciones; no necesita disco para guardar todos los registros.

```sh
sudo useradd --system --create-home --home-dir /home/hcmbackup hcmbackup
sudo install -d -m 0755 /opt/hcm-backup
sudo install -m 0644 backup/dynamodb_backup.py backup/requirements.txt /opt/hcm-backup/
sudo python3 -m venv /opt/hcm-backup/.venv
sudo /opt/hcm-backup/.venv/bin/pip install -r /opt/hcm-backup/requirements.txt
sudo install -m 0644 backup/hcm-dynamodb-backup.service backup/hcm-dynamodb-backup.timer /etc/systemd/system/
echo 'HCM_BACKUP_BUCKET=hcm-backups-851725431647-us-east-1' | sudo tee /etc/hcm-backup.env
sudo chmod 0600 /etc/hcm-backup.env
sudo systemctl daemon-reload
sudo systemctl start hcm-dynamodb-backup.service
sudo journalctl -u hcm-dynamodb-backup.service -n 50 --no-pager
sudo systemctl enable --now hcm-dynamodb-backup.timer
systemctl list-timers hcm-dynamodb-backup.timer
```

Si `hcmbackup` ya existe, omitir `useradd`. El timer se ejecuta a las 03:00 UTC (22:00 Lima del día anterior). Systemd evita solapar la misma unidad. En una instalación existente, volver a copiar el script y el unit y ejecutar `daemon-reload` antes de la próxima copia.

En EC2 usar un instance profile IAM. En otras VMs configurar credenciales renovables para `hcmbackup`. No guardar claves en Git ni en el unit de systemd. AWS Academy expira sus credenciales: sin renovarlas, los nuevos respaldos fallan. Es necesaria conexión HTTPS y resolución DNS. Revisar el journal, el estado de las exportaciones y probar restauraciones periódicamente; no se configuró una alerta externa de fallos.

## Permisos necesarios

- `sts:GetCallerIdentity` para identificar la cuenta.
- `dynamodb:ListTables` sobre `*`.
- `dynamodb:DescribeTable`, `dynamodb:DescribeContinuousBackups`, `dynamodb:UpdateContinuousBackups` y `dynamodb:ExportTableToPointInTime` sobre las tablas `hcm-*`.
- `dynamodb:DescribeExport` sobre sus recursos `table/hcm-*/export/*`.
- `s3:CreateBucket` si hay que crear el bucket; `s3:ListBucket` para la comprobación de acceso/propiedad y `s3:PutBucketPublicAccessBlock` sobre el bucket de respaldo.
- `s3:PutObject`, `s3:PutObjectAcl` y `s3:AbortMultipartUpload` sobre los objetos de ese bucket. `s3:ListBucketMultipartUploads`/`s3:ListMultipartUploadParts` pueden requerirse para diagnóstico de cargas.
- Para consultar/descargar respaldos, `s3:ListBucket` y `s3:GetObject`.

Si las tablas usan claves KMS administradas por el cliente, revisar los permisos KMS de origen. El bucket de destino debe permitir SSE-S3; una política que obligue a usar una clave KMS distinta hará fallar esta configuración. AWS Academy puede restringir PITR/exportaciones aunque el login sea válido; el script reporta el error y no marca la copia como completada.

## Recuperación

Importar los archivos del directorio `data/` del export como `DYNAMODB_JSON`, compresión `GZIP`, a una **tabla nueva** de recuperación. Usar claves e índices de `schema.json`; no pasar la respuesta completa de `DescribeTable` como configuración de creación porque contiene campos de solo lectura. No importar `schema.json` ni los manifiestos como registros. [Guía AWS de exportación/importación](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-migrating-table-between-accounts-s3.html).

Verificar datos, índices, permisos, streams, TTL, PITR y conexiones antes de apuntar la API a la tabla restaurada. El script no restaura automáticamente ni reemplaza producción. El bucket continúa en la misma cuenta: esto no constituye una copia aislada contra pérdida completa de la cuenta.

Pruebas sin AWS: `python3 -m unittest discover -s backup -v`. La exportación real, la restauración y la instalación en una VM siguen pendientes de verificación.
