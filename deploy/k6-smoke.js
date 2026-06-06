import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = (__ENV.BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const ADMIN_ACCESS = __ENV.API_KEY || 'demo-admin-key';
const TENANT_ID = __ENV.TENANT_ID || 'demo-tenant';

export const options = {
  vus: Number(__ENV.VUS || 5),
  duration: __ENV.DURATION || '30s',
  thresholds: {
    checks: ['rate>0.99'],
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<1000'],
  },
};

export default function () {
  const health = http.get(`${BASE_URL}/healthz`);
  check(health, {
    'healthz status is 200': (response) => response.status === 200,
    'healthz reports ok': (response) => response.json('data.status') === 'ok',
  });

  const headers = { 'X-API-Key': ADMIN_ACCESS };
  const metrics = http.get(
    `${BASE_URL}/api/v1/admin/metrics/summary?tenant_id=${encodeURIComponent(TENANT_ID)}`,
    { headers }
  );
  check(metrics, {
    'metrics status is 200': (response) => response.status === 200,
    'metrics has response summary': (response) => response.json('data.response_time_summary') !== null,
  });

  sleep(1);
}
