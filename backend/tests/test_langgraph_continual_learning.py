import pytest
import json
from pathlib import Path
from starlette.testclient import TestClient

from backend.app.main import app, chat_orchestrator, memory_resolver, PROCESSED_DIR
from backend.app.services.langgraph_agent import LangGraphConversationAgent, ConversationState


@pytest.fixture
def client():
    return TestClient(app)


def test_langgraph_graph_structure():
    """Verify that LangGraph workflow is properly built and compiled."""
    agent = LangGraphConversationAgent(chat_orchestrator, memory_resolver, processed_dir=PROCESSED_DIR)
    assert agent.app is not None
    # Verify graph node names
    nodes = agent.workflow.nodes
    assert "enrich_context" in nodes
    assert "generate_response" in nodes
    assert "self_learn_memory" in nodes


def test_langgraph_run_turn_and_context_enrichment():
    """Verify LangGraph run_turn accurately populates state with IST schedule and emotion."""
    agent = LangGraphConversationAgent(chat_orchestrator, memory_resolver, processed_dir=PROCESSED_DIR)
    state = agent.run_turn(
        user_message="miss you da chello romba kavalaiya irukku",
        mock_time_str="2026-11-19T22:30:00+05:30"
    )

    assert state is not None
    assert state.get("time_ctx") is not None
    assert "slot_id" in state["time_ctx"]
    assert state.get("detected_emotion") is not None
    assert len(state.get("full_response", "")) > 0
    assert state.get("generation_provider") is not None


def test_continual_learning_memory_extraction_and_deduplication():
    """Verify that conversations automatically extract new memories and deduplicate."""
    import time
    agent = LangGraphConversationAgent(chat_orchestrator, memory_resolver, processed_dir=PROCESSED_DIR)

    # Turn 1: Shares a new unique favorite item
    unique_suffix = int(time.time() * 1000)
    user_msg_1 = f"enakku homemade chocolate cake {unique_suffix} romba pudikkum da chello"
    state_1 = agent.run_turn(user_msg_1, session_id="test_session_learn")

    assert state_1.get("learned_memory_count", 0) >= 1
    extracted_1 = state_1.get("extracted_memories", [])
    assert len(extracted_1) >= 1
    assert any("chocolate" in m.get("title", "").lower() or "chocolate" in m.get("description", "").lower() for m in extracted_1)

    # Turn 2: Repeat the same preference -> Should deduplicate and not save again
    state_2 = agent.run_turn(user_msg_1, session_id="test_session_learn")
    assert state_2.get("learned_memory_count", 0) == 0
    assert state_2.get("memory_update_status") == "skipped_duplicate"


def test_langgraph_direct_endpoint(client):
    """Test the /api/v1/chat/langgraph endpoint."""
    res = client.post(
        "/api/v1/chat/langgraph",
        json={
            "session_id": "test_langgraph_endpoint_sess",
            "message": "naan hotel la dosa saapten da"
        },
        headers={"x-mock-time": "2026-11-19T13:30:00+05:30"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["session_id"] == "test_langgraph_endpoint_sess"
    assert "reply" in data
    assert len(data["reply"]) > 0
    assert "provider" in data
    assert "time_slot" in data


def test_chat_stream_with_langgraph_integration(client):
    """Test SSE streaming endpoint wired through LangGraph agent."""
    res = client.post(
        "/api/v1/chat/stream",
        json={
            "session_id": "test_langgraph_stream_sess",
            "message": "hi chello enna panra?"
        },
        headers={"x-mock-time": "2026-11-19T10:30:00+05:30"}
    )
    assert res.status_code == 200
    assert "text/event-stream" in res.headers["content-type"]
    text = res.text
    assert "event: metadata" in text
    assert "event: token" in text
    assert "event: end" in text
    assert "langgraph-2.0" in text
