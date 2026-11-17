"""
Conversation Reconstruction Engine for HerAI Phase 8.
Reconstructs multi-bubble WhatsApp messages into coherent conversational turns.

Key features:
- Merges rapid consecutive message bubbles from the same speaker.
- Respects temporal boundaries (configurable max gap, default 300s).
- Preserves constituent message IDs and provenance.
- Assigns stable turn IDs and links preceding/following turns.
- Detects conversation topics automatically using domain taxonomy.
"""

import json
from uuid import uuid4
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

TOPIC_KEYWORDS = {
    "food_eating": ["saptya", "saaptiya", "sapdu", "briyani", "biriyani", "curd", "lunch", "dinner", "tiffin", "breakfast", "pasikuthu"],
    "travel_commute": ["bus", "seat", "potteneri", "thiruchengode", "reach", "kelambu", "traffic", "train", "auto"],
    "college_academics": ["class", "exam", "lab", "observation", "clg", "college", "test", "record", "staff", "mam", "sir", "study"],
    "family_secrecy": ["amma", "appa", "veetla", "phone check", "maatikitom", "parents", "threat", "police", "therinja"],
    "trust_privacy": ["trust", "unmai", "poi", "delete", "privacy", "disappearing", "secret", "promise", "address"],
    "affection_closeness": ["chello", "bujju", "kutty", "thangam", "miss u", "miss you", "love", "hug", "kiss", "muah"],
    "conflict_repair": ["sorry", "kovam", "kovama", "sanda", "breakup", "forgive", "leave that", "irritate"]
}

def infer_turn_topic(text: str) -> str:
    text_lower = text.lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return topic
    return "casual_banter"


class TurnReconstructor:
    """
    Reconstructs conversational turns from WhatsApp message stream.
    """

    def __init__(self, max_gap_seconds: int = 300):
        self.max_gap_seconds = max_gap_seconds

    def parse_dt(self, ts_str: str) -> Optional[datetime]:
        if not ts_str:
            return None
        try:
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except Exception:
            return None

    def reconstruct(self, messages_file: Path) -> List[Dict[str, Any]]:
        with open(messages_file, "r", encoding="utf-8") as f:
            raw_messages = [json.loads(line) for line in f]

        turns: List[Dict[str, Any]] = []
        current_turn: Optional[Dict[str, Any]] = None

        for m in raw_messages:
            # Skip system messages that do not represent speaker communication
            if m.get("is_system_message"):
                continue

            msg_id = m.get("id")
            sender = m.get("sender")
            session_id = m.get("session_id")
            ts_str = m.get("timestamp")
            msg_dt = self.parse_dt(ts_str)
            body = (m.get("body") or "").strip()

            if not body and m.get("message_type") != "media":
                continue

            if current_turn is None:
                # Start first turn
                current_turn = self._create_new_turn(sender, session_id, ts_str, msg_id, body)
                continue

            # Check if message continues current turn
            same_speaker = (sender == current_turn["speaker"])
            same_session = (session_id == current_turn["session_id"])
            
            time_gap_ok = True
            if current_turn["end_timestamp"] and ts_str and msg_dt:
                prev_dt = self.parse_dt(current_turn["end_timestamp"])
                if prev_dt:
                    gap = (msg_dt - prev_dt).total_seconds()
                    if gap > self.max_gap_seconds:
                        time_gap_ok = False

            if same_speaker and same_session and time_gap_ok:
                # Append to current turn
                current_turn["constituent_message_ids"].append(msg_id)
                if body:
                    current_turn["message_bodies"].append(body)
                current_turn["end_timestamp"] = ts_str
                current_turn["message_count"] += 1
            else:
                # Finalize current turn and start new turn
                self._finalize_turn(current_turn)
                turns.append(current_turn)
                current_turn = self._create_new_turn(sender, session_id, ts_str, msg_id, body)

        if current_turn is not None:
            self._finalize_turn(current_turn)
            turns.append(current_turn)

        # Link preceding and following turns across chronological order
        for i in range(len(turns)):
            if i > 0 and turns[i - 1]["session_id"] == turns[i]["session_id"]:
                turns[i]["preceding_turn_id"] = turns[i - 1]["turn_id"]
            if i < len(turns) - 1 and turns[i + 1]["session_id"] == turns[i]["session_id"]:
                turns[i]["following_turn_id"] = turns[i + 1]["turn_id"]

        return turns

    def _create_new_turn(self, speaker: str, session_id: str, ts: str, msg_id: str, body: str) -> Dict[str, Any]:
        return {
            "turn_id": str(uuid4()),
            "session_id": session_id,
            "speaker": speaker,
            "start_timestamp": ts,
            "end_timestamp": ts,
            "constituent_message_ids": [msg_id],
            "message_bodies": [body] if body else [],
            "combined_text": body,
            "message_count": 1,
            "preceding_turn_id": None,
            "following_turn_id": None,
            "conversation_topic": "casual_banter",
            "reconstruction_confidence": 0.95
        }

    def _finalize_turn(self, turn: Dict[str, Any]):
        turn["combined_text"] = " ".join(turn["message_bodies"])
        turn["conversation_topic"] = infer_turn_topic(turn["combined_text"])
        # If burst has multiple messages, confidence is high; if single boundary, calibrated
        if turn["message_count"] > 1:
            turn["reconstruction_confidence"] = 0.98
        else:
            turn["reconstruction_confidence"] = 0.92
        del turn["message_bodies"]
