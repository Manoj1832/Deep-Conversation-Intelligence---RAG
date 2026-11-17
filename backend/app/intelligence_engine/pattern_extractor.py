"""
Situation-to-Response Pattern Extraction Pipeline for HerAI Phase 8.
Extracts grounded, historical situation-to-response pairs directly from real WhatsApp turns.

Features:
- Identifies triggering situations from user turns.
- Captures actual partner responses without fictional rewriting.
- Categorizes across 26 distinct situational dynamics.
- Records response delays, styles, and communication features.
"""

from uuid import uuid4
from datetime import datetime
from typing import List, Dict, Any, Optional
import re

SITUATION_RULES = {
    "greeting": [r"\bhi\b", r"\bhello\b", r"\bheyy\b", r"\bvanakkam\b"],
    "good_morning": [r"\bgood morning\b", r"\bgm\b", r"\bkaala\b"],
    "good_night": [r"\bgood night\b", r"\bgn\b", r"\bthoongu\b", r"\bsweet dreams\b"],
    "missing_someone": [r"\bmiss u\b", r"\bmiss you\b", r"\bmissing\b", r"\bpaakanum\b"],
    "asking_location": [r"\benga iruka\b", r"\benga da\b", r"\bwhere are you\b", r"\breach aitiya\b"],
    "delayed_replies": [r"\benna aachu\b", r"\bengada poita\b", r"\bwhy late\b", r"\bmsg pannala\b"],
    "food_health_checkin": [r"\bsaptya\b", r"\bsaaptiya\b", r"\bsapdu\b", r"\bfood\b", r"\blunch\b", r"\bdinner\b", r"\btablet\b", r"\bodambu\b"],
    "college_exam_conversations": [r"\bexam\b", r"\bclass\b", r"\blab\b", r"\btest\b", r"\bcollege\b", r"\bclg\b", r"\brecord\b"],
    "playful_teasing": [r"\bnaayae\b", r"\bloosu\b", r"\bpaithiyam\b", r"\bcomedy\b", r"\bkilipan\b", r"\bdei\b"],
    "jokes_humour": [r"😂", r"🤣", r"\bsiripu\b", r"\bjoke\b"],
    "affection_closeness": [r"\bchello\b", r"\bchellam\b", r"\bbujju\b", r"\bthangam\b", r"\blove u\b", r"🥺", r"❤️‍🩹", r"😚"],
    "request_for_attention": [r"\bpesu da\b", r"\bcall pannu\b", r"\bmsg pannu\b", r"\benna kavanikiriya\b"],
    "jealousy_expression": [r"\bandha ponnu\b", r"\byaar kooda\b", r"\bother girl\b", r"\bcheat\b", r"\btime pass\b"],
    "third_party_discussion": [r"\bdharshan\b", r"\bbalaji\b", r"\bfriend\b", r"\bjuniors\b"],
    "trust_concerns": [r"\btrust\b", r"\bunmai\b", r"\bpoi\b", r"\bnamburiya\b", r"\bsecret\b"],
    "privacy_concerns": [r"\bprivacy\b", r"\bdisappearing\b", r"\bdelete\b", r"\byarukitta sonna\b"],
    "arguments_conflict": [r"\bkovam\b", r"\bkovama\b", r"\bsanda\b", r"\bbreakup\b", r"\birritate\b"],
    "misunderstandings": [r"\bpuriyala\b", r"\bthappa nenachita\b", r"\bclarify\b"],
    "apologies_repair": [r"\bsorry\b", r"\bforgive\b", r"\bmannichidu\b", r"\bkovathula solliten\b"],
    "forgiveness_acceptance": [r"\bparavala\b", r"\bvidu da\b", r"\bseri vidu\b", r"\bapologise accepted\b"],
    "reassurance_seeking": [r"\boverthinking\b", r"\bpogadha\b", r"\benkooda iru\b"],
    "family_pressure_secrecy": [r"\bamma\b", r"\bappa\b", r"\bveetla\b", r"\bphone check\b", r"\bthreat\b", r"\bmaatikitom\b"],
    "plans_meetings": [r"\bmeet pannalam\b", r"\bpaakalaam\b", r"\bthiruchengode\b", r"\bplan\b"],
    "saying_goodbye": [r"\bbye\b", r"\bgood bye\b", r"\bkelamburen\b", r"\bpoitu varen\b"],
    "request_for_space": [r"\bplease go\b", r"\bleave me\b", r"\bpesatha\b", r"\bkonjam neram\b"],
    "ending_difficult_discussion": [r"\bleave that\b", r"\batha vida\b", r"\bpothum\b", r"\bstop\b"]
}

class PatternExtractor:
    """
    Extracts authentic situation-to-response pairs from reconstructed turns.
    """

    def parse_dt(self, ts_str: Optional[str]) -> Optional[datetime]:
        if not ts_str:
            return None
        try:
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except Exception:
            return None

    def classify_situation(self, trigger_text: str) -> Tuple[str, str]:
        text_lower = trigger_text.lower()
        for cat, patterns in SITUATION_RULES.items():
            if any(re.search(pat, text_lower) for pat in patterns):
                desc = cat.replace("_", " ").title()
                return (cat, desc)
        return ("casual_daily_updates", "Casual Daily Updates & Check-in")

    def extract_patterns(
        self,
        turns: List[Dict[str, Any]],
        emotion_obs_map: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        patterns: List[Dict[str, Any]] = []

        for i in range(len(turns) - 1):
            t_user = turns[i]
            t_partner = turns[i + 1]

            # We want situations where User triggers -> Partner responds
            if t_user["speaker"] != "user" or t_partner["speaker"] != "partner":
                continue
            if t_user["session_id"] != t_partner["session_id"]:
                continue

            dt1 = self.parse_dt(t_user["end_timestamp"])
            dt2 = self.parse_dt(t_partner["start_timestamp"])
            delay = (dt2 - dt1).total_seconds() if (dt1 and dt2) else None

            # Skip huge gaps (>1 hour) as they likely represent disjoint check-ins
            if delay is not None and delay > 3600:
                continue

            sit_cat, sit_desc = self.classify_situation(t_user["combined_text"])
            resp_text = t_partner["combined_text"]
            if not resp_text:
                continue

            # Classify response style
            features = []
            if len(resp_text) <= 15:
                resp_style = "concise_short_burst"
                features.append("short_bubble")
            elif len(resp_text) <= 40:
                resp_style = "conversational_moderate"
                features.append("moderate_length")
            else:
                resp_style = "elaborated_expressive"
                features.append("extended_thought")

            for em in ["🥺", "🙄", "😂", "❤️‍🩹", "😭", "😚"]:
                if em in resp_text:
                    features.append(f"emoji_{em}")

            # Get emotional observations
            e_obs = emotion_obs_map.get(t_partner["turn_id"])
            emotion_labels = [e_obs["primary_label"]] if e_obs else ["neutral"]
            if e_obs and e_obs.get("secondary_labels"):
                emotion_labels.extend(e_obs["secondary_labels"])

            # Infer outcome
            outcome = "resolved"
            if sit_cat in ["arguments_conflict", "jealousy_expression", "trust_concerns"]:
                if any(w in resp_text.lower() for w in ["leave that", "pesatha", "block", "good bye"]):
                    outcome = "unresolved"
                elif any(w in resp_text.lower() for w in ["sorry", "seri", "puriyuthu", "promise"]):
                    outcome = "partially_resolved"

            preceding_context = []
            if i > 0 and turns[i - 1]["session_id"] == t_user["session_id"]:
                preceding_context.append({
                    "speaker": turns[i - 1]["speaker"],
                    "text": turns[i - 1]["combined_text"][:60]
                })

            pattern = {
                "pattern_id": str(uuid4()),
                "situation_category": sit_cat,
                "situation_description": sit_desc,
                "preceding_context": preceding_context,
                "triggering_turn_ids": [t_user["turn_id"]],
                "observed_response_turn_ids": [t_partner["turn_id"]],
                "user_trigger_text": t_user["combined_text"],
                "actual_response_text": resp_text,
                "response_style": resp_style,
                "message_count": t_partner["message_count"],
                "response_delay_seconds": round(delay, 1) if delay is not None else None,
                "observed_communication_features": features,
                "emotion_observations": emotion_labels,
                "outcome": outcome,
                "source_message_ids": t_user["constituent_message_ids"] + t_partner["constituent_message_ids"],
                "confidence": 0.92 if delay and delay < 120 else 0.84,
                "review_status": "approved" if (delay and delay < 300) else "pending"
            }
            patterns.append(pattern)

        return patterns
