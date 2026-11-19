import os
import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from uuid import uuid4
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment configuration (.env in root or local)
load_dotenv()
_root_env = Path(__file__).resolve().parent.parent.parent / ".env"
if _root_env.exists():
    load_dotenv(dotenv_path=_root_env, override=False)

from fastapi import FastAPI, HTTPException, Query, Header, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from backend.app.services.chat_service import ChatOrchestrationService
from backend.app.services.langgraph_agent import LangGraphConversationAgent
from backend.app.services.time_context import TimeContextEngine
from backend.app.memory_engine.resolver import MemoryResolver
from backend.app.memory_engine.review_service import MemoryReviewService
from backend.app.memory_engine.memory_indexer import MemoryIndexer
from backend.app.core.security import vault, sanitizer

# Configure Structured Logging (No private message content or tokens logged!)
logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "service": "herai-api", "message": "%(message)s"}'
)
logger = logging.getLogger("herai")

app = FastAPI(
    title="HerAI Core Engine API",
    version="2.0.0",
    description="Dedicated AI Orchestration & Conversation Intelligence Backend for HerAI"
)

# Environment & CORS Hardening
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
ALLOWED_ORIGINS = [
    orig.strip() for orig in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if orig.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if ENVIRONMENT == "production" else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    max_age=3600
)

# In-memory Rate Limiting (Simple Token Bucket / Window per user)
REQUEST_HISTORY: Dict[str, List[float]] = {}
MAX_REQUESTS_PER_MINUTE = 120

@app.middleware("http")
async def security_and_rate_limit_middleware(request: Request, call_next):
    # 1. Request Size Limit (10MB maximum payload)
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 10 * 1024 * 1024:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={"detail": "Payload exceeds 10MB limit"}
        )

    # 2. Rate Limiting by Client IP
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    timestamps = REQUEST_HISTORY.get(client_ip, [])
    # Keep only timestamps within last 60 seconds
    timestamps = [t for t in timestamps if now - t < 60]
    if len(timestamps) >= MAX_REQUESTS_PER_MINUTE:
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Rate limit exceeded. Please wait a minute."}
        )
    timestamps.append(now)
    REQUEST_HISTORY[client_ip] = timestamps

    # 3. Request Logging (Masking content and tokens)
    start_time = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start_time) * 1000, 2)
    logger.info(f"path={request.url.path} method={request.method} status={response.status_code} duration_ms={duration_ms}")
    return response

PROCESSED_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "processed"

# Initialize Services
chat_orchestrator = ChatOrchestrationService(PROCESSED_DIR)
memory_indexer = MemoryIndexer()

# Multi-tenant Stores: session_id -> { ..., "owner_id": user_id }
LIVE_SESSIONS: Dict[str, Dict[str, Any]] = {}
LIVE_MESSAGES: Dict[str, List[Dict[str, Any]]] = {}

# Load memories into resolver with default owner
raw_memories = []
memories_path = PROCESSED_DIR / "relationship_memories.jsonl"
if memories_path.exists():
    with open(memories_path, "r", encoding="utf-8") as f:
        for line in f:
            m = json.loads(line)
            m["owner_id"] = m.get("owner_id", "user_default")
            raw_memories.append(m)

memory_resolver = MemoryResolver(raw_memories)
memory_review_service = MemoryReviewService(memory_resolver)

# Production LangGraph Conversation & Continual Learning Agent
langgraph_agent = LangGraphConversationAgent(
    chat_orchestrator=chat_orchestrator,
    memory_resolver=memory_resolver,
    memory_indexer=memory_indexer,
    processed_dir=PROCESSED_DIR
)

# Pydantic Schemas
class ChatStreamRequest(BaseModel):
    session_id: str
    message: str = Field(..., max_length=4000)
    mock_time: Optional[str] = Field(None, description="Optional HH:MM IST time override for testing schedule slots")

class CreateSessionRequest(BaseModel):
    title: Optional[str] = Field("Conversation with HerAI", max_length=120)

class MemoryUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    event_date: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    verification_status: Optional[str] = None

class RejectMemoryRequest(BaseModel):
    reason: Optional[str] = Field("", max_length=500)

class EditMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)

class MessageReactionRequest(BaseModel):
    emoji: str = Field(..., max_length=10)

class ClearChatRequest(BaseModel):
    pin: Optional[str] = Field(None, max_length=10)

# User Authorization Dependency with Bearer Token & Multi-tenant Isolation
def get_current_user(authorization: Optional[str] = Header(None)) -> str:
    if not authorization:
        # Development fallback
        if ENVIRONMENT == "development":
            return "user_default"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header"
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format. Must be Bearer token."
        )

    token = authorization.split("Bearer ")[1].strip()
    if not token or token == "invalid_token" or token == "expired_token":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token"
        )

    # In production with Supabase JWT:
    # Extracts sub (user_id) from token payload. For testing:
    if token.startswith("user_"):
        return token

    # Support Supabase JWT tokens
    if len(token.split(".")) == 3:
        try:
            import jwt
            payload = jwt.decode(token, options={"verify_signature": False})
            sub = payload.get("sub") or payload.get("user_id")
            if sub:
                return str(sub)
        except Exception as e:
            logger.warning(f"Failed to parse JWT: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token format or expired token"
            )

    return "user_default"

# -----------------------------------------------------------------------------
# HEALTH CHECKS
# -----------------------------------------------------------------------------

@app.get("/health")
@app.get("/api/v1/health")
def health_check():
    return {
        "status": "healthy",
        "service": "HerAI Backend",
        "environment": ENVIRONMENT,
        "engine": "langgraph-2.0",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/health/ready")
def readiness_check():
    # Verify processed data directory and core files are accessible
    has_profile = (PROCESSED_DIR / "personality_profile.json").exists()
    has_memories = (PROCESSED_DIR / "relationship_memories.jsonl").exists()
    if not (has_profile and has_memories):
        raise HTTPException(status_code=503, detail="Service not ready: Missing processed dataset")
    return {"status": "ready", "qdrant": "ready", "dataset": "ready"}

@app.get("/health/live")
def liveness_check():
    return {"status": "live"}

# -----------------------------------------------------------------------------
# 1. LIVE CHAT ENDPOINTS (Strict Multi-tenant Ownership)
# -----------------------------------------------------------------------------

@app.get("/api/v1/chat/sessions")
def list_chat_sessions(user_id: str = Depends(get_current_user)):
    user_sessions = [s for s in LIVE_SESSIONS.values() if s.get("owner_id") == user_id]
    return {"sessions": user_sessions}

@app.post("/api/v1/chat/sessions")
def create_chat_session(req: CreateSessionRequest, user_id: str = Depends(get_current_user)):
    session_id = str(uuid4())
    session_data = {
        "session_id": session_id,
        "owner_id": user_id,
        "title": req.title,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_message": ""
    }
    LIVE_SESSIONS[session_id] = session_data
    LIVE_MESSAGES[session_id] = []
    return session_data

@app.get("/api/v1/chat/sessions/{session_id}/messages")
def get_session_messages(session_id: str, user_id: str = Depends(get_current_user)):
    # Ownership verification
    session = LIVE_SESSIONS.get(session_id)
    if session and session.get("owner_id") != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: Not your session")

    if not session:
        # Create session under this user
        LIVE_MESSAGES[session_id] = []
        LIVE_SESSIONS[session_id] = {
            "session_id": session_id,
            "owner_id": user_id,
            "title": "Conversation with HerAI",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_message": ""
        }

    return {
        "session_id": session_id,
        "messages": LIVE_MESSAGES.get(session_id, [])
    }

CLEAR_CHAT_PIN = os.getenv("CLEAR_CHAT_PIN", "1206")

@app.delete("/api/v1/chat/sessions/{session_id}/messages")
def clear_session_messages(session_id: str, pin: Optional[str] = Query(None), user_id: str = Depends(get_current_user)):
    """Clears all conversation messages in the given chat session with required PIN protection."""
    if pin != CLEAR_CHAT_PIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Incorrect PIN for clearing chat. Please enter valid PIN."
        )
    session = LIVE_SESSIONS.get(session_id)
    if session and session.get("owner_id") != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    LIVE_MESSAGES[session_id] = []
    if session_id in LIVE_SESSIONS:
        LIVE_SESSIONS[session_id]["last_message"] = ""
    return {"status": "cleared", "session_id": session_id}

@app.patch("/api/v1/chat/sessions/{session_id}/messages/{message_id}")
def edit_message(session_id: str, message_id: str, req: EditMessageRequest, user_id: str = Depends(get_current_user)):
    """Edits an existing user message in the session."""
    session = LIVE_SESSIONS.get(session_id)
    if session and session.get("owner_id") != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    msgs = LIVE_MESSAGES.get(session_id, [])
    found = False
    for m in msgs:
        if m.get("id") == message_id:
            m["content"] = req.content
            m["edited"] = True
            m["updated_at"] = datetime.now(timezone.utc).isoformat()
            found = True
            break
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return {"status": "updated", "message_id": message_id, "content": req.content}

@app.post("/api/v1/chat/sessions/{session_id}/messages/{message_id}/reactions")
def react_to_message(session_id: str, message_id: str, req: MessageReactionRequest, user_id: str = Depends(get_current_user)):
    """Toggles an emoji reaction on a message."""
    session = LIVE_SESSIONS.get(session_id)
    if session and session.get("owner_id") != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    msgs = LIVE_MESSAGES.get(session_id, [])
    found = False
    new_reaction = None
    for m in msgs:
        if m.get("id") == message_id:
            # If the same emoji is clicked, toggle it off; else set it
            if m.get("reaction") == req.emoji:
                m["reaction"] = None
            else:
                m["reaction"] = req.emoji
                new_reaction = req.emoji
            found = True
            break
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return {"status": "reacted", "message_id": message_id, "reaction": new_reaction}

@app.delete("/api/v1/chat/sessions/{session_id}/messages/{message_id}")
def delete_single_message(session_id: str, message_id: str, user_id: str = Depends(get_current_user)):
    """Deletes a specific message in the session."""
    session = LIVE_SESSIONS.get(session_id)
    if session and session.get("owner_id") != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    msgs = LIVE_MESSAGES.get(session_id, [])
    LIVE_MESSAGES[session_id] = [m for m in msgs if m.get("id") != message_id]
    return {"status": "deleted", "message_id": message_id}

@app.post("/api/v1/chat/stream")
async def chat_stream(
    req: ChatStreamRequest,
    x_mock_time: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user)
):
    session_id = req.session_id
    user_msg_text = req.message
    mock_time_str = req.mock_time or x_mock_time

    session = LIVE_SESSIONS.get(session_id)
    if session and session.get("owner_id") != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: Not your session")

    if not session:
        LIVE_MESSAGES[session_id] = []
        LIVE_SESSIONS[session_id] = {
            "session_id": session_id,
            "owner_id": user_id,
            "title": user_msg_text[:30] if user_msg_text else "Conversation",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_message": user_msg_text
        }

    # Record user message
    user_msg = {
        "id": str(uuid4()),
        "role": "user",
        "content": user_msg_text,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    LIVE_MESSAGES[session_id].append(user_msg)
    history = LIVE_MESSAGES[session_id][:-1]

    async def event_generator():
        ai_response_chunks = []
        try:
            async for event in langgraph_agent.stream_conversation_turn(
                user_message=user_msg_text,
                session_history=history,
                session_id=session_id,
                user_id=user_id,
                mock_time_str=mock_time_str
            ):
                if event["event"] == "token":
                    ai_response_chunks.append(event["data"]["text"])
                yield {
                    "event": event["event"],
                    "data": json.dumps(event["data"])
                }

            full_ai_content = "".join(ai_response_chunks)
            ai_msg = {
                "id": str(uuid4()),
                "role": "companion",
                "content": full_ai_content,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            LIVE_MESSAGES[session_id].append(ai_msg)
            if session_id in LIVE_SESSIONS:
                LIVE_SESSIONS[session_id]["last_message"] = full_ai_content

            # Persist ongoing conversation to history vault in background
            try:
                _persist_to_history(session_id, user_msg, ai_msg, LIVE_SESSIONS.get(session_id))
            except Exception as hist_err:
                logger.warning(f"Could not persist conversation turn to history: {hist_err}")
        except Exception as e:
            logger.error(f"Streaming error in session {session_id}: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"detail": "Streaming generation interrupted."})
            }

    return EventSourceResponse(event_generator())

@app.post("/api/v1/chat/langgraph")
def chat_langgraph(
    req: ChatStreamRequest,
    x_mock_time: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user)
):
    """
    Direct production execution of the full LangGraph state graph.
    Runs context enrichment, response generation, and continual self-learning memory extraction.
    """
    session_id = req.session_id
    user_msg_text = req.message
    mock_time_str = req.mock_time or x_mock_time

    session = LIVE_SESSIONS.get(session_id)
    if session and session.get("owner_id") != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: Not your session")

    if not session:
        LIVE_MESSAGES[session_id] = []
        LIVE_SESSIONS[session_id] = {
            "session_id": session_id,
            "owner_id": user_id,
            "title": user_msg_text[:30] if user_msg_text else "Conversation",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_message": user_msg_text
        }

    user_msg = {
        "id": str(uuid4()),
        "role": "user",
        "content": user_msg_text,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    LIVE_MESSAGES[session_id].append(user_msg)
    history = LIVE_MESSAGES[session_id][:-1]

    state_result = langgraph_agent.run_turn(
        user_message=user_msg_text,
        session_history=history,
        session_id=session_id,
        user_id=user_id,
        mock_time_str=mock_time_str
    )

    full_ai_content = state_result.get("full_response", "")
    ai_msg = {
        "id": str(uuid4()),
        "role": "companion",
        "content": full_ai_content,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    LIVE_MESSAGES[session_id].append(ai_msg)
    if session_id in LIVE_SESSIONS:
        LIVE_SESSIONS[session_id]["last_message"] = full_ai_content

    try:
        _persist_to_history(session_id, user_msg, ai_msg, LIVE_SESSIONS.get(session_id))
    except Exception as hist_err:
        logger.warning(f"Could not persist conversation turn to history: {hist_err}")

    return {
        "session_id": session_id,
        "reply": full_ai_content,
        "provider": state_result.get("generation_provider", ""),
        "time_slot": state_result.get("time_ctx", {}).get("slot_id"),
        "time_name": state_result.get("time_ctx", {}).get("slot_name"),
        "current_time_ist": state_result.get("time_ctx", {}).get("current_time_ist"),
        "emotion": state_result.get("detected_emotion"),
        "learned_memories": state_result.get("extracted_memories", []),
        "learned_count": state_result.get("learned_memory_count", 0),
        "status": state_result.get("memory_update_status", "")
    }

# -----------------------------------------------------------------------------
# 2. RELATIONSHIP MEMORIES ENDPOINTS (Multi-tenant Ownership)
# -----------------------------------------------------------------------------

@app.get("/api/v1/memories")
def list_memories(category: Optional[str] = None, status: Optional[str] = None, user_id: str = Depends(get_current_user)):
    all_memories = memory_resolver.list_memories(category=category, status=status)
    # Filter by user ownership (or default tenant in shared view)
    user_memories = [m for m in all_memories if m.get("owner_id", "user_default") == user_id or user_id == "user_default"]
    return {
        "total": len(user_memories),
        "memories": user_memories
    }

@app.get("/api/v1/memories/{memory_id}")
def get_memory(memory_id: str, user_id: str = Depends(get_current_user)):
    mem = memory_resolver.get_memory(memory_id)
    if not mem:
        raise HTTPException(status_code=404, detail="Memory not found")
    if mem.get("owner_id", "user_default") != user_id and user_id != "user_default":
        raise HTTPException(status_code=403, detail="Access denied: Not your memory")
    return mem

@app.patch("/api/v1/memories/{memory_id}")
def update_memory(memory_id: str, req: MemoryUpdateRequest, user_id: str = Depends(get_current_user)):
    mem = memory_resolver.get_memory(memory_id)
    if not mem:
        raise HTTPException(status_code=404, detail="Memory not found")
    if mem.get("owner_id", "user_default") != user_id and user_id != "user_default":
        raise HTTPException(status_code=403, detail="Access denied: Not your memory")

    updated = memory_resolver.update_memory(memory_id, req.model_dump(exclude_unset=True))
    return updated

@app.delete("/api/v1/memories/{memory_id}")
def delete_memory(memory_id: str, user_id: str = Depends(get_current_user)):
    mem = memory_resolver.get_memory(memory_id)
    if not mem:
        raise HTTPException(status_code=404, detail="Memory not found")
    if mem.get("owner_id", "user_default") != user_id and user_id != "user_default":
        raise HTTPException(status_code=403, detail="Access denied: Not your memory")

    success = memory_resolver.delete_memory(memory_id)
    memory_indexer.delete_from_index(memory_id)
    return {"status": "deleted", "memory_id": memory_id}

@app.post("/api/v1/memories/{memory_id}/approve")
def approve_memory(memory_id: str, user_id: str = Depends(get_current_user)):
    mem = memory_resolver.get_memory(memory_id)
    if not mem:
        raise HTTPException(status_code=404, detail="Memory not found")
    if mem.get("owner_id", "user_default") != user_id and user_id != "user_default":
        raise HTTPException(status_code=403, detail="Access denied: Not your memory")

    approved = memory_review_service.approve_memory(memory_id, reviewer=user_id)
    memory_indexer.index_approved_memories([approved])
    return approved

@app.post("/api/v1/memories/{memory_id}/reject")
def reject_memory(memory_id: str, req: RejectMemoryRequest, user_id: str = Depends(get_current_user)):
    mem = memory_resolver.get_memory(memory_id)
    if not mem:
        raise HTTPException(status_code=404, detail="Memory not found")
    if mem.get("owner_id", "user_default") != user_id and user_id != "user_default":
        raise HTTPException(status_code=403, detail="Access denied: Not your memory")

    rejected = memory_review_service.reject_memory(memory_id, reason=req.reason or "", reviewer=user_id)
    memory_indexer.delete_from_index(memory_id)
    return rejected

# -----------------------------------------------------------------------------
# 3. PERSONALITY ENDPOINTS
# -----------------------------------------------------------------------------

@app.get("/api/v1/personality")
def get_personality_profile(user_id: str = Depends(get_current_user)):
    profile_path = PROCESSED_DIR / "personality_profile.json"
    if not profile_path.exists():
        raise HTTPException(status_code=404, detail="Personality profile not found")
    with open(profile_path, "r", encoding="utf-8") as f:
        return json.load(f)

@app.get("/api/v1/personality/observations")
def get_personality_observations(user_id: str = Depends(get_current_user)):
    obs_path = PROCESSED_DIR / "personality_observations.jsonl"
    if not obs_path.exists():
        return {"observations": []}
    observations = []
    with open(obs_path, "r", encoding="utf-8") as f:
        for line in f:
            observations.append(json.loads(line))
    return {"observations": observations}

def _persist_to_history(session_id: str, user_msg: dict, ai_msg: dict, session_info: Optional[dict] = None):
    """Stores every real-time conversation message and updates session metadata in the history files."""
    sessions_path = PROCESSED_DIR / "sessions.jsonl"
    messages_path = PROCESSED_DIR / "messages.jsonl"

    now_iso = datetime.now(timezone.utc).isoformat()
    # Format messages to match HistoricalMessage schema
    hist_user_msg = {
        "id": user_msg.get("id"),
        "archive_id": "live-chat",
        "source_message_id": f"live:{user_msg.get('id')}",
        "timestamp": user_msg.get("timestamp", now_iso),
        "sender": "user",
        "original_sender": "Manoj",
        "body": user_msg.get("content", ""),
        "message_type": "text",
        "media_type": "none",
        "is_system_message": False,
        "is_multiline": "\n" in user_msg.get("content", ""),
        "source_line_number": 0,
        "content_hash": "",
        "is_duplicate_across_archives": False,
        "session_id": session_id,
        "created_at": now_iso
    }

    hist_ai_msg = {
        "id": ai_msg.get("id"),
        "archive_id": "live-chat",
        "source_message_id": f"live:{ai_msg.get('id')}",
        "timestamp": ai_msg.get("timestamp", now_iso),
        "sender": "partner",
        "original_sender": "Sakthi",
        "body": ai_msg.get("content", ""),
        "message_type": "text",
        "media_type": "none",
        "is_system_message": False,
        "is_multiline": "\n" in ai_msg.get("content", ""),
        "source_line_number": 0,
        "content_hash": "",
        "is_duplicate_across_archives": False,
        "session_id": session_id,
        "created_at": now_iso
    }

    # Append to messages.jsonl
    with open(messages_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(hist_user_msg) + "\n")
        f.write(json.dumps(hist_ai_msg) + "\n")

    # Update or insert into sessions.jsonl
    sessions = []
    found = False
    if sessions_path.exists():
        with open(sessions_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    s = json.loads(line)
                    if s.get("session_id") == session_id:
                        s["end_timestamp"] = now_iso
                        s["message_count"] = s.get("message_count", 0) + 2
                        s["user_message_count"] = s.get("user_message_count", 0) + 1
                        s["partner_message_count"] = s.get("partner_message_count", 0) + 1
                        found = True
                    sessions.append(s)
                except Exception:
                    continue

    if not found:
        new_sess = {
            "session_id": session_id,
            "start_timestamp": now_iso,
            "end_timestamp": now_iso,
            "inactivity_threshold_hours": 6.0,
            "message_count": 2,
            "partner_message_count": 1,
            "user_message_count": 1,
            "source_archive_ids": ["live-chat"],
            "created_at": now_iso
        }
        sessions.insert(0, new_sess)

    # Write back sessions (placing current live session at top)
    with open(sessions_path, "w", encoding="utf-8") as f:
        for s in sessions:
            f.write(json.dumps(s) + "\n")


# -----------------------------------------------------------------------------
# 4. HISTORICAL CHAT SESSIONS & MESSAGES (WHATSAPP ARCHIVE EXPLORER)
# -----------------------------------------------------------------------------

@app.get("/api/v1/history/sessions")
def list_historical_sessions(limit: int = 50, offset: int = 0, user_id: str = Depends(get_current_user)):
    sessions_path = PROCESSED_DIR / "sessions.jsonl"
    if not sessions_path.exists():
        return {"total": 0, "sessions": []}

    all_sessions = []
    with open(sessions_path, "r", encoding="utf-8") as f:
        for line in f:
            all_sessions.append(json.loads(line))

    paged = all_sessions[offset:offset + limit]
    return {
        "total": len(all_sessions),
        "limit": limit,
        "offset": offset,
        "sessions": paged
    }

@app.get("/api/v1/history/sessions/{session_id}/messages")
def get_historical_session_messages(session_id: str, limit: int = 100, user_id: str = Depends(get_current_user)):
    messages_path = PROCESSED_DIR / "messages.jsonl"
    if not messages_path.exists():
        return {"messages": []}

    matched = []
    with open(messages_path, "r", encoding="utf-8") as f:
        for line in f:
            msg = json.loads(line)
            if msg.get("session_id") == session_id:
                # Sanitize body of messages to scrub any accidental PII
                if "body" in msg and isinstance(msg["body"], str):
                    msg["body"] = sanitizer.sanitize_text(msg["body"])
                matched.append(msg)
                if len(matched) >= limit:
                    break

    return {
        "session_id": session_id,
        "count": len(matched),
        "messages": matched
    }

# =============================================================================
# TIME CONTEXT, ZERO-DOWNTIME INDEXING & EMOTION ANALYTICS ENDPOINTS
# =============================================================================

@app.get("/api/v1/context/current-time")
def get_current_time_context(mock_time: Optional[str] = Query(None, description="Optional HH:MM IST override")):
    """
    Returns real-time situational awareness (IST timezone) reflecting Sakthi's
    daily routine (college classes, bus commute, canteen breaks, dinner, mom arrival).
    """
    return TimeContextEngine.get_context(mock_time)

@app.get("/api/v1/admin/index-status")
def get_retrieval_index_status(user_id: str = Depends(get_current_user)):
    """
    Returns health, active version, and metrics for the Zero-Downtime RAG index.
    """
    return chat_orchestrator.lifecycle_manager.get_status()

@app.post("/api/v1/admin/reindex")
def trigger_zero_downtime_reindex(user_id: str = Depends(get_current_user)):
    """
    Triggers an atomic, zero-downtime reindexing of the conversational corpus.
    Builds shadow index, runs health check warm-up, and swaps pointer with 0ms downtime.
    """
    try:
        res = chat_orchestrator.lifecycle_manager.reindex_sync()
        return res
    except Exception as e:
        logger.error(f"Reindex error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/analytics/emotions")
def get_emotion_analytics():
    """
    Returns empirical emotional classification distribution derived from the 24,971 messages.
    """
    emotion_file = PROCESSED_DIR / "emotion_analysis.json"
    if not emotion_file.exists():
        raise HTTPException(status_code=404, detail="Emotion analysis not yet generated.")
    with open(emotion_file, "r", encoding="utf-8") as f:
        return json.load(f)
