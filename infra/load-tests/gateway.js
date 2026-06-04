import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

const errorRate = new Rate("errors");
const proxyLatency = new Trend("proxy_latency");

export const options = {
  stages: [
    { duration: "30s", target: 10 },   // ramp up to 10 users
    { duration: "1m",  target: 10 },   // hold at 10 users
    { duration: "30s", target: 50 },   // ramp up to 50 users
    { duration: "1m",  target: 50 },   // hold at 50 users
    { duration: "30s", target: 0 },    // ramp down
  ],
  thresholds: {
    http_req_duration: ["p(95)<2000"],  // 95% of requests under 2s
    errors: ["rate<0.1"],               // error rate under 10%
  },
};

const BASE_URL = "http://localhost:8000";
const TOKEN = __ENV.TOKEN;

export function setup() {
  const res = http.post(
    `${BASE_URL}/auth/login`,
    JSON.stringify({ email: "akshata@nexus.ai", password: "securepass123" }),
    { headers: { "Content-Type": "application/json" } }
  );
  return { token: res.json("access_token") };
}

export default function (data) {
  // Health check — lightweight
  const health = http.get(`${BASE_URL}/health`);
  check(health, { "health ok": r => r.status === 200 });

  // Auth endpoint
  const me = http.get(`${BASE_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${data.token}` },
  });
  check(me, { "me ok": r => r.status === 200 });
  errorRate.add(me.status !== 200);

  // Admin stats
  const stats = http.get(`${BASE_URL}/admin/stats`, {
    headers: { Authorization: `Bearer ${data.token}` },
  });
  check(stats, { "stats ok": r => r.status === 200 });

  sleep(1);
}