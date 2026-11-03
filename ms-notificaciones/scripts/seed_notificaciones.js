#!/usr/bin/env node
'use strict';

/**
 * Carga masiva de notificaciones: --count por tenant (por defecto 10k × 3 = 30k).
 *
 *   node scripts/seed_notificaciones.js --count 10000
 *   node scripts/seed_notificaciones.js --tenant andina --count 100
 *
 * IDs coherentes con los demás seeds: user_id = usr-{n:06d}.
 */
process.env.AWS_REGION = process.env.AWS_REGION || 'us-east-1';

const crypto = require('crypto');
const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const { DynamoDBDocumentClient, BatchWriteCommand } = require('@aws-sdk/lib-dynamodb');

const TENANTS = ['andina', 'pacifico', 'sierra'];
const TIPOS = ['BOLETA_DISPONIBLE', 'EVALUACION_COMPLETADA', 'AUSENCIA_APROBADA', 'BIENVENIDA', 'RECONOCIMIENTO'];
const MENSAJES = {
  BOLETA_DISPONIBLE: 'Tu boleta del periodo ya está disponible.',
  EVALUACION_COMPLETADA: 'Se completó tu evaluación de desempeño.',
  AUSENCIA_APROBADA: 'Tu solicitud de ausencia fue aprobada.',
  BIENVENIDA: 'Bienvenido/a al equipo. Tu cuenta fue creada.',
  RECONOCIMIENTO: 'Recibiste un reconocimiento de un compañero.',
};

function arg(nombre, defecto) {
  const i = process.argv.indexOf(nombre);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : defecto;
}

function idNotificacion(tenant, user, n) {
  return 'not-' + crypto.createHash('sha1').update(`${tenant}|${user}|${n}`).digest('hex').slice(0, 12);
}

async function escribir(ddb, table, items, concurrencia = 8) {
  let idx = 0;
  let escritos = 0;

  async function worker() {
    while (idx < items.length) {
      const lote = items.slice(idx, idx + 25);
      idx += 25;
      let pendientes = lote.map((Item) => ({ PutRequest: { Item } }));

      for (let intento = 0; pendientes.length && intento < 5; intento += 1) {
        const res = await ddb.send(new BatchWriteCommand({ RequestItems: { [table]: pendientes } }));
        pendientes = (res.UnprocessedItems && res.UnprocessedItems[table]) || [];
      }
      escritos += lote.length - pendientes.length;
    }
  }

  await Promise.all(Array.from({ length: concurrencia }, () => worker()));
  return escritos;
}

async function main() {
  const count = Number(arg('--count', process.env.COUNT || 10000));
  const stage = arg('--stage', 'dev');
  const table = arg('--table', `hcm-notificaciones-${stage}`);
  const unTenant = arg('--tenant', null);
  const tenants = unTenant ? [unTenant] : TENANTS;

  const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({}), {
    marshallOptions: { removeUndefinedValues: true },
  });

  const ahora = Date.now();
  let total = 0;

  for (const tenant of tenants) {
    const items = [];
    for (let n = 1; n <= count; n += 1) {
      const user = `usr-${String(n).padStart(6, '0')}`;
      const tipo = TIPOS[n % TIPOS.length];
      const dias = (n * 7) % 180;
      items.push({
        tenant_id: tenant,
        notificacion_id: idNotificacion(tenant, user, n),
        destinatario_id: user,
        tipo,
        mensaje: MENSAJES[tipo],
        leida: n % 5 === 0,
        created_at: new Date(ahora - dias * 86400000).toISOString(),
      });
    }

    const escritos = await escribir(ddb, table, items);
    total += escritos;
    console.log(`${tenant}: ${escritos}/${count} notificaciones`);
  }

  console.log(`Total: ${total} notificaciones en ${table}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
