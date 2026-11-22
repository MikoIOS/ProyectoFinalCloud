# Reporte de Auditoría de Base de Datos — SaaS HCM
**Entorno auditado:** `prod` (sin fallback a otro entorno)
Conteo consistente por página; no es una instantánea transaccional entre tablas. Evitar escrituras durante la auditoría.
**Fecha de ejecución:** `2026-11-22 06:46:19 UTC`
**Requisito de Rúbrica:** $\ge 30,000$ registros por microservicio en 3 tenants.

---

## 1. Resumen de Registros por Microservicio

| Microservicio | Nombre de Tabla DynamoDB | Total Registros | Andina | Pacífico | Sierra | Otros | Cumple Rúbrica ( $\ge$ 30k ) |
|---|---|---|---|---|---|---|:---:|
| **ms-usuarios** | `hcm-usuarios` | **30,014** | 10,008 | 10,001 | 10,000 | 5 | ✅ CUMPLE |
| **ms-empleados** | `hcm-empleados` | **30,007** | 10,005 | 10,000 | 10,000 | 2 | ✅ CUMPLE |
| **ms-reclutamiento** | `hcm-reclutamiento-dev` | **30,463** | 10,162 | 10,151 | 10,150 | 0 | ✅ CUMPLE |
| **ms-desempeno** | `hcm-desempeno-dev` | **30,009** | 10,008 | 10,001 | 10,000 | 0 | ✅ CUMPLE |
| **ms-notificaciones** | `hcm-notificaciones-dev` | **30,325** | 10,123 | 10,100 | 10,100 | 2 | ✅ CUMPLE |
| **ms-nominas** | `hcm-nominas-dev` | **40,508** | 19,926 | 10,292 | 10,290 | 0 | ✅ CUMPLE |
| **ms-asistencia** | `hcm-asistencia-dev` | **30,008** | 10,008 | 10,000 | 10,000 | 0 | ✅ CUMPLE |

**Total Global de Registros en DynamoDB:** `221,334` registros.
**Estado General del Requisito:** ✅ **VOLUMEN VERIFICADO EN ESTE ENTORNO**


El cumplimiento exige ≥30.000 ítems sumados entre Andina, Pacífico y Sierra y presencia de los tres; otros tenants no sustituyen esa distribución. Incluye entidades y registros de control, no solo empleados.

---

## 2. Aislamiento por Tenant
Cada registro almacena como clave de partición (`HASH`) el atributo `tenant_id`.
Se cuentan los registros por tenant. Este conteo no demuestra aislamiento de acceso; eso se verifica con pruebas HTTP entre tenants.
