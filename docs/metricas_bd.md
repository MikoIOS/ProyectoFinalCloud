# Reporte de Auditoría de Base de Datos — SaaS HCM
**Fecha de ejecución:** `2026-11-09 21:56:28 UTC`
**Requisito de Rúbrica:** $\ge 30,000$ registros por microservicio en 3 tenants.

---

## 1. Resumen de Registros por Microservicio

| Microservicio | Nombre de Tabla DynamoDB | Total Registros | Andina | Pacífico | Sierra | Cumple Rúbrica ( $\ge$ 30k ) |
|---|---|---|---|---|---|:---:|
| **ms-usuarios** | `hcm-usuarios` | **30,009** | 10,008 | 10,001 | 10,000 | ✅ CUMPLE |
| **ms-empleados** | `hcm-empleados` | **30,005** | 10,005 | 10,000 | 10,000 | ✅ CUMPLE |
| **ms-reclutamiento** | `hcm-reclutamiento-dev` | **30,463** | 10,162 | 10,151 | 10,150 | ✅ CUMPLE |
| **ms-desempeno** | `hcm-desempeno-dev` | **30,009** | 10,008 | 10,001 | 10,000 | ✅ CUMPLE |
| **ms-notificaciones** | `hcm-notificaciones-dev` | **30,321** | 10,121 | 10,100 | 10,100 | ✅ CUMPLE |
| **ms-nominas** | `hcm-nominas-dev` | **40,508** | 19,926 | 10,292 | 10,290 | ✅ CUMPLE |
| **ms-asistencia** | `hcm-asistencia-dev` | **30,004** | 10,004 | 10,000 | 10,000 | ✅ CUMPLE |

**Total Global de Registros en DynamoDB:** `221,319` registros.
**Estado General del Requisito:** ✅ **APROBADO PARA ENTREGA**

---

## 2. Aislamiento por Tenant
Cada registro almacena como clave de partición (`HASH`) el atributo `tenant_id`.
Se cuentan los registros por tenant. Este conteo no demuestra aislamiento de acceso; eso se verifica con pruebas HTTP entre tenants.
