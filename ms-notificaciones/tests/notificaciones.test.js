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

test('La notificación conserva ausencia_id para consultar el flujo EDA', async () => {
  const { ddb } = require('../src/lib/db');
  const { guardar } = require('../src/services/notificaciones');
  const send = ddb.send;
  let item;
  ddb.send = async (command) => { item = command.input.Item; return {}; };
  try {
    await guardar({ tenant_id: 'andina', tipo: 'AusenciaAprobada', destinatario_id: 'usr-000002',
      mensaje: 'Prueba', datos: { ausencia_id: 'aus-prueba', empleado_id: 'emp-000002' } });
    assert.equal(item.metadata.ausencia_id, 'aus-prueba');
  } finally {
    ddb.send = send;
  }
});

test('Los correos de asistencia contienen mensajes legibles para cada estado', async () => {
  const { ddb } = require('../src/lib/db');
  const { sns } = require('../src/lib/sns');
  const { procesarEvento } = require('../src/services/eventos');
  const originalDdb = ddb.send;
  const originalSns = sns.send;
  const originalTopic = process.env.EMAIL_TOPIC_ARN;
  const enviados = [];
  ddb.send = async () => ({});
  sns.send = async (command) => { enviados.push(command.input); return {}; };
  process.env.EMAIL_TOPIC_ARN = 'arn:aws:sns:us-east-1:123456789012:email-test';
  try {
    for (const [tipo, titulo] of [
      ['AusenciaSolicitada', 'Nueva solicitud de ausencia'],
      ['AusenciaAprobada', 'Solicitud de ausencia aprobada'],
      ['AusenciaFinalizada', 'Ausencia finalizada'],
    ]) {
      await procesarEvento({ tipo_evento: tipo, tenant_id: 'andina', datos: {
        ausencia_id: 'aus-prueba', empleado_id: 'emp-000002', nombre_empleado: 'Miguel Espinoza',
        tipo: 'SIN_GOCE', desde: '2035-07-14', hasta: '2035-07-15', dias: 2,
      } });
      const email = enviados.at(-1);
      assert.equal(email.Subject, `[HCM/andina] ${titulo}`);
      assert.match(email.Message, /Hola,\n/);
      assert.match(email.Message, /Empleado: Miguel Espinoza/);
      assert.match(email.Message, /Tipo de ausencia: SIN GOCE/);
      assert.match(email.Message, /Desde: 2035-07-14/);
      assert.match(email.Message, /Hasta: 2035-07-15/);
      assert.match(email.Message, /Duración: 2 día\(s\)/);
      assert.throws(() => JSON.parse(email.Message));
    }
    await procesarEvento({ tipo_evento: 'AusenciaAprobada', tenant_id: 'andina',
      datos: { empleado_id: 'emp-000002' } });
    assert.match(enviados.at(-1).Message, /Empleado: emp-000002/);
    assert.match(enviados.at(-1).Message, /Desde: Sin especificar/);
    await procesarEvento({ tipo_evento: 'NominaGenerada', tenant_id: 'andina',
      datos: { empleado_id: 'emp-000002', periodo: '2026-11' } });
    assert.equal(JSON.parse(enviados.at(-1).Message).tipo_evento, 'NominaGenerada');
  } finally {
    ddb.send = originalDdb;
    sns.send = originalSns;
    if (originalTopic === undefined) delete process.env.EMAIL_TOPIC_ARN;
    else process.env.EMAIL_TOPIC_ARN = originalTopic;
  }
});
