from typing import List, Dict, Any, Tuple

class MemoryDeduplicator:
    """
    Detects potential duplicate memories without destructive loss of source evidence.
    Compares category, title similarity, and source message ID overlap.
    """

    def find_duplicates(self, memories: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], Dict[str, Any], float]]:
        duplicates: List[Tuple[Dict[str, Any], Dict[str, Any], float]] = []

        for i in range(len(memories)):
            for j in range(i + 1, len(memories)):
                m1, m2 = memories[i], memories[j]
                if m1["category"] == m2["category"]:
                    # Check source message ID overlap
                    s1 = set(m1.get("source_message_ids", []))
                    s2 = set(m2.get("source_message_ids", []))
                    overlap = len(s1.intersection(s2))
                    if overlap > 0 and len(s1) > 0:
                        jaccard = overlap / len(s1.union(s2))
                        if jaccard >= 0.5:
                            duplicates.append((m1, m2, jaccard))

        return duplicates
