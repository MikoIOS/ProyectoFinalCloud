"""Reemplaza las referencias de infraestructura por los recursos existentes sin gestionarlos de nuevo."""
import copy
import re


def apply_existing(config, existing, background=True, bootstrap=False):
    config=copy.deepcopy(config);resources=config['resources']['Resources'];shared=existing['resources'];renames={}
    for key, external in shared.items():
        if key not in resources:raise ValueError('Recurso desconocido: '+key)
        props=resources[key]['Properties']
        for name in ('TableName','BucketName','TopicName','QueueName'):
            if name in props:
                actual=external['Ref'].split('/')[-1] if name=='QueueName' else external['Ref'].split(':')[-1] if name=='TopicName' else external['Ref']
                renames[props[name]]=actual
    # No confundir una tabla con el prefijo del nombre de un Lambda (usuarios_procesarEventos).
    pattern=re.compile(r'(?<![A-Za-z0-9_-])(?:'+'|'.join(re.escape(k) for k in sorted(renames,key=len,reverse=True))+r')(?![A-Za-z0-9_-])')
    def replace(value):
        if isinstance(value,list):return [replace(v) for v in value]
        if isinstance(value,dict):
            if value.get('Ref') in shared:return shared[value['Ref']]['Ref']
            if 'Fn::GetAtt' in value:
                ref=value['Fn::GetAtt'];key,attr=ref if isinstance(ref,list) else ref.split('.',1)
                if key in shared:
                    if attr not in shared[key]:raise ValueError('Atributo externo no disponible: '+key+'.'+attr)
                    return shared[key][attr]
            return {k:replace(v) for k,v in value.items()}
        return pattern.sub(lambda m:renames[m.group(0)],value) if isinstance(value,str) else value
    for key in list(resources):
        r=resources[key];p=r.get('Properties',{});kind=r['Type']
        if key in shared or kind in ('AWS::SQS::QueuePolicy','AWS::S3::BucketPolicy') or (kind=='AWS::SNS::Subscription' and p.get('Protocol')=='sqs'):
            del resources[key]
    config=replace(config);resources=config['resources']['Resources']
    if not background or bootstrap:
        for f in config['functions'].values():
            f['events']=[e for e in f.get('events',[]) if 'http' in e]
        for key in list(resources):
            kind=resources[key]['Type']
            if kind in ('AWS::CloudWatch::Alarm','AWS::Logs::MetricFilter') or key in ('TopicAlarmas','TopicAlarmasPolicy','AvisosPermission','AvisosSubscription','EmailTopicPolicy'):
                del resources[key]
        for key in list(config['resources']['Outputs']):
            if key.startswith('monitorizacion'):del config['resources']['Outputs'][key]
    for resource in resources.values():
        depends=resource.get('DependsOn',[])
        if depends:resource['DependsOn']=[k for k in ([depends] if isinstance(depends,str) else depends) if k in resources]
    if any(r['Type']=='AWS::DynamoDB::Table' for r in resources.values()):raise ValueError('No deben crearse tablas al reutilizar las existentes')
    return config
