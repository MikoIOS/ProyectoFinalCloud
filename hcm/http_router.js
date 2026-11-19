'use strict';

const routes = require('./hcm_routes.json');

function error(statusCode, codigo, mensaje) {
  return { statusCode, headers: {
    'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*',
  }, body: JSON.stringify({ error: { codigo, mensaje } }) };
}

exports.handler = async (event, context) => {
  const method = event.httpMethod;
  const resource = event.resource;
  const route = typeof method === 'string' && typeof resource === 'string'
    ? routes[method.toUpperCase() + ' ' + resource.replace(/^\/+|\/+$/g, '')] : null;
  if (!route) return error(404, 'NO_ENCONTRADO', 'Ruta no encontrada');
  if (route.protected) {
    const auth = event.requestContext?.authorizer || {};
    if (!['tenant_id', 'user_id', 'rol'].every(key => typeof auth[key] === 'string' && auth[key].trim())) {
      return error(401, 'NO_AUTENTICADO', 'Sin contexto de autenticación');
    }
  }
  const split = route.handler.lastIndexOf('.');
  return require('./' + route.handler.slice(0, split))[route.handler.slice(split + 1)](event, context);
};
