'use strict';

const crypto = require('crypto');
const {
  QueryCommand,
  GetCommand,
  UpdateCommand,
  PutCommand,
} = require('@aws-sdk/lib-dynamodb');
const { ddb, TABLE } = require('../lib/db');

const DESTINATARIO_RRHH = 'rol:admin_rrhh';

function usrDeEmpleado(value) {
  if (typeof value !== 'string' || !value.startsWith('emp-')) return null;
  return 'usr-' + value.slice(4);
}

/**
 * Traduce un evento del catálogo hcm-eventos a una o más notificaciones.
 * No toca la base de datos: es pura y fácil de testear.
 */
function construirDestinos(tipo, datos) {
  const d = datos || {};
  const empleado = usrDeEmpleado(d.empleado_id);

  switch (tipo) {
    case 'PostulanteContratado':
      return [{
        destinatario_id: DESTINATARIO_RRHH,
        mensaje: `Se contrató a ${d.nombre || 'un candidato'}${d.vacante_id ? ` para la vacante ${d.vacante_id}` : ''}.`,
      }];
    case 'EmpleadoCreado': {
      if (!empleado) return [];
      const nombre = [d.nombres, d.apellidos].filter(Boolean).join(' ') || 'al equipo';
      return [{ destinatario_id: empleado, mensaje: `Bienvenido/a ${nombre}. Tu cuenta fue creada.` }];
    }
    case 'EmpleadoCesado':
      return empleado ? [{ destinatario_id: empleado, mensaje: 'Tu cuenta fue desactivada por cese.' }] : [];
    case 'AusenciaSolicitada':
      return [{
        destinatario_id: DESTINATARIO_RRHH,
        mensaje: `Nueva solicitud de ausencia${d.tipo ? ` (${d.tipo})` : ''}${d.empleado_id ? ` de ${d.empleado_id}` : ''}.`,
      }];
    case 'AusenciaAprobada':
      return empleado
        ? [{ destinatario_id: empleado, mensaje: `Tu ausencia${d.tipo ? ` de tipo ${d.tipo}` : ''} fue aprobada.` }]
        : [];
    case 'AusenciaFinalizada':
      return empleado ? [{ destinatario_id: empleado, mensaje: 'Tu ausencia finalizó.' }] : [];
    case 'NominaGenerada':
      return empleado
        ? [{ destinatario_id: empleado, mensaje: `Tu boleta${d.periodo ? ` del periodo ${d.periodo}` : ''} está disponible.` }]
        : [];
    case 'EvaluacionCompletada': {
      const destinos = [];
      if (empleado) {
        destinos.push({
          destinatario_id: empleado,
          mensaje: `Se completó tu evaluación${d.periodo ? ` del periodo ${d.periodo}` : ''}${d.puntaje != null ? ` con puntaje ${d.puntaje}` : ''}.`,
        });
      }
      const evaluador = usrDeEmpleado(d.evaluador_id);
      if (evaluador && evaluador !== empleado) {
        destinos.push({
          destinatario_id: evaluador,
          mensaje: `Registraste la evaluación de ${d.empleado_id}${d.periodo ? ` (${d.periodo})` : ''}.`,
        });
      }
      return destinos;
    }
    default:
      return [];
  }
}

/** Id determinista a partir del evento: SQS entrega "al menos una vez". */
function idIdempotente(tenantId, tipo, destinatarioId, datos, timestamp) {
  const d = datos || {};
  const base = [
    tenantId, tipo, destinatarioId, timestamp || '',
    d.empleado_id || '', d.postulacion_id || '', d.evaluacion_id || '',
    d.periodo || '', d.nomina_id || '',
  ].join('|');
  return 'not-' + crypto.createHash('sha1').update(base).digest('hex').slice(0, 12);
}

function _limpio(obj) {
  return Object.fromEntries(Object.entries(obj).filter(([, v]) => v !== undefined && v !== null));
}

async function guardar({ tenant_id, tipo, destinatario_id, mensaje, datos, timestamp, email }) {
  const d = datos || {};
  const item = _limpio({
    tenant_id,
    notificacion_id: idIdempotente(tenant_id, tipo, destinatario_id, d, timestamp),
    destinatario_id,
    tipo,
    mensaje,
    leida: false,
    created_at: timestamp || new Date().toISOString(),
    email,
    metadata: _limpio({
      empleado_id: d.empleado_id,
      ausencia_id: d.ausencia_id,
      postulacion_id: d.postulacion_id,
      vacante_id: d.vacante_id,
      evaluacion_id: d.evaluacion_id,
      periodo: d.periodo,
    }),
  });

  try {
    await ddb.send(new PutCommand({
      TableName: TABLE,
      Item: item,
      ConditionExpression: 'attribute_not_exists(notificacion_id)',
    }));
    return { creada: true, item };
  } catch (err) {
    if (err && err.name === 'ConditionalCheckFailedException') {
      return { creada: false, item };
    }
    throw err;
  }
}

async function listar({ tenant_id, user_id, rol, leida, limit = 50 }) {
  const destinatarios = [user_id];
  if (rol) destinatarios.push('rol:' + rol);

  const acumulado = [];
  for (const destinatario of destinatarios) {
    let ExclusiveStartKey;
    do {
      const res = await ddb.send(new QueryCommand({
        TableName: TABLE,
        IndexName: 'destinatario-index',
        KeyConditionExpression: 'tenant_id = :t AND destinatario_id = :d',
        ExpressionAttributeValues: { ':t': tenant_id, ':d': destinatario },
        Limit: 100,
        ExclusiveStartKey,
      }));
      acumulado.push(...(res.Items || []));
      ExclusiveStartKey = res.LastEvaluatedKey;
    } while (ExclusiveStartKey && acumulado.length < 500);
  }

  const unicos = [...new Map(acumulado.map((n) => [n.notificacion_id, n])).values()];
  const filtrados = typeof leida === 'boolean' ? unicos.filter((n) => n.leida === leida) : unicos;
  filtrados.sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
  const max = Math.min(Math.max(Number(limit) || 50, 1), 200);
  return filtrados.slice(0, max);
}

async function marcarLeida({ tenant_id, user_id, rol, notificacion_id }) {
  const res = await ddb.send(new GetCommand({
    TableName: TABLE,
    Key: { tenant_id, notificacion_id },
  }));
  const item = res.Item;
  if (!item) return { status: 404 };

  const propio = item.destinatario_id === user_id || (rol && item.destinatario_id === 'rol:' + rol);
  if (!propio) return { status: 403 };

  const upd = await ddb.send(new UpdateCommand({
    TableName: TABLE,
    Key: { tenant_id, notificacion_id },
    UpdateExpression: 'SET leida = :l, leida_at = :f',
    ExpressionAttributeValues: { ':l': true, ':f': new Date().toISOString() },
    ReturnValues: 'ALL_NEW',
  }));
  return { status: 200, item: upd.Attributes };
}

module.exports = { construirDestinos, idIdempotente, guardar, listar, marcarLeida };
