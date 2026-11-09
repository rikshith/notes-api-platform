# notes-api

A tiny FastAPI app (Postgres + optional Redis) used as a practice target for DevOps/SRE work.
It contains **only app code**: no Dockerfile, CI config, Terraform or Kubernetes files.
Adding those is the exercise.

## Run locally (no Docker needed)
    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements-dev.txt
    uvicorn app.main:app --reload      # uses SQLite by default
    pytest

Interactive docs: http://localhost:8000/docs

## Configuration (environment variables)
| Variable | Default | Purpose |
|---|---|---|
| DATABASE_URL | sqlite:///./notes.db | e.g. postgresql://user:pass@host:5432/notes |
| REDIS_URL | (unset = no cache) | e.g. redis://host:6379/0 |
| CACHE_TTL_SECONDS | 60 | cache lifetime for GET /notes/{id} |
| ERROR_RATE | 0 | fraction of /notes requests that return 500 |
| EXTRA_LATENCY_MS | 0 | delay added to every /notes request |
| MAX_LEAK_MB | 512 | safety cap for the /leak drill |

## Endpoints
- `GET /health` liveness, `GET /ready` readiness (checks DB and Redis)
- `POST /notes`, `GET /notes`, `GET /notes/{id}`
- `GET /metrics` Prometheus metrics

## Failure drills
- `GET /slow?ms=2000` latency
- `GET /error?rate=0.3` random 500s
- `GET /cpu?seconds=20` CPU burn
- `GET /leak?mb=100`, `POST /leak/clear` memory growth
- Set `ERROR_RATE` or `EXTRA_LATENCY_MS` via config to simulate a bad release

## Your tasks
Dockerfile, CI (Jenkins and GitHub Actions), Terraform (VPC, EKS, RDS, ECR),
Helm chart, ArgoCD, Prometheus/Grafana dashboards and SLO alerts, security scans,
runbooks and postmortems.
