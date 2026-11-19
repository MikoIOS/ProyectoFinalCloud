'use strict';
const assert = require('node:assert/strict');
const path = require('node:path');
const root = process.argv[2];
const { ddb } = require(path.join(root, 'src/lib/db.js'));
const queries = [];
let updates = 0;
ddb.send = async command => {
  const input = command.input;
  if (command.constructor.name === 'QueryCommand') {
    queries.push(input.ExpressionAttributeValues[':t']);
    return { Items: [] };
  }
  if (command.constructor.name === 'GetCommand') {
    return { Item: input.Key.tenant_id === 'andina'
      ? { tenant_id: 'andina', notificacion_id: 'not-1', destinatario_id: 'usr-1' } : undefined };
  }
  if (command.constructor.name === 'UpdateCommand') {
    updates++;
    assert.equal(input.Key.tenant_id, 'andina');
    return { Attributes: { leida: true } };
  }
  throw new Error('Operación inesperada: ' + command.constructor.name);
};

(async () => {
  const { handler } = require(path.join(root, 'hcm_http.js'));
  assert.equal((await handler({ httpMethod: 'GET', resource: '/notificaciones/ping' })).statusCode, 200);
  const event = { httpMethod: 'GET', resource: '/notificaciones',
    requestContext: { authorizer: { tenant_id: 'andina', user_id: 'usr-1', rol: 'empleado' } },
    body: '{"tenant_id":"pacifico"}' };
  assert.equal((await handler(event)).statusCode, 200);
  assert(queries.length > 0 && queries.every(tenant => tenant === 'andina'));
  event.httpMethod = 'PATCH';
  event.resource = '/notificaciones/{id}/leida';
  event.pathParameters = { id: 'not-1' };
  assert.equal(JSON.parse((await handler(event)).body).leida, true);
  event.requestContext.authorizer.tenant_id = 'pacifico';
  assert.equal((await handler(event)).statusCode, 404);
  assert.equal(updates, 1);
  const worker = require(path.join(root, 'src/handlers/eventos.js')).handler;
  assert.deepEqual(await worker({ Records: [] }), { batchItemFailures: [] });
  assert.deepEqual(await worker({ Records: [{ messageId: 'm-1', body: 'no-json' }] }),
    { batchItemFailures: [{ itemIdentifier: 'm-1' }] });
  console.log('OK: handlers reales de notificaciones, lectura y aislamiento con DynamoDB simulado');
})().catch(error => { console.error(error); process.exitCode = 1; });
