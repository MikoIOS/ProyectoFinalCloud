'use strict';

/**
 * Consumidor SQS de eventos (cola suscrita a hcm-eventos).
 * Devuelve batchItemFailures: solo los mensajes que fallan se reintentan y,
 * tras 3 intentos, pasan a la DLQ.
 */
const { procesarEvento } = require('../services/eventos');

function parsear(body) {
  const data = JSON.parse(body);
  // SNS sin RawMessageDelivery envuelve el evento en { Message: "<json>" }.
  if (data && typeof data === 'object' && data.Message && !data.tipo_evento) {
    return JSON.parse(data.Message);
  }
  return data;
}

exports.handler = async (event) => {
  const fallos = [];
  for (const rec of event.Records || []) {
    try {
      const evt = parsear(rec.body);
      await procesarEvento(evt);
    } catch (err) {
      console.error('Fallo procesando mensaje', rec.messageId, err);
      fallos.push({ itemIdentifier: rec.messageId });
    }
  }
  return { batchItemFailures: fallos };
};
