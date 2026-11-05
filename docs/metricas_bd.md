# Reporte de Auditoría de Base de Datos — SaaS HCM
**Fecha de ejecución:** `2026-11-05 17:52:16 UTC`
**Requisito de Rúbrica:** $\ge 30,000$ registros por microservicio en 3 tenants.

---

## 1. Resumen de Registros por Microservicio

| Microservicio | Nombre de Tabla DynamoDB | Total Registros | Andina | Pacífico | Sierra | Cumple Rúbrica ( $\ge$ 30k ) |
|---|---|---|---|---|---|:---:|
| **ms-usuarios** | `hcm-usuarios-dev` | **15** | 5 | 5 | 5 | ⚠️ EN PROGRESO |
| **ms-empleados** | `hcm-empleados-dev` | **15** | 5 | 5 | 5 | ⚠️ EN PROGRESO |
| **ms-reclutamiento** | `hcm-reclutamiento-dev` | **42** | 14 | 14 | 14 | ⚠️ EN PROGRESO |
| **ms-desempeno** | `hcm-desempeno-dev` | **15** | 5 | 5 | 5 | ⚠️ EN PROGRESO |
| **ms-notificaciones** | `hcm-notificaciones-dev` | **15** | 5 | 5 | 5 | ⚠️ EN PROGRESO |

**Total Global de Registros en DynamoDB:** `102` registros.
**Estado General del Requisito:** ⏳ **FALTAN REGISTROS POR COMPLETAR**

---

## 2. Aislamiento por Tenant
Cada registro almacena como clave de partición (`HASH`) el atributo `tenant_id`.
Se comprueba que la repartición de datos sea equilibrada (~33% por tenant) sin mezcla de identificadores entre tenants.
