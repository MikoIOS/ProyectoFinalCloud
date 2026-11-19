import copy
import unittest
from legacy import data_only


class RetirementSafetyTest(unittest.TestCase):
    def test_preserva_tablas_buckets_colas_y_logs_sin_cambiar_propiedades(self):
        table={'Type':'AWS::DynamoDB::Table','Properties':{'TableName':'hcm-usuarios','KeySchema':[{'AttributeName':'tenant_id','KeyType':'HASH'}]}}
        source={'Resources':{'Table':copy.deepcopy(table),'Bucket':{'Type':'AWS::S3::Bucket','Properties':{'BucketName':'original'}},
                'API':{'Type':'AWS::ApiGateway::RestApi','Properties':{}},'Function':{'Type':'AWS::Lambda::Function','Properties':{}},
                'Logs':{'Type':'AWS::Logs::LogGroup','Properties':{'LogGroupName':'/aws/lambda/legacy'}},
                'Queue':{'Type':'AWS::SQS::Queue','Properties':{'QueueName':'original'}},
                'Subscription':{'Type':'AWS::SNS::Subscription','Properties':{'Protocol':'lambda','Endpoint':{'Fn::GetAtt':['Function','Arn']}}}},
                'Outputs':{'Endpoint':{'Value':{'Ref':'API'}},'Database':{'Value':{'Ref':'Table'}}}}
        result=data_only(source)
        self.assertEqual(result['Resources']['Table']['Properties'],table['Properties'])
        self.assertEqual(result['Resources']['Table']['DeletionPolicy'],'Retain')
        self.assertEqual(set(result['Resources']),{'Table','Bucket','Logs','Queue'})
        self.assertEqual(set(result['Outputs']),{'Database'})
        self.assertIn('API',source['Resources'])

    def test_una_referencia_insegura_en_datos_bloquea_el_retiro(self):
        source={'Resources':{'Data':{'Type':'AWS::DynamoDB::Table','Properties':{'TableName':{'Fn::Sub':'${Function}'}}},
                            'Function':{'Type':'AWS::Lambda::Function','Properties':{}}}}
        with self.assertRaises(ValueError):data_only(source)
