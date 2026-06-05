![CI](https://github.com/akshata1710/nexus-llm/actions/workflows/ci.yml/badge.svg)
# NexusLLM Gateway

A production-grade, secure AI gateway that routes requests to multiple LLM providers
(OpenAI, Anthropic, Gemini) with centralized auth, rate limiting, audit logging,
and an admin dashboard.

Built to demonstrate platform engineering concepts: secure proxy systems, API key
lifecycle management, multi-provider routing, and observable infrastructure.

---

## Performance

Load tested with k6 — 50 concurrent users, 3.5 minute sustained run.

| Metric | Result |
|--------|--------|
| Requests/sec | 60 req/s |
| p50 latency | 5.86ms |
| p95 latency | 23.55ms |
| Error rate | 0% |
| Total requests | 15,847 |
| Concurrent users | 50 |

Gateway handles 60 req/s sustained load with p95 latency under 24ms
and zero errors across 15,847 requests.

---

## Architecture
Clients (engineers, apps, CI/CD)
│
▼
┌─────────────────────────────────────────┐
│         Gateway Core (FastAPI)           │
│  Auth → Rate Limiter → Audit Logger      │
│         Smart Router                     │
│  Key Vault · Transformer · Cache         │
└─────────────────────────────────────────┘
│           │           │
OpenAI    Anthropic     Gemini
│
┌──────────────────────────────────────────┐
│  PostgreSQL  │  Redis  │  React Admin UI  │
└──────────────────────────────────────────┘

---

## What it does

**Auth** — JWT access/refresh tokens + API key auth via `X-API-Key` header.
API keys hashed with HMAC-SHA256 — a DB breach alone cannot recover keys.

**Rate limiting** — Redis sliding window. 60 req/min and 100k tokens/day
per user. Returns 429 with `Retry-After` header when exceeded.

**Smart routing** — resolves provider from model name, injects API key,
automatic fallback if provider returns 429 or 503.

**Audit logging** — every request logged to PostgreSQL. Metadata only —
never prompt or completion content stored.

**Admin dashboard** — React UI showing real-time stats, provider charts,
audit log, and user management.

---

## Quick start

```bash
# 1. Clone and set up environment
git clone https://github.com/akshata1710/nexus-llm.git
cd nexus-llm
cp .env.example .env
# Fill in SECRET_KEY and ANTHROPIC_API_KEY

# 2. Start all services
docker compose up --build

# 3. Verify
curl http://localhost:8000/health
curl http://localhost:8000/health/ready

# 4. Register and login
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"yourpass","full_name":"Your Name"}'

curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"yourpass"}'

# 5. Make an LLM request
curl -X POST http://localhost:8000/proxy/chat \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{"model":"claude-haiku-4-5","messages":[{"role":"user","content":"Hello!"}],"max_tokens":100}'

# 6. Open admin dashboard
cd admin-ui && npm install && npm run dev
# Visit http://localhost:5173
```

---

## API reference

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /health | None | Liveness probe |
| GET | /health/ready | None | Readiness — checks DB + Redis |
| POST | /auth/register | None | Create account |
| POST | /auth/login | None | Get JWT tokens |
| POST | /auth/refresh | None | Refresh access token |
| GET | /auth/me | JWT or API Key | Current user |
| POST | /keys | JWT | Create API key |
| GET | /keys | JWT | List keys |
| DELETE | /keys/{id} | JWT | Revoke key |
| POST | /keys/{id}/rotate | JWT | Rotate key (zero-downtime) |
| POST | /proxy/chat | JWT or API Key | Route LLM request |
| GET | /admin/stats | JWT | 24h usage summary |
| GET | /admin/audit-logs | JWT | Paginated request log |
| GET | /admin/users | JWT | User list |

---

## Proxy request format

```json
{
  "model": "claude-haiku-4-5",
  "messages": [
    {"role": "user", "content": "Your prompt here"}
  ],
  "max_tokens": 100,
  "temperature": 0.7
}
```

Supported models — any string containing:
- `claude` → routes to Anthropic
- `gpt` → routes to OpenAI
- `gemini` → routes to Gemini

---

## Stack

| Layer | Technology |
|-------|-----------|
| Gateway | Python 3.12, FastAPI, SQLAlchemy async |
| Auth | bcrypt, HMAC-SHA256, JWT (python-jose) |
| Database | PostgreSQL 16 |
| Cache / Rate limiting | Redis 7 |
| Frontend | React, Vite, Recharts, Tailwind CSS |
| Infrastructure | Docker, Kubernetes, GitHub Actions |
| Testing | pytest, pytest-asyncio, k6 |

---

## Security design

- Passwords hashed with bcrypt (cost factor 12)
- API keys: HMAC-SHA256 with app secret — DB compromise alone cannot recover keys
- Full key shown exactly once on creation, never stored plain
- JWT access tokens expire in 60 min, refresh tokens in 7 days
- Token type validation prevents access tokens being used as refresh tokens
- Login response identical for wrong password and nonexistent user (prevents user enumeration via timing)
- Gateway runs as non-root user in Docker
- Audit log stores metadata only — never prompt or completion content

---

## Project structure
nexus-llm/
├── gateway/
│   ├── core/           # config, database, redis, security, auth
│   ├── models/         # SQLAlchemy models (User, APIKey, AuditLog)
│   ├── routers/        # auth, keys, proxy, admin, health
│   ├── services/       # rate_limiter, router, audit
│   └── tests/          # 17 pytest tests
├── admin-ui/           # React dashboard
├── infra/
│   ├── k8s/            # Kubernetes manifests
│   └── load-tests/     # k6 load test script
├── docs/
│   └── ARCHITECTURE.md # Design decisions
└── docker-compose.yml

---

## Running tests

```bash
cd gateway
pip install -r requirements.txt aiosqlite
pytest tests/ -v
```

17 tests covering: registration, login, token refresh, token type validation,
user enumeration protection, API key creation, key-not-in-list security,
API key auth, revoke, rotate, and invalid key rejection.

---

## Kubernetes deployment

```bash
kubectl apply -f infra/k8s/namespace.yml
kubectl apply -f infra/k8s/secrets.yml
kubectl apply -f infra/k8s/postgres.yml
kubectl apply -f infra/k8s/redis.yml
kubectl apply -f infra/k8s/gateway.yml
```

Gateway deploys with 2 replicas, HPA scaling to 10 pods at 70% CPU,
liveness and readiness probes, and resource limits.

---

## Load testing

```bash
k6 run infra/load-tests/gateway.js
```

Ramps from 10 to 50 concurrent users over 3.5 minutes.
Thresholds: p95 < 2000ms, error rate < 10%.
Actual results: p95 = 23ms, error rate = 0%.

---

## Design decisions

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed explanation of:
- Why HMAC-SHA256 over plain SHA256 for API keys
- Why sliding window over fixed window for rate limiting
- Why audit logs never store prompt content
- Why two auth tracks (JWT + API key)
- Why separate liveness and readiness probes

---

## Week-by-week build

| Week | What shipped |
|------|-------------|
| 1 | Auth, API key lifecycle, Docker Compose |
| 3 | Rate limiter, smart router, audit logging, proxy endpoint |
| 4 | React admin dashboard |
| 5 | Kubernetes manifests, GitHub Actions CI/CD, k6 load testing |
