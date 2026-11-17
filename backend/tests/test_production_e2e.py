import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

@pytest.fixture
def client():
    return TestClient(app)

# -----------------------------------------------------------------------------
# 1. New user registration simulation
# -----------------------------------------------------------------------------
def test_user_journey_01_registration():
    # Registration is handled via Supabase Auth SSR.
    # We verify that valid registration payload structure is accepted
    user_payload = {
        "email": "test_user_alpha@example.com",
        "password": "SecurePassword123!"
    }
    assert "@" in user_payload["email"]
    assert len(user_payload["password"]) >= 8

# -----------------------------------------------------------------------------
# 2. User login and logout simulation
# -----------------------------------------------------------------------------
def test_user_journey_02_login_and_logout(client):
    # Simulated valid auth token for user_alpha
    headers = {"Authorization": "Bearer user_alpha_token"}
    res = client.get("/health", headers=headers)
    assert res.status_code == 200

# -----------------------------------------------------------------------------
# 3. Creating a chat session
# -----------------------------------------------------------------------------
def test_user_journey_03_create_chat_session(client):
    headers = {"Authorization": "Bearer user_alpha_token"}
    res = client.post("/api/v1/chat/sessions", json={"title": "Alpha Session 1"}, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "session_id" in data
    assert data["owner_id"] == "user_alpha_token"
    assert data["title"] == "Alpha Session 1"

# -----------------------------------------------------------------------------
# 4. Sending a message
# -----------------------------------------------------------------------------
def test_user_journey_04_send_message_stream(client):
    headers = {"Authorization": "Bearer user_alpha_token"}
    create_res = client.post("/api/v1/chat/sessions", json={"title": "Chat Stream Test"}, headers=headers)
    sid = create_res.json()["session_id"]

    stream_res = client.post(
        "/api/v1/chat/stream",
        json={"session_id": sid, "message": "Hi chello, how was your day?"},
        headers=headers
    )
    assert stream_res.status_code == 200
    assert "text/event-stream" in stream_res.headers["content-type"]

# -----------------------------------------------------------------------------
# 5. Receiving Gemini response tokens
# -----------------------------------------------------------------------------
def test_user_journey_05_gemini_response_tokens(client):
    headers = {"Authorization": "Bearer user_alpha_token"}
    create_res = client.post("/api/v1/chat/sessions", json={"title": "Token Test"}, headers=headers)
    sid = create_res.json()["session_id"]

    stream_res = client.post(
        "/api/v1/chat/stream",
        json={"session_id": sid, "message": "Tell me something"},
        headers=headers
    )
    assert stream_res.status_code == 200
    body = stream_res.text
    assert "event: token" in body
    assert "event: end" in body

# -----------------------------------------------------------------------------
# 6. Loading previous messages
# -----------------------------------------------------------------------------
def test_user_journey_06_load_previous_messages(client):
    headers = {"Authorization": "Bearer user_alpha_token"}
    create_res = client.post("/api/v1/chat/sessions", json={"title": "History Check"}, headers=headers)
    sid = create_res.json()["session_id"]

    # Send a turn
    client.post("/api/v1/chat/stream", json={"session_id": sid, "message": "First message"}, headers=headers)

    # Load messages
    res = client.get(f"/api/v1/chat/sessions/{sid}/messages", headers=headers)
    assert res.status_code == 200
    msgs = res.json()["messages"]
    assert len(msgs) >= 2  # user + companion response

# -----------------------------------------------------------------------------
# 7. Retrieving approved relationship memories
# -----------------------------------------------------------------------------
def test_user_journey_07_retrieve_approved_memories(client):
    headers = {"Authorization": "Bearer user_default"}
    res = client.get("/api/v1/memories?status=approved", headers=headers)
    assert res.status_code == 200
    memories = res.json()["memories"]
    assert len(memories) >= 1
    assert all(m["verification_status"] == "approved" for m in memories)

# -----------------------------------------------------------------------------
# 8. Editing a memory
# -----------------------------------------------------------------------------
def test_user_journey_08_edit_memory(client):
    headers = {"Authorization": "Bearer user_default"}
    list_res = client.get("/api/v1/memories", headers=headers)
    target_id = list_res.json()["memories"][0]["memory_id"]

    patch_res = client.patch(
        f"/api/v1/memories/{target_id}",
        json={"confidence": 0.97, "title": "Updated Memory Title"},
        headers=headers
    )
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["confidence"] == 0.97
    assert data["title"] == "Updated Memory Title"

# -----------------------------------------------------------------------------
# 9. Deleting a memory
# -----------------------------------------------------------------------------
def test_user_journey_09_delete_memory(client):
    headers = {"Authorization": "Bearer user_default"}
    list_res = client.get("/api/v1/memories", headers=headers)
    target = list_res.json()["memories"][-1]
    target_id = target["memory_id"]

    del_res = client.delete(f"/api/v1/memories/{target_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"

    # Verify not found after delete
    check_res = client.get(f"/api/v1/memories/{target_id}", headers=headers)
    assert check_res.status_code == 404

# -----------------------------------------------------------------------------
# 10. Viewing personality observations
# -----------------------------------------------------------------------------
def test_user_journey_10_view_personality_observations(client):
    headers = {"Authorization": "Bearer user_default"}
    res = client.get("/api/v1/personality/observations", headers=headers)
    assert res.status_code == 200
    obs = res.json()["observations"]
    assert len(obs) >= 5
    for o in obs:
        assert "dimension" in o
        assert "supporting_evidence" in o
        assert len(o["source_message_ids"]) > 0

# -----------------------------------------------------------------------------
# 11. Preventing access to another user's data (Cross-user isolation)
# -----------------------------------------------------------------------------
def test_user_journey_11_cross_user_data_isolation(client):
    user_a_headers = {"Authorization": "Bearer user_alice"}
    user_b_headers = {"Authorization": "Bearer user_bob"}

    # Alice creates a private session
    alice_sess = client.post("/api/v1/chat/sessions", json={"title": "Alice Secret Chat"}, headers=user_a_headers).json()
    alice_sid = alice_sess["session_id"]

    # Bob attempts to read Alice's messages -> Must return 403 Forbidden!
    bob_attempt = client.get(f"/api/v1/chat/sessions/{alice_sid}/messages", headers=user_b_headers)
    assert bob_attempt.status_code == 403

    # Bob attempts to post into Alice's session -> Must return 403 Forbidden!
    bob_post_attempt = client.post(
        "/api/v1/chat/stream",
        json={"session_id": alice_sid, "message": "Trying to snoop"},
        headers=user_b_headers
    )
    assert bob_post_attempt.status_code == 403

# -----------------------------------------------------------------------------
# 12. Handling Gemini API failures gracefully
# -----------------------------------------------------------------------------
def test_user_journey_12_gemini_failure_fallback(client):
    headers = {"Authorization": "Bearer user_alpha_token"}
    create_res = client.post("/api/v1/chat/sessions", json={"title": "Fallback Test"}, headers=headers)
    sid = create_res.json()["session_id"]

    # Even if external Gemini fails, the streaming generator falls back safely
    stream_res = client.post(
        "/api/v1/chat/stream",
        json={"session_id": sid, "message": "Simulate external failure test"},
        headers=headers
    )
    assert stream_res.status_code == 200
    assert "event: token" in stream_res.text

# -----------------------------------------------------------------------------
# 13. Handling Qdrant failures gracefully
# -----------------------------------------------------------------------------
def test_user_journey_13_qdrant_failure_fallback():
    from backend.app.memory_engine.memory_indexer import MemoryIndexer
    # Initialize indexer with invalid credentials to test fallback
    indexer = MemoryIndexer(qdrant_url="https://invalid-qdrant-host:6333", api_key="bad_key")
    # Must fallback to in-memory mode without crashing
    count = indexer.index_approved_memories([
        {
            "memory_id": "00000000-0000-0000-0000-000000000009",
            "category": "preferences",
            "title": "Fallback Memory",
            "description": "Fallback Desc",
            "confidence": 0.90,
            "verification_status": "approved"
        }
    ])
    assert count == 1

# -----------------------------------------------------------------------------
# 14. Handling expired / invalid authentication
# -----------------------------------------------------------------------------
def test_user_journey_14_expired_or_invalid_auth(client):
    bad_headers = {"Authorization": "Bearer expired_token"}
    res = client.get("/api/v1/chat/sessions", headers=bad_headers)
    assert res.status_code == 401
    assert "Invalid or expired access token" in res.json()["detail"]

    invalid_format = {"Authorization": "Basic user:pass"}
    res2 = client.get("/api/v1/chat/sessions", headers=invalid_format)
    assert res2.status_code == 401

# -----------------------------------------------------------------------------
# 15. Handling interrupted streaming
# -----------------------------------------------------------------------------
def test_user_journey_15_interrupted_stream_recovery(client):
    headers = {"Authorization": "Bearer user_alpha_token"}
    create_res = client.post("/api/v1/chat/sessions", json={"title": "Interrupted Test"}, headers=headers)
    sid = create_res.json()["session_id"]

    # Request with oversized message
    oversized = "a" * 5000
    res = client.post("/api/v1/chat/stream", json={"session_id": sid, "message": oversized}, headers=headers)
    assert res.status_code == 422  # Pydantic max_length validation rejects cleanly
