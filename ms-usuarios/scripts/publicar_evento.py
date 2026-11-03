"""Publica a mano un evento de prueba en el topic hcm-eventos (criterio de la etapa 3).

  set TOPIC_ARN=arn:aws:sns:us-east-1:<cuenta>:hcm-eventos
  python -m scripts.publicar_evento EmpleadoCreado --tenant andina --empleado emp-010001
  python -m scripts.publicar_evento EmpleadoCesado --tenant andina --empleado emp-010001
"""
import argparse

from src.common.events import publish_event


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tipo", choices=["EmpleadoCreado", "EmpleadoCesado"])
    ap.add_argument("--tenant", required=True)
    ap.add_argument("--empleado", required=True, help="p. ej. emp-010001")
    ap.add_argument("--nombres", default="Prueba")
    ap.add_argument("--apellidos", default="Evento")
    ap.add_argument("--documento", default="12345678")
    ap.add_argument("--email")
    a = ap.parse_args()

    n = a.empleado.split("-")[-1]
    datos = {"empleado_id": a.empleado}
    if a.tipo == "EmpleadoCreado":
        datos.update(email=a.email or "prueba%s@%s.pe" % (n, a.tenant), nombres=a.nombres,
                     apellidos=a.apellidos, documento=a.documento)
    print(publish_event(a.tipo, a.tenant, datos, origen="ms-empleados"))


if __name__ == "__main__":
    main()
