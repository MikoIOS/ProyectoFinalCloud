'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('../src/handlers/http');
const svc = require('../src/services/notificaciones');

test('GET /ping responde 200 con estado ok y cabeceras CORS', async () => {
  const res = await http.ping();
  assert.equal(res.statusCode, 200);
  assert.equal(res.headers['Content-Type'], 'application/json');
  assert.equal(res.headers['Access-Control-Allow-Origin'], '*');

  const body = JSON.parse(res.body);
  assert.equal(body.service, 'ms-notificaciones');
  assert.equal(body.status, 'ok');
});

test('GET /notificaciones rechaza 401 si falta autorización', async () => {
  const eventosSinAuth = [
    {},
    { requestContext: {} },
    { requestContext: { authorizer: {} } },
    { requestContext: { authorizer: { tenant_id: 'andina' } } }, // falta user_id
    { requestContext: { authorizer: { user_id: 'usr-000001' } } }, // falta tenant_id
  ];

  for (const evt of eventosSinAuth) {
    const res = await http.listar(evt);
    assert.equal(res.statusCode, 401);
    const body = JSON.parse(res.body);
    assert.equal(body.error.codigo, 'NO_AUTENTICADO');
  }
});

test('GET /notificaciones retorna 200 con items y conteo de no_leidas', async () => {
  const originalListar = svc.listar;
  svc.listar = async ({ tenant_id, user_id }) => {
    assert.equal(tenant_id, 'andina');
    assert.equal(user_id, 'usr-000045');
    return [
      { notificacion_id: 'not-1', leida: false, mensaje: 'Aviso 1' },
      { notificacion_id: 'not-2', leida: true, mensaje: 'Aviso 2' },
      { notificacion_id: 'not-3', leida: false, mensaje: 'Aviso 3' },
    ];
  };

  try {
    const event = {
      requestContext: {
        authorizer: { tenant_id: 'andina', user_id: 'usr-000045', rol: 'empleado' },
      },
    };

    const res = await http.listar(event);
    assert.equal(res.statusCode, 200);
    const body = JSON.parse(res.body);
    assert.equal(body.total, 3);
    assert.equal(body.no_leidas, 2);
    assert.equal(body.items.length, 3);
  } finally {
    svc.listar = originalListar;
  }
});

test('GET /notificaciones interpreta correctamente querystring params', async () => {
  const originalListar = svc.listar;
  let paramsCapturados = null;
  svc.listar = async (params) => {
    paramsCapturados = params;
    return [];
  };

  try {
    const event = {
      requestContext: {
        authorizer: { tenant_id: 'pacifico', user_id: 'usr-000002', rol: 'admin_rrhh' },
      },
      queryStringParameters: {
        leida: 'false',
        limit: '15',
      },
    };

    const res = await http.listar(event);
    assert.equal(res.statusCode, 200);
    assert.equal(paramsCapturados.leida, false);
    assert.equal(paramsCapturados.limit, 15);
  } finally {
    svc.listar = originalListar;
  }
});

test('PATCH /notificaciones/:id rechaza 401 si no está autenticado', async () => {
  const res = await http.marcarLeida({ pathParameters: { id: 'not-123' } });
  assert.equal(res.statusCode, 401);
});

test('PATCH /notificaciones/:id rechaza 400 si falta el parámetro id en la URL', async () => {
  const event = {
    requestContext: {
      authorizer: { tenant_id: 'andina', user_id: 'usr-000001', rol: 'admin' },
    },
    pathParameters: null,
  };
  const res = await http.marcarLeida(event);
  assert.equal(res.statusCode, 400);
  const body = JSON.parse(res.body);
  assert.equal(body.error.codigo, 'VALIDACION');
});

test('PATCH /notificaciones/:id maneja códigos 404, 403 y 200 según respuesta del servicio', async () => {
  const originalMarcar = svc.marcarLeida;

  try {
    const event = {
      requestContext: {
        authorizer: { tenant_id: 'andina', user_id: 'usr-000001', rol: 'empleado' },
      },
      pathParameters: { id: 'not-999' },
    };

    // Caso 404: Notificación inexistente
    svc.marcarLeida = async () => ({ status: 404 });
    const res404 = await http.marcarLeida(event);
    assert.equal(res404.statusCode, 404);

    // Caso 403: No le pertenece al usuario
    svc.marcarLeida = async () => ({ status: 403 });
    const res403 = await http.marcarLeida(event);
    assert.equal(res403.statusCode, 403);

    // Caso 200: Éxito
    svc.marcarLeida = async () => ({
      status: 200,
      item: { notificacion_id: 'not-999', leida: true },
    });
    const res200 = await http.marcarLeida(event);
    assert.equal(res200.statusCode, 200);
    const body200 = JSON.parse(res200.body);
    assert.equal(body200.leida, true);
  } finally {
    svc.marcarLeida = originalMarcar;
  }
});

