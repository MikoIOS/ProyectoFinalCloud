'use strict';
const assert = require('node:assert/strict');
const Module = require('node:module');
const path = require('node:path');
const directory = process.argv[2];
const routes = require(path.join(directory, 'hcm_routes.json'));
const response = { statusCode: 200, body: 'respuesta', headers: { test: 'sin modificar' } };
let called;
let reject = false;
const load = Module._load;
Module._load = function (request, ...args) {
  if (request === './src/handlers/http') return Object.fromEntries(['ping', 'listar', 'marcarLeida'].map(name => [name, async (event, context) => {
    called = { name, event, context };
    if (reject) throw new Error('fallo original');
    return response;
  }]));
  return load.call(this, request, ...args);
};

(async () => {
  const { handler } = require(path.join(directory, 'hcm_http.js'));
  for (const [key, route] of Object.entries(routes)) {
    const [httpMethod, resource] = key.split(' ');
    const event = { httpMethod, resource: '/' + resource, pathParameters: { id: 'not-1' },
      queryStringParameters: { leida: 'false' }, body: '{}',
      requestContext: { authorizer: { tenant_id: 'andina', user_id: 'usr-1', rol: 'empleado' } } };
    const before = structuredClone(event);
    const context = {};
    assert.equal(await handler(event, context), response);
    assert.equal(called.name, route.handler.split('.').at(-1));
    assert.equal(called.event, event);
    assert.equal(called.context, context);
    assert.deepEqual(event, before);
    called = null;
    if (route.protected) {
      for (const authorizer of [{}, { tenant_id: 'andina' }, { tenant_id: 'andina', user_id: 'usr-1', rol: '' }]) {
        assert.equal((await handler({ ...event, requestContext: { authorizer } })).statusCode, 401);
        assert.equal(called, null);
      }
    } else {
      assert.equal(await handler({ ...event, requestContext: {} }), response);
    }
    reject = true;
    await assert.rejects(handler(event), /fallo original/);
    reject = false;
  }
  assert.equal((await handler({ httpMethod: 'GET', resource: '/desconocida' })).statusCode, 404);
  assert.equal((await handler({})).statusCode, 404);
  console.log('OK: tres rutas Node, autenticación y errores originales');
})().catch(error => { console.error(error); process.exitCode = 1; });
