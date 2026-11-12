'use strict';

const HEADERS = {
  'Content-Type': 'application/json',
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'Content-Type,Authorization',
};

function json(statusCode, body) {
  return { statusCode, headers: HEADERS, body: JSON.stringify(body) };
}

function error(statusCode, codigo, mensaje) {
  return json(statusCode, { error: { codigo, mensaje } });
}

module.exports = { json, error, HEADERS };
