"""Publica a mano un evento de prueba en el topic hcm-eventos (para probar los consumidores de ms-empleados).

  set TOPIC_ARN=arn:aws:sns:us-east-1:<cuenta>:hcm-eventos
  python -m scripts.publicar_evento PostulanteContratado --tenant andina --postulacion pos-004567
  python -m scripts.publicar_evento AusenciaAprobada --tenant andina --empleado emp-000045
  python -m scripts.publicar_evento AusenciaFinalizada --tenant andina --empleado emp-000045
"""
import argparse

from src.common.events import publish_event


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tipo", choices=["PostulanteContratado", "AusenciaAprobada", "AusenciaFinalizada"])
    ap.add_argument("--tenant", required=True)
    ap.add_argument("--postulacion", default="pos-004567")
    ap.add_argument("--empleado", default="emp-000045")
    ap.add_argument("--documento", default="71234567")
    ap.add_argument("--email", default="luis.ramos@mail.com")
    a = ap.parse_args()

    if a.tipo == "PostulanteContratado":
        datos = {"postulacion_id": a.postulacion, "nombres": "Luis", "apellidos": "Ramos", "email": a.email,
                 "documento": a.documento, "area": "Tecnología", "cargo": "Desarrollador Backend",
                 "jefe_id": "emp-000001", "salario_base": 4200.00, "fecha_ingreso": "2026-11-03"}
        origen = "ms-reclutamiento"
    else:
        datos = {"empleado_id": a.empleado, "tipo": "VACACIONES", "desde": "2026-12-20", "hasta": "2026-12-27"}
        origen = "ms-asistencia"
    print(publish_event(a.tipo, a.tenant, datos, origen=origen))


if __name__ == "__main__":
    main()
