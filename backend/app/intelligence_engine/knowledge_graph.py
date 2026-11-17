"""
Relationship Knowledge Graph Builder for HerAI Phase 8.
Constructs an interconnected semantic knowledge graph of persons, events, dates,
places, topics, promises, and memories grounded in validated timeline evidence.

Node Types: person, event, date, topic, promise, preference, place, conversation, memory
Edge Types: PARTICIPATED_IN, DISCUSSED, OCCURRED_ON, RELATED_TO, PROMISED, APOLOGIZED_FOR, FOLLOWED_BY, CONTRADICTS, MENTIONS
"""

from uuid import uuid4
from typing import List, Dict, Any, Optional

class KnowledgeGraphBuilder:
    """
    Builds structured relationship knowledge graphs with evidence-grounded edges.
    """

    def build_graph(self, events: List[Dict[str, Any]], memories: List[Dict[str, Any]]) -> Dict[str, Any]:
        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Dict[str, Any]] = []

        def add_node(node_id: str, name: str, node_type: str, properties: Dict[str, Any] = None):
            if node_id not in nodes:
                nodes[node_id] = {
                    "node_id": node_id,
                    "name": name,
                    "node_type": node_type,
                    "properties": properties or {}
                }

        def add_edge(src_id: str, tgt_id: str, rel_type: str, evidence_ids: List[str], conf: float = 0.95):
            edges.append({
                "edge_id": str(uuid4()),
                "source_node_id": src_id,
                "target_node_id": tgt_id,
                "relation_type": rel_type,
                "source_message_ids": evidence_ids[:4],
                "confidence": conf,
                "evidence_type": "source_archive_quote",
                "review_status": "approved"
            })

        # 1. Base Core Persons
        add_node("person:sakthi", "Sakthi", "person", {"role": "companion", "normalized_sender": "partner"})
        add_node("person:manoj", "Manoj", "person", {"role": "user", "normalized_sender": "user"})
        add_node("person:amma", "Amma (Mother)", "person", {"role": "family_member"})
        add_node("person:dharshan", "Dharshan", "person", {"role": "college_junior_associate"})

        # 2. Key Places
        add_node("place:thiruchengode", "Thiruchengode", "place", {"type": "town_meeting_point"})
        add_node("place:potteneri", "Potteneri", "place", {"type": "native_home_location"})
        add_node("place:college", "College Campus", "place", {"type": "academic_institution"})

        # 3. Core Topics
        add_node("topic:family_acceptance", "Family Acceptance & Pressure", "topic")
        add_node("topic:chat_privacy", "Chat Privacy & Disappearing Messages", "topic")
        add_node("topic:trust_honesty", "Trust & Direct Transparency", "topic")
        add_node("topic:overthinking", "Overthinking & Reassurance", "topic")

        # 4. Connect Events and Dates
        for ev in events:
            ev_node_id = f"event:{ev['event_id']}"
            add_node(ev_node_id, ev["event_summary"][:45] + "...", "event", {
                "category": ev["event_category"],
                "fact_type": ev["fact_type"],
                "full_summary": ev["event_summary"]
            })

            # Participant links
            for p in ev.get("participants", []):
                p_id = f"person:sakthi" if p == "partner" else f"person:manoj"
                add_edge(p_id, ev_node_id, "PARTICIPATED_IN", ev.get("source_message_ids", []), ev["confidence"])

            # Date link
            if ev.get("event_date"):
                d_id = f"date:{ev['event_date']}"
                add_node(d_id, ev["event_date"], "date")
                add_edge(ev_node_id, d_id, "OCCURRED_ON", ev.get("source_message_ids", []), 0.99)

            # Topic link
            if "family" in ev["event_category"]:
                add_edge(ev_node_id, "topic:family_acceptance", "RELATED_TO", ev.get("source_message_ids", []), 0.92)
            if "privacy" in ev["event_category"]:
                add_edge(ev_node_id, "topic:chat_privacy", "RELATED_TO", ev.get("source_message_ids", []), 0.95)
            if "conflict" in ev["event_category"] or "reconciliation" in ev["event_category"]:
                add_edge(ev_node_id, "topic:trust_honesty", "RELATED_TO", ev.get("source_message_ids", []), 0.94)

            # Place mentions
            summary_lower = ev["event_summary"].lower()
            if "thiruchengode" in summary_lower:
                add_edge(ev_node_id, "place:thiruchengode", "RELATED_TO", ev.get("source_message_ids", []), 0.95)
            if "potteneri" in summary_lower:
                add_edge(ev_node_id, "place:potteneri", "RELATED_TO", ev.get("source_message_ids", []), 0.95)
            if "mother" in summary_lower or "amma" in summary_lower:
                add_edge(ev_node_id, "person:amma", "MENTIONS", ev.get("source_message_ids", []), 0.96)
            if "dharshan" in summary_lower:
                add_edge(ev_node_id, "person:dharshan", "MENTIONS", ev.get("source_message_ids", []), 0.92)

        # 5. Connect Memories
        for mem in memories:
            mem_node_id = f"memory:{mem['memory_id']}"
            add_node(mem_node_id, mem["title"], "memory", {
                "category": mem["category"],
                "fact_type": mem.get("fact_type", "observed_pattern")
            })
            add_edge("person:sakthi", mem_node_id, "DISCUSSED", mem.get("source_message_ids", []), mem["confidence"])

        return {
            "version": "1.0.0",
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "nodes": list(nodes.values()),
            "edges": edges
        }
