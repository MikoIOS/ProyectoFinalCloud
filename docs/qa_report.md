# Reporte de Aseguramiento de Calidad (QA) — SaaS HCM Multi-Tenant
**Fecha de ejecución:** `2026-11-05 18:23:35 UTC`
**Stage evaluado:** `dev` | **Región AWS:** `us-east-1`
**Efectividad general:** `100.0%` (19/19 pruebas exitosas)

---

## 1. Resumen Ejecutivo de Pruebas

| Categoría | Caso de Prueba | Resultado | Detalle de Validación |
|---|---|:---:|---|
| **Infraestructura** | Tabla ms-usuarios (hcm-usuarios-dev) | ✅ PASS | Estado: ACTIVE, Modo: PAY_PER_REQUEST |
| **Infraestructura** | Tabla ms-empleados (hcm-empleados-dev) | ✅ PASS | Estado: ACTIVE, Modo: PAY_PER_REQUEST |
| **Infraestructura** | Tabla ms-reclutamiento (hcm-reclutamiento-dev) | ✅ PASS | Estado: ACTIVE, Modo: PAY_PER_REQUEST |
| **Infraestructura** | Tabla ms-desempeno (hcm-desempeno-dev) | ✅ PASS | Estado: ACTIVE, Modo: PAY_PER_REQUEST |
| **Infraestructura** | Tabla ms-notificaciones (hcm-notificaciones-dev) | ✅ PASS | Estado: ACTIVE, Modo: PAY_PER_REQUEST |
| **Aislamiento** | Aislamiento en ms-usuarios | ✅ PASS | Cero fuga de datos en 15 items consultados por tenant |
| **Aislamiento** | Aislamiento en ms-empleados | ✅ PASS | Cero fuga de datos en 15 items consultados por tenant |
| **Aislamiento** | Aislamiento en ms-reclutamiento | ✅ PASS | Cero fuga de datos en 42 items consultados por tenant |
| **Aislamiento** | Aislamiento en ms-desempeno | ✅ PASS | Cero fuga de datos en 15 items consultados por tenant |
| **Aislamiento** | Aislamiento en ms-notificaciones | ✅ PASS | Cero fuga de datos en 15 items consultados por tenant |
| **Integridad** | Mapeo usr-xxx <-> emp-xxx | ✅ PASS | 5/5 entidades sincronizadas con mismo email y tenant |
| **EDA** | Schema estándar de eventos | ✅ PASS | Campos obligatorios presentes: ['tipo_evento', 'tenant_id', 'origen', 'timestamp', 'datos'] |
| **EDA** | Catálogo de eventos soportados | ✅ PASS | 8 eventos homologados (EmpleadoCreado, EmpleadoCesado, PostulanteContratado, AusenciaSolicitada...) |
| **EDA** | Idempotencia de Notificaciones (SHA-1 determinista) | ✅ PASS | Hash estable: not-86361a013ec1 (evita duplicación ante reintentos SQS) |
| **Casos Negativos** | Rechazo de Tenant Fantasma/Malicioso | ✅ PASS | Retornó estrictamente 0 registros ante consulta no autorizada |
| **Casos Negativos** | Protección contra Suplantación Cruzada de IDs | ✅ PASS | Imposible acceder a datos de 'andina' usando contexto de 'pacifico' |
| **Casos Negativos** | Validación de Evento Corrupto (Sin tipo_evento) | ✅ PASS | Evento descartado correctamente antes de encolar/procesar |
| **Casos Negativos** | Validación de Evento Corrupto (Sin tenant_id) | ✅ PASS | Rechazo estricto de eventos sin contexto de tenant (previene fuga EDA) |
| **Casos Negativos** | Seguridad de Auth (Rechazo de credenciales inválidas) | ✅ PASS | Credenciales incorrectas bloqueadas antes de emitir JWT |

---

## 2. Validación de Criterios de Aceptación (Rúbrica)

1. **Aislamiento Multi-Tenant:**
   - Se verificó que ninguna consulta (`Query` por partition key) devuelva registros pertenecientes a un tenant distinto.
   - Aislamiento 100% garantizado en base de datos.
2. **Integridad Referencial:**
   - Sincronía bidireccional entre las identidades de `ms-usuarios` (`usr-xxx`) y los registros laborales en `ms-empleados` (`emp-xxx`).
3. **Arquitectura Orientada a Eventos (EDA):**
   - Validado el contrato de datos en eventos SNS/SQS y el mecanismo de desduplicación/idempotencia por hash determinista en `ms-notificaciones`.
