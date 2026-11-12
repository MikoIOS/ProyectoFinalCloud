'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { resources: template, canales } = require('../recursos.cjs');
const resources = template.Resources;
const alarms = Object.values(resources).filter(r => r.Type === 'AWS::CloudWatch::Alarm');

test('Alarmas únicas con nombres y umbrales de dev', () => {
  assert.equal(alarms.length, 25);
  assert.equal(new Set(alarms.map(a => a.Properties.AlarmName)).size, alarms.length);
  for (const { Properties: a } of alarms) {
    assert.ok(a.AlarmName.startsWith('hcm-${sls:stage}-eda-'));
    assert.ok(a.AlarmDescription);
    assert.ok(a.AlarmActions.length);
    assert.ok(a.Period >= 60);
    assert.ok(a.DatapointsToAlarm <= a.EvaluationPeriods);
  }
});

test('Las cinco colas tienen alarmas de DLQ y retraso', () => {
  for (const id of ['Usuarios', 'Empleados', 'Notificaciones', 'Nominas', 'Planillas']) {
    assert.equal(resources[id + 'DLQ'].Properties.MetricName, 'ApproximateNumberOfMessagesVisible');
    assert.equal(resources[id + 'DLQ'].Properties.Threshold, 1);
    assert.equal(resources[id + 'Retraso'].Properties.MetricName, 'ApproximateAgeOfOldestMessage');
    assert.equal(resources[id + 'Retraso'].Properties.EvaluationPeriods, 2);
  }
  assert.equal(resources.PlanillasRetraso.Properties.Threshold, 1800);
});

test('Fallos parciales tienen filtros que emiten la métrica alarmada', () => {
  const metric = resources.FallosCapturados.Properties;
  const filtros = Object.values(resources).filter(r => r.Type === 'AWS::Logs::MetricFilter');
  assert.equal(filtros.length, 6);
  for (const { Properties: f } of filtros) {
    assert.equal(f.MetricTransformations[0].MetricName, metric.MetricName);
    assert.equal(f.MetricTransformations[0].MetricNamespace, metric.Namespace);
    assert.ok(f.FilterPattern.includes('Fallo procesando') || f.FilterPattern.includes('No se publicó el registro'));
  }
});

test('El stream alerta antes de vencer y los canales se revisan sin tráfico', () => {
  assert.equal(resources.AsistenciaStreamRetraso.Properties.Threshold, 300000);
  assert.equal(resources.CanalesDeshabilitados.Properties.TreatMissingData, 'breaching');
  assert.equal(resources.CanalesDeshabilitados.Properties.Period, 300);
  const funciones = JSON.parse(canales);
  assert.equal(funciones.length, 6);
  assert.ok(funciones.includes('ms-asistencia-${sls:stage}-publicarEventos'));
});

test('El respaldo evita depender del formateador y restringe permisos CloudWatch', () => {
  const topic = { 'Fn::ImportValue': 'ms-notificaciones-${sls:stage}-EmailTopicArn' };
  assert.deepEqual(resources.AvisosErrores.Properties.AlarmActions, [topic]);
  assert.deepEqual(resources.AvisosErrores.Properties.OKActions, []);
  const policy = resources.TopicAlarmasPolicy.Properties.PolicyDocument.Statement[0];
  assert.equal(policy.Principal.Service, 'cloudwatch.amazonaws.com');
  assert.ok(policy.Condition.StringEquals['aws:SourceAccount']);
  assert.ok(policy.Condition.ArnLike['aws:SourceArn']);
  const owner = resources.EmailTopicPolicy.Properties.PolicyDocument.Statement[0];
  assert.ok(Array.isArray(owner.Action));
  assert.ok(owner.Action.includes('SNS:Publish'));
  assert.ok(owner.Action.every(action => !action.includes('*')));
});

test('El canal de avisos está listo antes de crear las alarmas', () => {
  for (const alarm of alarms) {
    assert.ok(alarm.DependsOn.includes('TopicAlarmasPolicy'));
    assert.ok(alarm.DependsOn.includes('AvisosSubscription'));
  }
  assert.equal(resources.AvisosSubscription.DependsOn, 'AvisosPermission');
  assert.equal(resources.AvisosPermission.Properties.Principal, 'sns.amazonaws.com');
  assert.deepEqual(resources.AvisosPermission.Properties.SourceArn, { Ref: 'TopicAlarmas' });
  assert.ok(resources.AvisosErrores.DependsOn.includes('EmailTopicPolicy'));
});
