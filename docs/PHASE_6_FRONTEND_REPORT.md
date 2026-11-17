# HerAI — Phase 6: Next.js Frontend & Chat Application Report

**Version:** 2.0.0  
**Status:** Verification & Implementation Complete  
**Author:** Senior Frontend & Conversational AI Engineer  

---

## 1. Executive Summary

Phase 6 delivers the complete user-facing browser application for **HerAI**, built using **Next.js with App Router**, **TypeScript** (strict mode), **Tailwind CSS**, and **Supabase SSR authentication**. 

The frontend interfaces directly with the dedicated **Python FastAPI** AI orchestration backend, utilizing real-time Server-Sent Events (SSE) for streaming chat generation and accessing the ground-truth personality profile and relationship memories extracted from 24,971 historical messages.

---

## 2. Implemented Routes & Navigation

| Route | Rendering Mode | Purpose & Features |
| :--- | :--- | :--- |
| **`/login`** | Client Component | Supabase SSR email/password sign-in and sign-up with session persistence and route redirection. |
| **`/chat`** | Client Component | Interactive WhatsApp-style chat interface with real-time SSE token streaming, optimistic updates, session switching, and active memory badge. |
| **`/history`** | Hybrid Component | Chronological explorer for 205 historical conversation sessions with message inspect view, turn counts, and participant ratios. |
| **`/memories`** | Client/Server Hybrid | Curated relationship memory explorer displaying 8 verified memories, category filters, confidence badges, source citations, and human approval/rejection actions. |
| **`/personality`** | Server/Client Hybrid | Introspection dashboard displaying empirical linguistic charts, burstiness metrics, response latencies, and 5 evidence-backed observations. |
| **`/settings`** | Client Component | System preferences, active model selection (`gemini-2.5-flash`), Qdrant similarity thresholds, privacy disclosures, and account sign-out. |

---

## 3. Component Architecture

```
frontend/src/
├── app/
│   ├── (auth)/
│   │   └── login/page.tsx               # Supabase SSR Auth
│   ├── (dashboard)/
│   │   ├── layout.tsx                   # Main layout: AppHeader + AppSidebar + Responsive Content
│   │   ├── chat/page.tsx                # Chat window entry point
│   │   ├── history/page.tsx             # Archive history viewer
│   │   ├── memories/page.tsx            # Relationship memory cards & actions
│   │   ├── personality/page.tsx         # Linguistic profile & observation list
│   │   └── settings/page.tsx            # User preferences & disclosures
│   ├── layout.tsx                       # Root HTML/Body layout with Geist fonts
│   └── page.tsx                         # Root redirect to /chat
├── components/
│   ├── layout/
│   │   ├── app-header.tsx               # Header with mandatory "AI Simulation" badge
│   │   └── app-sidebar.tsx              # Desktop & slide-out mobile navigation drawer
│   ├── chat/
│   │   ├── chat-window.tsx              # Chat state manager, SSE stream consumer, auto-scroll
│   │   ├── message-bubble.tsx           # Distinct User vs Companion message bubbles with timestamps
│   │   └── typing-indicator.tsx         # Animated generation indicator
│   └── memories/
│       └── memory-card.tsx              # Memory card with category, confidence, and review actions
├── lib/
│   ├── api-client.ts                    # Centralized typed API client communicating with FastAPI
│   └── utils.ts                         # Tailwind merge & date/time formatters
├── utils/supabase/
│   ├── client.ts                        # createBrowserClient (@supabase/ssr)
│   ├── server.ts                        # createServerClient (@supabase/ssr)
│   └── middleware.ts                    # Edge session refresh and route protection
└── middleware.ts                        # Next.js route middleware
```

---

## 4. Visual Design & Theme Direction

- **Palette**: Minimal, warm, and elegant. Off-white soft backgrounds (`#faf9f6` / dark `#0a0a0a`), subtle pink/rose accents (`#f43f5e`, `#fb7185`), and lavender gradients for AI emblems.
- **Message Bubbles**:
  - **Companion (HerAI)**: Left-aligned white cards with delicate rose-tinted borders and companion avatar. Preserves Tamil/Tanglish unicode and emojis (`🙄`, `🥺`, `😂`, `😭`, `🥹`, `❤️‍🩹`).
  - **User**: Right-aligned vibrant rose bubbles with white text and user avatar.
- **AI Disclosure**: Omnipresent badge in `app-header.tsx` (`AI Simulation: Modeled on authorized historical conversations`) adhering to the mandatory disclosure directive.

---

## 5. API Integration & SSE Streaming

- **FastAPI Base URL**: Configured via `NEXT_PUBLIC_BACKEND_API_URL` (default: `http://localhost:8000/api/v1`).
- **SSE Stream Sequence**:
  1. Frontend dispatches `POST /api/v1/chat/stream` with `{ session_id, message }`.
  2. Receives `event: metadata` containing retrieved relationship memories and persona version.
  3. Receives progressive `event: token` chunks, dynamically appended to the companion bubble buffer without flickering.
  4. Receives `event: end` to seal the turn and synchronize with session history.

---

## 6. Verification & Build Results

### 6.1. Backend Test Suite (Pytest)
```
tests/test_data_engineering.py ..........               [ 47%]
tests/test_phase4.py .....                              [ 71%]
tests/test_phase5.py ......                             [100%]
======================== 21 passed in 2.55s ========================
```

### 6.2. Frontend Production Build (Next.js)
```
▲ Next.js 16.4.6 (Turbopack)
✓ Compiled successfully in 6.4s
✓ Finished TypeScript in 3.8s
✓ Collecting page data using 7 workers
✓ Generating static pages (10/10)

Route (app)
┌ ○ /
├ ○ /_not-found
├ ○ /chat
├ ○ /history
├ ○ /login
├ ○ /memories
├ ○ /personality
└ ○ /settings
```

---

## 7. How to Run the Application

### 1. Start the FastAPI Backend
```bash
cd /home/manoj/Documents/HerAI
source backend/.venv/bin/activate
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Start the Next.js Frontend
```bash
cd /home/manoj/Documents/HerAI/frontend
npm run dev
```
Open **`http://localhost:3000`** in your browser to interact with HerAI.
