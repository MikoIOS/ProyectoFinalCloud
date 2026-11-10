# ms-nominas — Nóminas, boletas y bandas salariales

Microservicio serverless del HCM (Grupo 2) para generación de planillas, cálculo de nóminas, boletas PDF, conceptos y bandas salariales. Usa Python 3.12, API Gateway REST, DynamoDB, SQS y el topic SNS compartido `hcm-eventos`.

## Estado desplegado (dev)

- API: `https://0f0k9vomdk.execute-api.us-east-1.amazonaws.com/dev`
- Tabla: `hcm-nominas-dev`
- Colas: `ms-nominas-trabajos`, `ms-nominas-trabajos-dlq`, `ms-nominas-eventos`, `ms-nominas-eventos-dlq`
- Autorizador: export `AuthorizerArn` de `ms-usuarios-dev`
- Topic: export `EventosTopicArn` de `ms-usuarios-dev` (`hcm-eventos`)
- Datos sembrados: **30,745 registros** (3 tenants), ampliados a **40,504** tras probar la generación asíncrona de `2026-12`.

## Arquitectura

```
Cliente / Frontend
      │  JWT (tenant_id, rol, empleado_id)
      ▼
API Gateway REST ──► Lambda Authorizer (ms-usuarios)
      │
      ├──► Lambdas HTTP ──► DynamoDB hcm-nominas-dev
      │                       ├── periodo-index
      │                       ├── empleado-index
      │                       ├── concepto-index
      │                       ├── planilla-index
      │                       └── cargo-index
      │
      └──► POST /nominas/generar ──► SQS ms-nominas-trabajos
                                          │
                                          ▼
                                  Lambda procesarPlanilla
                                          │
                                          ├── lee hcm-empleados (proyección)
                                          ├── calcula y guarda nóminas
                                          └── publica NominaGenerada (opcional)

SNS hcm-eventos ──► SQS ms-nominas-eventos ──► Lambda procesarEventos
   ├── AusenciaAprobada (sin goce) ──► concepto SIN_GOCE
   └── EmpleadoCesado             ──► liquidación referencial
```

## Endpoints

Todos requieren `Authorization: Bearer <token>` salvo el login. El `tenant_id` sale del JWT; **no** se envía en el body.

| Método | Ruta | Roles | Descripción |
|---|---|---|---|
| POST | `/nominas/generar` | `admin_rrhh` | Encola generación asíncrona. Body: `{"periodo":"YYYY-MM","notificar":false,"forzar":false}`. Responde `202`; `409` si ya existe. |
| GET | `/nominas?periodo=YYYY-MM&limit=10&next_token=...` | `admin_rrhh`, `gerente` | Lista nóminas del periodo. |
| GET | `/nominas/resumen?periodo=YYYY-MM` | `admin_rrhh`, `gerente` | Totales de la planilla y empleados activos. |
| GET | `/nominas/planillas?limit=10` | `admin_rrhh`, `gerente` | Lista planillas. |
| GET | `/nominas/planillas/{periodo}` | `admin_rrhh`, `gerente` | Estado y totales de una planilla. |
| GET | `/nominas/empleado/{empleado_id}` | propio / RR.HH. / gerente | Nóminas del empleado y su liquidación. |
| GET | `/nominas/liquidaciones/{empleado_id}` | propio / RR.HH. / gerente | Liquidación referencial por cese. |
| GET | `/nominas/{nomina_id}` | propio / RR.HH. / gerente | Detalle de una nómina. |
| GET | `/nominas/{nomina_id}/boleta` | propio / RR.HH. / gerente | Boleta PDF. Enviar `Accept: application/pdf`. |
| GET | `/nominas/{nomina_id}/boleta?formato=json` | propio / RR.HH. / gerente | Boleta como `{nombre_archivo, contenido_base64}`. |
| POST | `/nominas/conceptos` | `admin_rrhh` | Crea concepto manual (`BONO`, `DESCUENTO`, `SIN_GOCE`, etc.). |
| GET | `/nominas/conceptos?periodo=YYYY-MM&empleado_id=...` | `admin_rrhh`, `gerente` | Lista conceptos. |
| GET | `/bandas?limit=20` | autenticado | Lista bandas salariales por cargo. |
| PUT | `/bandas` | `admin_rrhh` | Crea/actualiza banda (`cargo`, `minimo`, `maximo`, `moneda`). |

### Ejemplo: generar planilla

```bash
curl -X POST "$BASE/nominas/generar" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"periodo":"2026-12","notificar":false}'
```

La generación es asíncrona. Consulta el estado con `GET /nominas/planillas/2026-12` hasta que `estado` sea `GENERADA` o `FALLIDA`.

### Ejemplo: descargar boleta PDF

```bash
curl "$BASE/nominas/nom-2026-11-emp-000001/boleta" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/pdf" \
  -o boleta.pdf
```

API Gateway solo decodifica la respuesta binaria si el cliente envía `Accept: application/pdf`. Si no, usa `?formato=json` y decodifica `contenido_base64`.

## Cálculo implementado

- Sueldo proporcional a días laborados (30 días base).
- Aporte pensionario ONP 13% sobre la remuneración afecta.
- EsSalud 9% como aporte del empleador.
- Bonos y descuentos manuales.
- Ausencias `SIN_GOCE` descuentan días.
- Liquidación referencial: vacaciones truncas, CTS trunca y gratificación trunca; es una **simplificación** para el proyecto, no reemplaza una liquidación legal completa.

La lógica está en `src/services/calculo.py` y `src/services/liquidacion.py`.

## Archivo de boletas en S3

Al descargar una boleta, el servicio valida el JWT, busca la nómina en el tenant del token y comprueba que el empleado sea su titular o que el usuario sea RR. HH./gerente. Después genera el PDF, lo guarda en S3 y devuelve el formato PDF o JSON existente.

- Bucket: `hcm-boletas-dev-851725431647`.
- Clave: `<tenant>/boletas/<periodo>/<nomina_id>.pdf`.
- Acceso público bloqueado, ACLs deshabilitadas, cifrado AES256 y política que exige HTTPS.
- Versionado habilitado; CloudFormation conserva el bucket si se elimina o reemplaza el recurso.
- No hay URLs públicas ni nuevas rutas. La descarga sigue pasando por la API autenticada.
- Si falla el archivado, la operación devuelve error; no informa una descarga exitosa sin haber persistido el PDF.

El servicio usa `BOLETAS_BUCKET`, inyectado por Serverless. Los PDFs no consultados aún no se materializan en S3. El saldo/cálculo de nómina no cambia con el archivado.

Se aprobaron 19 pruebas locales y 22 comprobaciones de integración en AWS/curl, incluidas las descargas desde dos tenants y el rechazo de accesos anónimos y de empleados ajenos. [Evidencia](../docs/prueba_boletas_s3.md).

## Datos y seeding

El seed crea 500 nóminas por tenant y conceptos hasta superar los 30k:

```bash
cd ms-nominas
TABLE_NAME=hcm-nominas-dev \
TABLE_EMPLEADOS=hcm-empleados \
python3 scripts/seed_nominas.py --periodo 2026-11
```

Para un tenant específico:

```bash
TABLE_NAME=hcm-nominas-dev TABLE_EMPLEADOS=hcm-empleados \
python3 scripts/seed_nominas.py --periodo 2026-11 --tenant andina
```

El seed es idempotente para los IDs determinísticos `seed-*`. No publica eventos (`notificar=false`).

## Pruebas

```bash
cd ms-nominas
python3 -m unittest discover -s tests -v
```

Incluye cálculo de nómina, bono, descuento, sin goce, ingreso a mitad de mes, cese, salario cero, PDF y liquidación con ingreso un 29 de febrero.

También verifica los tokens de paginación y que un mensaje repetido no recalcule una ejecución ya `GENERADA` o `PAGADA`; las ejecuciones `FALLIDA` pueden reintentarse. Esta protección no impide que dos entregas simultáneas procesen la misma ejecución en curso.

## Despliegue

Requisito: `ms-usuarios` desplegado antes (exports `AuthorizerArn` y `EventosTopicArn`).

```bash
cd ms-nominas
npx serverless@4 print --stage dev
npx serverless@4 deploy --stage dev
```

El `serverless.yml` usa el rol `arn:aws:iam::851725431647:role/LabRole` y crea la tabla, las colas, la suscripción SNS y las respuestas CORS de API Gateway.

## Postman

La colección está en `postman/ms-nominas-dev.postman_collection.json` (y copia local en `ms-nominas/postman/ms-nominas.postman_collection.json`). Ejecuta primero `00 Auth > Login admin andina` para cargar `{{token}}`.

## Limitaciones conocidas

- Las boletas se archivan en S3 al descargarlas; no se hace una carga anticipada de PDFs para toda la planilla. Cada descarga conserva una versión del archivo.
- La liquidación es referencial y simplificada.
- La generación de una planilla recorre los empleados del tenant y procesa lotes de 200; para 10k empleados tarda decenas de segundos, no es instantánea.
- El PDF usa un generador propio sin dependencias externas; cubre el formato de boleta del proyecto, no plantillas legales configurables.
