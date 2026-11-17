# Sakthi GPT (HerAI) - Production Deployment Guide
**Render (Backend Engine) & Vercel (Next.js Frontend)**

---

## 1. Architecture Overview

- **Backend**: FastAPI running with Uvicorn on **Render** (Web Service).
- **Frontend**: Next.js 16 (App Router) on **Vercel** with full WhatsApp UI and secret locked vault support.
- **Repository**: [https://github.com/Manoj1832/Deep-Conversation-Intelligence---RAG.git](https://github.com/Manoj1832/Deep-Conversation-Intelligence---RAG.git)
- **Security & Data Hiding**:
  - Implements Object-Oriented `SensitiveDataVault` (dunder attribute encapsulation, property getters, repr masking).
  - Implements `DataSanitizer` (scrubs phone numbers, emails, system paths).
  - Strict `.gitignore` policy isolating `.env`, `data/raw/`, `zip/`, and credentials.

---

## 2. Backend Deployment on Render

### Step A: Connect Repository
1. Log in to [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** $\rightarrow$ **Web Service**.
3. Select your GitHub repository: `Manoj1832/Deep-Conversation-Intelligence---RAG`.

### Step B: Build & Runtime Settings
The root of the repository includes `render.yaml` which automatically configures the service:
- **Name**: `herai-backend`
- **Runtime**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
- **Health Check Path**: `/health`

### Step C: Environment Variables (Render Dashboard $\rightarrow$ Environment)
Add the following secret keys in the Render environment variables tab:
| Variable Name | Example / Value | Description |
|---|---|---|
| `ENVIRONMENT` | `production` | Production environment flag |
| `ALLOWED_ORIGINS` | `https://*.vercel.app,http://localhost:3000` | Allowed CORS origins (add your Vercel URL) |
| `GEMINI_API_KEY` | `AIzaSy...` | Google Gemini API Key |
| `GEMINI_CHAT_MODEL` | `gemini-3.5-flash-lite` | Primary fast conversational model |
| `GROQ_API_KEY` | `gsk_...` | Groq API Key |
| `GROQ_MODEL` | `qwen/qwen3.8-27b` | Groq high-accuracy model |
| `SUPABASE_URL` | `https://your-proj.supabase.co` | Supabase URL (Optional) |
| `SUPABASE_SECRET_KEY` | `your-secret-key` | Supabase service key (Optional) |
| `QDRANT_URL` | `https://your-cluster.qdrant.io` | Qdrant vector database URL (Optional) |
| `QDRANT_API_KEY` | `your-api-key` | Qdrant API key (Optional) |

Once deployed, Render will provide a service URL:
`https://herai-backend.onrender.com`

---

## 3. Frontend Deployment on Vercel

### Step A: Import Project
1. Log in to [Vercel Dashboard](https://vercel.com/).
2. Click **Add New...** $\rightarrow$ **Project**.
3. Select `Manoj1832/Deep-Conversation-Intelligence---RAG`.
4. Set **Root Directory** to `frontend`.

### Step B: Build Settings
- **Framework Preset**: Next.js
- **Build Command**: `npm run build`
- **Output Directory**: `.next`
- **Install Command**: `npm install`

### Step C: Environment Variables (Vercel Project Settings)
Add these environment variables to Vercel:
| Variable Name | Value | Purpose |
|---|---|---|
| `INTERNAL_BACKEND_URL` | `https://herai-backend.onrender.com/api/v1` | Server-side Next.js rewrite proxy target |
| `NEXT_PUBLIC_BACKEND_API_URL` | `/api/backend` | Client-side API relative route (no CORS, mobile ready) |

Click **Deploy**.

---

## 4. Special Features

### 1. Secret Locked History Vault (`"kannachi"`)
- In the left sidebar search bar, typing **`kannachi`** (case-insensitive) triggers the secret vault.
- The vault opens a secure modal showing:
  - All 205 chronological conversation sessions.
  - Message breakdowns (Sakthi messages vs Manoj messages).
  - Full unredacted chronological transcript reader between Manoj and Sakthi.
- Clicking **Lock & Close** immediately re-locks the vault and resets the search query.

### 2. Mobile PWA & WhatsApp Experience
- Fully optimized responsive layout with `100dvh` support for iOS Safari and Android Chrome.
- Quick audio/voice note button, photo/emoji-sticker upload, reaction bar (❤️, 😂, 🥺, 🙄, 👍), and inline message editing.
