# HerAI — API Contracts & Interface Specification

**Version:** 2.0.0 (Updated for Next.js App Router Integration)  
**Status:** Architectural Specification  
**Author:** Principal Software Architect  
**Base Path:** `/api/v1`  

All protected endpoints require a valid Supabase JWT Bearer token in the `Authorization` header:
`Authorization: Bearer <supabase_jwt_access_token>`

In Next.js:
- **Server Components** (`/history`, `/memories`, `/personality`): Use `FASTAPI_INTERNAL_URL` and retrieve the access token server-side from `createServerClient(cookieStore).auth.getSession()`, injecting it into backend requests.
- **Client Components** (`/chat`, `/settings`): Use `NEXT_PUBLIC_BACKEND_API_URL` and retrieve the session token from `createBrowserClient().auth.getSession()`, maintaining direct SSE streaming connections.

---

## 1. Data Ingestion & Normalization Endpoints

### 1.1. Upload WhatsApp Archives
Uploads up to three (3) WhatsApp chat export ZIP files.
- **Endpoint:** `POST /api/v1/archives/upload`
- **Content-Type:** `multipart/form-data`
- **Request:**
  - `files`: List of ZIP binary files (1 to 3 files, max 50MB each).
- **Response (200 OK):**
```json
{
  "status": "success",
  "archives": [
    {
      "archive_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "original_filename": "WhatsApp Chat - Alex.zip",
      "file_hash": "a1b2c3d4e5f6...",
      "file_size_bytes": 1420583,
      "detected_source": "ios",
      "status": "uploaded",
      "message_count_preview": 12450
    }
  ],
  "discovered_participants": [
    {
      "raw_name": "Alex Mercer",
      "message_count": 6840,
      "sample_messages": ["Hey! Are you free tonight?", "Just sent over the file 📁"]
    },
    {
      "raw_name": "John Doe",
      "message_count": 5610,
      "sample_messages": ["On my way!", "Sounds great 👍"]
    }
  ]
}
```

---

### 1.2. Map Participants & Start Normalization Pipeline
Assigns participant identities ("User" vs. "Companion") and triggers asynchronous processing.
- **Endpoint:** `POST /api/v1/archives/participants/map`
- **Request Schema:**
```json
{
  "mappings": [
    {
      "raw_name": "John Doe",
      "role": "user",
      "display_alias": "John"
    },
    {
      "raw_name": "Alex Mercer",
      "role": "companion",
      "display_alias": "Alex"
    }
  ]
}
```
- **Response (202 Accepted):**
```json
{
  "status": "accepted",
  "job_id": "8b51d8b2-3bc9-4b17-a068-d01d143c7bfe",
  "message": "Archive normalization and AI extraction pipeline initiated."
}
```

---

### 1.3. Get Ingestion & Pipeline Job Status
Polls progress of the multi-archive ingestion, persona calculation, and vector indexing.
- **Endpoint:** `GET /api/v1/archives/status/{job_id}`
- **Response (200 OK):**
```json
{
  "job_id": "8b51d8b2-3bc9-4b17-a068-d01d143c7bfe",
  "state": "processing",
  "progress_percentage": 68.5,
  "steps": {
    "archive_decompression": "completed",
    "parsing_and_deduplication": "completed",
    "total_messages_stored": 23410,
    "personality_extraction": "completed",
    "relationship_memory_extraction": "in_progress",
    "qdrant_vector_indexing": "pending"
  },
  "diagnostics": {
    "duplicates_pruned": 1840,
    "system_messages_skipped": 45,
    "media_omissions_handled": 312
  }
}
```

---

## 2. Persona & Memory Endpoints

### 2.1. Get Companion Personality Profile (Ground Truth)
Fetches the mathematical, empirical persona metrics derived from historical chats.
- **Endpoint:** `GET /api/v1/persona`
- **Response (200 OK):**
```json
{
  "participant_id": "9c12a83e-9081-43ef-b203-1284752c0091",
  "display_alias": "Alex",
  "total_messages_analyzed": 11840,
  "lexical_metrics": {
    "type_token_ratio": 0.42,
    "top_vocabulary": [
      {"word": "totally", "count": 482},
      {"word": "coffee", "count": 310},
      {"word": "omg", "count": 295}
    ],
    "favorite_greetings": ["heyyy", "morning!", "yo"],
    "favorite_signoffs": ["talk soon", "goodnighttt", "byeee"]
  },
  "emoji_metrics": {
    "total_emojis_used": 5420,
    "top_emojis": [
      {"emoji": "✨", "count": 820, "percentage": 15.1},
      {"emoji": "☕", "count": 430, "percentage": 7.9},
      {"emoji": "😂", "count": 412, "percentage": 7.6}
    ],
    "top_combinations": ["✨💖", "😂💀"]
  },
  "syntactic_metrics": {
    "lowercase_start_percentage": 78.4,
    "average_message_length_chars": 38.6,
    "average_words_per_message": 7.2,
    "uses_trailing_ellipsis": true,
    "burstiness_avg_consecutive_messages": 2.8
  },
  "temporal_metrics": {
    "median_response_latency_seconds": 145,
    "peak_chatter_hours_utc": [18, 19, 20, 21, 22]
  }
}
```

---

### 2.2. Query Relationship Memories
Lists extracted episodic and semantic facts with optional category filtering.
- **Endpoint:** `GET /api/v1/memories?category=milestone&limit=20`
- **Response (200 OK):**
```json
{
  "total": 34,
  "memories": [
    {
      "id": "e4f8d21b-43ac-4899-b1d5-c93d9391ab10",
      "memory_type": "episodic_event",
      "category": "milestone",
      "title": "Weekend Hiking Trip in Boulder",
      "description": "User and Alex went hiking in Chautauqua Park and got caught in a sudden rainstorm.",
      "confidence_score": 0.94,
      "event_date": "2023-09-16T14:00:00Z",
      "source_message_count": 18
    }
  ]
}
```

---

## 3. Live Chat & AI Streaming Endpoints

### 3.1. Create or List Live Chat Sessions
- **Endpoint:** `GET /api/v1/chat/sessions`
- **Response (200 OK):**
```json
{
  "sessions": [
    {
      "id": "a24f0c91-...",
      "title": "Conversation with HerAI",
      "created_at": "2026-11-14T10:00:00Z",
      "last_message_preview": "Can't wait for the weekend!"
    }
  ]
}
```

- **Endpoint:** `POST /api/v1/chat/sessions`
- **Request:** `{"title": "Morning Catchup"}`
- **Response (201 Created):**
```json
{
  "session_id": "a24f0c91-...",
  "title": "Morning Catchup",
  "created_at": "2026-11-14T15:20:00Z"
}
```

---

### 3.2. Real-Time Streaming Chat (Server-Sent Events)
Sends a message to HerAI and streams the context-aware persona response token-by-token.
- **Endpoint:** `POST /api/v1/chat/stream`
- **Accept:** `text/event-stream`
- **Request Body:**
```json
{
  "session_id": "a24f0c91-...",
  "message": "Do you remember when we got caught in that rainstorm during our hike?"
}
```
- **SSE Stream Sequence:**
```
event: metadata
data: {"retrieved_memories": ["Weekend Hiking Trip in Boulder"], "context_count": 4}

event: token
data: {"text": "omg "}

event: token
data: {"text": "how could I forget?? "}

event: token
data: {"text": "we were completely soaked at Chautauqua 😂☔"}

event: token
data: {"text": " my boots took three days to dry out"}

event: end
data: {"live_message_id": "5cb891ef-...", "tokens_generated": 32, "disclaimer": "HerAI is an AI-generated companion."}
```

---

## 4. Administrative & Vector Index Maintenance

### 4.1. Vector Rebuild / Reindex
Regenerates Qdrant vector collections from Supabase data.
- **Endpoint:** `POST /api/v1/index/rebuild`
- **Request:**
```json
{
  "target": "all",
  "batch_size": 100
}
```
- **Response (202 Accepted):**
```json
{
  "status": "accepted",
  "message": "Vector index rebuild initiated for target: all."
}
```
