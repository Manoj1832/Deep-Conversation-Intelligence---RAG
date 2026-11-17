# HerAI — Production Environment Setup Guide

**Version:** 1.0.0  
**Status:** Approved Specification  
**Author:** DevOps & Application Security Engineer  

---

## 1. Environment Separation Principles

HerAI strictly decouples **Development** from **Production** environments:
- **Development**: Permits local fallback endpoints, verbose diagnostic logging, and local SQLite/memory fallback stores for offline testing.
- **Production**: Enforces mandatory validation of cloud secrets at startup, enables strict CORS origin checking, activates HTTPS reverse proxy headers, and masks all message text from operational logs.

---

## 2. Environment Variables Matrix

### 2.1. Backend Production Environment Variables (`backend/.env`)

| Variable | Description | Required in Production | Sample / Default |
| :--- | :--- | :---: | :--- |
| `ENVIRONMENT` | Operating environment (`production` or `development`) | **YES** | `production` |
| `LOG_LEVEL` | Logging verbosity (`INFO`, `WARNING`, `ERROR`) | **YES** | `INFO` |
| `BACKEND_HOST` | Bind IP address for Uvicorn | **YES** | `0.0.0.0` |
| `BACKEND_PORT` | Port number for Uvicorn | **YES** | `8000` |
| `ALLOWED_ORIGINS` | Comma-delimited list of permitted CORS frontend origins | **YES** | `https://herai.app,https://www.herai.app` |
| `SUPABASE_URL` | Cloud Supabase project endpoint | **YES** | `https://jbhnfqyinngiiqbcpilt.supabase.co` |
| `SUPABASE_ANON_KEY` | Public Supabase client key | **YES** | `sb_publishable_...` |
| `SUPABASE_SERVICE_ROLE_KEY` | Private Supabase admin key (backend only!) | **YES** | `eyJhbGci...` |
| `SUPABASE_DB_URL` | Direct PostgreSQL connection string | Optional (Direct ORM) | `postgresql://postgres:[PASSWORD]@...` |
| `QDRANT_URL` | Qdrant Cloud cluster endpoint | **YES** | `https://f76e7661-....aws.cloud.qdrant.io` |
| `QDRANT_API_KEY` | Qdrant Cloud cluster API key | **YES** | `eyJhbGci...` |
| `GEMINI_API_KEY` | Google Cloud Gemini API key (backend only!) | **YES** | `AQ.Ab8RN6...` |
| `GEMINI_CHAT_MODEL` | Foundation model for streaming chat | **YES** | `gemini-2.5-flash` |
| `GEMINI_REASONING_MODEL`| Model for memory and topic reasoning | **YES** | `gemini-2.5-pro` |
| `GEMINI_EMBEDDING_MODEL`| Model for vector representations | **YES** | `text-embedding-004` |

---

### 2.2. Frontend Production Environment Variables (`frontend/.env.production`)

| Variable | Description | Client Exposed | Sample Value |
| :--- | :--- | :---: | :--- |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase Cloud project endpoint | **YES** | `https://jbhnfqyinngiiqbcpilt.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Public client publishable key | **YES** | `sb_publishable_fdSRzsljqly4ZbCEVLqaNw_wPGIc2vK` |
| `NEXT_PUBLIC_BACKEND_API_URL` | Production URL of the FastAPI backend | **YES** | `https://api.herai.app/api/v1` |
| `NEXT_PUBLIC_APP_DISCLAIMER` | Persistent transparency disclosure | **YES** | `"HerAI is an AI-generated companion simulation."` |

> [!CAUTION]
> **Zero Leakage Rule**: Never prepend `NEXT_PUBLIC_` to `GEMINI_API_KEY`, `QDRANT_API_KEY`, or `SUPABASE_SERVICE_ROLE_KEY`. Doing so bakes sensitive credentials into the browser bundle.

---

## 3. Startup Validation & Safe Failure Protocol

When `ENVIRONMENT=production` is set, the FastAPI application executes startup integrity checks:
1. Verifies that `GEMINI_API_KEY` is present and non-empty.
2. Verifies that `QDRANT_URL` and `QDRANT_API_KEY` can establish a valid handshake.
3. Verifies that `ALLOWED_ORIGINS` does not contain wildcard `*`.
4. If any mandatory secret is absent, the backend aborts with exit code `1`, preventing unsafe initialization.

---

## 4. Production Secret Provisioning Steps

1. **Google Cloud Secret Manager / AWS Secrets Manager**:
   Store `GEMINI_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, and `QDRANT_API_KEY` in the cloud secret manager.
2. **Container Injection**:
   Reference secrets in the deployment manifest (e.g. Cloud Run or ECS task definition) to inject them as environment variables into the container runtime.
3. **Frontend Build Arguments**:
   Pass only the non-sensitive `NEXT_PUBLIC_*` values as Docker build arguments when compiling the standalone Next.js artifact.
