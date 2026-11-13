# HCM unificado: un servicio Serverless, una API por stage

`hcm` reúne los 68 Lambdas de usuarios, empleados, nómina, asistencia, reclutamiento, desempeño, notificaciones y monitorización en un único despliegue. Conserva los módulos y las siete tablas; no convierte todo el negocio en una sola función.

Cada despliegue tiene **una REST API** y su stage. `hcm-dev` y `hcm-prod` son stacks independientes: hay una API para dev y otra para prod. Esto no es una única REST API global con dos stages: esa alternativa requiere otra organización del gateway.

| Ambiente | Stack | Tabla de usuarios | Tabla de empleados |
|---|---|---|---|
| Desarrollo | `hcm-dev` | `hcm-dev-usuarios` | `hcm-dev-empleados` |
| Producción | `hcm-prod` | `hcm-prod-usuarios` | `hcm-prod-empleados` |

El resto de las tablas, colas, topics, buckets, Lambdas, logs y alarmas también queda separado por stage. Dentro de cada ambiente se conserva la multitenencia por `tenant_id`. Los nombres nuevos no colisionan con los stacks actuales. Las tablas y buckets tienen política de retención.

## Preparar y comprobar

Desde la raíz del backend, con Python 3.12 o superior y Node disponibles:

```sh
python3 -m venv /tmp/hcm-build
/tmp/hcm-build/bin/pip install -r hcm/requirements-build.txt
npm ci --prefix ms-notificaciones
/tmp/hcm-build/bin/python hcm/build.py
python3 -m unittest discover -s hcm/tests -v
```

El generador reutiliza los `serverless.yml` de los módulos como entradas. Genera `hcm/.build/service.json` y ocho ZIPs independientes. Mantener un ZIP por módulo evita colisiones entre sus paquetes Python `src` y `common`. El ZIP de usuarios incluye PyJWT y el de notificaciones incluye sus dependencias npm; los otros módulos Python utilizan boto3 provisto por Lambda. No se empaquetan entornos, tests del proyecto, archivos `.env`, credenciales ni datos de ejemplo.

Define `LAB_ROLE_ARN` con el rol autorizado de AWS Academy. Cada stage requiere su propia variable secreta: `HCM_JWT_SECRET_dev` o `HCM_JWT_SECRET_prod`. Utiliza valores diferentes y no los guardes en Git. Para probar únicamente el empaquetado pueden ser valores ficticios; nunca desplegar esos valores de prueba.

Dentro de `hcm/`:

```sh
serverless package --stage dev --package .build/check-dev
serverless package --stage prod --package .build/check-prod
```

Los archivos de `.build/` y `.serverless/` están ignorados por Git. La plantilla empaquetada de CloudFormation incluye variables de entorno resueltas; tratarla como un archivo sensible si se usaron secretos reales.

## Rutas y eventos

Se conservan las rutas de negocio: `/auth/login`, `/auth/register`, `/empleados`, `/nominas`, `/ausencias`, `/vacantes`, `/evaluaciones`, `/notificaciones`, etc. El frontend podrá apuntar sus siete clientes a la misma URL base del ambiente.

Solo usuarios conserva `GET /ping`. Los otros pings se exponen como `/empleados/ping`, `/asistencia/ping` y `/notificaciones/ping` para evitar rutas duplicadas. Hay un único authorizer compartido dentro de cada stage; los consumidores SQS, stream de asistencia y tareas programadas siguen incluidos.

La monitorización usa los nuevos nombres y el namespace `HCM/Unificado/EDA`. El monitor anterior conserva su comportamiento predeterminado para no alterar los stacks existentes.

## Migración pendiente

Esta configuración no importa ni mueve automáticamente recursos o datos existentes. No borra los stacks previos ni cambia Amplify. Ejecutar `serverless deploy --stage dev` crearía un ambiente nuevo con tablas vacías.

Antes de cambiar el frontend:

1. Desplegar el nuevo dev, copiar/verificar los datos que se quieran conservar y los objetos S3 correspondientes, y probar los siete módulos, permisos y eventos.
2. Mantener una única entrada de escritura durante la migración: no trabajar a la vez con los datos del dev anterior y el dev nuevo como si fueran la misma base.
3. Configurar el frontend para usar una sola URL base y publicar después de verificar el nuevo API. Las suscripciones de correo requieren su propia confirmación en el topic nuevo.
4. Desplegar prod con recursos y secreto propios; cargar solo sus datos autorizados.
5. Retirar la infraestructura antigua únicamente cuando la migración esté validada y exista respaldo. Las alarmas anteriores y las nuevas pertenecen a conjuntos de recursos diferentes.

Validar el empaquetado no equivale a un despliegue funcional ni a una migración de datos terminada.


## Resultado de preparación

Los paquetes de dev y prod se generaron correctamente. Cada plantilla contiene 68 Lambdas, una REST API y siete tablas, con 436 recursos de CloudFormation en total (límite de 500). Las pruebas verifican referencias y dependencias sin ciclos, handlers incluidos en los ZIPs, dependencias de JWT/SDK, límites de tamaño y separación de recursos y secretos entre ambientes. Los filtros de logs dependen de sus grupos de logs para evitar fallos por orden de creación.

Después de empaquetar ambos stages, repetir desde la raíz: `python3 -m unittest discover -s hcm/tests -v` (11 pruebas). La compatibilidad del monitor tiene otras siete pruebas en `monitorizacion/tests`.

[Evidencia de empaquetado](../docs/hcm_unificado_verificacion.json). Estado: **preparado, no desplegado**.
