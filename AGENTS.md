# AGENTS.md — Agent Operations & Architecture Guardrails for HerAI

## 1. Project Overview & Vision
HerAI is a private, cloud-hosted AI companion system powered by authorized historical WhatsApp conversations. It enables an authenticated user to converse with an authentic AI persona modeled on historical dialogue patterns, episodic memories, and relationship nuances derived from genuine conversations.

---

## 2. Invariant Architecture Principles
All autonomous agents and human developers contributing to this repository MUST strictly uphold the following principles:

1. **Architecture Before Code**: Never write application code without an approved architectural spec and design contract.
2. **Strict Architectural Boundaries**:
   - **Next.js (App Router)**: UI rendering, authentication integration, frontend routing, user interaction, and secure frontend server operations.
   - **FastAPI**: WhatsApp processing, conversation understanding, personality extraction, relationship memory, embedding generation, Qdrant retrieval, Gemini orchestration, and AI response generation.
   - **Do NOT duplicate backend business logic in Next.js API routes**.
3. **Supabase is the Source of Truth**: All transactional records (users, chat archives, normalized messages, sessions, extracted personality parameters, relationship memories, live chat interactions) reside in Supabase PostgreSQL under strict Row Level Security (RLS) and database migrations.
4. **Qdrant is Rebuildable**: Qdrant Cloud hosts vector embeddings for semantic retrieval. The Qdrant index is strictly secondary and must be 100% rebuildable at any time from Supabase data.
5. **Zero Mock Statistics**: Never fabricate, randomize, or invent personality attributes, lexical statistics, or emotional indices. Every trait and pattern must be empirically computed from companion message history.
6. **Separation of Raw vs. Processed Data**: Raw WhatsApp exports (ZIP files, extracted `.txt` logs, raw media markers) must remain isolated in secure server staging storage and must never leak into client payloads or unencrypted logs.
7. **Backend Key Isolation**: Client applications communicate only with Supabase Auth (using the public publishable/anon key) and the FastAPI backend. Sensitive keys (`GEMINI_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `QDRANT_API_KEY`) must strictly live on the FastAPI backend.
8. **Server Components by Default**: In Next.js, render all static and server-rendered data via React Server Components (RSC). Use Client Components (`"use client"`) only where interactive client-side state is strictly necessary (e.g., active chat input, SSE streaming listener, drag-and-drop file upload).
9. **Official SDK Standards**: Use the official `google-genai` Python SDK for all Gemini API calls (completions, structured JSON extraction, and embeddings with `text-embedding-004`).
10. **Explicit AI Disclosure**: Every client screen and AI interaction must clearly disclose that the persona is AI-generated and not an actual human.
11. **Modularity & Testability**: Every service layer must be decoupled, typed with Pydantic v2 schemas / TypeScript interfaces, and accompanied by comprehensive unit and integration tests.

---

## 3. Tech Stack Reference
| Domain | Technology | Notes / Constraints |
| :--- | :--- | :--- |
| **Frontend** | Next.js (App Router, current stable), React Server Components, TypeScript, Tailwind CSS, shadcn/ui, Lucide React | RSC by default; Client Components only for interactivity; `@supabase/ssr` for auth. |
| **Backend** | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy (where appropriate), Uvicorn | Async endpoints, typed models, clean domain layering, AI orchestration. |
| **Database** | Supabase (PostgreSQL 15+, Auth, RLS, Migrations) | Strict user data isolation via Row Level Security bound to `auth.uid()`. |
| **Vector DB** | Qdrant Cloud | Cosine distance, filtered collections, deterministic point IDs. |
| **AI / GenAI** | Google Gemini 2.5 Flash / Pro, Gemini Embedding 2 (`text-embedding-004`) | Official `google-genai` SDK (`from google import genai`). |
| **Testing** | Pytest, Pytest-Asyncio, HTTPX, Vitest, React Testing Library | High test coverage for parser regexes, memory extraction, and RAG retrieval. |
| **DevOps** | Docker, Docker Compose, Multi-stage builds | Production containerization with non-root security. |

---

## 4. Frontend Route Architecture (Next.js App Router)
Next.js handles presentation and authentication across the following explicit routes:
- `/login`: Public auth portal handling login/signup via Supabase SSR.
- `/chat`: Interactive conversational view with HerAI featuring real-time SSE streaming (Client Component).
- `/history`: Historical archive and session browser (Server Component with pagination).
- `/memories`: Curated relationship memory explorer displaying extracted episodic and semantic facts (Server Component).
- `/personality`: Introspection dashboard visualizing the companion's empirical linguistic metrics and emoji distributions (Server Component).
- `/settings`: Participant configuration, archive re-ingestion, and user preferences (Client/Server hybrid).

---

## 5. Directory Structure Target
```
HerAI/
├── .env.example
├── .gitignore
├── AGENTS.md
├── docs/
│   ├── PROJECT_REQUIREMENTS.md
│   ├── SYSTEM_ARCHITECTURE.md
│   ├── DATABASE_DESIGN.md
│   ├── AI_PIPELINE.md
│   ├── API_CONTRACTS.md
│   ├── IMPLEMENTATION_ROADMAP.md
│   └── SECURITY.md
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI versioned routers (/api/v1/...)
│   │   ├── core/         # Config, security, database clients, dependencies
│   │   ├── models/       # Pydantic schemas & SQLAlchemy ORM models
│   │   ├── services/     # Ingestion, parser, normalizer, persona, memory, retrieval, chat
│   │   └── main.py       # FastAPI application factory
│   ├── tests/            # Unit & integration tests
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── (auth)/
│   │   │   │   └── login/
│   │   │   │       └── page.tsx           # Supabase SSR login/signup
│   │   │   ├── (dashboard)/
│   │   │   │   ├── layout.tsx             # Shared navigation, sidebar, AI disclosure header
│   │   │   │   ├── chat/
│   │   │   │   │   └── page.tsx           # Interactive chat interface (Client Component)
│   │   │   │   ├── history/
│   │   │   │   │   └── page.tsx           # Historical sessions browser (Server Component)
│   │   │   │   ├── memories/
│   │   │   │   │   └── page.tsx           # Memory cards & timeline (Server Component)
│   │   │   │   ├── personality/
│   │   │   │   │   └── page.tsx           # Empirical persona charts (Server Component)
│   │   │   │   └── settings/
│   │   │   │       └── page.tsx           # Config & archive upload (Hybrid)
│   │   │   ├── api/                       # Lightweight Next.js route handlers (auth callbacks only)
│   │   │   ├── layout.tsx                 # Root layout & providers
│   │   │   └── page.tsx                   # Redirect / landing page
│   │   ├── components/
│   │   │   ├── ui/                        # shadcn/ui primitives
│   │   │   ├── chat/                      # Chat window, message bubble, streaming indicator
│   │   │   ├── ingestion/                 # Drag-and-drop uploader, participant picker
│   │   │   ├── layout/                    # Sidebar, navbar, disclaimer banner
│   │   │   └── shared/                    # Empty states, loading skeletons
│   │   ├── hooks/                         # useChatStream, useAuth
│   │   ├── lib/
│   │   │   ├── api-client.ts              # Typed API client for FastAPI endpoints
│   │   │   └── utils.ts                   # Tailwind class merge utilities
│   │   ├── utils/
│   │   │   └── supabase/
│   │   │       ├── client.ts              # createBrowserClient (@supabase/ssr)
│   │   │       ├── server.ts              # createServerClient with cookies() (@supabase/ssr)
│   │   │       └── middleware.ts          # Session refresh middleware
│   │   └── middleware.ts                  # Next.js edge middleware for route protection
│   ├── components.json                    # shadcn/ui configuration
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── Dockerfile
│   └── package.json
└── docker-compose.yml
```

---

## 6. Review & Approval Protocol
Before creating executable code in `backend/` or `frontend/`, all design documentation in `docs/` must be thoroughly updated and formally reviewed. Any deviations from the tech stack or rules require explicit user approval.
