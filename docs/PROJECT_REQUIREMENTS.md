# HerAI — Project Requirements Document (PRD)

**Version:** 2.0.0 (Updated for Next.js App Router)  
**Status:** Architectural Specification  
**Author:** Principal Software Architect  
**Classification:** Confidential / Authorized Personal Use  

---

## 1. Executive Summary
**HerAI** is a private, cloud-hosted AI companion system modeled from authorized historical WhatsApp conversation exports. The system enables a user to converse in real-time with an AI persona that mirrors the linguistic style, emotional cadence, shared memories, and contextual nuances of a specific historical companion.

The presentation tier is built using **Next.js with App Router**, **TypeScript**, **Tailwind CSS**, and **shadcn/ui**, leveraging React Server Components (RSC) by default for data-intensive views and Client Components for responsive interactive chat. The dedicated backend application tier is powered by **Python**, **FastAPI**, **Pydantic v2**, and **SQLAlchemy** (where appropriate), integrating **Supabase** (PostgreSQL, Auth, RLS, migrations), **Qdrant Cloud** (vector index), and **Google Gemini** via the official `google-genai` SDK.

---

## 2. Core Functional Requirements

### FR-01: Multi-Archive WhatsApp Ingestion
- Ingest and process three (3) distinct WhatsApp chat export ZIP archives.
- Support overlapping or sequential archive exports without creating duplicate messages.
- Support standard WhatsApp formats:
  - **iOS format**: `[DD/MM/YY, HH:MM:SS] Sender Name: Message text`
  - **Android format**: `DD/MM/YYYY, HH:MM - Sender Name: Message text`
  - 12-hour and 24-hour timestamp variations, AM/PM markers, and regional date representations (`DD/MM/YYYY`, `MM/DD/YYYY`, `YY/MM/DD`).
- Parse multi-line messages, non-standard unicode characters, emojis, and system messages.
- Filter or tag media omission markers (`<Media omitted>`, `image omitted`, `video omitted`, `audio omitted`, `Contact card omitted`).

### FR-02: Participant Identification & Normalization
- Precisely identify the two participants across all three archives.
- Provide an identity resolution interface to assign:
  1. **User Identity** (the authorized user interacting with HerAI).
  2. **Companion Identity** (the counterpart whose persona HerAI will emulate).
- Handle variations in contact naming across exports (e.g., phone numbers vs. address book names).

### FR-03: Message & Context Preservation
- Preserve every message with its exact timestamp, time zone offset, sender attribution, raw message content, cleaned message content, and sequential turn index.
- Maintain message clusters / conversational sessions: automatically delimit conversation sessions using a configurable inactivity threshold (default: 4 hours) or date transitions.

### FR-04: Conversation Understanding Engine
- Perform temporal and structural analysis across the entire message corpus.
- Compute conversational rhythm: average response latency, initiation frequency, time-of-day distribution, and message length distributions for each participant.
- Track thematic arcs and topic clusters across historical sessions.

### FR-05: Personality Extraction Engine (Ground Truth Only)
- Extract a detailed, empirical persona profile for the companion:
  - **Lexical markers**: favorite words, colloquialisms, slang, pet names, greeting styles, farewell patterns.
  - **Emoji fingerprints**: top emoji frequencies, emoji combinations, placement habits.
  - **Syntactic traits**: capitalization tendencies, punctuation habits (e.g., multiple exclamation marks, ellipsis usage, lowercase starts), sentence length distributions.
  - **Emotional tone**: sentiment variance across topics and times of day.
- **Strict Rule**: Zero mock or synthetic statistics. Every metric stored in the database must be derived directly from mathematical aggregation of the companion's messages.

### FR-06: Relationship Memory Engine
- Extract persistent relational facts, shared events, milestone dates, inside jokes, mutual acquaintances, and emotional disclosures.
- Classify memories into:
  - **Episodic Memories**: specific shared events (e.g., "Our trip to Goa in November 2022").
  - **Semantic Facts**: enduring personal knowledge (e.g., "Companion's favorite coffee is iced oat latte", "Companion has a golden retriever named Milo").
  - **Relational Dynamics**: nicknames used, recurring inside jokes, shared conflict resolutions.
- Store source message references (`message_id` range) and extraction confidence scores for each memory item.

### FR-07: Semantic Conversation Retrieval
- Embed messages and episodic memories using Google's `text-embedding-004` (Gemini Embedding 2).
- Index vectors in Qdrant Cloud under dedicated collections with payload metadata filtering (`user_id`, `participant_id`, `timestamp_range`, `topic`).
- Support hybrid retrieval: Combine semantic similarity (vector distance) with temporal recency and conversation session context using Maximal Marginal Relevance (MMR) to prevent redundant context retrieval.

### FR-08: Context-Aware AI Generation
- Generate responses using Google Gemini (via `google-genai` SDK) utilizing:
  - Base system instruction incorporating the empirical personality profile.
  - Retrieved episodic memories relevant to the user's prompt.
  - Retrieved historical conversation snippets demonstrating historical tone on related topics.
  - Sliding window of the current live chat conversation.
- Support real-time token streaming to the frontend via Server-Sent Events (SSE).
- Enforce strict AI persona disclosure: Prominently disclose AI status in system instructions and metadata.

### FR-09: Next.js App Router Web Application
- Modern, clean web interface built with **Next.js with App Router**, **TypeScript**, **Tailwind CSS**, **shadcn/ui**, and **Lucide React**.
- Implementation across explicit App Router routes:
  - `/login`: Public auth portal integrated with `@supabase/ssr` (email/password or magic link).
  - `/chat`: Interactive WhatsApp-inspired chat interface featuring optimistic messaging, streaming token rendering, and status indicators (Client Component).
  - `/history`: Historical message and session explorer with server-side pagination (Server Component).
  - `/memories`: Curated relationship memory browser displaying episodic milestones and semantic facts (Server Component).
  - `/personality`: Introspection dashboard visualizing the companion's empirical linguistic statistics and emoji charts (Server Component).
  - `/settings`: Participant configuration, archive upload, vector re-indexing, and preferences (Client/Server hybrid).
- React Server Components (RSC) used by default for data-fetching; Client Components (`"use client"`) reserved strictly for interactive state and streaming.
- Persistent top-level AI disclosure banner across all authenticated views.

### FR-10: Cloud Deployment & Security
- Complete containerization with Docker and Docker Compose (Next.js Node container + FastAPI Python container).
- Supabase SSR cookie handling via Next.js Edge Middleware for session refresh and route protection.
- Supabase Row Level Security (RLS) guaranteeing strict multi-tenant isolation.
- API keys (`GEMINI_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `QDRANT_API_KEY`) strictly confined to FastAPI backend.

---

## 3. Non-Functional Requirements (NFRs)

| Category | Requirement | Specification |
| :--- | :--- | :--- |
| **Performance** | Time-to-First-Token (TTFT) | < 1,200 ms for streaming chat responses. |
| **Performance** | Vector Search Latency | < 150 ms query time on Qdrant Cloud. |
| **Throughput** | Archive Parsing Speed | Process 50,000 WhatsApp messages in < 30 seconds. |
| **Scalability** | Vector Capacity | Capable of indexing 200,000+ vector points per user in Qdrant. |
| **Availability** | Cloud Uptime Target | 99.5% service availability. |
| **Data Integrity** | Vector Rebuildability | 100% of Qdrant indexes must be rebuildable from Supabase source of truth. |
| **Data Integrity** | Deduplication | 100% deduplication of identical messages across overlapping archives. |
| **Rendering** | RSC Performance | Server-rendered pages (`/memories`, `/personality`) paint initial content without client-side waterfall spinners. |
| **Compliance** | AI Transparency | Persistent notice: "HerAI is an AI-generated companion and not an actual human." |

---

## 4. Architectural Invariants & Boundaries

1. **Next.js Scope**: UI rendering, Supabase SSR auth integration, frontend routing, and interactive chat streaming presentation. Next.js does **not** duplicate FastAPI's data processing or AI orchestration logic.
2. **FastAPI Scope**: All WhatsApp parsing, session grouping, personality metric aggregation, memory extraction, vector embeddings, Qdrant indexing, and Gemini prompt synthesis.
3. **Storage Boundary**:
   - `Supabase PostgreSQL` is the single source of truth for all users, messages, sessions, memories, and app state.
   - `Qdrant Cloud` is an auxiliary, rebuildable search index.
4. **Key Security**: Gemini API keys, Qdrant API keys, and Supabase Service Role keys remain strictly on the FastAPI backend.
5. **No Mock Data**: No synthetic personality statistics. Every metric is derived mathematically from the parsed chat records.
