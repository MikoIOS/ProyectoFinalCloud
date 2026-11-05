'use strict';

const { PublishCommand } = require('@aws-sdk/client-sns');
const { construirDestinos, guardar } = require('./notificaciones');
const { sns } = require('../lib/sns');

async function _avisarPorEmail({ tenant_id, tipo, destinatario_id, mensaje, email }) {
  if (!process.env.EMAIL_TOPIC_ARN) return;
  const texto = [
    `=== NOTIFICACIÓN HCM [${tenant_id.toUpperCase()}] ===`,
    `Evento:       ${tipo}`,
    `Destinatario: ${destinatario_id}`,
    email ? `Correo:       ${email}` : null,
    `Fecha:        ${new Date().toISOString()}`,
    ``,
    `Mensaje:`,
    `${mensaje}`,
    ``,
    `----------------------------------------------------`,
    `SaaS HCM — Notificación del Sistema Cloud`,
  ].filter(Boolean).join('\n');

  await sns.send(new PublishCommand({
    TopicArn: process.env.EMAIL_TOPIC_ARN,
    Subject: `[HCM/${tenant_id}] ${tipo}`.slice(0, 99),
    Message: texto,
    MessageAttributes: {
      tipo_evento: { DataType: 'String', StringValue: tipo },
      tenant_id: { DataType: 'String', StringValue: tenant_id },
    },
  }));
}

/**
 * Procesa un evento del catálogo hcm-eventos. Es idempotente: un evento
 * repetido no duplica notificaciones (id determinista + condición).
 */
async function procesarEvento(evt) {
  if (!evt || typeof evt !== 'object') throw new Error('Evento inválido');

  const tipo = evt.tipo_evento;
  const tenantId = evt.tenant_id;
  if (!tipo) throw new Error('Evento sin tipo_evento');
  if (typeof tenantId !== 'string' || !tenantId.trim()) throw new Error('Evento sin tenant_id');

  const datos = evt.datos || {};
  const destinos = construirDestinos(tipo, datos);
  const resultados = [];

  for (const destino of destinos) {
    const res = await guardar({
      tenant_id: tenantId.trim(),
      tipo,
      destinatario_id: destino.destinatario_id,
      mensaje: destino.mensaje,
      datos,
      timestamp: evt.timestamp,
      email: datos.email,
    });
    resultados.push({ destinatario_id: destino.destinatario_id, creada: res.creada });

    if (res.creada) {
      await _avisarPorEmail({
        tenant_id: tenantId.trim(),
        tipo,
        destinatario_id: destino.destinatario_id,
        mensaje: destino.mensaje,
        email: datos.email,
      });
    }
  }

  return resultados;
}

module.exports = { procesarEvento };
