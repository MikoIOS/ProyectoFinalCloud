# ms-empleados

Core HR de la plataforma SaaS HCM (Grupo 2): ficha laboral, organigrama, autoservicio y resumen para el dashboard.
Publica `EmpleadoCreado` / `EmpleadoCesado` y reacciona a `PostulanteContratado` y a las ausencias.
**Estado: completo en código.** Pendiente desplegar y correr la colección Postman contra AWS.

## Requisitos
- **ms-usuarios desplegado antes**: de ahí salen el Authorizer y el topic `hcm-eventos` (`${cf:ms-usuarios-<stage>...}`).
- Python 3.12, Node.js y `npm i -g serverless@3`. Sin dependencias Python externas (no hace falta ningún plugin).
- AWS Academy: credenciales del laboratorio en `~/.aws/credentials`.

## Desarrollo local (PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m pytest -q              # 44 pruebas con moto, sin AWS
```

## Despliegue
```powershell
$env:LAB_ROLE_ARN = "arn:aws:iam::<CUENTA>:role/LabRole"
serverless deploy
python -m scripts.seed_empleados          # 30 000 empleados (10 000 por tenant); cargar DESPUÉS de seed_usuarios
```
Los dos APIs tienen URL distinta (una por servicio): el frontend usa una base para ms-usuarios y otra para ms-empleados.

## Estructura del proyecto
```
ms-empleados/
|-- serverless.yml              # funciones, tabla + 4 GSIs, cola + DLQ suscrita a hcm-eventos, Authorizer importado
|-- requirements.txt            # sin dependencias externas
|-- requirements-dev.txt        # boto3, pytest, moto
|-- pytest.ini
|-- src/
|   |-- handlers/               # capa de entrada: evento -> servicio -> respuesta
|   |   |-- ping.py             # ping
|   |   |-- empleados.py        # crear, listar, obtener, actualizar, cambiar_estado
|   |   |-- consultas.py        # organigrama, resumen
|   |   |-- autoservicio.py     # mi_ficha, actualizar_mi_contacto
|   |   `-- eventos.py          # consumidor SQS: PostulanteContratado / AusenciaAprobada / AusenciaFinalizada
|   |-- services/               # reglas de negocio
|   |   |-- empleados_service.py  # validaciones, transiciones de estado, vistas por rol, organigrama, resumen
|   |   `-- eventos_service.py    # alta por postulante y cambios de estado por ausencias (idempotente)
|   |-- repositories/
|   |   `-- empleados_repo.py   # único módulo que habla con DynamoDB
|   `-- common/                 # errors, response, tenant, pagination, events
|-- scripts/
|   |-- tabla.py                # esquema de la tabla (lo usan el seed y las pruebas)
|   |-- seed_empleados.py       # 30 000 empleados, coherentes con ms-usuarios
|   `-- publicar_evento.py      # publica un PostulanteContratado/Ausencia de prueba
|-- tests/unit/                 # 44 pruebas (pytest + moto)
`-- postman/                    # colección de este servicio
```
Flujo de una petición: `handlers` (lee el contexto y el body) → `services` (aplica las reglas) → `repositories` (DynamoDB).
`errors.py` y `tenant.py` son idénticos a los de ms-usuarios; `response.py`, `events.py` y `pagination.py` están adaptados (soporte de `Decimal`, claves de empleados).

## Cómo empezar (rutas de entrada)
Al terminar `serverless deploy` se imprimen los endpoints (también con `serverless info`). La URL base tiene la forma
`https://<api-id>.execute-api.us-east-1.amazonaws.com/dev` y es **distinta de la de ms-usuarios**.
1. `GET <base>/ping`: comprueba que el servicio responde (sin token). En PowerShell: `curl.exe <base>/ping`
2. Este servicio **no tiene login**: primero se obtiene el JWT en `POST <ms-usuarios>/auth/login`.
3. Todas las demás rutas llevan la cabecera `Authorization: Bearer <token>` (el mismo token vale en los dos servicios).

```powershell
curl.exe <base>/empleados/resumen -H "Authorization: Bearer <token>"
```
La primera ruta útil para comprobar que todo está conectado es `GET /empleados/resumen` con el token de un `admin_rrhh`
(tras cargar el seed debe devolver `total: 10000` para ese tenant).

## Endpoints
| Método | Ruta | Roles | Función |
|---|---|---|---|
| GET | `/ping` | público | Salud |
| POST | `/empleados` | admin_rrhh | Crea la ficha (ACTIVO). 409 si el documento ya existe en el tenant. Publica `EmpleadoCreado` |
| GET | `/empleados` | admin_rrhh, gerente | Listado **resumido** paginado: `?area=&estado=&limit=&next_token=` |
| GET | `/empleados/{id}` | admin, gerente; empleado solo el suyo (403 si no) | Ficha. Gerente no ve `salario_base`, `documento`, contacto |
| PUT | `/empleados/{id}` | admin_rrhh | Actualiza campos laborales (parcial). No cambia estado ni ids |
| PATCH | `/empleados/{id}/estado` | admin_rrhh | Transiciones; a `CESADO` exige `fecha_cese` y publica `EmpleadoCesado` |
| GET | `/empleados/organigrama` | admin, gerente | `?jefe_id=` subordinados directos · `?area=` empleados agrupados por jefe |
| GET | `/empleados/resumen` | admin, gerente | Totales por estado y por área (dashboard) |
| GET | `/empleados/me` | cualquiera con empleado | Mi ficha completa |
| PATCH | `/empleados/me` | cualquiera con empleado | Solo `telefono`, `direccion`, `contacto_emergencia` |

Estados: `ACTIVO ⇄ VACACIONES → CESADO` (final). Errores: `{"error": {"codigo", "mensaje"}}` con 400/401/403/404/409.
El tenant sale siempre del token; un recurso de otro tenant da 404.

## Eventos
| Evento | Dirección | Qué hace |
|---|---|---|
| `EmpleadoCreado` | publica | `datos`: `empleado_id, email, nombres, apellidos, documento, area, cargo, fecha_ingreso, jefe_id?, salario_base` |
| `EmpleadoCesado` | publica | `datos`: `empleado_id, fecha_cese, motivo?` |
| `PostulanteContratado` | consume | Crea el empleado con id `emp-p<n>` derivado de `postulacion_id` (idempotente) y publica `EmpleadoCreado` |
| `AusenciaAprobada` | consume | Si `datos.tipo == "VACACIONES"` y está ACTIVO → `VACACIONES` |
| `AusenciaFinalizada` | consume | **Propuesta**: VACACIONES → ACTIVO (por confirmar con ms-asistencia) |

`PostulanteContratado` debe traer en `datos`: `postulacion_id, nombres, apellidos, email, documento, area, cargo, fecha_ingreso, salario_base` (y `jefe_id` opcional).
Los mensajes que fallan se reintentan 3 veces y pasan a la DLQ `ms-empleados-eventos-dlq`.
Prueba manual: `$env:TOPIC_ARN="<arn>"; python -m scripts.publicar_evento PostulanteContratado --tenant andina`

## Datos de prueba (coherentes con ms-usuarios)
`emp-{n:06d}` ↔ `usr-{n:06d}`, mismo email y nombre. Verificado: 30 000 registros en cada servicio y 0 diferencias.
`CESADO` si `n > 4 and n % 40 == 0` (su usuario está desactivado); `VACACIONES` si `n % 22 == 0` (≈4,5 %).
Jerarquía: jefe de `n` = `(n-2)//8 + 1` (ancho 8, sin ciclos, nunca un cesado). 10 áreas, cuentas demo = n 1 a 4.

## Cambios respecto al plan en PDF (a confirmar en grupo)
- **El listado es resumido** y nunca lleva salario ni documento (ni para el admin); esos datos solo salen en la ficha. Así los GSIs guardan menos.
- **Jefe válido = no cesado** (el PDF decía ACTIVO): alguien de vacaciones puede seguir siendo jefe.
- **`/resumen` recorre `area-index` una sola vez** leyendo solo `area` y `estado` (en vez de varios `Select=COUNT`); no usa Scan.
- **`PUT` es una actualización parcial**; no se puede cambiar un empleado cesado (409).
- `empleado_id` nuevos: `emp-<8 hex>`; los creados por evento: `emp-p<n>`. Ninguno choca con el seed (`emp-000001`…).
- `EmpleadoCreado` lleva además `area, cargo, fecha_ingreso, jefe_id, salario_base` para que ms-nominas no tenga que consultar esta tabla.

## Límites conocidos
- Si SNS falla al publicar, el alta/cese **se guarda igual** y la respuesta trae `"aviso"`; no hay reintento automático (un outbox queda fuera del alcance).
- Documento único por tenant se verifica con `documento-index` antes de insertar: no es atómico (dos altas simultáneas podrían colarse).
- El tiempo de `/resumen` con 10 000 empleados no se midió en AWS (en moto tarda ~5 s, que no es representativo); si molesta, cachear en el frontend.

## Pruebas de aislamiento y flujo
Colección unificada de los dos servicios, con su entorno: `HCM-ms-usuarios-ms-empleados.postman_collection.json` y `HCM.postman_environment.json` (se entregan aparte; 41 requests, ejecutar en orden). La de este servicio solo (`postman/ms-empleados.postman_collection.json`, 28 requests): aislamiento, roles y datos sensibles,
autoservicio y el flujo completo con ms-usuarios (crear empleado → usuario creado → cesar → login 403, con 6 s de espera entre pasos).
