import test from 'node:test';
import assert from 'node:assert/strict';
import { allowedPages, createApi, query } from '../src/api.js';

test('roles de empleado y reclutador no reciben navegación de administración', () => {
  assert.equal(allowedPages({ rol: 'empleado' }).includes('empleados'), false);
  assert.equal(allowedPages({ rol: 'empleado' }).includes('reclutamiento'), false);
  assert.equal(allowedPages({ rol: 'reclutador' }).includes('reclutamiento'), true);
  assert.equal(allowedPages({ rol: 'admin_rrhh' }).includes('empleados'), true);
});
test('query escapa tokens y omite campos vacíos', () => {
  assert.equal(query({ empleado: 'emp-1', next_token: 'a+b/=', empty: '' }), '?empleado=emp-1&next_token=a%2Bb%2F%3D');
});
test('peticiones autenticadas no se cachean ni mandan tenant desde el cliente', async t => {
  const calls = [];
  t.mock.method(globalThis, 'fetch', async (...args) => { calls.push(args); return new Response(JSON.stringify({ items: [] }), { headers: { 'Content-Type': 'application/json' } }); });
  await createApi('token-prueba')('empleados', '/empleados');
  assert.equal(calls[0][1].headers.Authorization, 'Bearer token-prueba');
  assert.equal(calls[0][1].cache, 'no-store');
  assert.equal(calls[0][0].includes('tenant_id'), false);
});
test('sesión expirada se comunica y no se oculta el error', async t => {
  let expired = false;
  t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify({ error: { mensaje: 'Sesión vencida' } }), { status: 401 }));
  await assert.rejects(createApi('token', () => { expired = true; })('nominas', '/nominas'), /Sesión vencida/);
  assert.equal(expired, true);
});
test('descarga rechaza respuestas que no sean PDF', async t => {
  t.mock.method(globalThis, 'fetch', async () => new Response('{}', { headers: { 'Content-Type': 'application/json' } }));
  await assert.rejects(createApi('token')('nominas', '/boleta', { pdf: true }), /no devolvió una boleta PDF/);
});
