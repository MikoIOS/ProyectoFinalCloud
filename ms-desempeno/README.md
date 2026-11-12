# ms-desempeno

Microservicio de desempeño y talento del HCM.

**Responsable:** Luciano Sánchez (Backend C)

## Qué hace

- Evaluaciones por periodo con puntaje, competencias, objetivos y comentarios
- Pipeline de evaluación: `PENDIENTE → EN_PROGRESO → COMPLETADA`
- Reconocimientos entre empleados
- Publica evento `EvaluacionCompletada` al topic SNS compartido

## Recursos AWS creados

| Recurso | Nombre |
|---|---|
| DynamoDB Table | `hcm-desempeno-${stage}` (PK `tenant_id`, SK `sk`) |
| GSI | `empleado-index` (PK `tenant_id`, SK `empleado_id`) |

Importa el topic SNS creado por `ms-reclutamiento` vía `Fn::ImportValue hcm-eventos-topic-arn-${stage}`.

## Despliegue

Requiere que `ms-reclutamiento` ya esté desplegado (el topic SNS compartido se crea ahí).

```bash
sls deploy --stage dev
```

## Endpoints

| Método | Path |
|---|---|
| POST | `/evaluaciones` |
| GET | `/evaluaciones?tenant_id=X&empleado=emp-ID` |
| PUT | `/evaluaciones/{evaluacion_id}` |
| POST | `/reconocimientos` |

Ejemplos en [`../api/endpoints.http`](../api/endpoints.http).

## Estructura

```
ms-desempeno/
├── serverless.yml
└── handlers/
    ├── evaluaciones.py
    └── reconocimientos.py
```

## Eventos publicados

### EvaluacionCompletada

Se publica cuando una evaluación pasa a estado `COMPLETADA`.

```json
{
  "tipo_evento": "EvaluacionCompletada",
  "tenant_id": "andina",
  "origen": "ms-desempeno",
  "timestamp": "...",
  "datos": {
    "evaluacion_id": "eva-XXX",
    "empleado_id": "emp-XXX",
    "evaluador_id": "emp-XXX",
    "periodo": "2026-S2",
    "puntaje": 4.5
  }
}
```

## Nota de diseño

La misma tabla contiene **evaluaciones** (SK `eva-XXX`) y **reconocimientos** (SK `rec-XXX`) siguiendo el patrón single-table. El GSI `empleado-index` permite consultar ambos tipos por empleado; los endpoints filtran por tipo con `FilterExpression` sobre el prefijo del SK.
