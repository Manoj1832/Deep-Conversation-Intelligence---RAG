import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_health_check(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"

def test_chat_session_lifecycle(client):
    # Create session
    create_res = client.post("/api/v1/chat/sessions", json={"title": "Test Chat"})
    assert create_res.status_code == 200
    sess = create_res.json()
    assert "session_id" in sess
    sess_id = sess["session_id"]

    # List sessions
    list_res = client.get("/api/v1/chat/sessions")
    assert list_res.status_code == 200
    sessions = list_res.json()["sessions"]
    assert any(s["session_id"] == sess_id for s in sessions)

    # Get session messages (empty initially)
    msg_res = client.get(f"/api/v1/chat/sessions/{sess_id}/messages")
    assert msg_res.status_code == 200
    assert msg_res.json()["messages"] == []

def test_chat_streaming(client):
    # Stream a message
    res = client.post(
        "/api/v1/chat/stream",
        json={"session_id": "test_stream_sess", "message": "Hi chello! Enna panra?"}
    )
    assert res.status_code == 200
    assert "text/event-stream" in res.headers["content-type"]
    text_content = res.text
    assert "event: metadata" in text_content
    assert "event: token" in text_content
    assert "event: end" in text_content

def test_personality_endpoints(client):
    res = client.get("/api/v1/personality")
    assert res.status_code == 200
    data = res.json()
    assert data["version"] == "1.0.0"
    assert "language_patterns" in data

    obs_res = client.get("/api/v1/personality/observations")
    assert obs_res.status_code == 200
    obs = obs_res.json()["observations"]
    assert len(obs) >= 5

def test_memories_endpoints_and_actions(client):
    # List memories
    res = client.get("/api/v1/memories")
    assert res.status_code == 200
    memories = res.json()["memories"]
    assert len(memories) >= 7

    target_id = memories[0]["memory_id"]

    # Get single memory
    single_res = client.get(f"/api/v1/memories/{target_id}")
    assert single_res.status_code == 200
    assert single_res.json()["memory_id"] == target_id

    # Patch memory
    patch_res = client.patch(f"/api/v1/memories/{target_id}", json={"confidence": 0.99})
    assert patch_res.status_code == 200
    assert patch_res.json()["confidence"] == 0.99

    # Approve memory
    appr_res = client.post(f"/api/v1/memories/{target_id}/approve")
    assert appr_res.status_code == 200
    assert appr_res.json()["verification_status"] == "approved"

    # Reject memory
    rej_res = client.post(f"/api/v1/memories/{target_id}/reject", json={"reason": "Testing reject"})
    assert rej_res.status_code == 200
    assert rej_res.json()["verification_status"] == "rejected"

def test_historical_sessions_and_messages(client):
    res = client.get("/api/v1/history/sessions?limit=5")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 205
    assert len(data["sessions"]) == 5

    sample_session_id = data["sessions"][0]["session_id"]
    msg_res = client.get(f"/api/v1/history/sessions/{sample_session_id}/messages?limit=10")
    assert msg_res.status_code == 200
    assert "messages" in msg_res.json()
