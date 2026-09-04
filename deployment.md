# SatQuery AI — Deployment, CI/CD & Autonomous Building Pipeline

**Document Target:** Automated Continuous Integration, Continuous Deployment (CI/CD), Containerization, and Autonomous Claude Execution Setup for SatQuery AI (SIH26167).

---

## 1. Overview & Deployment Strategy

To ensure SatQuery AI can be built autonomously and deployed cleanly, the infrastructure uses a containerized, API-first deployment stack:

- **Backend Service:** FastAPI + Rasterio + GDAL + LangGraph + PyTorch running inside a CUDA/CPU-optimized Docker container.
- **Frontend Console:** React + Vite + MapLibre GL compiled to static assets and served via Nginx.
- **CI/CD Automation:** GitHub Actions pipeline running unit tests (`pytest`), geospatial integrity checks, Docker builds, and automated server deployment.
- **Autonomous Build Agent Loop:** Autonomous execution instructions allowing Claude Code to read `plan.md`, implement code, run self-checks, commit to git, and trigger deployment automatically.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      AUTONOMOUS BUILDING & CI/CD LOOP                   │
├─────────────────────────────────────────────────────────────────────────┤
│ 1. Claude Execution Agent reads current pending task in plan.md         │
│ 2. Writes code implementation in backend/ or frontend/                  │
│ 3. Executes self-checks & automated pytest suite                        │
│ 4. Commits code & pushes to GitHub repository                           │
│ 5. GitHub Actions runs CI pipeline (Linting ➔ Tests ➔ Docker Build)    │
│ 6. Auto-deploys updated container to staging/production server          │
│ 7. Agent marks task complete in plan.md and moves to next task          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Containerization Setup

### A. Backend Dockerfile (`backend/Dockerfile`)

```dockerfile
FROM python:3.11-slim

# Install system GDAL and Geospatial C dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin \
    libgdal-dev \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set GDAL environment variables
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

WORKDIR /app

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### B. Frontend Dockerfile (`frontend/Dockerfile`)

```dockerfile
# Stage 1: Build static React bundle
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: Serve via Nginx
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### C. Docker Compose Setup (`docker-compose.yml`)

```yaml
version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - ENV=production
      - LOG_LEVEL=info
    volumes:
      - ./data/sample_rasters:/app/data/sample_rasters
    restart: always

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "80:80"
    depends_on:
      - backend
    restart: always
```

---

## 3. GitHub Actions CI/CD Pipeline (`.github/workflows/ci-cd.yml`)

Save this file as `.github/workflows/ci-cd.yml` in your repository. Every git push triggers automated testing, container build, and deployment.

```yaml
name: SatQuery AI CI/CD Pipeline

on:
  push:
    branches: [ main, dev ]
  pull_request:
    branches: [ main ]

jobs:
  test-backend:
    name: Run Backend Spatial & Agent Unit Tests
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install System GDAL
        run: |
          sudo apt-get update
          sudo apt-get install -y gdal-bin libgdal-dev

      - name: Install Python Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install pytest pytest-cov rasterio numpy fastapi httpx langgraph

      - name: Run Pytest Suite
        run: |
          pytest backend/tests/ --doctest-modules --junitxml=junit/test-results.xml

  build-and-deploy:
    name: Build Docker Images & Deploy
    needs: test-backend
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Log in to GitHub Container Registry (GHCR)
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build & Push Backend Container
        uses: docker/build-push-action@v5
        with:
          context: ./backend
          push: true
          tags: ghcr.io/${{ github.repository }}/backend:latest

      - name: Build & Push Frontend Container
        uses: docker/build-push-action@v5
        with:
          context: ./frontend
          push: true
          tags: ghcr.io/${{ github.repository }}/frontend:latest

      - name: Deploy to Staging / Production via SSH
        uses: appleboy/ssh-action@v1.0.0
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /opt/satquery-ai
            docker compose pull
            docker compose up -d --remove-orphans
```

---

## 4. Autonomous Claude Agent Execution Protocol

To let Claude build the product autonomously task-by-task:

### The Autonomous Loop Shell Command
Run this in your terminal to allow Claude Code to work continuously through `plan.md`:

```bash
# Execute autonomous build loop
claude -p "Read plan.md, pick the next uncompleted task, implement code, run tests, update plan.md status to completed, commit changes, and continue until all tasks are done."
```

### Self-Correction & Auto-Verification Protocol
For every task executed autonomously:
1. **Implement:** Write code in `backend/` or `frontend/`.
2. **Test:** Run local verification (`pytest backend/tests/`).
3. **Handle Blockers:** If a test fails or a dependency error occurs, Claude automatically adjusts the implementation or modifies the deliverable approach in `plan.md`.
4. **Commit:** Execute git commit: `git commit -m "feat: complete Day X task - [Task Name]"`.
5. **Deploy Verification:** GitHub Actions CI automatically runs and verifies the container build.
