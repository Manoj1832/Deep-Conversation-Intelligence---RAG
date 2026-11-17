"""
Reply Linking Engine for HerAI Phase 8.
Identifies and links conversational turns with calibrated confidence levels:
- explicit (direct question-answer or direct syntactic/topical continuation)
- strong_inference (immediate speaker alternation <120s with topical alignment)
- weak_inference (delayed response 120s-600s with partial topical overlap)
- unknown (gaps >600s or topic shifts where reply dependency is ambiguous)
"""

from uuid import uuid4
from datetime import datetime
from typing import List, Dict, Any, Optional
import re

QUESTION_MARKERS = {
    "?", "enna", "enga", "eppo", "eppadi", "ethuku", "why", "what", "where",
    "when", "how", "saptya", "saaptiya", "panriya", "irukiya", "varalaama", "va?"
}

AFFIRMATIVE_NEGATIVE_MARKERS = {
    "ama", "aama", "illa", "illai", "seri", "ok", "hmm", "haan", "dhaa", "poren", "reach"
}

class ReplyLinker:
    """
    Links conversational turns and establishes reply dependencies.
    """

    def parse_dt(self, ts_str: Optional[str]) -> Optional[datetime]:
        if not ts_str:
            return None
        try:
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except Exception:
            return None

    def link_turns(self, turns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        links: List[Dict[str, Any]] = []

        for i in range(len(turns) - 1):
            t1 = turns[i]
            t2 = turns[i + 1]

            # Only link across the same session and alternating speakers
            if t1["session_id"] != t2["session_id"]:
                continue
            if t1["speaker"] == t2["speaker"]:
                continue

            dt1 = self.parse_dt(t1["end_timestamp"])
            dt2 = self.parse_dt(t2["start_timestamp"])

            latency_seconds = 0.0
            if dt1 and dt2:
                latency_seconds = max(0.0, (dt2 - dt1).total_seconds())

            # Analyze linguistic features
            text1_lower = t1["combined_text"].lower()
            text2_lower = t2["combined_text"].lower()

            is_q1 = any(q in text1_lower for q in QUESTION_MARKERS) or text1_lower.rstrip().endswith("?")
            has_answer_cue = any(a in text2_lower for a in AFFIRMATIVE_NEGATIVE_MARKERS)
            
            # Words overlap
            w1 = set(re.findall(r"\w+", text1_lower))
            w2 = set(re.findall(r"\w+", text2_lower))
            overlap = len(w1 & w2)

            features = []
            confidence_level = "unknown"
            confidence_score = 0.40

            if is_q1 and latency_seconds < 90 and (has_answer_cue or overlap > 0):
                confidence_level = "explicit"
                confidence_score = 0.95
                features.append("direct_question_answer_pair")
                features.append("rapid_latency")
            elif latency_seconds <= 120 and (t1["conversation_topic"] == t2["conversation_topic"] or overlap >= 2):
                confidence_level = "strong_inference"
                confidence_score = 0.88
                features.append("immediate_turn_alternation")
                features.append("topical_continuity")
            elif latency_seconds <= 600 and (t1["conversation_topic"] == t2["conversation_topic"] or overlap >= 1):
                confidence_level = "weak_inference"
                confidence_score = 0.70
                features.append("moderate_latency_window")
                features.append("shared_topic")
            else:
                confidence_level = "unknown"
                confidence_score = 0.45
                features.append("ambiguous_temporal_or_topical_distance")

            link = {
                "link_id": str(uuid4()),
                "session_id": t1["session_id"],
                "source_turn_id": t1["turn_id"],
                "response_turn_id": t2["turn_id"],
                "source_speaker": t1["speaker"],
                "response_speaker": t2["speaker"],
                "latency_seconds": round(latency_seconds, 1),
                "confidence_level": confidence_level,
                "confidence_score": round(confidence_score, 2),
                "linking_features": features,
                "source_topic": t1["conversation_topic"],
                "response_topic": t2["conversation_topic"]
            }
            links.append(link)

        return links
