'use strict';

const { json, error } = require('../lib/response');
const svc = require('../services/notificaciones');

function contexto(event) {
  const auth = (event.requestContext && event.requestContext.authorizer) || {};
  return {
    tenant_id: auth.tenant_id,
    user_id: auth.user_id,
    rol: auth.rol,
  };
}

exports.ping = async () => json(200, { service: 'ms-notificaciones', status: 'ok' });

exports.listar = async (event) => {
  const { tenant_id, user_id, rol } = contexto(event);
  if (!tenant_id || !user_id) {
    return error(401, 'NO_AUTENTICADO', 'Token sin contexto de tenant/usuario');
  }

  const qs = event.queryStringParameters || {};
  let leida;
  if (qs.leida === 'true') leida = true;
  if (qs.leida === 'false') leida = false;

  const limit = Number.parseInt(qs.limit || '50', 10);
  const items = await svc.listar({
    tenant_id,
    user_id,
    rol,
    leida,
    limit: Number.isNaN(limit) ? 50 : limit,
  });

  const no_leidas = items.filter((i) => !i.leida).length;
  return json(200, { items, total: items.length, no_leidas });
};

exports.marcarLeida = async (event) => {
  const { tenant_id, user_id, rol } = contexto(event);
  if (!tenant_id || !user_id) {
    return error(401, 'NO_AUTENTICADO', 'Token sin contexto de tenant/usuario');
  }

  const id = event.pathParameters && event.pathParameters.id;
  if (!id) return error(400, 'VALIDACION', 'id requerido');

  const res = await svc.marcarLeida({
    tenant_id,
    user_id,
    rol,
    notificacion_id: id,
  });

  if (res.status === 404) return error(404, 'NO_ENCONTRADO', 'Notificación no encontrada');
  if (res.status === 403) return error(403, 'PROHIBIDO', 'La notificación no te pertenece');
  return json(200, res.item);
};
