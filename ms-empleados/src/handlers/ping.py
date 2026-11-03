from src.common.response import api, ok


@api
def ping(event, context=None):
    return ok({"service": "ms-empleados", "status": "ok"})
