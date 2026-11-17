import pytest
from pathlib import Path
from backend.app.personality_engine.profile_validator import ProfileValidator
from backend.app.personality_engine.profile_builder import PersonalityProfileBuilder
from backend.app.memory_engine.extractor import RelationshipMemoryExtractor
from backend.app.memory_engine.resolver import MemoryResolver
from backend.app.memory_engine.deduplicator import MemoryDeduplicator
from backend.app.memory_engine.contradiction_detector import ContradictionDetector
from backend.app.memory_engine.review_service import MemoryReviewService
from backend.app.memory_engine.memory_indexer import MemoryIndexer

@pytest.fixture
def processed_dir():
    return Path("/home/manoj/Documents/HerAI/data/processed")

def test_personality_profile_builder_and_validator(processed_dir):
    builder = PersonalityProfileBuilder(processed_dir)
    profile, observations = builder.build()
    
    assert profile["version"] == "1.0.0"
    assert profile["total_messages_analyzed"] > 10000
    assert len(observations) == 5
    assert ProfileValidator.validate(profile, observations) is True

def test_memory_extraction_and_grounding(processed_dir):
    extractor = RelationshipMemoryExtractor(processed_dir)
    memories, report = extractor.extract()

    assert len(memories) >= 7
    assert report["evidence_grounding_rate"] == 1.0
    for m in memories:
        assert len(m["source_message_ids"]) > 0
        assert 0.0 <= m["confidence"] <= 1.0
        assert m["verification_status"] in ["approved", "pending_review"]

def test_memory_review_lifecycle():
    sample_memory = {
        "memory_id": "test_mem_001",
        "category": "preferences",
        "title": "Favorite Drink",
        "description": "Prefers hot tea in the morning",
        "verification_status": "pending_review",
        "confidence": 0.90,
        "source_message_ids": ["msg_1"]
    }

    resolver = MemoryResolver([sample_memory])
    review_svc = MemoryReviewService(resolver)

    # Approve
    approved = review_svc.approve_memory("test_mem_001")
    assert approved["verification_status"] == "approved"

    # Reject
    rejected = review_svc.reject_memory("test_mem_001", reason="Duplicate")
    assert rejected["verification_status"] == "rejected"

def test_memory_resolver_update_and_delete():
    sample = {
        "memory_id": "test_mem_002",
        "category": "nicknames",
        "title": "Old Title",
        "description": "Old desc",
        "verification_status": "approved",
        "confidence": 0.85
    }

    resolver = MemoryResolver([sample])
    updated = resolver.update_memory("test_mem_002", {"title": "New Title"})
    assert updated["title"] == "New Title"

    deleted = resolver.delete_memory("test_mem_002")
    assert deleted is True
    assert resolver.get_memory("test_mem_002") is None

def test_qdrant_memory_indexer():
    indexer = MemoryIndexer()
    sample_memories = [
        {
            "memory_id": "00000000-0000-0000-0000-000000000001",
            "category": "preferences",
            "title": "Test Memory Approved",
            "description": "Desc",
            "confidence": 0.95,
            "verification_status": "approved"
        },
        {
            "memory_id": "00000000-0000-0000-0000-000000000002",
            "category": "preferences",
            "title": "Test Memory Pending",
            "description": "Desc",
            "confidence": 0.80,
            "verification_status": "pending_review"
        }
    ]

    indexed_count = indexer.index_approved_memories(sample_memories)
    # Only approved memory should be indexed
    assert indexed_count == 1

    # Test deletion
    indexer.delete_from_index("00000000-0000-0000-0000-000000000001")
