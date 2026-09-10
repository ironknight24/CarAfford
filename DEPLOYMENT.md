# CarAfford Production Deployment Guide

This guide documents the procedures for deploying the **CarAfford** platform to production environments using containerized microservices and automated infrastructure orchestrations.

---

## Architecture Overview

```
[ Internet / Client Devices ]
              |
              v (HTTPS :443)
       [ NGINX Reverse Proxy ]
        /                   \
       /                     \
      v                       v
[ Next.js Frontend ]    [ FastAPI Backend ]
  (:3000 Node.js)         (:8000 Uvicorn / Async)
                              |           \
                              |            \
                              v             v
                       [ PostgreSQL 16 ]  [ Redis 7 ]
```

---

## 1. Prerequisites

- **Docker Engine** >= 24.0.0
- **Docker Compose** >= 2.20.0
- **Domain Name & SSL Certificates** (Let's Encrypt / Certbot or Managed Cloud Load Balancer)
- PostgreSQL & Redis instances (Containerized or Managed Cloud RDS / Memorystore)

---

## 2. Environment Configuration

CarAfford enforces fail-fast production configuration validation. Copy `.env.example` to `.env` on your target deployment server and configure production secrets:

```bash
cp .env.example .env
chmod 600 .env
```

### Critical Production Environment Variables

| Variable | Description | Production Requirement |
| :--- | :--- | :--- |
| `ENVIRONMENT` | Deployment stage | Must be set to `production` |
| `DEBUG` | FastAPI debug mode | Must be set to `false` |
| `SECRET_KEY` | JWT signing secret | Must be a unique 64+ char random token (`openssl rand -hex 32`) |
| `POSTGRES_PASSWORD` | Database credentials | Strong alphanumeric + special password |
| `ADMIN_DEFAULT_PASSWORD` | Initial admin portal password | Change immediately after deployment |
| `CORS_ORIGINS` | Permitted client origins | Explicit domains (e.g. `["https://carafford.in"]`), **no wildcards (`*`)** |

---

## 3. Production Build & Launch

Run the hardened production compose stack:

```bash
# 1. Build and launch production containers in detached mode
docker compose -f docker-compose.prod.yml up -d --build

# 2. Verify container health status
docker compose -f docker-compose.prod.yml ps

# 3. View live application logs
docker compose -f docker-compose.prod.yml logs -f backend
```

---

## 4. Database Migrations & Seeding

Migrations and initial master data seeding execute automatically on backend container startup. To manually run migrations:

```bash
# Run latest Alembic migrations
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head

# Verify migration history
docker compose -f docker-compose.prod.yml exec backend alembic current
```

---

## 5. SSL / TLS Termination

The bundled `nginx/nginx.conf` acts as the ingress controller. For production TLS:

1. Mount SSL certificates into `/etc/nginx/certs/`
2. Uncomment the HTTPS server block in `nginx/nginx.conf`
3. Reload NGINX:
   ```bash
   docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
   ```

---

## 6. Health Checks & Probes

| Probe Endpoint | Purpose | Target Port |
| :--- | :--- | :--- |
| `GET /health/live` | Kubernetes / Cloud Liveness probe (HTTP 200) | `8000` |
| `GET /health/ready` | Readiness probe (validates DB & Redis connectivity) | `8000` |
| `GET /health/metrics` | System telemetry & cache statistics | `8000` |
