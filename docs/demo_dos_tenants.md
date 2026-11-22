# Demo HTTP con dos tenants (dev)

Ejecutar desde la raíz del repositorio con Python 3 y curl:

```bash
python3 scripts/demo_dos_tenants.py
```

Usa exclusivamente `https://mwxvk1jpd3.execute-api.us-east-1.amazonaws.com/dev`.
Cada ejecución crea dos empresas ficticias distintas, un administrador y un empleado
por empresa. No modifica Andina/Pacífico de producción. Los RUC y documentos son
ficticios y los correos `example.invalid` no reciben mensajes.

El script recorre por curl: registro y login; vacante y contratación; creación
asíncrona de empleado y usuario; cambio de contraseña inicial; solicitud y aprobación
de dos días sin goce; espera del descuento automático; bono 100 y descuento 50;
planilla del próximo mes (neto esperado 2486); descarga de PDF; evaluación completada;
notificaciones de bienvenida, ausencia, nómina y evaluación.

Comprueba en ambos sentidos el rechazo de acceso a empleado, usuario, ausencia,
nómina y lectura de notificación de la otra empresa; los listados de evaluaciones y
postulaciones cruzados deben estar vacíos. Comprueba acceso anónimo y token inválido.
Estos controles se hacen en HTTP. No demuestran por sí solos la salud de cada cola,
la ausencia de mensajes en DLQ, el cifrado de S3 ni entrega de correo.

Al terminar imprime el directorio `hcm/.runtime/demo-<id>/` que contiene:

- `cuentas.json`: credenciales de ambos administradores y empleados, tenant IDs,
  periodo, identificadores y tokens privados. Permisos 600; ignorado por Git.
- `boleta-andina-demo.pdf` y `boleta-pacifico-demo.pdf`.
- `resultado.json`: `APROBADO` únicamente si todos los controles terminan bien.

En el frontend **compilado para dev** (`VITE_API_URL` igual a la URL anterior),
iniciar sesión con `admin_email`/`admin_password` de cada empresa, preferiblemente
en dos perfiles de navegador. Para mostrar la vista empleado usar
`empleado_email`/`empleado_password`. El frontend productivo apunta a prod y no
puede autenticar estas cuentas de dev.

Si falla, conserva las cuentas parciales y el resultado. No publica éxito, no
reintenta escrituras automáticamente y no borra datos de la ejecución. Una nueva
ejecución crea otras empresas. No subir `cuentas.json` ni tokens al informe o Git.

## Estado de esta preparación

Las pruebas locales del transporte y controles están en `scripts/test_demo_dos_tenants.py`.
El intento del 22-Nov-2026 desde el agente falló en el primer GET `/ping` con
`curl: (6) Could not resolve host`; no se crearon cuentas ni se aprobó el ciclo real.
Ejecutar desde la terminal que tiene conectividad y conservar su resultado.
