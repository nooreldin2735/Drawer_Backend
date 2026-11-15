#!/usr/bin/env bash
# =============================================================================
# Deployment Script for 3-Replica CanvasDrawer Architecture
# Used by Jenkins CI/CD pipeline
# =============================================================================

set -e

COMPOSE_FILE="${1:-docker-compose.yml}"

echo "=================================================================="
echo "Deploying CanvasDrawer via Docker Compose with 3 Backend Replicas"
echo "Compose File: ${COMPOSE_FILE}"
echo "=================================================================="

# 1. Pull latest images or build
echo "1. Building Docker containers..."
docker compose -f "${COMPOSE_FILE}" build

# 2. Start database and cache services first
echo "2. Ensuring Postgres & Redis are up and healthy..."
docker compose -f "${COMPOSE_FILE}" up -d postgres redis

# 3. Run database migrations before starting backend replicas
echo "3. Running database migrations..."
docker compose -f "${COMPOSE_FILE}" run --rm migration

# 4. Start all 3 backend replicas
echo "4. Starting backend replicas (backend-1, backend-2, backend-3)..."
docker compose -f "${COMPOSE_FILE}" up -d backend-1 backend-2 backend-3

# 5. Start frontend and Nginx load balancer
echo "5. Starting frontend and Nginx load balancer..."
docker compose -f "${COMPOSE_FILE}" up -d frontend nginx

# 6. Verify container states
echo "6. Active container status:"
docker compose -f "${COMPOSE_FILE}" ps

echo "=================================================================="
echo "Deployment completed successfully!"
echo "=================================================================="

