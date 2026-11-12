'use strict';

const { SNSClient } = require('@aws-sdk/client-sns');

const sns = new SNSClient({ region: process.env.AWS_REGION });

module.exports = { sns };
