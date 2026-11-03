# Backend_B · ms-nominas + ms-asistencia

Proyecto Final CS2032 · Grupo 2 · SaaS HCM multi-tenant · Backend B (Rodrigo Gomez)

Este backend contiene la lógica de **nóminas** (planillas, boletas en PDF, bonos y descuentos, bandas salariales,
liquidación) y de **asistencia** (marcaciones, vacaciones, permisos con aprobación del jefe, saldo y reportes).
Usa Spring Boot 4.1.2, Java 17, JPA, Lombok y Spring Security con JWT. No incluye nada de AWS: el despliegue
se hace aparte.

## Estructura

```
src/main/java/com/example/backend_b/
├── BackendBApplication.java
├── controllers/            REST (/api/v1/...)
├── services/               lógica de negocio
├── entities/               JPA: Empleado, Planilla, Nomina, NominaDetalle, ConceptoNomina,
│                           BandaSalarial, Liquidacion, Marcacion, Ausencia
├── infrastructure/
│   ├── repositories/       Spring Data JPA
│   └── DTOs/request|Response
└── common/
    ├── Enums/  config/  exception/  security/  pdf/
    └── Utils.java
```

## Ejecutar

```bash
./mvnw spring-boot:run          # http://localhost:8080 · H2 en memoria + datos ficticios
```

- Consola H2: `http://localhost:8080/h2-console`, con JDBC URL `jdbc:h2:mem:backend_b` y usuario `sa`.
- Producción con PostgreSQL: `SPRING_PROFILES_ACTIVE=prod`, con `DB_URL`, `DB_USER`, `DB_PASSWORD` y `JWT_SECRET`.
- Tests: `./mvnw test`. Incluyen un flujo completo sobre H2 (`FlujoBackendBTests`).

| Variable | Por defecto | Para qué |
|---|---|---|
| `JWT_SECRET` | `dev-secret-…` | **El mismo secreto HS256 con el que ms-usuarios firma los tokens** |
| `HCM_DEV` | `true` (`false` en prod) | habilita `POST /api/v1/dev/token` para obtener tokens de prueba |
| `HCM_SEED` / `HCM_SEED_EMPLEADOS` | `true` / `50` | datos ficticios al arrancar con la BD vacía (`10000` → más de 30,000 registros por servicio) |
| `EVENTOS_API_KEY` | vacío | si se define, `POST /api/v1/eventos` exige la cabecera `X-Api-Key` |
| `EVENTOS_WEBHOOK_URL` | vacío | si se define, cada evento publicado se envía por POST a esa URL |
| `CORS_ORIGENES` | `*` | orígenes permitidos para el frontend |

## Autenticación y multi-tenancy

Todas las rutas (salvo `/api/v1/eventos`, `/api/v1/dev/**` y `/api/v1/salud`) piden `Authorization: Bearer <jwt>`.
El token debe traer los claims `tenant_id`, `user_id`, `rol` (`admin_rrhh` | `gerente` | `reclutador` | `empleado`)
y **`empleado_id`**. Este último hace falta para el autoservicio: ver mis boletas, marcar, pedir vacaciones.
Toda consulta se filtra por el `tenant_id` del token, nunca por el que venga en el body o la URL.

```bash
TOKEN=$(curl -s -X POST localhost:8080/api/v1/dev/token -H 'Content-Type: application/json' \
  -d '{"tenantId":"andina","rol":"admin_rrhh","empleadoId":"emp-000002"}' | jq -r .token)
curl -s localhost:8080/api/v1/nominas/resumen -H "Authorization: Bearer $TOKEN"
```

Con los datos ficticios, `emp-000001` es el gerente general, `emp-000002` a `emp-000007` son jefes de área
(RR.HH., Tecnología, Finanzas, Ventas, Operaciones, Logística) y el resto reporta a su jefe de área.

## Endpoints

**Nóminas**

| Método | Ruta | Quién |
|---|---|---|
| POST | `/api/v1/nominas/generar` `{periodo:"2026-11", forzar?}` → **202**, se genera en segundo plano | admin_rrhh |
| GET | `/api/v1/nominas/planillas` · `/api/v1/nominas/planillas/{periodo}` (avance y totales) | admin_rrhh, gerente |
| GET | `/api/v1/nominas?periodo=&area=&page=&size=` | admin_rrhh, gerente |
| GET | `/api/v1/nominas/resumen?periodo=` (dashboard) | admin_rrhh, gerente |
| GET | `/api/v1/nominas/empleado/{empleadoId}` (historial y liquidación) | supervisor o el propio empleado |
| GET | `/api/v1/nominas/{id}` · `/api/v1/nominas/{id}/boleta` (PDF; `?descargar=true`) | supervisor o el propio empleado |
| GET | `/api/v1/nominas/liquidaciones/{empleadoId}` | supervisor o el propio empleado |
| POST / GET | `/api/v1/nominas/conceptos` `{empleadoId, periodo, tipo: BONO\|DESCUENTO, concepto, monto}` · `?periodo=&empleadoId=` | admin_rrhh / lectura |
| GET / PUT | `/api/v1/bandas` · `{cargo, minimo, maximo, moneda}` | lectura admin, gerente, reclutador / escritura admin |

**Asistencia**

| Método | Ruta | Quién |
|---|---|---|
| POST | `/api/v1/marcaciones` con `{}` → entrada o salida a la hora actual (Lima); RR.HH. puede enviar `empleadoId, tipo, fecha, hora` | empleado / admin |
| GET | `/api/v1/marcaciones?empleadoId=&desde=&hasta=` · `/api/v1/marcaciones/dia?fecha=` | propio / supervisor |
| POST | `/api/v1/ausencias` `{tipo: VACACIONES\|PERMISO\|LICENCIA_MEDICA\|SIN_GOCE, desde, hasta, motivo}` | empleado |
| GET | `/api/v1/ausencias?empleadoId=&estado=&tipo=` · `/api/v1/ausencias/{id}` | propio / supervisor |
| GET | `/api/v1/ausencias/pendientes` (bandeja del jefe; admin: `?todas=true`) | jefe / admin |
| PATCH | `/api/v1/ausencias/{id}/estado` `{estado: APROBADA\|RECHAZADA\|CANCELADA, comentario}` | jefe directo o admin (cancelar: el solicitante) |
| GET | `/api/v1/ausencias/saldo/{empleadoId}` | propio / supervisor |
| GET | `/api/v1/asistencia/resumen?fecha=` (dashboard) | admin_rrhh, gerente |
| GET | `/api/v1/asistencia/reportes?periodo=2026-11&tipo=MARCACIONES\|AUSENCIAS` → CSV | admin_rrhh, gerente |

Los errores tienen la forma `{"error": "...", "mensaje": "..."}`:

| Código | Cuándo |
|---|---|
| 400 | validación |
| 401 | sin token |
| 403 | rol o dueño incorrecto |
| 404 | no existe |
| 409 | duplicado o cruce de fechas |
| 422 | regla de negocio: saldo insuficiente, planilla pagada, etc. |

## Eventos (EDA)

**Entrada:** `POST /api/v1/eventos` recibe eventos de otros microservicios en el formato del grupo.
Al desplegar, ahí se conecta la suscripción (por ejemplo SNS → HTTP, o un consumidor SQS que reenvíe):

```json
{"tipo_evento":"EmpleadoCreado","tenant_id":"andina","origen":"ms-empleados","timestamp":"...",
 "datos":{"empleado_id":"emp-000045","nombres":"María","apellidos":"Quispe","email":"...","area":"Recursos Humanos",
          "cargo":"Analista de Nóminas","jefe_id":"emp-000010","fecha_ingreso":"2023-03-15","salario_base":3500}}
```

| Evento recibido | Efecto |
|---|---|
| `EmpleadoCreado` / `EmpleadoActualizado` | crea o actualiza la copia local del empleado (entra a la planilla; 30 días de vacaciones) |
| `EmpleadoCesado` `{empleado_id, fecha_cese, motivo}` | estado CESADO, liquidación y cancelación de sus ausencias pendientes |

**Salida:** se publican `NominaGenerada`, `AusenciaSolicitada`, `AusenciaAprobada` y `AusenciaRechazada`.
Siempre quedan en el log, y si `EVENTOS_WEBHOOK_URL` está configurada se envían por POST a esa URL.
Dentro de la app, `AusenciaAprobada` de tipo sin goce registra automáticamente los días a descontar en la planilla.

## Reglas de negocio (simplificadas)

- **Boleta:** `neto = sueldo + bonos − (ONP 13% + días sin goce + otros descuentos)`. Se usa un mes comercial
  de 30 días, proporcional si el empleado ingresa o cesa a mitad de mes. EsSalud 9% se muestra como aporte del
  empleador. Ejemplo de la Fase 1: 3500 + 300 − 455 = **3345**.
- **Liquidación:** vacaciones, CTS y gratificación truncas por meses completos. Es un cálculo referencial.
- **Ausencias:** se cuentan en días calendario. No se permiten cruces de fechas; las vacaciones se validan contra
  el saldo; nadie aprueba su propia solicitud; sin jefe asignado, la solicitud va a la bandeja de RR.HH.
- **Marcaciones:** una por día. La tardanza se cuenta desde las 09:00 más 10 minutos de tolerancia.
