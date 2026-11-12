# ms-reclutamiento

Microservicio de reclutamiento y onboarding del HCM.

**Responsable:** Luciano Sánchez (Backend C)

## Qué hace

- CRUD de vacantes (ABIERTA / CERRADA)
- Postulantes con CV en S3 mediante URL prefirmada
- Pipeline de postulación: `RECIBIDO → ENTREVISTA → OFERTA → CONTRATADO / RECHAZADO`
- Tareas de onboarding por empleado (checklist)
- Publica evento `PostulanteContratado` al topic SNS compartido

## Recursos AWS creados

| Recurso | Nombre |
|---|---|
| DynamoDB Table | `hcm-reclutamiento-${stage}` (PK `tenant_id`, SK `sk`) |
| GSI | `vacante-index` (PK `tenant_id`, SK `vacante_id`) |
| S3 Bucket | `hcm-cvs-${stage}-${accountId}` (CORS habilitado) |
| SNS Topic | `hcm-eventos-${stage}` (exportado como `hcm-eventos-topic-arn-${stage}`) |

## Despliegue

```bash
sls deploy --stage dev
```

El deploy crea el topic SNS compartido que los demás microservicios importan vía `Fn::ImportValue`.

## Endpoints

| Método | Path |
|---|---|
| POST | `/vacantes` |
| GET | `/vacantes?tenant_id=X` |
| POST | `/postulaciones` |
| GET | `/vacantes/{vacante_id}/postulaciones?tenant_id=X` |
| PATCH | `/postulaciones/{postulacion_id}/estado` |
| POST | `/onboarding` |
| GET | `/onboarding/{empleado_id}?tenant_id=X` |
| PATCH | `/onboarding/{empleado_id}/{onboarding_id}?tenant_id=X` |

Ejemplos de llamadas en [`../api/endpoints.http`](../api/endpoints.http).

## Estructura

```
ms-reclutamiento/
├── serverless.yml
└── handlers/
    ├── vacantes.py
    ├── postulaciones.py
    └── onboarding.py
```

## Eventos publicados

### PostulanteContratado

Se publica cuando una postulación pasa a estado `CONTRATADO`.

```json
{
  "tipo_evento": "PostulanteContratado",
  "tenant_id": "andina",
  "origen": "ms-reclutamiento",
  "timestamp": "...",
  "datos": {
    "postulacion_id": "pos-XXX",
    "vacante_id": "vac-XXX",
    "nombre": "...",
    "email": "..."
  }
}
```
