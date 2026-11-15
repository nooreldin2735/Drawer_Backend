# CanvasDrawer DevOps Architecture: Nginx Load Balancer & Jenkins CI/CD

This document details the high-availability 3-replica backend architecture, Nginx reverse proxy configuration, and the automated Jenkins CI/CD pipeline for the collaborative Whiteboard project.

---

## 1. System Architecture

Traffic flows through an **Nginx Reverse Proxy & Load Balancer** that distributes incoming REST API and WebSocket connections across **3 backend replicas** (`backend-1`, `backend-2`, `backend-3`).

```mermaid
flowchart TD
    Client["Clients / Browsers"] -->|Port 80 (HTTP & WS)| Nginx["Nginx Load Balancer (Port 80)"]

    subgraph Cluster["3-Replica High-Availability Backend Cluster"]
        Nginx -->|/api & /ws (ip_hash)| B1["backend-1:8000 (Daphne/ASGI)"]
        Nginx -->|/api & /ws (ip_hash)| B2["backend-2:8000 (Daphne/ASGI)"]
        Nginx -->|/api & /ws (ip_hash)| B3["backend-3:8000 (Daphne/ASGI)"]
    end

    subgraph FrontendService["Frontend"]
        Nginx -->|/ (Static & HMR)| FE["frontend:5173 (Vite React)"]
    end

    subgraph StateAndCache["Shared State & Synchronization"]
        B1 & B2 & B3 <-->|Channel Layer Pub/Sub| Redis[("Redis (Port 6379)\nCross-Replica Sync")]
        B1 & B2 & B3 <-->|Durable Storage| Postgres[("PostgreSQL (Port 5432)\nWhiteboards & Versions")]
    end
```

### Key Architectural Highlights
1. **Cross-Replica WebSocket Synchronization**:
   - WebSockets are handled by Django Channels using `channels_redis`.
   - When User A connects to `backend-1` and User B connects to `backend-3`, drawing operations and cursor movements are broadcast through Redis to room `board_<id>`, ensuring real-time multi-user collaboration across replicas.
2. **Session Affinity via `ip_hash`**:
   - Nginx uses `ip_hash;` in `backend_cluster` to preserve session affinity while distributing traffic evenly.
3. **Migration Locking**:
   - The `migration` service runs schema migrations once before the 3 backend replicas start, preventing database migration race conditions.

---

## 2. Nginx Load Balancer Configuration

Located in [`nginx/nginx.conf`](./nginx/nginx.conf):

```nginx
upstream backend_cluster {
    ip_hash;
    server backend-1:8000 max_fails=3 fail_timeout=10s;
    server backend-2:8000 max_fails=3 fail_timeout=10s;
    server backend-3:8000 max_fails=3 fail_timeout=10s;
    keepalive 32;
}
```

- **Route `/api/`**: Proxies REST endpoints (authentication, invite codes, whiteboard CRUD) to `backend_cluster`.
- **Route `/ws/`**: Proxies WebSocket connections with `Upgrade` and `Connection: "upgrade"` headers and extended timeouts (`proxy_read_timeout 86400s`).
- **Route `/`**: Proxies frontend traffic to `frontend:5173`.
- **Route `/healthz`**: Lightweight healthcheck endpoint returning HTTP 200 for pipeline monitoring.

---

## 3. Jenkins CI/CD Pipeline

The declarative pipeline is defined in [`Jenkinsfile`](./Jenkinsfile).

### Pipeline Stages

| Stage | Name | Description |
|---|---|---|
| 1 | **Checkout SCM** | Clones/fetches the latest code from Git. |
| 2 | **Static Analysis & Linting** | Validates Python syntax bytecode (`compileall`) and runs TypeScript production build checks. |
| 3 | **Automated Tests** | Runs Django test suite (auth, invite codes, access controls, and WebSocket communicator tests). |
| 4 | **Validate & Build Cluster** | Validates `docker-compose.yml` syntax and builds Docker images. |
| 5 | **Deploy 3-Replica Cluster** | Runs database migrations and starts `backend-1`, `backend-2`, `backend-3`, `redis`, `postgres`, `frontend`, and `nginx`. |
| 6 | **Smoke Test & Health Check** | Runs `scripts/healthcheck.sh` against Nginx (`/healthz` and `/api/dashboard/me/`). |

---

## 4. Setting Up Jenkins

### Step 1: Install Required Jenkins Plugins
In Jenkins (`Manage Jenkins -> Plugins -> Available Plugins`):
- **Pipeline**
- **Docker Pipeline**
- **Git Plugin**
- **AnsiColor**

### Step 2: Grant Docker Permissions to Jenkins Agent
Ensure the Jenkins user has permissions to run Docker:
```bash
sudo usermod -aG docker jenkins
sudo systemctl restart jenkins
```

### Step 3: Create Jenkins Pipeline Job
1. In Jenkins dashboard, click **New Item**.
2. Enter item name (e.g. `canvas-drawer-pipeline`), select **Pipeline**, and click **OK**.
3. Under **Build Triggers**:
   - Check **GitHub hook trigger for GITScm polling** (or GitLab webhook).
4. Under **Pipeline**:
   - Definition: **Pipeline script from SCM**
   - SCM: **Git**
   - Repository URL: `<your-git-repository-url>`
   - Branch Specifier: `*/main`
   - Script Path: `Jenkinsfile`
5. Click **Save**.

### Step 4: Configure Webhook (GitHub / GitLab)
- Go to your repository settings -> **Webhooks** -> **Add Webhook**.
- Payload URL: `http://<your-jenkins-host>:8080/github-webhook/`
- Content type: `application/json`
- Events: **Pushes** and **Pull Requests**.

---

## 5. Local Execution & Verification

### Running the Cluster Locally with Docker Compose
```bash
# Build and start the entire 3-replica cluster + Nginx
docker compose up -d

# Inspect status of all services (Nginx, 3 backend replicas, frontend, DB, Redis)
docker compose ps
```

### Running the Health Check Script
```bash
./scripts/healthcheck.sh http://localhost
```

### Running Tests Locally
```bash
cd CanvasDrawerProject
/home/noor/Projects/CanvasDrawer/bin/python manage.py test
```

