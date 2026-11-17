from typing import List, Dict, Any, Tuple

class ContradictionDetector:
    """
    Detects contradictions across extracted memories (e.g. conflicting dates, mutually exclusive facts).
    """

    def detect_contradictions(self, memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        contradictions = []

        # Check for memories with the same category and title but different event dates
        by_category_title = {}
        for m in memories:
            key = (m.get("category"), m.get("title"))
            if key in by_category_title:
                prev = by_category_title[key]
                if prev.get("event_date") and m.get("event_date") and prev.get("event_date") != m.get("event_date"):
                    contradictions.append({
                        "type": "conflicting_dates",
                        "memory_id_1": prev["memory_id"],
                        "memory_id_2": m["memory_id"],
                        "details": f"Conflicting dates: {prev.get('event_date')} vs {m.get('event_date')}"
                    })
            else:
                by_category_title[key] = m

        return contradictions
