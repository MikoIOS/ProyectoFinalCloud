"""Describe los recursos actuales; no crea, copia ni modifica bases de datos."""
import argparse
import json
from pathlib import Path

import boto3
import yaml

from build import MODULES, module_dir, CloudFormationLoader

STATEFUL = {'AWS::DynamoDB::Table', 'AWS::S3::Bucket', 'AWS::SQS::Queue', 'AWS::SNS::Topic'}


def discover(stage='dev'):
    session = boto3.Session(region_name='us-east-1')
    cf, db, sqs = (session.client(s) for s in ('cloudformation', 'dynamodb', 'sqs'))
    resources = {}
    for module in MODULES:
        if module == 'monitorizacion':continue
        cfg = yaml.load((module_dir(module)/'serverless.yml').read_text(), Loader=CloudFormationLoader)
        stack = cfg['service'] + '-' + stage
        physical = {}
        for page in cf.get_paginator('list_stack_resources').paginate(StackName=stack):
            physical.update({r['LogicalResourceId']:r['PhysicalResourceId'] for r in page['StackResourceSummaries'] if r.get('PhysicalResourceId')})
        for logical, spec in cfg['resources']['Resources'].items():
            kind=spec['Type']
            if kind not in STATEFUL:continue
            name=physical[logical]; entry={'Ref':name,'type':kind,'source_stack':stack}
            if kind=='AWS::DynamoDB::Table':
                table=db.describe_table(TableName=name)['Table'];entry['Arn']=table['TableArn']
                if table.get('LatestStreamArn'):entry['StreamArn']=table['LatestStreamArn']
            elif kind=='AWS::S3::Bucket':entry['Arn']='arn:aws:s3:::'+name
            elif kind=='AWS::SQS::Queue':entry['Arn']=sqs.get_queue_attributes(QueueUrl=name,AttributeNames=['QueueArn'])['Attributes']['QueueArn']
            elif kind=='AWS::SNS::Topic':entry['Arn']=name
            resources[logical]=entry
    return {'data_stage':stage,'resources':resources}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage',default='dev');args=parser.parse_args()
    result=discover(args.stage);directory=Path(__file__).resolve().parent/'.runtime';directory.mkdir(mode=0o700,exist_ok=True)
    target=directory/('existing-'+args.stage+'.json');target.write_text(json.dumps(result,indent=2)+'\n');target.chmod(0o600)
    print('Recursos existentes identificados:',len(result['resources']),'; no se modificaron datos.')
