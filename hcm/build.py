"""Un despliegue Serverless; cada módulo conserva sus imports y su artefacto."""
import copy
import importlib.util
import json
import re
import subprocess
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MODULES = ('usuarios', 'empleados', 'nominas', 'asistencia', 'reclutamiento', 'desempeno', 'notificaciones', 'monitorizacion')
TABLES = {'TablaUsuarios': 'usuarios', 'TablaEmpleados': 'empleados', 'NominaTable': 'nominas',
          'AsistenciaTable': 'asistencia', 'ReclutamientoTable': 'reclutamiento',
          'DesempenoTable': 'desempeno', 'TablaNotificaciones': 'notificaciones'}
STAGE = '${sls:stage}'


class CloudFormationLoader(yaml.SafeLoader):
    pass


def intrinsic(loader, tag, node):
    if isinstance(node, yaml.ScalarNode):
        value = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node)
    else:
        value = loader.construct_mapping(node)
    if tag == 'GetAtt' and isinstance(value, str):
        value = value.split('.', 1)
    return {'Ref' if tag == 'Ref' else 'Fn::' + tag: value}


CloudFormationLoader.add_multi_constructor('!', intrinsic)


def module_dir(module):
    return ROOT / ('monitorizacion' if module == 'monitorizacion' else 'ms-' + module)


def function_key(module, name):
    return 'authorizer' if (module, name) == ('usuarios', 'authorizer') else module + '_' + name


def function_id(key):
    # Serverless normalizes underscores in CloudFormation logical IDs.
    return key[0].upper() + key[1:].replace('_', 'Underscore') + 'LambdaFunction'


def compose():
    configs = {m: yaml.load((module_dir(m) / 'serverless.yml').read_text(), Loader=CloudFormationLoader) for m in MODULES}
    monitor = json.loads(subprocess.check_output(
        ['node', '-e', "process.stdout.write(JSON.stringify(require('./recursos.cjs')))"],
        cwd=module_dir('monitorizacion'), text=True))
    configs['monitorizacion']['resources'] = monitor['resources']
    configs['monitorizacion']['provider']['environment']['CANALES'] = monitor['canales']

    resources, outputs, functions, replacements = {}, {}, {}, {}
    for module, config in configs.items():
        for name in config['functions']:
            key = function_key(module, name)
            replacements[f"{config['service']}-{STAGE}-{name}"] = f'hcm-{STAGE}-{key}'
        for logical, resource in config['resources']['Resources'].items():
            if logical in resources and resources[logical] != resource:
                raise ValueError('Recurso duplicado distinto: ' + logical)
            resources[logical] = copy.deepcopy(resource)
        for name, output in config['resources'].get('Outputs', {}).items():
            outputs[module + name] = copy.deepcopy(output)

    for logical, resource in resources.items():
        props, kind = resource['Properties'], resource['Type']
        if kind == 'AWS::DynamoDB::Table':
            old = props['TableName']; new = f'hcm-{STAGE}-{TABLES[logical]}'
            replacements[old] = new; props['TableName'] = new
        elif kind == 'AWS::SQS::Queue':
            old = props['QueueName']; new = f'hcm-{STAGE}-{old}'
            replacements[old] = new
        elif kind == 'AWS::SNS::Topic':
            old = props['TopicName']
            replacements[old] = f'hcm-{STAGE}-' + {'EventosTopic': 'eventos', 'EmailTopic': 'notificaciones-email', 'TopicAlarmas': 'alarmas'}[logical]
        elif kind == 'AWS::S3::Bucket':
            old = props['BucketName']
            replacements[old] = f'hcm-{STAGE}-' + ('cvs' if logical == 'CVBucket' else 'boletas') + '-${aws:accountId}'
        if kind in ('AWS::DynamoDB::Table', 'AWS::S3::Bucket'):
            resource.update(DeletionPolicy='Retain', UpdateReplacePolicy='Retain')

    # The legacy monitor must not observe the old stack's queues or metrics.
    replacements[f'hcm-{STAGE}-eda-'] = f'hcm-{STAGE}-unificado-eda-'
    replacements['HCM/EDA'] = 'HCM/Unificado/EDA'
    pattern = re.compile('|'.join(re.escape(k) for k in sorted(replacements, key=len, reverse=True)))
    topic = {'Ref': 'EventosTopic'}
    auth = {'name': 'authorizer', 'type': 'token', 'identitySource': 'method.request.header.Authorization', 'resultTtlInSeconds': 300}

    def normalize(value, module):
        if isinstance(value, list):
            return [normalize(v, module) for v in value]
        if isinstance(value, dict):
            if value.get('Fn::ImportValue') == f'ms-notificaciones-{STAGE}-EmailTopicArn':
                return {'Ref': 'EmailTopic'}
            result = {}
            for key, v in value.items():
                if key == 'Ref' and isinstance(v, str):
                    candidates = {name[0].upper() + name[1:] + 'LambdaFunction': function_id(function_key(module, name)) for name in configs[module]['functions']}
                    v = candidates.get(v, v)
                elif key == 'Fn::GetAtt' and isinstance(v, list):
                    candidates = {name[0].upper() + name[1:] + 'LambdaFunction': function_id(function_key(module, name)) for name in configs[module]['functions']}
                    v = [candidates.get(v[0], v[0]), *v[1:]]
                result[key] = normalize(v, module)
            return result
        if not isinstance(value, str):
            return value
        if value in ('${self:custom.topicArn}', f'${{cf:ms-usuarios-{STAGE}.EventosTopicArn}}'):
            return copy.deepcopy(topic)
        if value == '${self:custom.auth}':
            return copy.deepcopy(auth)
        return pattern.sub(lambda match: replacements[match.group(0)], value)

    # Transform each resource with its original module so Lambda references remain correct.
    for module, config in configs.items():
        for logical in config['resources']['Resources']:
            resources[logical] = normalize(resources[logical], module)
        for name in config['resources'].get('Outputs', {}):
            outputs[module + name] = normalize(outputs[module + name], module)
        env = normalize(copy.deepcopy(config['provider'].get('environment', {})), module)
        if module == 'usuarios':
            env['TABLE_USUARIOS'] = {'Ref': 'TablaUsuarios'}
            env['JWT_SECRET'] = '${env:HCM_JWT_SECRET_${sls:stage}}'
        elif module == 'empleados':
            env['TABLE_EMPLEADOS'] = {'Ref': 'TablaEmpleados'}
        elif module in TABLES.values():
            env['TABLE_NAME'] = {'Ref': next(k for k, v in TABLES.items() if v == module)}
        if 'TABLE_EMPLEADOS' in env:
            env['TABLE_EMPLEADOS'] = {'Ref': 'TablaEmpleados'}
        if module == 'monitorizacion':
            env['METRICS_NAMESPACE'] = 'HCM/Unificado/EDA'
        for name, original in config['functions'].items():
            fn = normalize(copy.deepcopy(original), module)
            fn.update(runtime=config['provider']['runtime'], timeout=fn.get('timeout', config['provider'].get('timeout', 6)),
                      environment=copy.deepcopy(env), package={'artifact': f'.build/{module}.zip'})
            for event in fn.get('events', []):
                if 'http' in event and event['http']['path'] == 'ping' and module != 'usuarios':
                    event['http']['path'] = module + '/ping'
            functions[function_key(module, name)] = fn
    for name, output in outputs.items():
        if 'Export' in output:
            output['Export']['Name'] = '${self:service}-' + STAGE + '-' + name
    for resource in resources.values():
        if resource['Type'] == 'AWS::Logs::MetricFilter':
            physical = resource['Properties']['LogGroupName']
            key = physical.removeprefix(f'/aws/lambda/hcm-{STAGE}-')
            if key not in functions:
                raise ValueError('Filtro de logs sin función: ' + physical)
            resource['Properties']['LogGroupName'] = {'Ref': function_id(key).removesuffix('LambdaFunction') + 'LogGroup'}
    outputs.pop('asistenciaApiUrl', None)
    outputs['ApiUrl'] = {'Value': {'Fn::Sub': 'https://${ApiGatewayRestApi}.execute-api.${AWS::Region}.amazonaws.com/' + STAGE}}
    result = {'provider': {'name': 'aws', 'runtime': 'python3.12', 'region': 'us-east-1',
              'stage': "${opt:stage, 'dev'}", 'timeout': 29, 'versionFunctions': False,
              'logRetentionInDays': 14, 'iam': {'role': '${env:LAB_ROLE_ARN}'},
              'apiGateway': {'binaryMediaTypes': ['application/pdf']}},
              'custom': {}, 'functions': functions, 'resources': {'Resources': resources, 'Outputs': outputs}}
    validate(result)
    return result


def validate(config):
    routes = set()
    for key, fn in config['functions'].items():
        for event in fn.get('events', []):
            if 'http' not in event:
                continue
            http = event['http']; route = (http['method'].upper(), http['path'])
            if route in routes:
                raise ValueError('Ruta duplicada: ' + str(route))
            routes.add(route)
    serialized = json.dumps(config)
    for legacy in ('${cf:', '${file(', 'Fn::ImportValue'):
        if legacy in serialized:
            raise ValueError('Dependencia de stack anterior: ' + legacy)
    if len(TABLES) != sum(r['Type'] == 'AWS::DynamoDB::Table' for r in config['resources']['Resources'].values()):
        raise ValueError('Se necesitan siete tablas independientes')


def package_modules():
    output = Path(__file__).parent / '.build'; output.mkdir(exist_ok=True)
    for module in MODULES:
        source = module_dir(module)
        roots = [source / d for d in ('src', 'common', 'handlers') if (source / d).is_dir()]
        if module == 'monitorizacion':
            roots = [source / 'avisos.py', source / 'canales.py']
        if module == 'notificaciones':
            dependencies = source / 'node_modules'
            if not dependencies.is_dir():
                raise RuntimeError('Ejecuta npm ci dentro de ms-notificaciones antes de empaquetar')
            roots.append(dependencies)
        with zipfile.ZipFile(output / (module + '.zip'), 'w', zipfile.ZIP_DEFLATED) as z:
            for base in roots:
                for p in ([base] if base.is_file() else base.rglob('*')):
                    if p.is_file() and not p.is_symlink() and (base.name == 'node_modules' or p.suffix in ('.py', '.js')) and '__pycache__' not in p.parts:
                        z.write(p, p.relative_to(source))
            if module == 'usuarios':
                spec = importlib.util.find_spec('jwt')
                if not spec or not spec.origin:
                    raise RuntimeError('Instala requirements-build.txt antes de empaquetar')
                base = Path(spec.origin).parent
                for p in base.rglob('*.py'):
                    z.write(p, Path('jwt') / p.relative_to(base))


if __name__ == '__main__':
    config = compose()
    package_modules()
    destination = Path(__file__).parent / '.build/service.json'
    destination.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n')
    print(f"Configuración preparada: {len(config['functions'])} Lambdas, una API por stage, siete tablas y monitorización.")
