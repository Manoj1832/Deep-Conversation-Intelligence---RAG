from pathlib import Path
from backend.app.personality_engine.profile_builder import PersonalityProfileBuilder
from backend.app.personality_engine.profile_validator import ProfileValidator
from backend.app.memory_engine.extractor import RelationshipMemoryExtractor
from backend.app.memory_engine.memory_indexer import MemoryIndexer

def run_phase4():
    processed_dir = Path("/home/manoj/Documents/HerAI/data/processed")
    print("[*] Starting Phase 4: Personality Engine & Relationship Memory Engine...")

    # 1. Build Personality Profile & Observations
    builder = PersonalityProfileBuilder(processed_dir)
    profile, observations = builder.build()
    ProfileValidator.validate(profile, observations)
    print(f"[+] Generated Personality Profile (version: {profile['version']}) with {len(observations)} verified observations.")

    # 2. Extract Relationship Memories
    extractor = RelationshipMemoryExtractor(processed_dir)
    memories, report = extractor.extract()
    print(f"[+] Extracted {len(memories)} relationship memories ({report['approved_memories']} approved, {report['pending_review_memories']} pending review).")

    # 3. Index Approved Memories into Qdrant
    indexer = MemoryIndexer()
    indexed_count = indexer.index_approved_memories(memories)
    print(f"[+] Successfully indexed {indexed_count} approved memories into Qdrant collection 'herai_memories'.")

    return {
        "profile": profile,
        "observations_count": len(observations),
        "memories_count": len(memories),
        "approved_memories": report["approved_memories"],
        "pending_review": report["pending_review_memories"]
    }

if __name__ == "__main__":
    run_phase4()
