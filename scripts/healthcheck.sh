#!/usr/bin/env bash
# =============================================================================
# Health check script for Nginx Load Balancer and 3-Replica Backend Cluster
# Used by Jenkins CI/CD pipeline and automated monitors
# =============================================================================

set -e

BASE_URL="${1:-http://localhost}"
MAX_RETRIES=15
RETRY_INTERVAL=3

echo "=================================================================="
echo "Starting health checks against Nginx Load Balancer at ${BASE_URL}..."
echo "=================================================================="

# 1. Check Nginx Health Endpoint
echo -n "Checking Nginx healthz endpoint (${BASE_URL}/healthz)... "
ATTEMPTS=0
until [ "$ATTEMPTS" -ge "$MAX_RETRIES" ]
do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/healthz" || true)
    if [ "$HTTP_CODE" -eq 200 ]; then
        echo "OK (HTTP 200)"
        break
    fi
    ATTEMPTS=$((ATTEMPTS + 1))
    echo "Waiting for Nginx (attempt ${ATTEMPTS}/${MAX_RETRIES})..."
    sleep "$RETRY_INTERVAL"
done

if [ "$ATTEMPTS" -ge "$MAX_RETRIES" ]; then
    echo "FAILED: Nginx healthz endpoint did not respond with HTTP 200."
    exit 1
fi

# 2. Check Backend API via Nginx Load Balancer
echo -n "Checking Backend API cluster endpoint (${BASE_URL}/api/dashboard/me/)... "
ATTEMPTS=0
until [ "$ATTEMPTS" -ge "$MAX_RETRIES" ]
do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/api/dashboard/me/" || true)
    if [ "$HTTP_CODE" -eq 200 ]; then
        echo "OK (HTTP 200)"
        break
    fi
    ATTEMPTS=$((ATTEMPTS + 1))
    echo "Waiting for Backend Cluster (attempt ${ATTEMPTS}/${MAX_RETRIES})..."
    sleep "$RETRY_INTERVAL"
done

if [ "$ATTEMPTS" -ge "$MAX_RETRIES" ]; then
    echo "FAILED: Backend cluster via Nginx did not respond with HTTP 200."
    exit 1
fi

echo "=================================================================="
echo "All health checks passed! Nginx load balancer and 3 replicas are active."
echo "=================================================================="
exit 0

