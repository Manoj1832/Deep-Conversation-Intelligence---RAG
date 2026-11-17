import os
import json
import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from pathlib import Path

from backend.app.models.schemas import SourceMessageSchema, ConversationSessionSchema
from backend.app.services.parser import WhatsAppParser
from backend.app.services.normalizer import SenderNormalizer
from backend.app.services.deduplicator import MessageDeduplicator
from backend.app.services.sessionizer import ConversationSessionizer
from backend.app.services.exporter import DataExporter
from backend.app.services.storage import DatabaseStorageService

def test_ios_format_parsing():
    parser = WhatsAppParser()
    lines = [
        "[11/29/25, 6:09:06 PM] Sakthi: Hey! How are you?",
        "[11/29/25, 6:09:16 PM] Manoj: All good, just finishing work.",
    ]
    def gen():
        for l in lines: yield l

    records = list(parser.stream_parse(gen()))
    assert len(records) == 2
    assert records[0].original_sender == "Sakthi"
    assert records[0].body == "Hey! How are you?"
    assert records[0].message_type == "text"
    assert records[0].timestamp_dt.year == 2025
    assert records[0].timestamp_dt.month == 11
    assert records[0].timestamp_dt.day == 29
    assert records[0].timestamp_dt.hour == 18
    assert records[0].timestamp_dt.minute == 9

def test_android_format_parsing():
    parser = WhatsAppParser()
    lines = [
        "29/11/2025, 18:09 - Sakthi: Hi from Android",
        "29/11/2025, 18:10 - Manoj: Replying back",
    ]
    def gen():
        for l in lines: yield l

    records = list(parser.stream_parse(gen()))
    assert len(records) == 2
    assert records[0].original_sender == "Sakthi"
    assert records[0].body == "Hi from Android"

def test_multiline_messages():
    parser = WhatsAppParser()
    lines = [
        "[11/29/25, 6:09:06 PM] Sakthi: Line one of message",
        "Line two continuation",
        "Line three continuation",
        "[11/29/25, 6:10:00 PM] Manoj: Received."
    ]
    def gen():
        for l in lines: yield l

    records = list(parser.stream_parse(gen()))
    assert len(records) == 2
    assert records[0].is_multiline is True
    assert "Line one of message\nLine two continuation\nLine three continuation" == records[0].body

def test_emojis_and_tamil_transliteration():
    parser = WhatsAppParser()
    lines = [
        "[11/29/25, 6:09:06 PM] Sakthi: Seri da ❤️‍🩹🥺 super",
        "[11/29/25, 6:10:00 PM] Manoj: Enga veetla solliten pa",
    ]
    def gen():
        for l in lines: yield l

    records = list(parser.stream_parse(gen()))
    assert len(records) == 2
    assert "❤️‍🩹🥺" in records[0].body
    assert "Enga veetla solliten pa" in records[1].body

def test_media_and_deleted_placeholders():
    parser = WhatsAppParser()
    lines = [
        "[11/29/25, 6:09:06 PM] Sakthi: \u200eimage omitted",
        "[11/29/25, 6:09:16 PM] Sakthi: \u200esticker omitted",
        "[11/29/25, 6:09:26 PM] Manoj: \u200eThis message was deleted.",
        "[11/29/25, 6:09:36 PM] Sakthi: \u200eMissed voice call, \u200eTap to call back",
        "[11/29/25, 6:09:46 PM] Sakthi: \u200eMessages and calls are end-to-end encrypted.",
    ]
    def gen():
        for l in lines: yield l

    records = list(parser.stream_parse(gen()))
    assert len(records) == 5
    assert records[0].message_type == "media"
    assert records[0].media_type == "image"
    assert records[1].message_type == "media"
    assert records[1].media_type == "sticker"
    assert records[2].message_type == "deleted"
    assert records[3].message_type == "call_log"
    assert records[4].message_type == "system"

def test_sender_normalization():
    norm = SenderNormalizer({
        "Manoj": "user",
        "Sakthi": "partner",
        "sakthijayasri": "partner",
        "❤️‍🩹": "partner"
    })

    assert norm.normalize("Manoj")[0] == "user"
    assert norm.normalize("Sakthi")[0] == "partner"
    assert norm.normalize("sakthijayasri")[0] == "partner"
    assert norm.normalize("❤️‍🩹")[0] == "partner"
    
    # Unknown sender check
    val, is_known = norm.normalize("RandomHacker")
    assert not is_known
    assert "RandomHacker" in norm.get_unknown_senders()

def test_duplicate_detection_preserves_legitimate_repeated_words():
    dedup = MessageDeduplicator()
    archive_a = "archive_a.zip"
    archive_b = "archive_b.zip"

    # Message 1: "seri" at 10:00:00
    msg1 = SourceMessageSchema(
        id=uuid4(),
        archive_id=uuid4(),
        source_message_id="a:1",
        timestamp=datetime(2025, 11, 29, 10, 0, 0),
        sender="partner",
        original_sender="Sakthi",
        body="seri",
        message_type="text",
        media_type="none",
        is_system_message=False,
        is_multiline=False,
        source_line_number=1,
        content_hash=MessageDeduplicator.compute_hash(
            datetime(2025, 11, 29, 10, 0, 0), "partner", "text", "seri"
        ),
        created_at=datetime.utcnow()
    )

    # Message 2: "seri" at 10:05:00 (Legitimate repeat -> NOT a duplicate!)
    msg2 = SourceMessageSchema(
        id=uuid4(),
        archive_id=uuid4(),
        source_message_id="a:2",
        timestamp=datetime(2025, 11, 29, 10, 5, 0),
        sender="partner",
        original_sender="Sakthi",
        body="seri",
        message_type="text",
        media_type="none",
        is_system_message=False,
        is_multiline=False,
        source_line_number=2,
        content_hash=MessageDeduplicator.compute_hash(
            datetime(2025, 11, 29, 10, 5, 0), "partner", "text", "seri"
        ),
        created_at=datetime.utcnow()
    )

    # Message 3: Exact same message 1 appearing in archive B (Cross-archive duplicate!)
    msg3 = SourceMessageSchema(
        id=uuid4(),
        archive_id=uuid4(),
        source_message_id="b:1",
        timestamp=datetime(2025, 11, 29, 10, 0, 0),
        sender="partner",
        original_sender="sakthijayasri",
        body="seri",
        message_type="text",
        media_type="none",
        is_system_message=False,
        is_multiline=False,
        source_line_number=1,
        content_hash=MessageDeduplicator.compute_hash(
            datetime(2025, 11, 29, 10, 0, 0), "partner", "text", "seri"
        ),
        created_at=datetime.utcnow()
    )

    is_dup1, _ = dedup.process(msg1, archive_a)
    is_dup2, _ = dedup.process(msg2, archive_a)
    is_dup3, canonical = dedup.process(msg3, archive_b)

    assert is_dup1 is False
    assert is_dup2 is False
    assert is_dup3 is True
    assert dedup.total_duplicates_found == 1
    assert archive_b in canonical.duplicate_archive_provenance

def test_session_segmentation_threshold():
    sessionizer = ConversationSessionizer(inactivity_threshold_hours=6.0)

    t0 = datetime(2025, 11, 29, 10, 0, 0)
    msgs = [
        # Session 1: 10:00 and 12:00
        SourceMessageSchema(
            id=uuid4(), archive_id=uuid4(), source_message_id="1", timestamp=t0,
            sender="partner", original_sender="Sakthi", body="Hi", message_type="text",
            media_type="none", source_line_number=1, content_hash="h1"
        ),
        SourceMessageSchema(
            id=uuid4(), archive_id=uuid4(), source_message_id="2", timestamp=t0 + timedelta(hours=2),
            sender="user", original_sender="Manoj", body="Hey", message_type="text",
            media_type="none", source_line_number=2, content_hash="h2"
        ),
        # Session 2: 7 hours after last message (> 6 hrs)
        SourceMessageSchema(
            id=uuid4(), archive_id=uuid4(), source_message_id="3", timestamp=t0 + timedelta(hours=9),
            sender="partner", original_sender="Sakthi", body="Back again", message_type="text",
            media_type="none", source_line_number=3, content_hash="h3"
        )
    ]

    sessions, assigned_msgs = sessionizer.segment(msgs)
    assert len(sessions) == 2
    assert sessions[0].message_count == 2
    assert sessions[1].message_count == 1
    assert assigned_msgs[0].session_id == sessions[0].session_id
    assert assigned_msgs[2].session_id == sessions[1].session_id

def test_jsonl_export_validity(tmp_path):
    exporter = DataExporter(tmp_path)
    msg = SourceMessageSchema(
        id=uuid4(), archive_id=uuid4(), source_message_id="test:1", timestamp=datetime.utcnow(),
        sender="partner", original_sender="Sakthi", body="Test jsonl", message_type="text",
        media_type="none", source_line_number=1, content_hash="hash_test"
    )

    p = exporter.export_messages_jsonl([msg])
    assert p.exists()
    with open(p, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["body"] == "Test jsonl"
        assert data["sender"] == "partner"

def test_database_idempotent_batch(tmp_path):
    db_file = tmp_path / "test.db"
    storage = DatabaseStorageService(f"sqlite:///{db_file}")

    archive_id = uuid4()
    msg = SourceMessageSchema(
        id=uuid4(), archive_id=archive_id, source_message_id="test:1", timestamp=datetime.utcnow(),
        sender="partner", original_sender="Sakthi", body="DB test message", message_type="text",
        media_type="none", source_line_number=1, content_hash="db_hash_1"
    )

    # First insert
    count1 = storage.persist_messages_batch([msg])
    assert count1 == 1

    # Re-running insert with same message (idempotency check)
    count2 = storage.persist_messages_batch([msg])
    assert count2 == 0
