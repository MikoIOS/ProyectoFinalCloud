# ms-usuarios

Identidad y acceso de la plataforma SaaS HCM (Grupo 2): login por tenant, JWT, roles,
Authorizer compartido y reacción a eventos de empleados.
**Estado: completo (etapas 0 a 3).** Pendiente solo desplegar y correr la colección Postman contra AWS.

## Requisitos
- Python 3.12 y Node.js
- `npm i -g serverless@3` y, dentro de esta carpeta, `npm i -D serverless-python-requirements`
- AWS Academy: credenciales del laboratorio en `~/.aws/credentials`

## Desarrollo local (PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m pytest -q              # 41 pruebas con moto, sin AWS
```

## Despliegue
```powershell
$env:LAB_ROLE_ARN = "arn:aws:iam::<CUENTA>:role/LabRole"
$env:JWT_SECRET   = "<cadena aleatoria de 32+ caracteres>"
serverless deploy
python -m scripts.seed_usuarios          # 30 000 usuarios (10 000 por tenant)
```
Con Serverless v3 puede salir un aviso por `python3.12` en el esquema; es solo una advertencia.
`serverless package` genera la plantilla sin errores.

## Cuentas de demo (clave `Demo1234!`, mismas en cada tenant: andina, pacifico, sierra)
`admin@<tenant>.pe` (admin_rrhh) · `gerente@<tenant>.pe` · `reclutador@<tenant>.pe` · `empleado@<tenant>.pe`

## Estructura del proyecto
```
ms-usuarios/
|-- serverless.yml              # funciones, tabla + 2 GSIs, topic hcm-eventos, cola + DLQ, Authorizer, Outputs
|-- requirements.txt            # pyjwt (única dependencia)
|-- requirements-dev.txt        # boto3, pytest, moto
|-- pytest.ini
|-- src/
|   |-- handlers/               # capa de entrada: evento -> servicio -> respuesta
|   |   |-- auth.py             # ping, login, cambiar_password
|   |   |-- usuarios.py         # crear, listar, obtener, actualizar, mi_usuario
|   |   |-- authorizer.py       # Lambda Authorizer compartido (valida el JWT)
|   |   `-- eventos.py          # consumidor SQS: EmpleadoCreado / EmpleadoCesado
|   |-- services/               # reglas de negocio
|   |   |-- auth_service.py     # verificar credenciales y emitir el JWT
|   |   |-- usuarios_service.py # roles válidos, email único, cambio de contraseña
|   |   `-- eventos_service.py  # crear / desactivar usuario por evento (idempotente)
|   |-- repositories/
|   |   `-- usuarios_repo.py    # único módulo que habla con DynamoDB
|   `-- common/                 # errors, response, tenant, pagination, events, security
|-- scripts/
|   |-- tabla.py                # esquema de la tabla (lo usan el seed y las pruebas)
|   |-- seed_usuarios.py        # 30 000 usuarios (10 000 por tenant)
|   `-- publicar_evento.py      # publica un EmpleadoCreado/Cesado de prueba
|-- tests/unit/                 # 41 pruebas (pytest + moto)
`-- postman/                    # colección de este servicio
```
Flujo de una petición: `handlers` (lee el contexto y el body) → `services` (aplica las reglas) → `repositories` (DynamoDB).

## Cómo empezar (rutas de entrada)
Al terminar `serverless deploy` se imprimen los endpoints (también con `serverless info`). La URL base tiene la forma
`https://<api-id>.execute-api.us-east-1.amazonaws.com/dev` y es **distinta de la de ms-empleados**.
1. `GET <base>/ping`: comprueba que el servicio responde (sin token). En PowerShell: `curl.exe <base>/ping`
2. `POST <base>/auth/login`: la puerta de entrada del sistema; devuelve el JWT. Es la única ruta donde el tenant va en el body.
3. Todas las demás rutas (y todas las de ms-empleados) llevan la cabecera `Authorization: Bearer <token>`.

```powershell
curl.exe -X POST <base>/auth/login -H "Content-Type: application/json" `
  -d '{\"tenant_id\":\"andina\",\"email\":\"admin@andina.pe\",\"password\":\"Demo1234!\"}'
```

## Endpoints
| Método | Ruta | Rol | Función |
|---|---|---|---|
| GET | `/ping` | público | Salud del servicio |
| POST | `/auth/login` | público | `{tenant_id, email, password}` → JWT (8 h) |
| POST | `/auth/cambiar-password` | autenticado | `{password_actual, password_nueva}` (mín. 8) |
| GET | `/usuarios/me` | autenticado | Perfil del token |
| POST | `/usuarios` | admin_rrhh | Crea usuario en el tenant del token (201; 409 si el email existe en el tenant) |
| GET | `/usuarios` | admin_rrhh | Lista paginada: `?rol=&activo=&limit=&next_token=` |
| GET | `/usuarios/{id}` | admin_rrhh | Detalle (404 si no existe en el tenant) |
| PATCH | `/usuarios/{id}` | admin_rrhh | Cambia `nombre`, `rol`, `activo` (no a uno mismo) |

Errores: `{"error": {"codigo", "mensaje"}}` con 400/401/403/404/409.

## Eventos (topic `hcm-eventos`, lo crea y exporta este servicio)
- Consume `EmpleadoCreado` → crea `usr-<n>` (rol empleado, clave inicial = `documento`, `debe_cambiar_password=true`).
  Necesita en `datos`: `empleado_id, email, nombres, apellidos, documento`.
- Consume `EmpleadoCesado` → `activo=false` (usa `empleado-index`).
- Idempotente. Los mensajes que fallan se reintentan 3 veces y pasan a la DLQ `ms-usuarios-eventos-dlq`.
- Prueba manual: `$env:TOPIC_ARN="<arn>"; python -m scripts.publicar_evento EmpleadoCreado --tenant andina --empleado emp-010001`

## Lo que necesita ms-empleados de este servicio
```yaml
# serverless.yml de ms-empleados
functions:
  listar:
    handler: src/handlers/empleados.listar
    events:
      - http:
          path: empleados
          method: get
          cors: true
          authorizer:
            arn: ${cf:ms-usuarios-${sls:stage}.AuthorizerArn}
            type: token
            identitySource: method.request.header.Authorization
            resultTtlInSeconds: 300
# Topic para publicar/suscribirse: ${cf:ms-usuarios-${sls:stage}.EventosTopicArn}
```
En el handler: `from src.common.tenant import contexto` y `ctx = contexto(event, roles=("admin_rrhh",))`
(`src/common/errors.py` y `tenant.py` son idénticos en ambos servicios; en ms-empleados `response.py`, `events.py` y `pagination.py` están adaptados: soporte de `Decimal` y claves de paginación de empleados; `security.py` no se usa allí).
Usar el mismo `JWT_SECRET` en todos los servicios no hace falta: solo el Authorizer lo verifica.

## Decisiones y límites
- Hash scrypt (stdlib) en lugar de bcrypt: no hay que compilar para Lambda ni usar Docker en Windows.
- Email único por tenant: se verifica con `email-index` antes de insertar (no es atómico; dos altas simultáneas
  con el mismo email podrían colarse; aceptable para el curso).
- El Authorizer cachea 300 s por token: un usuario desactivado conserva acceso hasta ese plazo o hasta que
  venza su JWT (8 h) en rutas ya autorizadas; el login sí lo rechaza al instante.
- `empleado_id` se omite (no se guarda nulo) en usuarios sin empleado, por el GSI.

## Pruebas de aislamiento
Colección unificada de los dos servicios, con su entorno: `HCM-ms-usuarios-ms-empleados.postman_collection.json` y `HCM.postman_environment.json` (se entregan aparte). La de este servicio solo (`postman/ms-usuarios.postman_collection.json`, 16 requests) usa la variable `base_url`.
Cubre las pruebas 1 a 6 del plan (la 7, cese → login 403, se hace con `publicar_evento`; ya la cubren las pruebas unitarias).
