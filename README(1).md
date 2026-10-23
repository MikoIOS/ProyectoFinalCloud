# Proyecto Final – CS2032 Cloud Computing (2026-2)

**Grupo 2 · SaaS tipo HCM (Human Capital Management)**
Plataforma multi-tenant, serverless y basada en eventos desplegada en AWS.

---

## 1. Resumen del proyecto

Solución SaaS para gestionar **empleados, nóminas, talento, contratación y desempeño**, con aislamiento por tenant.

| Requisito del enunciado | Cómo lo cumpliremos |
|---|---|
| Multi-tenancy | `tenant_id` en cada registro/token; 3 tenants de prueba |
| Serverless | API Gateway + Lambda, desplegado con Serverless Framework |
| Basada en eventos (EDA) | SNS (publicación) + SQS (consumo) entre microservicios |
| ≥ 5 microservicios protegidos | Autorizador (Lambda authorizer / Cognito) en cada API |
| BD propia por microservicio | DynamoDB (estructura JSON documentada por servicio) |
| ≥ 30,000 registros por microservicio | Script de datos ficticios, repartidos en 3 tenants |
| S3, SNS, SQS | S3 (CVs, boletas de pago, reportes), SNS + SQS (eventos) |
| Frontend | Framework a elección, desplegado en AWS Amplify |
| Demo | Con 2 tenants distintos |

### Microservicios propuestos

1. **ms-usuarios** – autenticación, usuarios y roles por tenant
2. **ms-empleados** – legajo de empleados, áreas, cargos y contratos
3. **ms-nominas** – planillas, boletas de pago, descuentos y bonos
4. **ms-reclutamiento** – vacantes, postulantes y proceso de contratación
5. **ms-desempeno** – evaluaciones de desempeño, objetivos y desarrollo de talento
6. **ms-notificaciones** – consume eventos (SQS) y notifica (SNS)

> Ajustable según lo que decida el grupo en la Fase 1.

---

## 2. Equipo (6 integrantes)

| # | Integrante | Rol principal | Responsabilidades |
|---|---|---|---|
| 1 | Miguel Espinoza | Líder técnico / DevOps | Arquitectura, `serverless.yml`, CI/CD, Amplify, IAM |
| 2 | Fernando Espinoza | Backend A | ms-usuarios (auth) + ms-empleados |
| 3 | Rodrigo Miguel Gomez Pacheco | Backend B | ms-nominas + ms-reclutamiento |
| 4 | Luciano Matias Sanchez Goicochea| Backend C | ms-desempeno + ms-notificaciones (SNS/SQS) |
| 5 | _(nombre)_ | Frontend | UI, integración con APIs, login multi-tenant |
| 6 | _(nombre)_ | Datos / QA / Documentación | Datos ficticios (30k/servicio), pruebas, informe y PPT |

---

## 3. Fechas clave

| Fecha | Hito |
|---|---|
| **Sáb 14-Nov-2026** | Exposición virtual con ACL: avance proporcional al **30%** (3 pts) |
| **Dom 22-Nov-2026, 23:59** | Entrega en Canvas: informe (Word/PDF) + PPT |
| **Semana 16** | Exposición presencial + demo (obligatoria; sin ella la nota máxima es 10) |

**Rúbrica:** Diagrama de arquitectura (2) · BackEnd (8) · FrontEnd (6) · Exposición presencial (1) · Exposición virtual ACL (3)

---

## 4. Fases del trabajo

### Fase 0 – Organización (22 – 25 Oct)
- [ ] Crear repositorios (uno por microservicio + frontend + infra) y hacerlos públicos
- [ ] Definir tablero de tareas y reunión fija semanal
- [ ] Asignar roles (sección 2) y convención de ramas/commits
- [ ] Cuenta AWS compartida, usuarios IAM y región única

**Entregable:** repos creados, roles asignados, tablero activo.

### Fase 1 – Diseño y arquitectura (26 Oct – 1 Nov)
- [ ] Definir funcionalidades HCM por microservicio
- [ ] Estrategia multi-tenant (tenant en token, claves y particiones DynamoDB)
- [ ] Estructura JSON de cada tabla (documentar para el informe)
- [ ] Catálogo de eventos SNS/SQS (quién publica, quién consume)
- [ ] **Diagrama de Arquitectura de Solución** (2 pts)
- [ ] Mockups del frontend

**Entregable:** diagrama de arquitectura, modelo de datos, lista de eventos.

### Fase 2 – Base de infraestructura (2 – 8 Nov)
- [ ] Plantilla común de Serverless Framework (stages, tablas, permisos)
- [ ] Autenticación y autorizador reutilizable para todos los APIs
- [ ] ms-usuarios y ms-empleados funcionando con tenant aislado
- [ ] Esqueleto del frontend con login, desplegado en Amplify
- [ ] Script generador de datos ficticios (3 tenants)

**Entregable:** 2 microservicios desplegados + login funcional.

### Fase 3 – Hito 30% y exposición virtual (9 – 14 Nov)
- [ ] Consolidar lo avanzado (≥ 30% del proyecto) y preparar demo corta
- [ ] Probar flujo extremo a extremo con 1–2 tenants
- [ ] Preparar presentación para la exposición virtual con ACL del **14-Nov**

**Entregable:** avance demostrable + exposición virtual.

### Fase 4 – Resto del backend y EDA (15 – 18 Nov)
- [ ] ms-nominas, ms-reclutamiento, ms-desempeno, ms-notificaciones
- [ ] Integración SNS → SQS → Lambda consumidoras
- [ ] S3 para CVs, boletas de pago y reportes
- [ ] Carga de **≥ 30,000 registros por microservicio** en 3 tenants

**Entregable:** los 5+ microservicios desplegados y comunicándose por eventos.

### Fase 5 – Frontend e integración (17 – 20 Nov)
- [ ] Pantallas: empleados, nóminas, vacantes y contratación, evaluaciones de desempeño, dashboard
- [ ] Consumo de todas las APIs con token y tenant
- [ ] Pruebas con 2 tenants (verificar aislamiento de datos)
- [ ] Corrección de errores y manejo de fallos

**Entregable:** aplicación completa funcionando en Amplify.

### Fase 6 – Documentación y entrega (19 – 22 Nov)
- [ ] **Informe** (Word/PDF): evidencias, enlaces públicos a repos, diseño de BD de cada microservicio
- [ ] **PPT** resumen con todo lo solicitado
- [ ] Capturas/evidencias de despliegue, datos y eventos
- [ ] Subir a Canvas antes del **22-Nov 23:59** (no dejar para último minuto)

**Entregable:** informe + PPT en Canvas.

### Fase 7 – Exposición presencial (Semana 16)
- [ ] Ensayo general con la demo de **2 tenants**
- [ ] Definir quién presenta qué (asistencia de todos es obligatoria)
- [ ] Plan B: video de la demo y datos precargados por si falla la red

---

## 5. Checklist final de entrega

- [ ] Diagrama de arquitectura de solución
- [ ] ≥ 5 microservicios serverless protegidos (API Gateway + Lambda)
- [ ] Una BD por microservicio, con diseño documentado
- [ ] ≥ 30,000 registros por microservicio en 3 tenants
- [ ] S3, SNS y SQS en uso
- [ ] Despliegue 100% automatizado con Serverless Framework
- [ ] Frontend en Amplify
- [ ] Demo con 2 tenants
- [ ] Informe (Word/PDF) con enlaces públicos a repositorios
- [ ] PPT resumen
- [ ] Entrega en Canvas antes del 22-Nov-2026 23:59

---

## 6. Convenciones del equipo

- Ramas: `main` (estable), `dev` (integración), `feature/<nombre>`
- Commits cortos y descriptivos; Pull Request revisado por al menos 1 persona
- Nunca subir credenciales de AWS al repositorio (usar variables de entorno / SSM)
- Un mismo `stage` de pruebas compartido; cada quien usa su propio stage para desarrollar
