'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const consumer = require('../src/handlers/eventos');
const { procesarEvento } = require('../src/services/eventos');

test('procesarEvento valida estructura mínima requerida', async () => {
  await assert.rejects(
    async () => procesarEvento(null),
    { message: /Evento inválido/ }
  );

  await assert.rejects(
    async () => procesarEvento({}),
    { message: /Evento sin tipo_evento/ }
  );

  await assert.rejects(
    async () => procesarEvento({ tipo_evento: 'EmpleadoCreado' }),
    { message: /Evento sin tenant_id/ }
  );

  await assert.rejects(
    async () => procesarEvento({ tipo_evento: 'EmpleadoCreado', tenant_id: '   ' }),
    { message: /Evento sin tenant_id/ }
  );
});

test('SQS handler retorna batchItemFailures vacío cuando event.Records está vacío', async () => {
  const res = await consumer.handler({});
  assert.deepEqual(res, { batchItemFailures: [] });

  const res2 = await consumer.handler({ Records: [] });
  assert.deepEqual(res2, { batchItemFailures: [] });
});

test('SQS handler captura mensaje corrupto y reporta failure para DLQ sin caerse', async () => {
  const origErr = console.error;
  console.error = () => {}; // Silenciar log esperado de error

  try {
    const event = {
      Records: [
        {
          messageId: 'msg-corrupto-001',
          body: 'ESTO NO ES UN JSON VALIDO',
        },
      ],
    };

    const res = await consumer.handler(event);
    assert.equal(res.batchItemFailures.length, 1);
    assert.equal(res.batchItemFailures[0].itemIdentifier, 'msg-corrupto-001');
  } finally {
    console.error = origErr;
  }
});

test('SQS handler desempaqueta mensaje envuelto en envelope SNS correctamente', async () => {
  const origErr = console.error;
  console.error = () => {}; // Silenciar log esperado de error

  try {
    const event = {
      Records: [
        {
          messageId: 'msg-sns-envelope',
          body: JSON.stringify({
            Type: 'Notification',
            MessageId: 'sns-uuid-123',
            TopicArn: 'arn:aws:sns:us-east-1:123456789012:hcm-eventos',
            Message: JSON.stringify({
              // Evento sin tenant_id para forzar fallo controlado en procesarEvento
              tipo_evento: 'EmpleadoCreado',
            }),
          }),
        },
      ],
    };

    const res = await consumer.handler(event);
    // Al fallar la validación interna de procesarEvento (sin tenant_id), se aísla en batchItemFailures
    assert.equal(res.batchItemFailures.length, 1);
    assert.equal(res.batchItemFailures[0].itemIdentifier, 'msg-sns-envelope');
  } finally {
    console.error = origErr;
  }
});
