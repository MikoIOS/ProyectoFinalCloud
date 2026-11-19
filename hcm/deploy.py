"""Despliega un stage reutilizando su secreto en Lambda; nunca lo imprime ni guarda en Git."""
import argparse
import os
import secrets
import subprocess
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('dev', 'prod'), required=True)
    parser.add_argument('--bootstrap', action='store_true')
    args = parser.parse_args()
    session = boto3.Session(region_name='us-east-1')
    account = session.client('sts').get_caller_identity()['Account']
    env = os.environ.copy()
    key = 'HCM_JWT_SECRET_' + args.stage
    if not env.get(key):
        for function in ('usuarios_http', 'usuarios_login'):
            try:
                current = session.client('lambda').get_function_configuration(FunctionName=f'hcm-{args.stage}-{function}')
                env[key] = current['Environment']['Variables']['JWT_SECRET']
                break
            except ClientError as error:
                if error.response['Error']['Code'] != 'ResourceNotFoundException':
                    raise
        if not env.get(key):
            env[key] = secrets.token_urlsafe(48)
    if env[key].startswith('package-only') or len(env[key]) < 32:
        raise ValueError('El despliegue requiere un secreto real de al menos 32 caracteres')
    env['LAB_ROLE_ARN'] = env.get('LAB_ROLE_ARN') or f'arn:aws:iam::{account}:role/LabRole'
    directory = Path(__file__).resolve().parent
    for private in ('.build', '.runtime', '.serverless'):
        path = directory / private
        path.mkdir(mode=0o700, exist_ok=True)
        path.chmod(0o700)
    if args.stage == 'prod':
        subprocess.run([os.sys.executable, str(directory / 'existing.py'), '--stage', 'dev'], env=env, check=True)
    build = [os.sys.executable, str(directory / 'build.py'), '--stage', args.stage]
    if args.bootstrap:
        build.append('--bootstrap')
    subprocess.run(build, env=env, check=True)
    artifact = '.build/deploy-' + args.stage
    subprocess.run(['serverless', 'package', '--stage', args.stage, '--package', artifact], cwd=directory, env=env, check=True)
    subprocess.run(['serverless', 'deploy', '--stage', args.stage, '--package', artifact], cwd=directory, env=env, check=True)


if __name__ == '__main__':
    main()
