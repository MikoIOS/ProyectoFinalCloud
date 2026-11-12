'use strict';

const stage = '${sls:stage}';
const prefix = `hcm-${stage}-eda-`;
function emailTopic() { return { 'Fn::ImportValue': `ms-notificaciones-${stage}-EmailTopicArn` }; }
const resources = {
  TopicAlarmas: { Type: 'AWS::SNS::Topic', Properties: { TopicName: `hcm-alarmas-${stage}` } },
  AvisosPermission: { Type: 'AWS::Lambda::Permission', Properties: {
    FunctionName: { Ref: 'AvisarAlarmaLambdaFunction' }, Action: 'lambda:InvokeFunction',
    Principal: 'sns.amazonaws.com', SourceArn: { Ref: 'TopicAlarmas' },
  } },
  AvisosSubscription: { Type: 'AWS::SNS::Subscription', DependsOn: 'AvisosPermission', Properties: {
    TopicArn: { Ref: 'TopicAlarmas' }, Protocol: 'lambda',
    Endpoint: { 'Fn::GetAtt': ['AvisarAlarmaLambdaFunction', 'Arn'] },
  } },
  TopicAlarmasPolicy: {
    Type: 'AWS::SNS::TopicPolicy', Properties: {
      Topics: [{ Ref: 'TopicAlarmas' }],
      PolicyDocument: { Version: '2012-10-17', Statement: [{
        Effect: 'Allow', Principal: { Service: 'cloudwatch.amazonaws.com' }, Action: 'sns:Publish',
        Resource: { Ref: 'TopicAlarmas' }, Condition: {
          StringEquals: { 'aws:SourceAccount': { Ref: 'AWS::AccountId' } },
          ArnLike: { 'aws:SourceArn': { 'Fn::Join': ['', ['arn:', { Ref: 'AWS::Partition' },
            ':cloudwatch:', { Ref: 'AWS::Region' }, ':', { Ref: 'AWS::AccountId' }, `:alarm:${prefix}*`]] } },
        },
      }] },
    },
  },
};

function alarm(id, suffix, description, namespace, metric, dimensions, threshold, statistic = 'Sum', periods = 1) {
  resources[id] = { Type: 'AWS::CloudWatch::Alarm',
    DependsOn: ['TopicAlarmasPolicy', 'AvisosSubscription'], Properties: {
    AlarmName: prefix + suffix, AlarmDescription: description,
    Namespace: namespace, MetricName: metric, Dimensions: dimensions,
    Statistic: statistic, Period: 60, EvaluationPeriods: periods, DatapointsToAlarm: periods,
    Threshold: threshold, ComparisonOperator: 'GreaterThanOrEqualToThreshold',
    TreatMissingData: 'notBreaching',
    AlarmActions: [{ Ref: 'TopicAlarmas' }], OKActions: [{ Ref: 'TopicAlarmas' }],
  } };
}

const workers = [
  ['Usuarios', 'ms-usuarios', 'procesarEventos'],
  ['Empleados', 'ms-empleados', 'procesarEventos'],
  ['Notificaciones', 'ms-notificaciones', 'procesarEventos'],
  ['Nominas', 'ms-nominas', 'procesarEventos'],
  ['Planillas', 'ms-nominas', 'procesarPlanilla'],
  ['Asistencia', 'ms-asistencia', 'publicarEventos'],
  ['Calendario', 'ms-asistencia', 'calendario'],
];
for (const [id, service, handler] of workers) {
  const fn = `${service}-${stage}-${handler}`;
  alarm(`${id}Errores`, `${id.toLowerCase()}-errores`,
    `Falló ${fn}. Revisar los logs y el origen del evento antes de reintentar.`,
    'AWS/Lambda', 'Errors', [{ Name: 'FunctionName', Value: fn }], 1);
  if (id !== 'Calendario') {
    resources[`${id}FallosLog`] = { Type: 'AWS::Logs::MetricFilter', Properties: {
      LogGroupName: `/aws/lambda/${fn}`,
      FilterPattern: id === 'Asistencia' ? '"No se publicó el registro"' : '"Fallo procesando"',
      MetricTransformations: [{ MetricNamespace: 'HCM/EDA', MetricName: `FallosProcesamiento-${stage}`,
        MetricValue: '1', DefaultValue: 0 }],
    } };
  }
}
alarm('FallosCapturados', 'fallos-capturados',
  'Un consumidor capturó un error y pidió reintentar el mensaje. Revisar logs de usuarios, empleados, notificaciones, nóminas o asistencia.',
  'HCM/EDA', `FallosProcesamiento-${stage}`, [], 1);

// Las colas actuales tienen nombres compartidos sin stage; este stack monitorea el dev existente.
const queues = [
  ['Usuarios', 'ms-usuarios-eventos', 300],
  ['Empleados', 'ms-empleados-eventos', 300],
  ['Notificaciones', 'ms-notificaciones-eventos', 300],
  ['Nominas', 'ms-nominas-eventos', 300],
  ['Planillas', 'ms-nominas-trabajos', 1800],
];
for (const [id, queue, age] of queues) {
  alarm(`${id}DLQ`, `${id.toLowerCase()}-dlq`,
    `Hay mensajes en ${queue}-dlq. Inspeccionar y corregir la causa; no purgar ni reenviar automáticamente.`,
    'AWS/SQS', 'ApproximateNumberOfMessagesVisible', [{ Name: 'QueueName', Value: queue + '-dlq' }], 1, 'Maximum');
  alarm(`${id}Retraso`, `${id.toLowerCase()}-retraso`,
    `La cola ${queue} tiene mensajes de al menos ${age} segundos durante dos minutos. Revisar que su conexión con Lambda esté habilitada.`,
    'AWS/SQS', 'ApproximateAgeOfOldestMessage', [{ Name: 'QueueName', Value: queue }], age, 'Maximum', 2);
}
alarm('AsistenciaStreamRetraso', 'asistencia-stream-retraso',
  'La publicación de asistencia lleva al menos 5 minutos de retraso. Revisar el stream y los logs antes de que venza su retención de 24 horas.',
  'AWS/Lambda', 'IteratorAge', [{ Name: 'FunctionName', Value: `ms-asistencia-${stage}-publicarEventos` }], 300000, 'Maximum', 2);
for (const [id, topic] of [['Eventos', 'hcm-eventos'], ['Correo', `hcm-notificaciones-email-${stage}`]]) {
  alarm(`${id}EntregaFallida`, `${id.toLowerCase()}-entrega-fallida`,
    `SNS reporta fallos de entrega en ${topic}. Revisar suscripciones, permisos y destinatarios.`,
    'AWS/SNS', 'NumberOfNotificationsFailed', [{ Name: 'TopicName', Value: topic }], 1);
}
alarm('PruebaAlarma', 'prueba',
  'PRUEBA CONTROLADA del canal de alarmas. No representa un fallo de los microservicios.',
  'HCM/EDA', `PruebaAlarma-${stage}`, [], 1);

// Si falla el formateador, CloudWatch avisa directamente al topic de correo existente.
alarm('AvisosErrores', 'avisos-errores',
  'Falló el formateador de alertas HCM. Este aviso de respaldo usa el formato nativo de CloudWatch.',
  'AWS/Lambda', 'Errors', [{ Name: 'FunctionName', Value: `hcm-monitorizacion-${stage}-avisarAlarma` }], 1);
resources.AvisosErrores.Properties.AlarmActions = [emailTopic()];
resources.AvisosErrores.Properties.OKActions = [];
resources.AvisosErrores.DependsOn.push('EmailTopicPolicy');
resources.EmailTopicPolicy = { Type: 'AWS::SNS::TopicPolicy', Properties: {
  Topics: [emailTopic()], PolicyDocument: { Version: '2012-10-17', Statement: [
    { Sid: 'Propietario', Effect: 'Allow', Principal: { AWS: { 'Fn::Join': ['', ['arn:',
      { Ref: 'AWS::Partition' }, ':iam::', { Ref: 'AWS::AccountId' }, ':root']] } },
      Action: ['SNS:GetTopicAttributes', 'SNS:SetTopicAttributes', 'SNS:AddPermission',
        'SNS:RemovePermission', 'SNS:DeleteTopic', 'SNS:Subscribe', 'SNS:ListSubscriptionsByTopic', 'SNS:Publish'],
      Resource: emailTopic() },
    { Sid: 'AlarmaRespaldo', Effect: 'Allow', Principal: { Service: 'cloudwatch.amazonaws.com' },
      Action: 'sns:Publish', Resource: emailTopic(), Condition: {
        StringEquals: { 'aws:SourceAccount': { Ref: 'AWS::AccountId' } },
        ArnEquals: { 'aws:SourceArn': { 'Fn::Join': ['', ['arn:', { Ref: 'AWS::Partition' },
          ':cloudwatch:', { Ref: 'AWS::Region' }, ':', { Ref: 'AWS::AccountId' }, `:alarm:${prefix}avisos-errores`]] } },
      } },
  ] },
} };


alarm('ComprobarCanalesErrores', 'comprobar-canales-errores',
  'Falló la revisión periódica de los canales EDA. Revisar los logs del monitor y los permisos de Lambda y CloudWatch.',
  'AWS/Lambda', 'Errors', [{ Name: 'FunctionName', Value: `hcm-monitorizacion-${stage}-comprobarCanales` }], 1);
alarm('CanalesDeshabilitados', 'canales-deshabilitados',
  `Hay conexiones SQS/Streams sin habilitar o el monitor dejó de reportar durante 10 minutos. Ver detalles en /aws/lambda/hcm-monitorizacion-${stage}-comprobarCanales.`,
  'HCM/EDA', `CanalesDeshabilitados-${stage}`, [], 1, 'Maximum', 2);
resources.CanalesDeshabilitados.Properties.Period = 300;
resources.CanalesDeshabilitados.Properties.TreatMissingData = 'breaching';

module.exports = { resources: { Resources: resources, Outputs: {
  TopicAlarmasArn: { Value: { Ref: 'TopicAlarmas' } },
  PruebaAlarmName: { Value: prefix + 'prueba' },
} }, canales: JSON.stringify(workers.filter(([id]) => id !== 'Calendario').map(([, service, handler]) => `${service}-${stage}-${handler}`)) };
