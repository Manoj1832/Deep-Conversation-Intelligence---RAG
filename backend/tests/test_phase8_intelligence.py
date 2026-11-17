"""
Comprehensive Integration Tests for Phase 8: Deep Conversation Intelligence.
Verifies all 8 intelligence engine modules and deliverables:
- Turn Reconstruction
- Reply Linking
- Emotional Context Extraction
- Reply Pattern Extraction
- Communication Style Profiling
- Relationship Event Extraction
- Knowledge Graph Construction
- Held-out Evaluation Pipeline
"""

import pytest
import json
from pathlib import Path

from backend.app.intelligence_engine.turn_reconstructor import TurnReconstructor
from backend.app.intelligence_engine.reply_linker import ReplyLinker
from backend.app.intelligence_engine.emotional_extractor import EmotionalContextExtractor
from backend.app.intelligence_engine.pattern_extractor import PatternExtractor
from backend.app.intelligence_engine.style_profiler import StyleProfiler
from backend.app.intelligence_engine.event_extractor import EventExtractor
from backend.app.intelligence_engine.knowledge_graph import KnowledgeGraphBuilder
from backend.app.intelligence_engine.evaluation_pipeline import EvaluationPipeline

PROCESSED_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "processed"
EVALUATION_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "evaluation"


def test_turn_reconstruction_integrity():
    """Verifies that reconstructed turns preserve constituent IDs and group rapid bubbles."""
    turns_file = PROCESSED_DIR / "conversation_turns.jsonl"
    assert turns_file.exists(), "conversation_turns.jsonl must exist"

    turns = []
    with open(turns_file, "r", encoding="utf-8") as f:
        for line in f:
            turns.append(json.loads(line))

    assert len(turns) >= 5000, f"Expected at least 5000 turns, got {len(turns)}"

    for t in turns[:100]:
        assert "turn_id" in t
        assert "speaker" in t and t["speaker"] in ["partner", "user"]
        assert "constituent_message_ids" in t
        assert len(t["constituent_message_ids"]) >= 1
        assert "combined_text" in t
        assert "conversation_topic" in t
        assert 0.0 <= t["reconstruction_confidence"] <= 1.0


def test_reply_linking_and_confidence():
    """Verifies that reply links have calibrated confidence and alternating speakers."""
    links_file = PROCESSED_DIR / "reply_links.jsonl"
    assert links_file.exists(), "reply_links.jsonl must exist"

    links = []
    with open(links_file, "r", encoding="utf-8") as f:
        for line in f:
            links.append(json.loads(line))

    assert len(links) >= 4000

    valid_levels = {"explicit", "strong_inference", "weak_inference", "unknown"}
    for l in links[:100]:
        assert l["confidence_level"] in valid_levels
        assert 0.0 <= l["confidence_score"] <= 1.0
        assert l["source_speaker"] != l["response_speaker"]
        assert len(l["linking_features"]) >= 1


def test_emotional_contexts_cues_and_intensities():
    """Verifies emotional observations have cues, intensities, and no diagnostic claims."""
    emotions_file = PROCESSED_DIR / "emotional_contexts.jsonl"
    assert emotions_file.exists(), "emotional_contexts.jsonl must exist"

    emotions = []
    with open(emotions_file, "r", encoding="utf-8") as f:
        for line in f:
            emotions.append(json.loads(line))

    assert len(emotions) >= 5000

    valid_intensities = {"low", "medium", "high", "unknown"}
    for e in emotions[:100]:
        assert e["intensity"] in valid_intensities
        assert "primary_label" in e
        assert len(e["evidence_message_ids"]) >= 1
        assert 0.0 <= e["confidence"] <= 1.0
        assert "interpretation" in e
        # Must never contain clinical diagnosis words
        interp_lower = e["interpretation"].lower()
        for bad_word in ["bpd", "narcissis", "depression diagnosis", "disorder", "patholog"]:
            assert bad_word not in interp_lower


def test_reply_patterns_grounded_responses():
    """Verifies situation-to-response patterns preserve actual responses without fictional rewriting."""
    patterns_file = PROCESSED_DIR / "reply_patterns.jsonl"
    assert patterns_file.exists(), "reply_patterns.jsonl must exist"

    patterns = []
    with open(patterns_file, "r", encoding="utf-8") as f:
        for line in f:
            patterns.append(json.loads(line))

    assert len(patterns) >= 2000

    categories = set()
    for p in patterns:
        categories.add(p["situation_category"])
        assert len(p["actual_response_text"]) > 0
        assert len(p["source_message_ids"]) >= 2
        assert p["outcome"] in ["resolved", "partially_resolved", "unresolved", "unknown"]

    assert len(categories) >= 15, f"Expected at least 15 situation categories, got {len(categories)}"


def test_communication_style_profile_metrics():
    """Verifies that style profile reports deterministic median/mean lengths and token ratios."""
    profile_file = PROCESSED_DIR / "communication_style_profile.json"
    assert profile_file.exists(), "communication_style_profile.json must exist"

    with open(profile_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    partner = data["partner_profile"]
    assert partner["participant"] == "partner"
    rhythm = partner["message_rhythm"]
    assert rhythm["median_character_length"] <= 15.0
    assert rhythm["percentage_two_tokens_or_less"] >= 50.0
    assert len(partner["language_patterns"]["top_colloquial_vocabulary"]) >= 10


def test_relationship_events_and_provenance():
    """Verifies chronological relationship events have quotes and fact types."""
    events_file = PROCESSED_DIR / "relationship_events.jsonl"
    assert events_file.exists(), "relationship_events.jsonl must exist"

    events = []
    with open(events_file, "r", encoding="utf-8") as f:
        for line in f:
            events.append(json.loads(line))

    assert len(events) >= 8
    for ev in events:
        assert ev["fact_type"] in ["explicit_statement", "observed_event", "interpretation"]
        assert len(ev["what_was_explicitly_said"]) >= 1
        assert len(ev["source_message_ids"]) >= 1
        assert len(ev["participants"]) >= 2


def test_relationship_knowledge_graph_connectivity():
    """Verifies knowledge graph has valid nodes, edges, and relationship types."""
    kg_file = PROCESSED_DIR / "relationship_knowledge_graph.json"
    assert kg_file.exists(), "relationship_knowledge_graph.json must exist"

    with open(kg_file, "r", encoding="utf-8") as f:
        graph = json.load(f)

    assert graph["total_nodes"] >= 30
    assert graph["total_edges"] >= 40
    node_ids = {n["node_id"] for n in graph["nodes"]}
    for edge in graph["edges"]:
        assert edge["source_node_id"] in node_ids
        assert edge["target_node_id"] in node_ids
        assert len(edge["source_message_ids"]) >= 1


def test_heldout_evaluation_dataset_and_report():
    """Verifies held-out evaluation dataset and benchmark report."""
    eval_file = EVALUATION_DIR / "herai_heldout_dataset.jsonl"
    report_file = EVALUATION_DIR / "evaluation_report.json"

    assert eval_file.exists(), "herai_heldout_dataset.jsonl must exist"
    assert report_file.exists(), "evaluation_report.json must exist"

    eval_items = []
    with open(eval_file, "r", encoding="utf-8") as f:
        for line in f:
            eval_items.append(json.loads(line))

    assert len(eval_items) >= 200
    for it in eval_items[:50]:
        assert "user_prompt" in it
        assert "target_ground_truth_response" in it
        assert len(it["target_ground_truth_response"]) > 0

    with open(report_file, "r", encoding="utf-8") as f:
        report = json.load(f)

    metrics = report["quantitative_metrics"]
    assert metrics["hallucination_rate"] == 0.0
    assert metrics["context_understanding_accuracy"] >= 0.90
    assert report["evaluation_verdict"]["status"] == "PASSED_STRICT_BENCHMARK"
