# Backend C — ms-reclutamiento + ms-desempeno

**Responsable:** Luciano Matías Sánchez Goicochea
**Proyecto:** CS2032 Cloud Computing — HCM SaaS (Grupo 2)
**Entrega parcial:** 14-Nov-2026 · **Final:** 22-Nov-2026

---

## Resumen

Backend C cubre los dos microservicios de talento del HCM:

- **ms-reclutamiento** — vacantes, postulaciones (con CV en S3), pipeline de contratación y onboarding
- **ms-desempeno** — evaluaciones de desempeño y reconocimientos entre empleados

**Stack común:**

- Serverless Framework 4 + AWS Lambda (Python 3.12)
- DynamoDB single-table con GSIs
- API Gateway HTTP API
- Multi-tenant: `tenant_id` como partition key en todas las tablas
- Eventos: SNS topic compartido `hcm-eventos-dev`
- IAM: usa el `LabRole` existente (Learner Lab)

---

## Arquitectura

```
                   API Gateway (HTTP API)
                           │
             ┌─────────────┴─────────────┐
             │                           │
      ┌──────▼──────┐             ┌──────▼──────┐
      │  Lambdas    │             │  Lambdas    │
      │ reclutam.   │             │  desempeno  │
      └──────┬──────┘             └──────┬──────┘
             │                           │
             ├──▶ DynamoDB               ├──▶ DynamoDB
             │    hcm-reclutamiento      │    hcm-desempeno
             │    GSI vacante-index      │    GSI empleado-index
             │                           │
             ├──▶ S3                     │
             │    hcm-cvs-dev            │
             │    (CVs via presigned)    │
             │                           │
             └──▶ SNS ◀──────────────────┘
                  hcm-eventos-dev
                       │
                  (consumen ms-empleados,
                   ms-notificaciones, …)
```

---

## Despliegue

### Prerequisitos

- Learner Lab activo con credenciales en `~/.aws/credentials`
- Serverless Framework 4 (`npm i -g serverless`)
- Python 3.12 (viene en CloudShell)
- Variable `AWS_DEFAULT_REGION=us-east-1`

### Orden

```bash
# 1) ms-reclutamiento primero (crea el topic SNS compartido)
cd ms-reclutamiento
sls deploy --stage dev

# 2) ms-desempeno después (importa el topic ARN del paso 1)
cd ../ms-desempeno
sls deploy --stage dev
```

Cada deploy imprime los endpoints de API Gateway.

### Variables de entorno (Lambdas)

| Variable | Valor | Para |
|---|---|---|
| `TABLE_NAME` | `hcm-reclutamiento-dev` / `hcm-desempeno-dev` | DynamoDB |
| `CV_BUCKET` | `hcm-cvs-dev-<accountId>` | S3 (solo reclutamiento) |
| `EVENTS_TOPIC_ARN` | `arn:aws:sns:...:hcm-eventos-dev` | SNS |

---

## Tablas DynamoDB

### `hcm-reclutamiento-dev`

Single-table con PK `tenant_id` + SK `sk` (patrón `tipo#id`):

| Tipo | SK | Ejemplo |
|---|---|---|
| Vacante | `VACANTE#vac-XXX` | `VACANTE#vac-77adca25` |
| Postulación | `POSTULACION#pos-XXX` | `POSTULACION#pos-18c920ae` |
| Onboarding | `ONBOARDING#<empleado_id>#onb-XXX` | `ONBOARDING#emp-000045#onb-96c43958` |

**GSI `vacante-index`** · PK `tenant_id`, SK `vacante_id` — para listar postulaciones por vacante.

### `hcm-desempeno-dev`

Single-table con PK `tenant_id` + SK `sk`:

| Tipo | SK | Ejemplo |
|---|---|---|
| Evaluación | `eva-XXX` | `eva-f2fc617e` |
| Reconocimiento | `rec-XXX` | `rec-8c8eef20` |

**GSI `empleado-index`** · PK `tenant_id`, SK `empleado_id` — para listar evaluaciones y reconocimientos por empleado.

---

## Endpoints

### ms-reclutamiento (8 endpoints)

| Método | Path | Qué hace |
|---|---|---|
| POST | `/vacantes` | Crear vacante |
| GET | `/vacantes?tenant_id=X` | Listar vacantes del tenant |
| POST | `/postulaciones` | Crear postulación + URL S3 prefirmada para subir el CV |
| GET | `/vacantes/{vacante_id}/postulaciones?tenant_id=X` | Listar postulaciones por vacante (GSI) |
| PATCH | `/postulaciones/{postulacion_id}/estado` | Avanzar pipeline — publica evento si llega a CONTRATADO |
| POST | `/onboarding` | Crear tarea de onboarding para un empleado |
| GET | `/onboarding/{empleado_id}?tenant_id=X` | Listar tareas de un empleado |
| PATCH | `/onboarding/{empleado_id}/{onboarding_id}?tenant_id=X` | Marcar tarea como completada |

**Pipeline de estados** de postulación: `RECIBIDO → ENTREVISTA → OFERTA → CONTRATADO / RECHAZADO`

### ms-desempeno (4 endpoints)

| Método | Path | Qué hace |
|---|---|---|
| POST | `/evaluaciones` | Crear evaluación (estado inicial PENDIENTE) |
| GET | `/evaluaciones?tenant_id=X&empleado=emp-ID` | Listar evaluaciones de un empleado (GSI) |
| PUT | `/evaluaciones/{evaluacion_id}` | Actualizar — publica evento si estado=COMPLETADA |
| POST | `/reconocimientos` | Crear reconocimiento entre empleados |

**Estados de evaluación:** `PENDIENTE → EN_PROGRESO → COMPLETADA`

Ver `endpoints.http` para ejemplos listos de curl / request.

---

## Eventos SNS

**Topic:** `hcm-eventos-dev`
**ARN exportado como:** `hcm-eventos-topic-arn-dev` (importable desde otros stacks con `Fn::ImportValue`)

### Formato común

```json
{
  "tipo_evento": "PostulanteContratado",
  "tenant_id": "andina",
  "origen": "ms-reclutamiento",
  "timestamp": "2026-11-02T04:33:45.870885+00:00",
  "datos": { ... }
}
```

**Message attributes** para filter policies en SQS:

- `tipo_evento`: String — nombre del evento
- `tenant_id`: String — tenant que lo originó

### `PostulanteContratado`

- Publica: `ms-reclutamiento`
- Cuándo: PATCH `/postulaciones/{id}/estado` con `estado=CONTRATADO`
- Datos:
  ```json
  {
    "postulacion_id": "pos-18c920ae",
    "vacante_id": "vac-77adca25",
    "nombre": "María García",
    "email": "maria@test.com"
  }
  ```

### `EvaluacionCompletada`

- Publica: `ms-desempeno`
- Cuándo: PUT `/evaluaciones/{id}` que deje `estado=COMPLETADA`
- Datos:
  ```json
  {
    "evaluacion_id": "eva-f2fc617e",
    "empleado_id": "emp-000045",
    "evaluador_id": "emp-000010",
    "periodo": "2026-S2",
    "puntaje": 4.5
  }
  ```

---

## Integración desde otros microservicios

### Suscribir una SQS al topic (ejemplo para ms-notificaciones)

En el `serverless.yml` del consumidor:

```yaml
resources:
  Resources:
    EventosQueue:
      Type: AWS::SQS::Queue
      Properties:
        QueueName: ms-notificaciones-eventos-${sls:stage}
        VisibilityTimeout: 60
    EventosDLQ:
      Type: AWS::SQS::Queue
      Properties:
        QueueName: ms-notificaciones-eventos-dlq-${sls:stage}
    EventosSub:
      Type: AWS::SNS::Subscription
      Properties:
        Protocol: sqs
        TopicArn:
          Fn::ImportValue: hcm-eventos-topic-arn-${sls:stage}
        Endpoint:
          Fn::GetAtt: [EventosQueue, Arn]
        FilterPolicy:
          tipo_evento:
            - PostulanteContratado
            - EvaluacionCompletada
    EventosQueuePolicy:
      Type: AWS::SQS::QueuePolicy
      Properties:
        Queues: [!Ref EventosQueue]
        PolicyDocument:
          Statement:
            - Effect: Allow
              Principal: '*'
              Action: sqs:SendMessage
              Resource: !GetAtt EventosQueue.Arn
              Condition:
                ArnEquals:
                  aws:SourceArn:
                    Fn::ImportValue: hcm-eventos-topic-arn-${sls:stage}
```

### Convención de IDs

Los IDs de empleado se mantienen consistentes entre microservicios: formato `emp-NNNNNN` (6 dígitos con padding). El pool actual de prueba es `emp-000001..emp-000500`.

---

## Volumen de datos (carga masiva)

Script: `scripts/seed_data.py` — genera data realista coherente entre tablas.

| Tabla | Items | Distribución por tenant |
|---|---|---|
| `hcm-reclutamiento-dev` | 30,450+ | 150 vacantes + 5,000 postulaciones + 5,000 onboarding |
| `hcm-desempeno-dev` | 30,000+ | 7,000 evaluaciones + 3,000 reconocimientos |

**Correr desde CloudShell:**

```bash
export AWS_DEFAULT_REGION=us-east-1
pip install boto3 --break-system-packages
python3 scripts/seed_data.py
```

Tiempo total: ~55s para 60K items. Usa `batch_writer` de boto3 (25 items por request).

---

## Tenants de prueba

Definidos en el documento de arquitectura (sección 1):

- **`andina`** — tenant principal, usado en la demo
- **`pacifico`** — tenant secundario, usado en la demo
- **`sierra`** — tercer tenant para demostrar aislamiento

Cada tenant tiene ~10,000 registros por tabla.

---

## Checklist de entrega

- [x] Dos microservicios serverless funcionando (ms-reclutamiento + ms-desempeno)
- [x] Tablas DynamoDB single-table con GSIs
- [x] S3 bucket para CVs con URL prefirmada
- [x] SNS topic compartido con export CFN
- [x] Dos eventos publicados (PostulanteContratado, EvaluacionCompletada)
- [x] Multi-tenancy por partition key (3 tenants)
- [x] Carga masiva: 30K+ registros por tabla
- [x] 12 endpoints HTTP totales (8 reclutamiento + 4 desempeno)
- [ ] Lambda Authorizer compartido (depende de ms-usuarios — Fernando)
- [ ] Integración con ms-empleados para flujo PostulanteContratado → crear empleado (depende de Fernando)
- [ ] Integración con ms-notificaciones para consumir eventos (depende de Brhandon)
