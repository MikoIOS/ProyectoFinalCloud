import logging
import re
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation

from src.common import events, pagination
from src.common.errors import Conflicto, NoEncontrado, Prohibido, Validacion
from src.repositories import empleados_repo as repo

log = logging.getLogger()

ESTADOS = ("ACTIVO", "VACACIONES", "CESADO")
TRANSICIONES = {"ACTIVO": {"VACACIONES", "CESADO"}, "VACACIONES": {"ACTIVO", "CESADO"}, "CESADO": set()}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DOC_RE = re.compile(r"^\d{8}$")

RESUMEN = ("empleado_id", "nombres", "apellidos", "email", "area", "cargo", "jefe_id", "estado", "fecha_ingreso")
SOLO_ADMIN_Y_PROPIO = ("salario_base", "documento", "telefono", "direccion", "contacto_emergencia")
EDITABLES = {"nombres", "apellidos", "documento", "email", "area", "cargo", "jefe_id",
             "fecha_ingreso", "salario_base", "telefono", "direccion", "contacto_emergencia"}
CONTACTO = {"telefono", "direccion", "contacto_emergencia"}


# ---------------------------------------------------------------- validaciones
def _texto(v, campo, max_len=120):
    if not isinstance(v, str) or not v.strip():
        raise Validacion("%s es obligatorio" % campo)
    v = v.strip()
    if len(v) > max_len:
        raise Validacion("%s es demasiado largo (máx. %d)" % (campo, max_len))
    return v


def _fecha(v, campo):
    try:
        return date.fromisoformat(_texto(v, campo, 10)).isoformat()
    except ValueError:
        raise Validacion("%s debe tener formato AAAA-MM-DD" % campo)


def _salario(v):
    if isinstance(v, bool) or not isinstance(v, (int, float, str, Decimal)):
        raise Validacion("salario_base debe ser un número")
    try:
        d = Decimal(str(v))
    except InvalidOperation:
        raise Validacion("salario_base debe ser un número")
    if not d.is_finite() or d <= 0 or d > 1_000_000:
        raise Validacion("salario_base debe ser mayor que 0 y razonable")
    return d.quantize(Decimal("0.01"))


def _validar_campo(campo, valor):
    if campo in ("nombres", "apellidos", "area", "cargo"):
        return _texto(valor, campo)
    if campo == "documento":
        v = _texto(valor, campo, 8)
        if not DOC_RE.match(v):
            raise Validacion("documento debe tener 8 dígitos")
        return v
    if campo == "email":
        v = _texto(valor, campo, 150).lower()
        if not EMAIL_RE.match(v):
            raise Validacion("email inválido")
        return v
    if campo == "fecha_ingreso":
        return _fecha(valor, campo)
    if campo == "salario_base":
        return _salario(valor)
    if campo in CONTACTO:
        return _texto(valor, campo, 200)
    raise Validacion("Campo no permitido: %s" % campo)


def _validar_jefe(tenant_id, jefe_id, empleado_id=None):
    jefe_id = _texto(jefe_id, "jefe_id", 40)
    if empleado_id and jefe_id == empleado_id:
        raise Validacion("Un empleado no puede ser su propio jefe")
    jefe = repo.get(tenant_id, jefe_id)
    if not jefe:
        raise Validacion("jefe_id no existe en este tenant")
    if jefe["estado"] == "CESADO":
        raise Validacion("El jefe indicado está cesado")
    if empleado_id:  # evitar ciclos: subir por la cadena de jefes
        actual, saltos = jefe, 0
        while actual.get("jefe_id") and saltos < 50:
            if actual["jefe_id"] == empleado_id:
                raise Validacion("Ese jefe es subordinado (directo o indirecto) del empleado: crearía un ciclo")
            actual = repo.get(tenant_id, actual["jefe_id"]) or {}
            saltos += 1
    return jefe_id


# ---------------------------------------------------------------- vistas por rol
def resumido(item):
    return {k: item[k] for k in RESUMEN if k in item}


def vista(item, ctx):
    """Ficha según quién mira: admin y el propio empleado ven todo; el gerente no ve datos sensibles."""
    if ctx.rol == "admin_rrhh" or item["empleado_id"] == ctx.empleado_id:
        return item
    return {k: v for k, v in item.items() if k not in SOLO_ADMIN_Y_PROPIO}


# ---------------------------------------------------------------- creación (HTTP y evento)
def datos_evento_creado(item):
    d = {k: item[k] for k in ("empleado_id", "email", "nombres", "apellidos", "documento",
                              "area", "cargo", "fecha_ingreso") if k in item}
    if item.get("jefe_id"):
        d["jefe_id"] = item["jefe_id"]
    d["salario_base"] = item["salario_base"]
    return d


def construir_y_guardar(tenant_id, body, empleado_id=None):
    """Valida y guarda un empleado. Devuelve (item, creado). Si `empleado_id` viene dado (alta por evento) y
    ya existe, devuelve (item_existente, False) para que la operación sea idempotente."""
    faltan = [c for c in ("nombres", "apellidos", "documento", "email", "area", "cargo", "fecha_ingreso", "salario_base")
              if body.get(c) in (None, "")]
    if faltan:
        raise Validacion("Faltan campos obligatorios: %s" % ", ".join(faltan))
    item = {c: _validar_campo(c, body[c]) for c in
            ("nombres", "apellidos", "documento", "email", "area", "cargo", "fecha_ingreso", "salario_base")}
    for c in CONTACTO:
        if body.get(c) not in (None, ""):
            item[c] = _validar_campo(c, body[c])

    existente_doc = repo.get_id_por_documento(tenant_id, item["documento"])
    if existente_doc:
        if empleado_id and existente_doc == empleado_id:
            return repo.get(tenant_id, empleado_id), False
        raise Conflicto("Ya existe un empleado con ese documento en este tenant")

    if body.get("jefe_id") not in (None, ""):
        item["jefe_id"] = _validar_jefe(tenant_id, body["jefe_id"])

    item.update({"tenant_id": tenant_id,  # del token o del evento, nunca del body
                 "empleado_id": empleado_id or "emp-" + uuid.uuid4().hex[:8],
                 "estado": "ACTIVO"})
    try:
        return repo.put_new(item), True
    except Conflicto:
        if empleado_id:  # alta por evento ya procesada (carrera entre entregas duplicadas)
            return repo.get(tenant_id, empleado_id), False
        raise


def crear(ctx, body):
    item, _ = construir_y_guardar(ctx.tenant_id, body)
    respuesta = dict(item)
    try:
        events.publish_event("EmpleadoCreado", ctx.tenant_id, datos_evento_creado(item), origen="ms-empleados")
    except Exception:  # noqa: BLE001
        log.exception("No se pudo publicar EmpleadoCreado de %s", item["empleado_id"])
        respuesta["aviso"] = "Empleado creado, pero el evento EmpleadoCreado no se pudo publicar"
    return respuesta


# ---------------------------------------------------------------- consultas
def _paginado(items, last):
    return {"items": [resumido(i) for i in items], "next_token": pagination.encode_token(last)}


def listar(ctx, qs):
    qs = qs or {}
    limit = pagination.parse_limit(qs)
    start = pagination.decode_token(qs.get("next_token"), ctx.tenant_id)
    area = (qs.get("area") or "").strip() or None
    estado = qs.get("estado") or None
    if estado and estado not in ESTADOS:
        raise Validacion("estado inválido; valores: %s" % ", ".join(ESTADOS))
    if area:
        items, last = repo.consultar(ctx.tenant_id, limit, start, "area-index", area, estado)
    elif estado:
        items, last = repo.consultar(ctx.tenant_id, limit, start, "estado-index", estado)
    else:
        items, last = repo.consultar(ctx.tenant_id, limit, start)
    return _paginado(items, last)


def obtener(ctx, empleado_id):
    if ctx.rol not in ("admin_rrhh", "gerente") and empleado_id != ctx.empleado_id:
        raise Prohibido("Solo puedes consultar tu propia ficha")
    item = repo.get(ctx.tenant_id, empleado_id)
    if not item:
        raise NoEncontrado("Empleado no encontrado")
    return vista(item, ctx)


def mi_ficha(ctx):
    if not ctx.empleado_id:
        raise NoEncontrado("Tu usuario no está vinculado a un empleado")
    item = repo.get(ctx.tenant_id, ctx.empleado_id)
    if not item:
        raise NoEncontrado("Empleado no encontrado")
    return item


def resumen(ctx):
    por_estado = {e: 0 for e in ESTADOS}
    por_area, total = {}, 0
    for it in repo.recorrer_area_estado(ctx.tenant_id):
        total += 1
        por_estado[it["estado"]] = por_estado.get(it["estado"], 0) + 1
        por_area[it["area"]] = por_area.get(it["area"], 0) + 1
    return {"total": total, "por_estado": por_estado, "por_area": dict(sorted(por_area.items()))}


def organigrama(ctx, qs):
    qs = qs or {}
    area, jefe_id = (qs.get("area") or "").strip(), (qs.get("jefe_id") or "").strip()
    if bool(area) == bool(jefe_id):
        raise Validacion("Indica area o jefe_id (solo uno)")
    limit = pagination.parse_limit(qs)
    start = pagination.decode_token(qs.get("next_token"), ctx.tenant_id)

    if jefe_id:
        jefe = repo.get(ctx.tenant_id, jefe_id)
        if not jefe:
            raise NoEncontrado("Jefe no encontrado")
        items, last = repo.consultar(ctx.tenant_id, limit, start, "jefe-index", jefe_id)
        return {"jefe": resumido(jefe), "subordinados": [resumido(i) for i in items],
                "next_token": pagination.encode_token(last)}

    items, last = repo.consultar(ctx.tenant_id, limit, start, "area-index", area)
    grupos = {}
    for it in items:
        grupos.setdefault(it.get("jefe_id"), []).append(resumido(it))
    return {"area": area,
            "grupos": [{"jefe_id": j, "empleados": e} for j, e in sorted(grupos.items(), key=lambda kv: kv[0] or "")],
            "next_token": pagination.encode_token(last)}


# ---------------------------------------------------------------- modificaciones
def actualizar(ctx, empleado_id, body):
    if not body:
        raise Validacion("Nada que actualizar")
    extra = set(body) - EDITABLES
    if extra:
        raise Validacion("Campos no editables aquí: %s" % ", ".join(sorted(extra)))
    actual = repo.get(ctx.tenant_id, empleado_id)
    if not actual:
        raise NoEncontrado("Empleado no encontrado")
    if actual["estado"] == "CESADO":
        raise Conflicto("No se puede modificar un empleado cesado")

    cambios, remover = {}, []
    for campo, valor in body.items():
        if campo == "jefe_id":
            if valor in (None, ""):
                remover.append("jefe_id")
            else:
                cambios["jefe_id"] = _validar_jefe(ctx.tenant_id, valor, empleado_id)
        else:
            cambios[campo] = _validar_campo(campo, valor)
    if "documento" in cambios and cambios["documento"] != actual["documento"]:
        otro = repo.get_id_por_documento(ctx.tenant_id, cambios["documento"])
        if otro and otro != empleado_id:
            raise Conflicto("Ya existe un empleado con ese documento en este tenant")
    return repo.update(ctx.tenant_id, empleado_id, cambios, remover)


def cambiar_estado(ctx, empleado_id, body):
    nuevo = body.get("estado")
    if nuevo not in ESTADOS:
        raise Validacion("estado inválido; valores: %s" % ", ".join(ESTADOS))
    actual = repo.get(ctx.tenant_id, empleado_id)
    if not actual:
        raise NoEncontrado("Empleado no encontrado")
    if nuevo not in TRANSICIONES[actual["estado"]]:
        raise Conflicto("Transición no permitida: %s → %s" % (actual["estado"], nuevo))

    cambios, fecha_cese = {"estado": nuevo}, None
    if nuevo == "CESADO":
        if empleado_id == ctx.empleado_id:
            raise Prohibido("No puedes cesarte a ti mismo")
        fecha_cese = _fecha(body.get("fecha_cese"), "fecha_cese")
        if fecha_cese < actual["fecha_ingreso"]:
            raise Validacion("fecha_cese no puede ser anterior a fecha_ingreso")
        cambios["fecha_cese"] = fecha_cese
        if body.get("motivo"):
            cambios["motivo_cese"] = _texto(body["motivo"], "motivo", 200)
    item = repo.update(ctx.tenant_id, empleado_id, cambios, estado_actual=actual["estado"])

    respuesta = dict(item)
    if nuevo == "CESADO":
        datos = {"empleado_id": empleado_id, "fecha_cese": fecha_cese}
        if cambios.get("motivo_cese"):
            datos["motivo"] = cambios["motivo_cese"]
        try:
            events.publish_event("EmpleadoCesado", ctx.tenant_id, datos, origen="ms-empleados")
        except Exception:  # noqa: BLE001
            log.exception("No se pudo publicar EmpleadoCesado de %s", empleado_id)
            respuesta["aviso"] = "Empleado cesado, pero el evento EmpleadoCesado no se pudo publicar"
    return respuesta


def actualizar_mi_contacto(ctx, body):
    if not ctx.empleado_id:
        raise NoEncontrado("Tu usuario no está vinculado a un empleado")
    if not body:
        raise Validacion("Nada que actualizar")
    extra = set(body) - CONTACTO
    if extra:
        raise Validacion("Solo puedes editar: %s. No permitido: %s"
                         % (", ".join(sorted(CONTACTO)), ", ".join(sorted(extra))))
    cambios = {c: _validar_campo(c, v) for c, v in body.items()}
    return repo.update(ctx.tenant_id, ctx.empleado_id, cambios)
