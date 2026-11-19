"""Traspasa consumidores y retira solo ejecución legada; preserva todos los recursos de datos."""
import argparse
import copy
import json
import re
import time
from pathlib import Path

import boto3
import yaml

from build import MODULES, module_dir, CloudFormationLoader

PRIVATE = Path(__file__).resolve().parent / '.runtime/legacy'
KEEP = {'AWS::DynamoDB::Table','AWS::S3::Bucket','AWS::S3::BucketPolicy','AWS::SNS::Topic',
        'AWS::SNS::TopicPolicy','AWS::SNS::Subscription','AWS::SQS::Queue','AWS::SQS::QueuePolicy','AWS::Logs::LogGroup'}
DATA = {'AWS::DynamoDB::Table','AWS::S3::Bucket','AWS::SQS::Queue','AWS::SNS::Topic'}


def refs(value, declared):
    result=set()
    if isinstance(value,list):
        for v in value:result.update(refs(v,declared))
    elif isinstance(value,dict):
        if value.get('Ref') in declared:result.add(value['Ref'])
        if 'Fn::GetAtt' in value:
            v=value['Fn::GetAtt'];key=v[0] if isinstance(v,list) else v.split('.')[0]
            if key in declared:result.add(key)
        if 'Fn::Sub' in value:
            v=value['Fn::Sub'];text=v[0] if isinstance(v,list) else v
            result.update(k.split('.')[0] for k in re.findall(r'\$\{([^}]+)\}',text) if k.split('.')[0] in declared)
        d=value.get('DependsOn',[]);result.update(k for k in ([d] if isinstance(d,str) else d) if k in declared)
        for v in value.values():result.update(refs(v,declared))
    return result


def data_only(template):
    result=copy.deepcopy(template);all_resources=template['Resources'];declared=set(all_resources)
    kept={k:copy.deepcopy(v) for k,v in all_resources.items() if v['Type'] in KEEP}
    while True:
        invalid=[k for k,v in kept.items() if refs(v,declared)-kept.keys()]
        if not invalid:break
        for key in invalid:
            if kept[key]['Type'] in DATA:raise ValueError('No se puede preservar el recurso de datos '+key)
            del kept[key]
    for key,value in all_resources.items():
        if value['Type'] in DATA:
            if key not in kept:raise ValueError('Falta preservar '+key)
            kept[key]['DeletionPolicy']='Retain';kept[key]['UpdateReplacePolicy']='Retain'
            original=copy.deepcopy(value);actual=copy.deepcopy(kept[key])
            for item in (original,actual):item.pop('DeletionPolicy',None);item.pop('UpdateReplacePolicy',None)
            if original!=actual:raise ValueError('Se intentó cambiar la definición de '+key)
    for value in kept.values():
        value['DeletionPolicy']='Retain';value['UpdateReplacePolicy']='Retain'
    result['Resources']=kept
    result['Outputs']={k:v for k,v in template.get('Outputs',{}).items() if not(refs(v,declared)-kept.keys())}
    result['Description']='Datos y logs conservados; APIs y Lambdas activos en el servicio hcm.'
    return result


def save(name,value):
    PRIVATE.mkdir(mode=0o700,parents=True,exist_ok=True)
    p=PRIVATE/name;p.write_text(json.dumps(value,default=str,indent=2)+'\n');p.chmod(0o600)


def pause(session):
    lam,ev,cw=(session.client(s) for s in ('lambda','events','cloudwatch'))
    if (PRIVATE/'handoff.json').exists():raise RuntimeError('Ya existe un traspaso; revisar el estado guardado')
    state={'mappings':[],'rules':[],'alarms':[]}
    for module in MODULES:
        cfg=yaml.load((module_dir(module)/'serverless.yml').read_text(),Loader=CloudFormationLoader)
        for name,fn in cfg['functions'].items():
            if any('sqs' in e or 'stream' in e for e in fn.get('events',[])):
                for page in lam.get_paginator('list_event_source_mappings').paginate(FunctionName=cfg['service']+'-dev-'+name):
                    state['mappings'].extend({'uuid':m['UUID'],'enabled':m['State']=='Enabled'} for m in page['EventSourceMappings'])
        for page in ev.get_paginator('list_rules').paginate(NamePrefix=cfg['service']+'-dev'):
            state['rules'].extend({'name':r['Name'],'enabled':r['State']=='ENABLED'} for r in page['Rules'])
    for page in cw.get_paginator('describe_alarms').paginate(AlarmNamePrefix='hcm-dev-eda-'):
        state['alarms'].extend(a['AlarmName'] for a in page.get('MetricAlarms',[]) if a['ActionsEnabled'])
    save('handoff.json',state)
    if state['alarms']:cw.disable_alarm_actions(AlarmNames=state['alarms'])
    for r in state['rules']:
        if r['enabled']:ev.disable_rule(Name=r['name'])
    for m in state['mappings']:
        if m['enabled']:lam.update_event_source_mapping(UUID=m['uuid'],Enabled=False)
    for m in state['mappings']:
        for _ in range(90):
            if lam.get_event_source_mapping(UUID=m['uuid'])['State']=='Disabled':break
            time.sleep(2)
        else:raise TimeoutError('El consumidor antiguo no se detuvo')
    print('Consumidores antiguos pausados:',len(state['mappings']),'; no se detuvieron los endpoints HTTP ni se modificaron tablas.',flush=True)


def restore(session):
    state=json.loads((PRIVATE/'handoff.json').read_text());lam,ev,cw=(session.client(s) for s in ('lambda','events','cloudwatch'))
    for m in state['mappings']:
        if m['enabled']:lam.update_event_source_mapping(UUID=m['uuid'],Enabled=True)
    for r in state['rules']:
        if r['enabled']:ev.enable_rule(Name=r['name'])
    if state['alarms']:cw.enable_alarm_actions(AlarmNames=state['alarms'])
    print('Consumidores y acciones originales restablecidos.')


def plan(session):
    cf=session.client('cloudformation');result=[]
    for module in MODULES:
        cfg=yaml.load((module_dir(module)/'serverless.yml').read_text(),Loader=CloudFormationLoader);name=cfg['service']+'-dev'
        current=cf.get_template(StackName=name)['TemplateBody']
        if isinstance(current,str):current=json.loads(current)
        wanted=data_only(current);save(name+'-before.json',current);save(name+'-data-only.json',wanted)
        result.append({'stack':name,'remove':[{'logical_id':k,'type':v['Type']} for k,v in current['Resources'].items() if k not in wanted['Resources']],
                       'preserve':[{'logical_id':k,'type':v['Type']} for k,v in wanted['Resources'].items()]})
    save('retirement-plan.json',result)
    print(json.dumps([{'stack':p['stack'],'remove_runtime_resources':len(p['remove']),'preserve_data_resources':sum(r['type'] in DATA for r in p['preserve'])} for p in result]))
    return result


def retire(session):
    # These checks make it impossible to retire the old API before prod's consumers are healthy.
    lam=session.client('lambda');cf=session.client('cloudformation')
    for key in ('usuarios_procesarEventos','empleados_procesarEventos','notificaciones_procesarEventos','nominas_procesarEventos','nominas_procesarPlanilla','asistencia_publicarEventos'):
        items=lam.list_event_source_mappings(FunctionName='hcm-prod-'+key)['EventSourceMappings']
        if len(items)!=1 or items[0]['State']!='Enabled':raise RuntimeError('El consumidor nuevo no está listo: '+key)
    report=sorted(plan(session),key=lambda p:p['stack']=='ms-usuarios-dev')
    # All payloads must be small enough before any destructive update is attempted.
    for p in report:
        if len((PRIVATE/(p['stack']+'-data-only.json')).read_bytes())>51200:raise ValueError('Template demasiado grande')
    for p in report:
        if not p['remove']:continue
        name=p['stack'];template=json.loads((PRIVATE/(name+'-data-only.json')).read_text())
        info=cf.describe_stacks(StackName=name)['Stacks'][0]
        protected=['LogicalResourceId/'+k for k in template['Resources']]
        policy=[{'Effect':'Allow','Action':'Update:*','Principal':'*','Resource':'*'}]
        if protected:policy.append({'Effect':'Deny','Action':['Update:Delete','Update:Replace'],'Principal':'*','Resource':protected})
        cf.update_stack(StackName=name,TemplateBody=json.dumps(template),Capabilities=['CAPABILITY_NAMED_IAM'],
            Parameters=[{'ParameterKey':x['ParameterKey'],'UsePreviousValue':True} for x in info.get('Parameters',[])],
            StackPolicyDuringUpdateBody=json.dumps({'Statement':policy}))
        print('Retirando API/Lambdas antiguos; datos conservados:',name,flush=True)
        for _ in range(180):
            status=cf.describe_stacks(StackName=name)['Stacks'][0]['StackStatus']
            if status=='UPDATE_COMPLETE':break
            if 'ROLLBACK' in status or 'FAILED' in status:raise RuntimeError(name+': '+status)
            time.sleep(5)
        else:raise TimeoutError(name)
    save('retired.json',{'stacks':[p['stack'] for p in report],'data_preserved':True})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('pause','restore','plan','retire'));args=parser.parse_args()
    session=boto3.Session(region_name='us-east-1')
    {'pause':pause,'restore':restore,'plan':plan,'retire':retire}[args.action](session)
