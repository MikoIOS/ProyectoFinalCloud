"""Excepciones de negocio. El decorador @api las traduce a respuestas HTTP."""


class AppError(Exception):
    status = 500
    codigo = "ERROR_INTERNO"

    def __init__(self, mensaje="Error interno"):
        super().__init__(mensaje)
        self.mensaje = mensaje


class Validacion(AppError):
    status = 400
    codigo = "VALIDACION"


class NoAutenticado(AppError):
    status = 401
    codigo = "NO_AUTENTICADO"


class Prohibido(AppError):
    status = 403
    codigo = "PROHIBIDO"


class NoEncontrado(AppError):
    status = 404
    codigo = "NO_ENCONTRADO"


class Conflicto(AppError):
    status = 409
    codigo = "CONFLICTO"
