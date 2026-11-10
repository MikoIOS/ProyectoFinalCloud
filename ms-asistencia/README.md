# ms-asistencia

Marcaciones, permisos, vacaciones y ausencias del SaaS HCM. Python 3.12, API Gateway, Lambda y DynamoDB; utiliza el Lambda Authorizer y SNS de `ms-usuarios`.

## Reglas

- El tenant se obtiene del JWT. Empleados registran y consultan sus propios datos; RR. HH. puede registrar para otros. RR. HH. y gerentes consultan reportes.
- Una entrada y una salida por empleado/día. El empleado usa la hora del servidor en Lima; solo RR. HH. indica fecha/hora manual. Entrada posterior a 09:10 registra tardanza. Se rechazan fechas futuras y salidas anteriores a la entrada.
- Ausencias: `VACACIONES`, `PERMISO`, `LICENCIA_MEDICA`, `SIN_GOCE`; de 1 a 90 días calendario. No se admiten cruces con solicitudes pendientes o aprobadas.
- El jefe directo o RR. HH. aprueba/rechaza, sin autoaprobación. El solicitante o RR. HH. cancela solicitudes pendientes. Solo se finalizan aprobadas después del último día.
- Las vacaciones reservan saldo al solicitarse y lo liberan al rechazar/cancelar. Modelo del proyecto: 30 días por año calendario, sin cálculo de antigüedad ni acumulación de años anteriores.
- Se consulta al empleado en su tabla y tenant; se rechaza registrar o aprobar para empleados cesados.
- Las escrituras de ausencias usan transacciones y una versión por empleado: una solicitud concurrente recibe HTTP 409 y debe reintentarse.

## API

Todas las rutas salvo `/ping` requieren `Authorization: Bearer <token>`.

| Método | Ruta | Uso |
|---|---|---|
| GET | `/ping` | Estado del servicio |
| POST | `/marcaciones` | Entrada/salida: `{tipo?, empleado_id?, fecha?, hora?}` |
| GET | `/marcaciones?empleado=&fecha=&limit=&next_token=` | Historial propio o del tenant según rol |
| POST | `/ausencias` | `{tipo, desde, hasta, motivo, empleado_id?}` |
| GET | `/ausencias?empleado=&estado=&tipo=&limit=&next_token=` | Historial de ausencias |
| GET | `/ausencias/pendientes` | RR. HH.: todas; otros: asignadas como jefe directo |
| GET | `/ausencias/{ausencia_id}?empleado=emp-...` | Detalle |
| PATCH | `/ausencias/{ausencia_id}/estado` | `{empleado_id, estado, comentario?}` |
| GET | `/ausencias/saldo/{empleado_id}?anio=2026` | Saldo de vacaciones |
| GET | `/asistencia/resumen?fecha=2026-11-09` | Marcaciones, tardanzas, horas y entradas abiertas |
| GET | `/asistencia/reportes?fecha=2026-11-09` | Descarga CSV diario |

Las consultas devuelven `{items, next_token}`; una página filtrada puede estar vacía y tener continuación. Se debe seguir `next_token` hasta que sea `null`. Los tokens se validan contra el tenant y el prefijo del empleado consultado.

## Datos y eventos

Tabla `hcm-asistencia-dev`: PK `tenant_id`; SK `EMP#<empleado>#MAR#<fecha>`, `EMP#<empleado>#AUS#<ausencia_id>` o `EMP#<empleado>#CONTROL` (versión).

DynamoDB Streams publica `AusenciaSolicitada`, `AusenciaAprobada`, `AusenciaRechazada`, `AusenciaCancelada` y `AusenciaFinalizada` al topic `hcm-eventos`. El publicador conserva el timestamp del cambio en los reintentos. Notificaciones atiende solicitudes, aprobaciones y finalizaciones; los otros eventos quedan disponibles en SNS sin aviso al usuario por ahora.

La aprobación `SIN_GOCE` alimenta los conceptos de nóminas. Los avisos conservan `metadata.ausencia_id` para seguir el flujo. Los correos de solicitud, aprobación y finalización se envían como mensajes legibles en español, con nombre del empleado, tipo, fechas y duración.

Una tarea diaria a las 00:05 de Lima activa vacaciones al comenzar (vuelve a publicar `AusenciaAprobada`) y finaliza ausencias al terminar. Empleados ignora aprobaciones de vacaciones futuras o ya vencidas y solo procesa finalizaciones de vacaciones.

El stream conserva registros durante 24 horas; si el publicador permanece caído más tiempo puede perderse la publicación. Las [alarmas EDA](../monitorizacion/README.md) ya están desplegadas; la recuperación de registros sigue siendo manual. La tarea diaria recorre la tabla: para volúmenes mayores se debe reemplazar por un índice de ausencias pendientes de activación/finalización.

## Desarrollo y despliegue

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m unittest discover -s tests -v
serverless deploy --stage dev
```

No se requieren dependencias adicionales en Lambda: se utiliza boto3 del runtime. La cuenta del laboratorio y `LabRole` siguen la configuración de `ms-nominas`.

Carga ficticia de 30 000 marcaciones (10 000 por tenant):

```bash
python3 scripts/seed_asistencia.py
```

El seed escribe registros identificados con `seed=true` para `2026-10-01`, usando los IDs del seed de empleados. No emite eventos; repetirlo reemplaza esas claves de marcaciones. Son datos sintéticos de demostración.

Prueba real con curl desde la raíz del repositorio:

```bash
python3 ms-asistencia/scripts/probar_curl.py --base-url https://p79musr10g.execute-api.us-east-1.amazonaws.com/dev
```

Solicita la contraseña de las cuentas de demo. Usa el empleado demo de Andina y deja marcaciones históricas y ausencias identificadas con `E2E`. La ausencia sin goce se registra entre 2035 y 2037 para no modificar la nómina actual. Guarda la evidencia en `docs/prueba_asistencia_curl.json`, sin tokens ni contraseñas.
