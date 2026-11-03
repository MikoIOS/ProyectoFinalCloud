"""Definición de la tabla hcm-usuarios (la usan el seed y las pruebas).
En AWS la crea serverless.yml; mantener ambos iguales."""


def crear_tabla(dynamodb, nombre="hcm-usuarios"):
    tabla = dynamodb.create_table(
        TableName=nombre,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "tenant_id", "AttributeType": "S"},
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "email", "AttributeType": "S"},
            {"AttributeName": "empleado_id", "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "tenant_id", "KeyType": "HASH"},
            {"AttributeName": "user_id", "KeyType": "RANGE"},
        ],
        GlobalSecondaryIndexes=[
            {"IndexName": "email-index",
             "KeySchema": [{"AttributeName": "tenant_id", "KeyType": "HASH"},
                           {"AttributeName": "email", "KeyType": "RANGE"}],
             "Projection": {"ProjectionType": "ALL"}},
            {"IndexName": "empleado-index",
             "KeySchema": [{"AttributeName": "tenant_id", "KeyType": "HASH"},
                           {"AttributeName": "empleado_id", "KeyType": "RANGE"}],
             "Projection": {"ProjectionType": "KEYS_ONLY"}},
        ],
    )
    tabla.wait_until_exists()
    return tabla
