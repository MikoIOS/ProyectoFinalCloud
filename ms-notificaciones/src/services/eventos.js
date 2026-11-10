'use strict';

const { PublishCommand } = require('@aws-sdk/client-sns');
const { construirDestinos, guardar } = require('./notificaciones');
const { sns } = require('../lib/sns');

const ASUNTOS_ASISTENCIA = {
  AusenciaSolicitada: 'Nueva solicitud de ausencia',
  AusenciaAprobada: 'Solicitud de ausencia aprobada',
  AusenciaFinalizada: 'Ausencia finalizada',
};

async function _avisarPorEmail({ tenant_id, tipo, destinatario_id, mensaje, email, datos }) {
  if (!process.env.EMAIL_TOPIC_ARN) return;
  const asunto = ASUNTOS_ASISTENCIA[tipo];
  await sns.send(new PublishCommand({
    TopicArn: process.env.EMAIL_TOPIC_ARN,
    Subject: `[HCM/${tenant_id}] ${asunto || tipo}`.slice(0, 99),
    Message: asunto ? [
      'Hola,',
      '',
      asunto + '.',
      '',
      `Empresa: ${tenant_id}`,
      `Empleado: ${datos.nombre_empleado || datos.empleado_id || 'Sin especificar'}`,
      `Tipo de ausencia: ${(datos.tipo || 'Sin especificar').replace(/_/g, ' ')}`,
      `Desde: ${datos.desde || 'Sin especificar'}`,
      `Hasta: ${datos.hasta || 'Sin especificar'}`,
      `Duración: ${datos.dias ?? 'Sin especificar'} día(s)`,
      '',
      'Si necesitas más información, comunícate con Recursos Humanos.',
      '',
      'Equipo HCM',
    ].join('\n') : JSON.stringify({
      tipo_evento: tipo,
      tenant_id,
      destinatario_id,
      mensaje,
      email: email || null,
    }, null, 2),
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
        datos,
      });
    }
  }

  return resultados;
}

module.exports = { procesarEvento };
