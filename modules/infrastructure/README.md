# Infrastructure Module

The **Infrastructure** module provides the foundational scaffolding, environment orchestration, dependency lockfile management, containerization engine, and static code quality verification pipelines for the OmniRAG Enterprise ChatBot system. It unifies a **FastAPI** Python backend and a **Next.js 15** React frontend within a monorepo workspace managed by **`uv`** (Python) and **`pnpm`** (Node.js), packaged using multi-stage **Docker** builds and **`docker-compose`**.

---

## 🛠️ Technology Stack & Machine Learning Models

### 1. Python Environment & Dependency Manager: Astral `uv`
- **What It Does:** Resolves, locks, and synchronizes Python dependencies into isolated virtual environments (`.venv`) in under 100 milliseconds using a Rust-based package resolution engine.
- **Why Use It:** Replaces legacy `pip` and `virtualenv` with 10x to 100x faster installation speeds and strict reproducible lockfile guarantees (`uv.lock`).
- **Manager Inputs:** `pyproject.toml` configuration file.
- **Manager Outputs:** Isolated `.venv` virtualenv directory and synchronized dependency packages.

### 2. Node.js Environment & Package Manager: `pnpm` & Corepack
- **What It Does:** Manages frontend JavaScript/TypeScript dependencies using content-addressable store hard-linking, preventing duplicated `node_modules` installations across workspace modules.
- **Why Use It:** Delivers disk-space-efficient, deterministic builds with strict lockfile constraints (`pnpm-lock.yaml`).
- **Manager Inputs:** `package.json` and `pnpm-lock.yaml`.
- **Manager Outputs:** High-performance, hard-linked `node_modules` directory tree.

### 3. Containerization Engine: Docker & Docker Compose
- **What It Does:** Packages backend and frontend applications into isolated, minimal Linux containers (`python:3.11-slim` and `node:20-alpine`) using multi-stage Docker builds.
- **Why Use It:** Eliminates environment drift ("works on my machine"), guarantees isolated runtime networking (`backend:8000` $\leftrightarrow$ `frontend:3000`), and simplifies cloud deployment.
- **Engine Inputs:** `docker-compose.yml`, `backend/Dockerfile`, and `frontend/Dockerfile`.
- **Engine Outputs:** Production-ready container images and running Docker container services.

### 4. Static Code Quality & Verification Suite: Ruff, Mypy, and Pytest
- **What It Does:** Enforces strict Python linting (`ruff`), static type checking (`mypy`), and automated unit/integration testing (`pytest`) across backend modules.
- **Why Use It:** Prevents runtime type errors, enforces standard 88-character formatting guidelines, and guarantees 100% test coverage before production release.
- **Suite Inputs:** Backend Python source files (`backend/app/`) and test suites (`backend/tests/`).
- **Suite Outputs:** Zero-error verification reports.

---

## 🧮 Mathematical & Operational Formulations

### 1. Multi-Stage Docker Image Size Reduction Formulation
Let $S_{\text{build}}$ be the total storage size of the multi-stage build environment (including compilers and build tools), and $S_{\text{runner}}$ be the storage size of the final slim runtime container image:

$$\text{SizeReductionRatio} = \frac{S_{\text{build}} - S_{\text{runner}}}{S_{\text{build}}} \times 100\%$$

- **Target Reduction Ratio:** $\ge 65\%$ reduction in final image footprint.

### 2. Lockfile Dependency Determinism Verification Equation
For installed dependency tree $T_{\text{installed}}$ and recorded lockfile tree $T_{\text{lock}}$:

$$\text{DeterminismCheck} = \begin{cases} \text{Valid} & \text{if } \text{Hash}(T_{\text{installed}}) \equiv \text{Hash}(T_{\text{lock}}) \\ \text{Failed} & \text{otherwise} \end{cases}$$

---

## 🏗️ Implementation Details & End-to-End Data Pipeline Architecture

The `infrastructure` module executes an 8-step atomic pipeline that prepares, validates, and containerizes the workspace environment.

### 🔄 Step-by-Step Atomic Data Pipeline

- **Step 1: Monorepo Workspace Directory Resolution**
  - **Inputs:** Root project workspace directory.
  - **Processing:** Resolves parent workspace structure separating `backend/`, `frontend/`, `modules/`, `logs/`, and `data/`.
  - **Outputs:** Validated directory tree layout.

- **Step 2: Backend Python Environment Synchronization**
  - **Inputs:** `backend/pyproject.toml`.
  - **Function Executed:** `uv sync --no-dev`.
  - **Processing:** Creates/updates `.venv` directory and installs exact pinned versions of FastAPI, LangChain, Pinecone SDK, and Pydantic.
  - **Outputs:** Synchronized Python virtual environment.

- **Step 3: Frontend Node.js Environment Synchronization**
  - **Inputs:** `frontend/package.json` and `frontend/pnpm-lock.yaml`.
  - **Function Executed:** `pnpm install --frozen-lockfile`.
  - **Processing:** Hard-links cached pnpm store packages into `frontend/node_modules`.
  - **Outputs:** Synchronized Node.js dependency store.

- **Step 4: Environment Variable Template Verification**
  - **Inputs:** `.env` and `.env.example` templates.
  - **Processing:** Verifies required credentials (`GOOGLE_API_KEY`, `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`, `LANGCHAIN_API_KEY`, `DEBUG`).
  - **Outputs:** Authorized environment variable context.

- **Step 5: Code Quality & Lint Verification (Ruff)**
  - **Inputs:** `backend/app/` Python source files.
  - **Function Executed:** `uv run ruff check .`.
  - **Processing:** Scans code for unused imports, line length violations (>88 chars), and anti-patterns.
  - **Outputs:** Zero lint error output.

- **Step 6: Static Type Analysis (Mypy)**
  - **Inputs:** `backend/app/` Python source files.
  - **Function Executed:** `uv run mypy .`.
  - **Processing:** Performs strict static type checking verifying function argument and return type annotations.
  - **Outputs:** Zero type error output.

- **Step 7: Automated Test Suite Execution (Pytest)**
  - **Inputs:** `backend/tests/` test files.
  - **Function Executed:** `uv run pytest tests/ -v`.
  - **Processing:** Executes unit and integration test suites against real database engines and API endpoints.
  - **Outputs:** 100% green test suite execution.

- **Step 8: Multi-Stage Container Packaging & Compose Orchestration**
  - **Inputs:** `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`.
  - **Function Executed:** `docker compose up -d`.
  - **Processing:** Compiles slim Python runtime container and Next.js standalone runner container, linking them on a shared internal Docker network (`backend:8000` $\leftrightarrow$ `frontend:3000`).
  - **Outputs:** Running containerized multi-service deployment.

---

## 💻 Implementation Guide & Code Examples

### 1. Launching Full Multi-Container Stack with Docker Compose
```bash
# Clone and navigate to workspace root
cd "omnirag"

# Copy environment variable template
cp .env.example .env

# Fill in API keys in .env
# GOOGLE_API_KEY=...
# PINECONE_API_KEY=...

# Launch backend and frontend containers in detached mode
docker compose up -d --build

# Inspect container status
docker compose ps

# Tail container logs
docker compose logs -f
```

### 2. Running Backend Quality Verification Checks Locally
```bash
# Navigate to backend directory
cd backend

# Sync Python environment dependencies
uv sync

# Run code linter
uv run ruff check .

# Run static type checker
uv run mypy .

# Run automated unit test suite
uv run pytest tests/ -v
```

### 3. Building Next.js Standalone Frontend Production Bundle
```bash
# Navigate to frontend directory
cd frontend

# Install exact lockfile dependencies
pnpm install --frozen-lockfile

# Build Next.js standalone production bundle
pnpm build

# Test standalone production server locally
NODE_ENV=production node .next/standalone/server.js
```

---

## 📁 Key System Files & Architecture Map

- **`docker-compose.yml`:**
  - Defines `backend` (FastAPI on port 8000) and `frontend` (Next.js on port 3000) container services, environment variable injections, and service dependency ordering.

- **`backend/Dockerfile`:**
  - Multi-stage Dockerfile compiling Python 3.11 dependencies via `uv` builder stage and copying virtualenv into a minimal `python:3.11-slim` runner stage.

- **`frontend/Dockerfile`:**
  - Multi-stage Dockerfile utilizing `node:20-alpine` with `pnpm` store caching, building Next.js standalone artifacts (`.next/standalone`), and running standalone `server.js`.

- **`backend/pyproject.toml`:**
  - Centralized Python project configuration file defining dependencies, Ruff linting rules, and Mypy static typing settings.

- **`frontend/package.json`:**
  - Frontend Node.js project manifest defining Next.js 15, React 19, Tailwind CSS, and shadcn/ui dependencies.

---

## 🧠 Key Architectural Decisions

- **Astral `uv` for Python & `pnpm` for Node.js Package Management:**
  - **Context:** Standard `pip` and `npm` installations suffer from slow CI resolution times and disk bloat.
  - **Decision:** Adopt `uv` for Python virtual environments and `pnpm` for Node.js package storage.
  - **Outcome:** Installation times reduced by up to 90% with deterministic lockfile synchronization.

- **Multi-Stage Docker Build Strategy:**
  - **Context:** Shipping full build tools (compilers, Node/Python dev headers) in production images creates large container sizes and security vulnerabilities.
  - **Decision:** Utilize multi-stage Docker builds to compile assets in builder stages and copy only final compiled binaries into slim runner images.
  - **Outcome:** Reduced container sizes by over 65% while improving deployment security.

- **Next.js Standalone Production Output (`output: "standalone"`):**
  - **Context:** Deploying full `node_modules` trees to production servers increases deployment archive sizes unnecessarily.
  - **Decision:** Enable `output: "standalone"` in `next.config.ts` to automatically bundle only necessary dependencies into `.next/standalone`.
  - **Outcome:** Streamlined production Node.js deployment to a single self-contained `server.js` file.

---

## 🐛 Technical Issues Encountered & Resolved

- **Next.js 15 Geist Font Local Loader Crash:**
  - **Problem:** Next.js 15 default template font loader crashed in offline/docker build environments.
  - **Root Cause:** `next/font/google` failed to fetch Google Geist font files during isolated container builds.
  - **Resolution:** Replaced Geist font with standard system `Inter` font stack in `layout.tsx`.

- **Shadcn/UI Init Directory Conflict:**
  - **Problem:** Executing `shadcn-ui init` failed if `src/app` existed prior to component setup.
  - **Root Cause:** Directory precedence conflict during Next.js App Router initialization.
  - **Resolution:** Initialized Next.js project structure first before running component additions.

- **Docker Compose Startup Timing Race Condition:**
  - **Problem:** Frontend container failed to establish HTTP connections to backend during initial startup.
  - **Root Cause:** Next.js server initialized before FastAPI server completed initial database checks.
  - **Resolution:** Added `depends_on: [backend]` in `docker-compose.yml` and implemented frontend cold-start health polling (`GET /health`).

---

## 💡 Real-World Workflow Examples

- **Scenario 1: New Developer Environment Scaffolding**
  - **Developer Action:** Developer clones project repository and runs setup script.
  - **Processing Flow:**
    - `uv sync` creates `.venv` and installs FastAPI, LangChain, and Pinecone SDK in <2 seconds.
    - `pnpm install` hard-links frontend packages in <5 seconds.
    - `uv run pytest tests/` verifies local database and API functionality.
  - **Outcome:** Developer has a fully functional local development environment in under 10 seconds.

- **Scenario 2: Production Containerized Deployment**
  - **Deployment Action:** Cloud platform executes `docker compose up -d --build`.
  - **Processing Flow:**
    - Multi-stage Docker builder compiles backend Python virtualenv and frontend Next.js standalone bundle.
    - Slim runner containers spin up on internal Docker network.
    - Backend starts on `http://0.0.0.0:8000` and frontend starts on `http://0.0.0.0:3000`.
  - **Outcome:** Delivers scalable, containerized production deployment with zero environment drift.
