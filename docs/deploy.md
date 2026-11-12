# Guía de despliegue — Backend C

Cómo levantar `ms-reclutamiento` + `ms-desempeno` en una cuenta AWS Learner Lab distinta a la del dueño original.

> **Ejecuta todos los comandos desde la raíz del repositorio** (`ProyectoFinalCloud/`), no desde esta carpeta `docs/`.

## Prerequisitos

En tu máquina (Mac/Linux):

- **Node.js 20+** y **Serverless Framework 4**: `npm i -g serverless`
- **Python 3.12** (para la carga masiva opcional)
- **AWS CLI** configurado con credenciales de TU Learner Lab (`~/.aws/credentials`)
- Lab verde (activo) con credenciales no expiradas

Verifica con:

```bash
aws sts get-caller-identity
```

Debe devolver tu account ID (algo como `arn:aws:sts::XXXXXXXXXXXX:assumed-role/voclabs/...`). Si da error, renueva credenciales en el Learner Lab.

---

## IMPORTANTE antes de desplegar: cambiar el account ID

Los `serverless.yml` de ambos microservicios tienen hardcodeado el account ID del dueño original. **Hay que cambiarlo** al tuyo.

**1) Obtén tu account ID:**

```bash
aws sts get-caller-identity --query Account --output text
```

Te imprime 12 dígitos (ej: `123456789012`).

**2) Reemplaza en los dos `serverless.yml`:**

```bash
# Desde la raíz del repo. Reemplaza 123456789012 por TU account ID real.
sed -i '' 's/555330235657/123456789012/g' ms-reclutamiento/serverless.yml ms-desempeno/serverless.yml
```

(En Linux: usa `sed -i` sin las comillas vacías.)

Verifica que haya cambiado:

```bash
grep "arn:aws:iam" ms-reclutamiento/serverless.yml
# debe mostrar: role: arn:aws:iam::TU_ACCOUNT_ID:role/LabRole
```

---

## Orden de deploy

**ms-reclutamiento tiene que ir primero** porque crea el topic SNS `hcm-eventos` que `ms-desempeno` importa.

```bash
# 1) ms-reclutamiento
cd ms-reclutamiento
sls deploy --stage dev
# Al final imprime los endpoints. Anótalos.

# 2) ms-desempeno
cd ../ms-desempeno
sls deploy --stage dev
# Al final imprime sus propios endpoints.
```

Si falla con `iam:CreateRole`, es porque el serverless.yml está intentando crear un rol nuevo (no debería si cambiaste el account ID bien). Revisa que la línea `iam.role` apunte al LabRole de TU cuenta.

---

## Actualizar documentación con los nuevos URLs

Los URLs cambiarán porque son nuevos para tu cuenta. Actualiza:
- `postman/backend-c.postman_collection.json`
- `api/openapi.yaml`
- `api/swagger.html`

```bash
# Desde la raíz del repo. Reemplaza por los URLs reales que te imprimió sls deploy.
URL_RECL_VIEJA="k9zoy1ou55.execute-api.us-east-1.amazonaws.com"
URL_RECL_NUEVA="<tu URL de ms-reclutamiento>"
URL_DESE_VIEJA="b5k8pbnfqa.execute-api.us-east-1.amazonaws.com"
URL_DESE_NUEVA="<tu URL de ms-desempeno>"

sed -i '' "s|$URL_RECL_VIEJA|$URL_RECL_NUEVA|g" api/swagger.html api/openapi.yaml postman/backend-c.postman_collection.json
sed -i '' "s|$URL_DESE_VIEJA|$URL_DESE_NUEVA|g" api/swagger.html api/openapi.yaml postman/backend-c.postman_collection.json
```

---

## Carga masiva (opcional, para la demo con 30K registros)

```bash
export AWS_DEFAULT_REGION=us-east-1
pip install boto3 --break-system-packages

cd scripts
python3 seed_data.py
```

Tarda ~1 min y mete 60K+ items repartidos en 3 tenants (`andina`, `pacifico`, `sierra`).

---

## Probar

Email para notificaciones SNS (opcional):

```bash
TOPIC=$(aws sns list-topics --query "Topics[?contains(TopicArn, 'hcm-eventos-dev')].TopicArn" --output text)
aws sns subscribe --topic-arn $TOPIC --protocol email --notification-endpoint tu-email@dominio.com
# Confirma el email que te llega
```

Importa `postman/backend-c.postman_collection.json` en Postman y corre los requests en orden. El request **"7. Pipeline → CONTRATADO"** y el **"3. Completar evaluación"** disparan los eventos SNS que llegarán al email suscrito.

---

## Nota sobre integración entre cuentas

El `Fn::ImportValue` solo funciona dentro de la misma cuenta AWS. Si otro integrante del equipo (ms-empleados, ms-notificaciones) despliega en SU cuenta, no podrá importar el topic SNS de tu cuenta.

**Para la integración EDA en el expo**, lo recomendable es que todo el equipo despliegue en **una sola cuenta AWS compartida** (la del líder técnico Miguel).
