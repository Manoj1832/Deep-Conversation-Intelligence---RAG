"""
Comprehensive Integration Tests for:
1. Time-Aware Contextual Engine
2. Emotion Analysis & Classification Engine
3. Cross-Encoder Reranking
4. Data Lifecycle & Zero-Downtime Indexing
5. New REST Endpoints
"""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.time_context import TimeContextEngine, SCHEDULE
from backend.app.services.emotion_engine import EmotionEngine
from backend.app.services.reranker import CrossEncoderReranker
from backend.app.services.index_lifecycle import IndexLifecycleManager

client = TestClient(app)
PROCESSED_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "processed"


def test_time_context_engine_schedule_slots():
    """Verifies that all 13 daily routine windows are accurately resolved."""
    test_cases = [
        ("07:15", "morning_travel"),
        ("08:50", "college_entry_bfast"),
        ("09:30", "morning_class"),
        ("10:45", "morning_break"),
        ("12:00", "class_lab"),
        ("13:30", "lunch_time"),
        ("14:30", "afternoon_class"),
        ("16:00", "bus_seat_transit"),
        ("17:45", "travel_to_potteneri"),
        ("19:15", "home_arrival_freshup"),
        ("20:15", "home_dinner_chat"),
        ("21:30", "post_mom_arrival_night"),
        ("02:00", "late_night_sleep")
    ]

    for mock_t, expected_slot in test_cases:
        ctx = TimeContextEngine.get_context(mock_t)
        assert ctx["slot_id"] == expected_slot, f"Expected {expected_slot} for time {mock_t}, got {ctx['slot_id']}"
        assert "prompt_injection" in ctx
        assert len(ctx["prompt_injection"]) > 20
        assert ctx["location"] != ""
        assert ctx["activity"] != ""


def test_emotion_engine_dimensions():
    """Verifies that emotion engine accurately detects all 7 emotional states."""
    test_inputs = {
        "affectionate": "chello bujju miss u so much 🥺❤️",
        "playful_teasing": "dei naayae over ah pannadha kilipan 😂",
        "caring_routine": "saptya da? food saapdu modhalla take care",
        "anxious_tense": "bayam bayama irukku veetla maatikitom 😭",
        "irritated_angry": "kovama irruken enkitta pesatha block",
        "sad_vulnerable": "azhudhuten romba valikuthu mudiyala 💔",
        "casual_neutral": "seri da seri reach aaiten"
    }

    for expected_emotion, text in test_inputs.items():
        emotion, conf = EmotionEngine.classify_text(text)
        assert emotion == expected_emotion, f"Expected {expected_emotion} for '{text}', got {emotion}"
        assert conf >= 0.60


def test_cross_encoder_reranking_temporal_boost():
    """Verifies that cross-encoder boosts candidate interactions matching current time slot."""
    reranker = CrossEncoderReranker()

    candidates = [
        {
            "user_trigger": "saptya da?",
            "partner_reaction": "night dinner saapten da..",
            "time_slot": "home_dinner_chat",
            "emotion": "caring_routine",
            "score": 3.0
        },
        {
            "user_trigger": "saptya da?",
            "partner_reaction": "mushroom biryani lunch saapdren da 🥺",
            "time_slot": "lunch_time",
            "emotion": "caring_routine",
            "score": 3.0
        }
    ]

    # At lunch time (13:30), the lunch_time candidate should rank higher!
    reranked = reranker.rerank(
        query="saptya da?",
        candidates=candidates,
        top_k=2,
        mock_time_str="13:30"
    )

    assert len(reranked) == 2
    assert reranked[0]["time_slot"] == "lunch_time"
    assert reranked[0]["final_score"] >= reranked[1]["final_score"]


def test_index_lifecycle_zero_downtime_reindexing():
    """Verifies zero-downtime atomic pointer swap and version bumping."""
    manager = IndexLifecycleManager(PROCESSED_DIR)
    initial_status = manager.get_status()
    assert initial_status["status"] == "READY"
    initial_version = initial_status["current_version"]

    # Reindex sync
    res = manager.reindex_sync()
    assert res["success"] is True
    assert res["interactions_indexed"] > 3000
    assert res["utterances_indexed"] > 15000
    assert res["warmup_sample_found"] is True

    new_status = manager.get_status()
    assert new_status["status"] == "READY"
    assert new_status["current_version"] != initial_version


def test_time_context_api_endpoint():
    """Tests GET /api/v1/context/current-time endpoint."""
    resp = client.get("/api/v1/context/current-time?mock_time=13:30")
    assert resp.status_code == 200
    data = resp.json()
    assert data["slot_id"] == "lunch_time"
    assert "Mess" in data["location"] or "Canteen" in data["location"]
    assert "saptya da?" in data["typical_topics"]


def test_index_status_and_reindex_endpoints():
    """Tests GET /api/v1/admin/index-status and POST /api/v1/admin/reindex."""
    status_resp = client.get("/api/v1/admin/index-status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["status"] == "READY"
    assert "current_version" in status_data

    reindex_resp = client.post("/api/v1/admin/reindex")
    assert reindex_resp.status_code == 200
    reindex_data = reindex_resp.json()
    assert reindex_data["success"] is True
    assert reindex_data["interactions_indexed"] > 3000


def test_emotion_analytics_endpoint():
    """Tests GET /api/v1/analytics/emotions endpoint."""
    resp = client.get("/api/v1/analytics/emotions")
    assert resp.status_code == 200
    data = resp.json()
    assert "partner_emotion_distribution" in data
    assert "affectionate" in data["partner_emotion_distribution"]
    assert "playful_teasing" in data["partner_emotion_distribution"]
    assert data["total_analyzed_partner_messages"] > 15000


def test_provenance_separation_and_timeline_memories():
    """Verifies that evidence-based memories strictly enforce provenance classes."""
    import json
    from backend.app.services.chat_service import ChatOrchestrationService
    
    memories_file = PROCESSED_DIR / "relationship_memories.jsonl"
    with open(memories_file, "r", encoding="utf-8") as f:
        memories = [json.loads(line) for line in f]

    assert len(memories) >= 15
    for m in memories:
        assert "fact_type" in m
        assert "provenance" in m
        assert "do_not_present_as_fact" in m
        assert len(m["source_message_ids"]) > 0

    # Verify unverified recollections are quarantined
    unverified = [m for m in memories if m.get("do_not_present_as_fact")]
    assert len(unverified) >= 1
    assert any("Dharshan" in m["title"] for m in unverified)

    # Verify ChatOrchestrationService excludes unverified memories from approved retrieval
    chat = ChatOrchestrationService(PROCESSED_DIR)
    approved = chat.get_approved_memories()
    assert all(not m.get("do_not_present_as_fact") for m in approved)


def test_system_prompt_evidence_based_profile_constraints():
    """Verifies that the system prompt strictly incorporates conciseness and situation mapping."""
    from backend.app.services.chat_service import ChatOrchestrationService

    chat = ChatOrchestrationService(PROCESSED_DIR)
    prompt = chat._build_system_instruction()

    # Conciseness & Rhythm checks
    assert "13 characters" in prompt
    assert "52%" in prompt
    assert "Inga paaru" in prompt

    # Situation-to-Response checks
    assert "Manoj says he misses you" in prompt
    assert "jealousy" in prompt
    assert "family discovery" in prompt
    assert "physically unwell" in prompt

    # Negative Constraints checks
    assert "NEVER claim she cheated" in prompt
    assert "NEVER use guilt, threats" in prompt
    assert "MANDATORY DISCLOSURE" in prompt
