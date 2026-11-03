'use strict';

process.env.AWS_REGION = process.env.AWS_REGION || 'us-east-1';
process.env.TABLE_NAME = process.env.TABLE_NAME || 'hcm-notificaciones-test';

const test = require('node:test');
const assert = require('node:assert/strict');
const { construirDestinos, idIdempotente } = require('../src/services/notificaciones');

test('EmpleadoCreado notifica al usuario derivado del empleado', () => {
  const destinos = construirDestinos('EmpleadoCreado', {
    empleado_id: 'emp-000045',
    nombres: 'María',
    apellidos: 'Quispe',
  });
  assert.equal(destinos.length, 1);
  assert.equal(destinos[0].destinatario_id, 'usr-000045');
  assert.match(destinos[0].mensaje, /María Quispe/);
});

test('PostulanteContratado avisa a RR.HH.', () => {
  const destinos = construirDestinos('PostulanteContratado', {
    postulacion_id: 'pos-1234',
    vacante_id: 'vac-5678',
    nombre: 'Ana Torres',
  });
  assert.equal(destinos.length, 1);
  assert.equal(destinos[0].destinatario_id, 'rol:admin_rrhh');
  assert.match(destinos[0].mensaje, /Ana Torres/);
});

test('EvaluacionCompletada notifica al empleado y al evaluador', () => {
  const destinos = construirDestinos('EvaluacionCompletada', {
    empleado_id: 'emp-000002',
    evaluador_id: 'emp-000001',
    periodo: '2026-Q4',
    puntaje: 4.8,
  });
  assert.deepEqual(destinos.map((d) => d.destinatario_id).sort(), ['usr-000001', 'usr-000002']);
});

test('Un evento desconocido no genera notificaciones', () => {
  assert.deepEqual(construirDestinos('EventoRaro', { empleado_id: 'emp-000001' }), []);
});

test('El id de idempotencia es estable y distinto por destinatario', () => {
  const datos = { empleado_id: 'emp-000001' };
  const a = idIdempotente('andina', 'EmpleadoCreado', 'usr-000001', datos, '2026-01-01T00:00:00Z');
  const b = idIdempotente('andina', 'EmpleadoCreado', 'usr-000001', datos, '2026-01-01T00:00:00Z');
  const c = idIdempotente('andina', 'EmpleadoCreado', 'rol:admin_rrhh', datos, '2026-01-01T00:00:00Z');
  assert.equal(a, b);
  assert.notEqual(a, c);
});
