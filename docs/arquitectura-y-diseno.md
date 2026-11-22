# Fase 1 – Diseño y arquitectura (SaaS HCM · Grupo 2)

> Documento base para el informe. Lo marcado como **decisión** conviene confirmarlo en grupo.
> Funcionalidades alineadas con los ejemplos del PPT del curso: **SAP (SuccessFactors) HCM, BambooHR y Workday**.

---

## 0. Qué ofrecen los ejemplos del PPT y cómo lo cubrimos

| Capacidad | SAP HCM | BambooHR | Workday | Nuestro microservicio |
|---|---|---|---|---|
| Core HR / ficha del empleado | Core HR y autoservicio | Employee Records | Human Resource Mgmt | **ms-empleados** |
| Nómina y compensación | Payroll, compensation | Payroll, Compensation (bandas salariales) | Payroll | **ms-nominas** |
| Tiempo y asistencia / ausencias | Time and attendance | Time Tracking, Time Off | Workforce Mgmt | **ms-asistencia** |
| Contratación y onboarding | Recruiting, Onboarding | Applicant Tracking, Onboarding Tasks | Talent Acquisition | **ms-reclutamiento** |
| Desempeño y desarrollo | Performance, Learning, Succession | Performance Growth, Recognition | Talent Management | **ms-desempeno** |
| Alertas / experiencia del empleado | Employee experience | Employee Experience | Self-Service Agent | **ms-notificaciones** + portal del empleado |
| Analítica y reportes | HR analytics | Automated Reporting, Dashboards | Decision Intelligence | **Dashboard** en el frontend (agrega los endpoints `/resumen`) |
| Roles y seguridad | Permisos | Zero Trust, SAML | Permisos y auditoría | **ms-usuarios** + authorizer |

Fuera de alcance (por tiempo): beneficios, encuestas de clima, IA/agentes, integraciones externas.

---

## 1. Decisiones de arquitectura

| Tema | Decisión | Motivo |
|---|---|---|
| Región AWS | `us-east-1` | Mejor soporte en cuentas educativas |
| Lenguaje Lambdas | Python 3.12 **o** Node.js 20 (uno solo para todo el grupo) | Menos fricción entre integrantes |
| Base de datos | DynamoDB, **una tabla por microservicio** | Cumple "BD propia" sin crear RDS |
| Multi-tenancy | Tenant en el JWT + `tenant_id` como partition key | Aislamiento simple y demostrable |
| Autenticación | `ms-usuarios` emite JWT (`tenant_id`, `rol`) + **Lambda Authorizer compartido** | Fácil de probar con 2 tenants |
| Eventos | 1 topic SNS + 1 cola SQS por consumidor (filtros + DLQ) | EDA desacoplada |
| Archivos | S3: CVs y boletas de pago | Uso con sentido de negocio |
| Despliegue | Serverless Framework, un `serverless.yml` por servicio | Requisito del enunciado |
| Frontend | React + Vite en Amplify | Framework libre |

**Tenants de prueba (3):** `andina`, `pacifico`, `sierra`. La demo usa `andina` y `pacifico`.

---

## 2. Funcionalidades por microservicio

### 2.1 ms-usuarios
- Registro y login por tenant (JWT), cambio de contraseña
- Roles: `admin_rrhh`, `gerente`, `reclutador`, `empleado`
- Activar/desactivar usuario
- Authorizer compartido: valida JWT e inyecta `tenant_id` y `rol`

### 2.2 ms-empleados  (Core HR)
- CRUD de empleados: datos personales, área, cargo, jefe directo
- Estados: `ACTIVO`, `VACACIONES`, `CESADO`
- Organigrama simple (empleados por área y por jefe)
- Autoservicio: el empleado consulta y edita sus datos de contacto
- `GET /empleados/resumen` para el dashboard

### 2.3 ms-nominas  (Payroll + compensación)
- Generar planilla mensual (sueldo base + bonos − descuentos)
- Bandas salariales por cargo (referencia de compensación)
- Boletas por empleado y periodo; PDF/JSON en S3
- Reacciona a altas, ceses y ausencias sin goce

### 2.4 ms-asistencia  (Tiempo y ausencias)
- Marcaciones de entrada/salida
- Solicitud de vacaciones/permisos y aprobación por el jefe
- Saldo de vacaciones por empleado
- Publica `AusenciaSolicitada` y `AusenciaAprobada`

### 2.5 ms-reclutamiento  (Contratación + onboarding)
- CRUD de vacantes (abrir/cerrar)
- Postulantes con CV en S3 (URL prefirmada)
- Pipeline: `RECIBIDO → ENTREVISTA → OFERTA → CONTRATADO / RECHAZADO`
- Tareas de onboarding del nuevo empleado (checklist)
- Publica `PostulanteContratado`

### 2.6 ms-desempeno  (Desempeño y talento)
- Ciclos de evaluación por periodo
- Evaluación con puntaje, competencias, objetivos y comentarios
- Reconocimientos entre compañeros
- Historial por empleado; publica `EvaluacionCompletada`

### 2.7 ms-notificaciones
- Consume eventos desde SQS y crea la notificación del usuario
- Envía avisos por SNS (email)
- Listar y marcar como leídas

> 7 servicios: `ms-usuarios` y `ms-notificaciones` son livianos, así que la carga real son 5 servicios de negocio.

---

## 3. Multi-tenancy

1. Login en `ms-usuarios` → JWT con `tenant_id`, `user_id`, `rol`.
2. El frontend envía `Authorization: Bearer …`.
3. El Authorizer valida y entrega `tenant_id` al Lambda por `requestContext.authorizer`.
4. **El Lambda nunca toma el `tenant_id` del body ni de la URL**. Toda consulta usa `tenant_id` como partition key.

---

## 4. Diseño de datos (estructura JSON)

Diseño contrastado con los `serverless.yml` y los escritores de cada módulo (22-Nov-2026). Los ejemplos son ilustrativos, no registros consultados hoy en AWS. DynamoDB usa cadenas (`S`) para todas las claves e índices de estas tablas; el resto de atributos depende de cada entidad.

Cada tabla tiene PK `tenant_id`. Los GSI son dispersos: un ítem solo participa cuando contiene sus atributos de clave. `login-email-index` permite localizar la cuenta durante el login; las consultas autenticadas deben conservar el filtro de tenant.

Los nombres de producción son históricos. Pruebas usa `hcm-dev-<modulo>`; consultar el [mapa de entornos](../hcm/README.md#datos-separados-por-entorno-desplegado).

### 4.1 `ms-usuarios` (PK `tenant_id` · SK `user_id`)

Fuente: [`ms-usuarios/serverless.yml`](../ms-usuarios/serverless.yml).

```json
{
  "tenant_id": "andina",
  "user_id": "usr-000123",
  "email": "maria.quispe@andina.pe",
  "password_hash": "scrypt$16384$8$1$<salt_base64>$<hash_base64>",
  "nombre": "María Quispe",
  "rol": "admin_rrhh",
  "activo": true,
  "empleado_id": "emp-000045",
  "created_at": "2026-10-01T10:00:00Z"
}
```

| Índice | PK (S) | SK (S) |
|---|---|---|
| `login-email-index` | `email` | — |
| `email-index` | `tenant_id` | `email` |
| `empleado-index` | `tenant_id` | `empleado_id` |

### 4.2 `ms-empleados` (PK `tenant_id` · SK `empleado_id`)

Fuente: [`ms-empleados/serverless.yml`](../ms-empleados/serverless.yml).

```json
{
  "tenant_id": "andina",
  "empleado_id": "emp-000045",
  "nombres": "María",
  "apellidos": "Quispe Huamán",
  "documento": "71234567",
  "email": "maria.quispe@andina.pe",
  "area": "Recursos Humanos",
  "cargo": "Analista de Nóminas",
  "jefe_id": "emp-000010",
  "fecha_ingreso": "2023-03-15",
  "salario_base": 3500.0,
  "estado": "ACTIVO"
}
```

| Índice | PK (S) | SK (S) |
|---|---|---|
| `area-index` | `tenant_id` | `area` |
| `jefe-index` | `tenant_id` | `jefe_id` |
| `estado-index` | `tenant_id` | `estado` |
| `documento-index` | `tenant_id` | `documento` |

### 4.3 `ms-nominas` (PK `tenant_id` · SK `sk`)

Fuente: [`ms-nominas/serverless.yml`](../ms-nominas/serverless.yml).

```json
{
  "tenant_id": "andina",
  "nomina_id": "nom-2026-10-emp-000045",
  "empleado_id": "emp-000045",
  "periodo": "2026-10",
  "sueldo_base": 3500.0,
  "bonos": 300.0,
  "descuentos": 455.0,
  "neto": 3345.0,
  "estado": "GENERADO",
  "sk": "NOMINA#nom-2026-10-emp-000045",
  "tipo": "NOMINA",
  "empleado_periodo": "emp-000045#2026-10",
  "periodo_empleado": "2026-10#emp-000045"
}
```

| Índice | PK (S) | SK (S) |
|---|---|---|
| `empleado-index` | `tenant_id` | `empleado_periodo` |
| `periodo-index` | `tenant_id` | `periodo_empleado` |
| `concepto-index` | `tenant_id` | `periodo_concepto` |
| `planilla-index` | `tenant_id` | `periodo_planilla` |
| `cargo-index` | `tenant_id` | `banda_cargo` |

Otras entidades de la misma tabla (ejemplos abreviados):

```json
{
  "tenant_id": "andina",
  "sk": "BANDA#Analista",
  "tipo": "BANDA",
  "banda_cargo": "Analista",
  "cargo": "Analista",
  "minimo": 2500,
  "maximo": 5000,
  "moneda": "PEN"
}
```

```json
{
  "tenant_id": "andina",
  "sk": "CONCEPTO#con-001",
  "tipo": "CONCEPTO",
  "concepto_id": "con-001",
  "empleado_id": "emp-000045",
  "periodo": "2026-10",
  "periodo_concepto": "2026-10#con-001",
  "tipo_concepto": "BONO",
  "concepto": "Bono de productividad",
  "monto": 300
}
```

```json
{
  "tenant_id": "andina",
  "sk": "PLANILLA#2026-10",
  "tipo": "PLANILLA",
  "planilla_id": "pla-2026-10",
  "periodo_planilla": "2026-10",
  "periodo": "2026-10",
  "estado": "GENERADA",
  "total_empleados": 1,
  "procesados": 1
}
```

```json
{
  "tenant_id": "andina",
  "sk": "LIQUIDACION#emp-000045",
  "tipo": "LIQUIDACION",
  "empleado_id": "emp-000045",
  "empleado_periodo": "emp-000045#LIQ",
  "fecha_cese": "2026-10-31",
  "total": 1500
}
```


### 4.4 `ms-asistencia` (PK `tenant_id` · SK `sk`)

Fuente: [`ms-asistencia/serverless.yml`](../ms-asistencia/serverless.yml).

```json
{
  "tenant_id": "andina",
  "sk": "EMP#emp-000045#MAR#2026-10-20",
  "empleado_id": "emp-000045",
  "fecha": "2026-10-20",
  "hora_entrada": "08:57",
  "hora_salida": "18:03",
  "clase": "MAR",
  "estado": "CERRADA"
}
```

```json
{
  "tenant_id": "andina",
  "sk": "EMP#emp-000045#AUS#aus-002345",
  "empleado_id": "emp-000045",
  "tipo": "VACACIONES",
  "desde": "2026-12-20",
  "hasta": "2026-12-27",
  "dias": 6,
  "estado": "PENDIENTE",
  "aprobador_id": "emp-000010",
  "clase": "AUS",
  "ausencia_id": "aus-002345",
  "con_goce": true
}
```

| Índice | PK (S) | SK (S) |
|---|---|---|
| Sin GSI | — | — |

Consulta por prefijo de SK: `EMP#<empleado_id>#MAR#<fecha>` y `EMP#<empleado_id>#AUS#<ausencia_id>`. El ítem `EMP#<empleado_id>#CONTROL` mantiene el control de concurrencia de ausencias. No existe `empleado-index` en esta tabla.

### 4.5 `ms-reclutamiento` (PK `tenant_id` · SK `sk`)

Fuente: [`ms-reclutamiento/serverless.yml`](../ms-reclutamiento/serverless.yml).

```json
{
  "tenant_id": "andina",
  "sk": "VACANTE#vac-000089",
  "titulo": "Desarrollador Backend",
  "area": "Tecnología",
  "estado": "ABIERTA",
  "fecha_publicacion": "2026-10-01"
}
```

```json
{
  "tenant_id": "andina",
  "sk": "POSTULACION#pos-004567",
  "vacante_id": "vac-000089",
  "nombre": "Luis Ramos",
  "email": "luis.ramos@mail.com",
  "estado": "ENTREVISTA",
  "cv_s3_key": "andina/cvs/pos-004567.pdf"
}
```

```json
{
  "tenant_id": "andina",
  "sk": "ONBOARDING#emp-000045#onb-001200",
  "empleado_id": "emp-000045",
  "tarea": "Entregar laptop",
  "completada": false,
  "onboarding_id": "onb-001200"
}
```

| Índice | PK (S) | SK (S) |
|---|---|---|
| `vacante-index` | `tenant_id` | `vacante_id` |

### 4.6 `ms-desempeno` (PK `tenant_id` · SK `sk`)

Fuente: [`ms-desempeno/serverless.yml`](../ms-desempeno/serverless.yml).

```json
{
  "tenant_id": "andina",
  "evaluacion_id": "eva-000777",
  "empleado_id": "emp-000045",
  "evaluador_id": "emp-000010",
  "periodo": "2026-S1",
  "puntaje": 4.3,
  "competencias": [
    {
      "nombre": "Trabajo en equipo",
      "puntaje": 5
    },
    {
      "nombre": "Puntualidad",
      "puntaje": 4
    }
  ],
  "objetivos": [
    "Automatizar reporte mensual"
  ],
  "comentarios": "Excelente desempeño",
  "estado": "COMPLETADA",
  "sk": "eva-000777"
}
```

| Índice | PK (S) | SK (S) |
|---|---|---|
| `empleado-index` | `tenant_id` | `empleado_id` |

Evaluaciones: `sk = evaluacion_id` (`eva-…`). Reconocimientos: `sk = reconocimiento_id` (`rec-…`), con `empleado_id`, `de_empleado_id`, `mensaje` y `fecha`.

### 4.7 `ms-notificaciones` (PK `tenant_id` · SK `notificacion_id`)

Fuente: [`ms-notificaciones/serverless.yml`](../ms-notificaciones/serverless.yml).

```json
{
  "tenant_id": "andina",
  "notificacion_id": "not-009999",
  "destinatario_id": "usr-000123",
  "tipo": "NominaGenerada",
  "mensaje": "Tu boleta de octubre ya está disponible",
  "leida": false,
  "created_at": "2026-10-31T08:00:00Z"
}
```

| Índice | PK (S) | SK (S) |
|---|---|---|
| `destinatario-index` | `tenant_id` | `destinatario_id` |

Volumen exigido: ≥30.000 ítems por microservicio repartidos en tres tenants; no son 30.000 por tenant. El conteo incluye entidades y registros de control. Ver [métricas de producción y fecha de verificación](metricas_bd_prod.md); el conteo no demuestra aislamiento HTTP.

---

## 5. Catálogo de eventos (EDA)

Topic SNS `hcm-eventos`; cada consumidor tiene su cola SQS con filtro por `tipo_evento` y su DLQ.

| Evento | Publica | Consumen | Acción |
|---|---|---|---|
| `EmpleadoCreado` | ms-empleados | ms-usuarios, ms-nominas, ms-reclutamiento, ms-notificaciones | Crear usuario, incluir en planilla, generar tareas de onboarding, dar bienvenida |
| `EmpleadoCesado` | ms-empleados | ms-usuarios, ms-nominas | Desactivar usuario, liquidación |
| `PostulanteContratado` | ms-reclutamiento | ms-empleados, ms-notificaciones | Crear empleado, avisar a RR.HH. |
| `AusenciaSolicitada` | ms-asistencia | ms-notificaciones | Avisar al jefe |
| `AusenciaAprobada` | ms-asistencia | ms-nominas, ms-empleados, ms-notificaciones | Descuento si es sin goce, estado `VACACIONES`, avisar al empleado |
| `NominaGenerada` | ms-nominas | ms-notificaciones | Boleta disponible |
| `EvaluacionCompletada` | ms-desempeno | ms-notificaciones | Avisar al empleado y su jefe |

Formato común:
```json
{
  "tipo_evento": "EmpleadoCreado",
  "tenant_id": "andina",
  "origen": "ms-empleados",
  "timestamp": "2026-10-20T12:00:00Z",
  "datos": { "empleado_id": "emp-000045", "email": "maria.quispe@andina.pe" }
}
```

**Flujo estrella para la demo:** contratar postulante → se crea empleado → se crea usuario, tareas de onboarding y notificación (todo por eventos).

---

## 6. Endpoints principales

| Servicio | Endpoints |
|---|---|
| ms-usuarios | `POST /auth/login` · `POST /usuarios` · `GET /usuarios` · `PATCH /usuarios/{id}` |
| ms-empleados | `POST /empleados` · `GET /empleados` · `GET /empleados/{id}` · `PUT /empleados/{id}` · `GET /empleados/resumen` |
| ms-nominas | `POST /nominas/generar` · `GET /nominas?periodo=` · `GET /nominas/empleado/{id}` · `GET /nominas/{id}/boleta` · `GET /bandas` |
| ms-asistencia | `POST /marcaciones` · `GET /marcaciones?empleado=` · `POST /ausencias` · `PATCH /ausencias/{id}/estado` · `GET /ausencias/saldo/{empleado}` |
| ms-reclutamiento | `POST /vacantes` · `GET /vacantes` · `POST /postulaciones` · `PATCH /postulaciones/{id}/estado` · `POST /postulaciones/cv-url` · `GET /onboarding/{empleado}` |
| ms-desempeno | `POST /evaluaciones` · `GET /evaluaciones?empleado=` · `PUT /evaluaciones/{id}` · `POST /reconocimientos` |
| ms-notificaciones | `GET /notificaciones` · `PATCH /notificaciones/{id}/leida` |

---

## 7. Pantallas del frontend (mockups)

1. Login (con tenant)
2. Dashboard (empleados activos, vacantes abiertas, nómina del mes, ausencias pendientes, evaluaciones)
3. Empleados (tabla, filtros, ficha, organigrama simple)
4. Nóminas (planilla por periodo, boletas, bandas salariales)
5. Asistencia y ausencias (marcaciones, solicitudes, aprobación)
6. Reclutamiento (vacantes, kanban de postulantes, checklist de onboarding)
7. Desempeño (evaluaciones, gráfico de puntajes, reconocimientos)
8. Portal del empleado (mi ficha, mis boletas, mis ausencias, mis notificaciones)

---

## 8. Checklist de la Fase 1

- [ ] Grupo confirma decisiones (sección 1) y alcance (sección 0)
- [ ] Cada dueño de microservicio revisa su estructura JSON (sección 4)
- [ ] Catálogo de eventos aprobado (sección 5)
- [ ] Diagrama de arquitectura exportado para informe y PPT
- [ ] Mockups listos
- [ ] Repos creados con plantilla de `serverless.yml`
