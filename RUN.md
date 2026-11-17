# HerAI — Local Run Guide (`RUN.md`)

This guide explains step-by-step how to run HerAI locally on your machine.

---

## 1. System Requirements & Architecture

HerAI consists of two local services working together:
- **Backend**: Python 3.11+ / FastAPI running on `http://localhost:8000`
- **Frontend**: Next.js 16 (App Router) running on `http://localhost:3000`
- **Cloud Integrations (Pre-configured)**: Supabase Auth & PostgreSQL, Qdrant Cloud Vector Store, Google Gemini 2.5 AI.

| Port | Service | Tech Stack | Health Endpoint |
| :--- | :--- | :--- | :--- |
| **8000** | HerAI Backend API | Python FastAPI, Uvicorn, Pydantic v2 | `http://localhost:8000/api/v1/health` |
| **3000** | HerAI Frontend UI | Next.js 16, TypeScript, Tailwind CSS | `http://localhost:3000` |

---

## 2. Environment Configuration

The repository includes pre-configured local environment files (`.env` in the root and `frontend/.env.local`).

If you ever need to inspect or recreate them:
- **Root `.env`**: Contains backend secrets, Gemini API key, Qdrant cluster endpoint, and Supabase credentials.
- **Frontend `frontend/.env.local`**: Contains public Supabase keys and backend proxy URL:
  ```env
  NEXT_PUBLIC_SUPABASE_URL=https://jbhnfqyinngiiqbcpilt.supabase.co
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_fdSRzsljqly4ZbCEVLqaNw_wPGIc2vK
  NEXT_PUBLIC_BACKEND_API_URL=http://localhost:8000/api/v1
  NEXT_PUBLIC_APP_DISCLAIMER="HerAI is an AI-generated companion modeled after historical conversation records. It is not an actual human."
  ```

---

## 3. Quick Start: Running Native Local Development

Open two terminal tabs in `/home/manoj/Documents/HerAI`.

### Terminal 1: Backend (FastAPI API Server)

1. Navigate to the project root and activate the Python virtual environment:
   ```bash
   cd /home/manoj/Documents/HerAI
   source backend/.venv/bin/activate
   ```
2. Start the Uvicorn development server:
   ```bash
   PYTHONPATH=. uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
   ```
3. Verify the backend is healthy:
   ```bash
   curl http://localhost:8000/api/v1/health
   ```
   *Expected response:*
   ```json
   {"status":"healthy","service":"HerAI Backend","environment":"development"}
   ```
   Interactive Swagger API documentation is available at: **[http://localhost:8000/docs](http://localhost:8000/docs)**.

---

### Terminal 2: Frontend (Next.js Application)

1. Navigate to the frontend directory:
   ```bash
   cd /home/manoj/Documents/HerAI/frontend
   ```
2. Start the Next.js development server:
   ```bash
   npm run dev
   ```
3. Open your browser at: **[http://localhost:3000](http://localhost:3000)**.

---

## 4. Alternative Quick Start: Docker Compose (1 Command)

If you prefer running everything inside isolated Docker containers:

1. Ensure Docker is running on your machine.
2. From the project root, launch both services:
   ```bash
   cd /home/manoj/Documents/HerAI
   docker compose up --build
   ```
3. Once running:
   - Frontend: `http://localhost:3000`
   - Backend: `http://localhost:8000`
   - To stop: press `Ctrl+C` or run `docker compose down`.

---

## 5. Running the Automated Test Suite

HerAI comes with 36 automated unit, integration, and user-journey tests.

To run the complete test suite:
```bash
cd /home/manoj/Documents/HerAI
PYTHONPATH=. backend/.venv/bin/pytest backend/tests/
```
*Expected Result:*
```text
======================== 36 passed, 7 warnings in 6.07s ========================
```

To run individual test modules:
- WhatsApp data parser & deduplication: `PYTHONPATH=. backend/.venv/bin/pytest backend/tests/test_data_engineering.py`
- Personality & memory engine tests: `PYTHONPATH=. backend/.venv/bin/pytest backend/tests/test_phase4.py`
- Chat API & memory filtering tests: `PYTHONPATH=. backend/.venv/bin/pytest backend/tests/test_phase5.py`
- 15 Production end-to-end user journeys: `PYTHONPATH=. backend/.venv/bin/pytest backend/tests/test_production_e2e.py`

---

## 6. How to Re-Run Data Ingestion (Optional)

All 24,971 messages from the three WhatsApp archives are already parsed and indexed in `data/processed/`. If you ever want to re-execute the ingestion pipeline from scratch:

### Step A: Process Raw WhatsApp Archives
Parses the 3 ZIP files, removes duplicates, normalizes senders, and creates conversation sessions:
```bash
cd /home/manoj/Documents/HerAI
PYTHONPATH=. backend/.venv/bin/python backend/app/pipeline.py
```

### Step B: Extract Personality Profile & Relationship Memories
Calculates stylometrics and extracts evidence-grounded memories:
```bash
PYTHONPATH=. backend/.venv/bin/python backend/app/run_phase4.py
```

### Step C: Index Memories into Vector Database
Embeds approved memories into Qdrant Cloud:
```bash
PYTHONPATH=. backend/.venv/bin/python -m backend.app.memory_engine.memory_indexer
```

---

## 7. Interactive Feature Walkthrough

When you open `http://localhost:3000`:

1. **Sign In (`/login`)**:
   - Log in using your email and password, or use test credentials during local testing.
2. **Chat Interface (`/chat`)**:
   - Send messages to HerAI.
   - Responses stream in real-time using Server-Sent Events (SSE).
   - Relevant relationship memories are dynamically retrieved from Qdrant and displayed in the sidebar.
   - The persistent AI simulation disclosure banner is visible at the top.
3. **Memories Dashboard (`/memories`)**:
   - View all extracted relationship memories.
   - Filter by status: `Approved`, `Pending Review`, or `Rejected`.
   - Click to approve, reject, or edit confidence scores and notes.
4. **Personality Profile (`/personality`)**:
   - Inspect authentic partner communication metrics (burstiness: 4.85 msgs/burst, latency: 10s, top emojis, and bilingual Tamil/Tanglish vocabulary patterns).
5. **WhatsApp History Browser (`/history`)**:
   - Browse the 205 segmented historical sessions and 24,971 original WhatsApp messages with timestamp navigation.
6. **Settings & Privacy (`/settings`)**:
   - Review data protection policies, model boundaries, and export or wipe account data.

---

## 8. Troubleshooting & FAQ

### Port 8000 or 3000 is already in use
- Check what process is using the port: `lsof -i :8000` or `lsof -i :3000`.
- Kill the process or specify a different port:
  - Backend: `uvicorn backend.app.main:app --port 8001` (update `NEXT_PUBLIC_BACKEND_API_URL` in `frontend/.env.local`).
  - Frontend: `npm run dev -- -p 3001`.

### Offline / Fallback Mode
If your machine is offline or cannot connect to Qdrant Cloud:
- The backend automatically falls back to an in-memory vector index without throwing errors or crashing.
- Chat will continue to function normally using local conversation memory.

### CORS Errors
- By default in development, CORS is configured to accept requests from `http://localhost:3000` and `http://127.0.0.1:3000`.
- If accessing from a custom IP or domain, add it to `ALLOWED_ORIGINS` in your `.env`.
