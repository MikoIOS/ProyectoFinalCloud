"""Definición de la tabla hcm-empleados (la usan el seed y las pruebas).
En AWS la crea serverless.yml; mantener ambos iguales."""

# Atributos del listado resumido. Los GSIs de consulta los proyectan (INCLUDE) menos su propia clave.
RESUMEN = ["nombres", "apellidos", "email", "area", "cargo", "jefe_id", "estado", "fecha_ingreso"]


def _include(clave_propia):
    return {"ProjectionType": "INCLUDE", "NonKeyAttributes": [a for a in RESUMEN if a != clave_propia]}


def crear_tabla(dynamodb, nombre="hcm-empleados"):
    def gsi(nombre_idx, atributo, proyeccion):
        return {"IndexName": nombre_idx,
                "KeySchema": [{"AttributeName": "tenant_id", "KeyType": "HASH"},
                              {"AttributeName": atributo, "KeyType": "RANGE"}],
                "Projection": proyeccion}

    tabla = dynamodb.create_table(
        TableName=nombre,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[{"AttributeName": a, "AttributeType": "S"}
                              for a in ("tenant_id", "empleado_id", "area", "jefe_id", "estado", "documento")],
        KeySchema=[{"AttributeName": "tenant_id", "KeyType": "HASH"},
                   {"AttributeName": "empleado_id", "KeyType": "RANGE"}],
        GlobalSecondaryIndexes=[
            gsi("area-index", "area", _include("area")),
            gsi("jefe-index", "jefe_id", _include("jefe_id")),
            gsi("estado-index", "estado", _include("estado")),
            gsi("documento-index", "documento", {"ProjectionType": "KEYS_ONLY"}),
        ],
    )
    tabla.wait_until_exists()
    return tabla
