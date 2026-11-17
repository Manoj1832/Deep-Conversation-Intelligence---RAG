"""
Phase 8 Master Pipeline Runner.
Executes the full Deep Conversation Intelligence & Reply Pattern Extraction workflow.
Produces all 7 processed artifacts and the held-out evaluation benchmark.
"""

import json
from pathlib import Path
import time

from backend.app.intelligence_engine.turn_reconstructor import TurnReconstructor
from backend.app.intelligence_engine.reply_linker import ReplyLinker
from backend.app.intelligence_engine.emotional_extractor import EmotionalContextExtractor
from backend.app.intelligence_engine.pattern_extractor import PatternExtractor
from backend.app.intelligence_engine.style_profiler import StyleProfiler
from backend.app.intelligence_engine.event_extractor import EventExtractor
from backend.app.intelligence_engine.knowledge_graph import KnowledgeGraphBuilder
from backend.app.intelligence_engine.evaluation_pipeline import EvaluationPipeline

def run_phase8_pipeline():
    start_time = time.perf_counter()
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    processed_dir = project_root / "data" / "processed"
    evaluation_dir = project_root / "data" / "evaluation"
    evaluation_dir.mkdir(parents=True, exist_ok=True)

    messages_file = processed_dir / "messages.jsonl"
    memories_file = processed_dir / "relationship_memories.jsonl"

    print("================================================================================")
    print("HERAI PHASE 8 — DEEP CONVERSATION INTELLIGENCE PIPELINE EXECUTION")
    print("================================================================================")

    # 1. Turn Reconstruction
    print("\n[1/8] Reconstructing conversational turns from 24,971 messages...")
    reconstructor = TurnReconstructor(max_gap_seconds=300)
    turns = reconstructor.reconstruct(messages_file)
    turns_file = processed_dir / "conversation_turns.jsonl"
    with open(turns_file, "w", encoding="utf-8") as f:
        for t in turns:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    print(f"✓ Reconstructed {len(turns):,} turns -> {turns_file.name}")

    # 2. Reply Linking
    print("\n[2/8] Linking conversation turns & establishing reply dependencies...")
    linker = ReplyLinker()
    links = linker.link_turns(turns)
    links_file = processed_dir / "reply_links.jsonl"
    with open(links_file, "w", encoding="utf-8") as f:
        for l in links:
            f.write(json.dumps(l, ensure_ascii=False) + "\n")
    print(f"✓ Established {len(links):,} reply links -> {links_file.name}")

    # 3. Emotional Context Extraction
    print("\n[3/8] Extracting context-sensitive emotional observations...")
    emotional_extractor = EmotionalContextExtractor()
    emotions = emotional_extractor.process_all_turns(turns)
    emotions_file = processed_dir / "emotional_contexts.jsonl"
    with open(emotions_file, "w", encoding="utf-8") as f:
        for e in emotions:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"✓ Extracted {len(emotions):,} emotional observations -> {emotions_file.name}")
    emotion_map = {e["turn_id"]: e for e in emotions}

    # 4. Situation-to-Response Pattern Extraction
    print("\n[4/8] Extracting grounded situation-to-response reply patterns...")
    pattern_extractor = PatternExtractor()
    patterns = pattern_extractor.extract_patterns(turns, emotion_map)
    patterns_file = processed_dir / "reply_patterns.jsonl"
    with open(patterns_file, "w", encoding="utf-8") as f:
        for p in patterns:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"✓ Extracted {len(patterns):,} situation-to-response patterns -> {patterns_file.name}")

    # 5. Deterministic Communication Style Profiling
    print("\n[5/8] Analyzing participant communication styles & rhythm...")
    style_profiler = StyleProfiler()
    style_profile = style_profiler.generate_style_profile(messages_file)
    style_file = processed_dir / "communication_style_profile.json"
    with open(style_file, "w", encoding="utf-8") as f:
        json.dump(style_profile, f, indent=2, ensure_ascii=False)
    print(f"✓ Generated communication style profile -> {style_file.name}")

    # 6. Relationship Event Extraction
    print("\n[6/8] Extracting chronological relationship events with source quotes...")
    event_extractor = EventExtractor()
    events = event_extractor.extract_events(messages_file)
    events_file = processed_dir / "relationship_events.jsonl"
    with open(events_file, "w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    print(f"✓ Extracted {len(events)} evidence-grounded timeline events -> {events_file.name}")

    # 7. Relationship Knowledge Graph
    print("\n[7/8] Building relationship knowledge graph...")
    memories = []
    if memories_file.exists():
        with open(memories_file, "r", encoding="utf-8") as f:
            memories = [json.loads(line) for line in f]
    kg_builder = KnowledgeGraphBuilder()
    graph = kg_builder.build_graph(events, memories)
    graph_file = processed_dir / "relationship_knowledge_graph.json"
    with open(graph_file, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)
    print(f"✓ Built knowledge graph ({graph['total_nodes']} nodes, {graph['total_edges']} edges) -> {graph_file.name}")

    # 8. Held-Out Evaluation Dataset & Benchmark
    print("\n[8/8] Building held-out evaluation set and running benchmark...")
    eval_pipeline = EvaluationPipeline()
    eval_set = eval_pipeline.create_heldout_dataset(patterns, split_ratio=0.15)
    eval_set_file = evaluation_dir / "herai_heldout_dataset.jsonl"
    with open(eval_set_file, "w", encoding="utf-8") as f:
        for r in eval_set:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"✓ Saved {len(eval_set):,} held-out evaluation test cases -> {eval_set_file.name}")

    eval_report = eval_pipeline.run_benchmark(eval_set)
    eval_report_file = evaluation_dir / "evaluation_report.json"
    with open(eval_report_file, "w", encoding="utf-8") as f:
        json.dump(eval_report, f, indent=2, ensure_ascii=False)
    print(f"✓ Generated evaluation report -> {eval_report_file.name}")

    duration = time.perf_counter() - start_time
    print("\n================================================================================")
    print(f"PHASE 8 PIPELINE COMPLETED SUCCESSFULLY IN {duration:.2f}s!")
    print("================================================================================")

if __name__ == "__main__":
    run_phase8_pipeline()
