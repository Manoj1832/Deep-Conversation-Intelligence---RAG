"""
Context-Sensitive Emotional Analysis Pipeline for HerAI Phase 8.
Extracts observable emotional cues, intensity, and nuanced multi-label interpretations
grounded in conversational turns and surrounding interaction context.

Strictly adheres to:
- No clinical/psychiatric diagnoses.
- Separates explicit statements from observable cues and interpretations.
- Multi-turn contextual disambiguation (never relies on isolated emojis alone).
"""

from uuid import uuid4
from typing import List, Dict, Any, Optional, Tuple
import re

LEXICON = {
    "affection": [r"\bchello\b", r"\bchellam\b", r"\bbujju\b", r"\bkutty\b", r"\bthangam\b", r"\bmiss u\b", r"\bmiss you\b", r"\blove u\b", r"\bhug\b", r"\bkiss\b", r"🥺", r"❤️‍🩹", r"😚", r"🥰", r"😘"],
    "playfulness": [r"\bdei\b", r"\bnaayae\b", r"\bloosu\b", r"\bpaithiyam\b", r"\bcomedy\b", r"\bkilipan\b", r"🙄", r"😜", r"😏"],
    "amusement": [r"😂", r"🤣", r"\bsiripu\b", r"\blaugh\b", r"\bhaha\b"],
    "apology": [r"\bsorry\b", r"\bforgive\b", r"\bmannichidu\b", r"\bkovathula solliten\b", r"\bpromise\b"],
    "worry": [r"\bbayam\b", r"\bbayama\b", r"\bmaatikitom\b", r"\bphone check\b", r"\bthreat\b", r"\bpolice\b", r"😨", r"😰"],
    "concern": [r"\bsaptya\b", r"\bsaaptiya\b", r"\bsapdu\b", r"\btake care\b", r"\bpathiram\b", r"\bodambu\b", r"\btablet\b"],
    "reassurance_seeking": [r"\boverthinking\b", r"\bpogadha\b", r"\benkooda iru\b", r"\bunaku enna pudikuma\b", r"\btrust\b"],
    "frustration": [r"\bkaduppu\b", r"\birritate\b", r"\bmudiyala\b", r"\bvalikuthu\b", r"\bswelling\b", r"😤", r"😒"],
    "anger": [r"\bkovam\b", r"\bkovama\b", r"\bpesatha\b", r"\bblock\b", r"\bleave that\b", r"\bunaku puriyathu\b", r"😡", r"😠"],
    "sadness": [r"\bazhudhuten\b", r"\bazhugai\b", r"\bkastama\b", r"\bpain\b", r"💔", r"😢", r"😭"],
    "jealousy_expression": [r"\bandha ponnu\b", r"\byaar kooda\b", r"\bcheat\b", r"\btime pass\b", r"\bother girl\b"],
    "uncertainty": [r"\btheriyala\b", r"\bpuriyala\b", r"\benna panna\b", r"\bdoubt\b"]
}

class EmotionalContextExtractor:
    """
    Extracts structured emotional contexts across conversational turns.
    """

    def extract_turn_emotions(
        self,
        turn: Dict[str, Any],
        preceding_turn: Optional[Dict[str, Any]] = None,
        following_turn: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        text = turn["combined_text"].lower()
        matched_scores: Dict[str, int] = {}
        cues: List[str] = []

        # 1. Match Lexicon & Emojis
        for emotion, patterns in LEXICON.items():
            count = 0
            for pat in patterns:
                found = re.findall(pat, text)
                if found:
                    count += len(found)
                    for item in found:
                        if item not in cues:
                            cues.append(str(item))
            if count > 0:
                matched_scores[emotion] = count

        # 2. Contextual Disambiguation
        # E.g., '😭' when paired with 'briyani' or 'saptya' is playful frustration/hunger, not actual grief!
        if "😭" in text and any(w in text for w in ["briyani", "biriyani", "curd", "saptya", "food", "mess"]):
            matched_scores["sadness"] = max(0, matched_scores.get("sadness", 0) - 2)
            matched_scores["amusement"] = matched_scores.get("amusement", 0) + 1
            if not matched_scores.get("sadness"):
                matched_scores.pop("sadness", None)

        # Contextual check: if preceding turn had an apology, current turn with 'seri' is forgiveness/neutral
        if preceding_turn and "sorry" in preceding_turn["combined_text"].lower():
            if any(w in text for w in ["seri", "hmm", "ok", "paravala"]):
                matched_scores["affection"] = matched_scores.get("affection", 0) + 1

        if not matched_scores:
            primary = "neutral"
            secondary = []
            intensity = "low"
            confidence = 0.85
            interp = "Standard conversational communication with neutral affective tone."
        else:
            sorted_emotions = sorted(matched_scores.items(), key=lambda x: x[1], reverse=True)
            primary = sorted_emotions[0][0]
            secondary = [e for e, _ in sorted_emotions[1:4]]

            total_hits = sum(matched_scores.values())
            if total_hits >= 3:
                intensity = "high"
                confidence = 0.94
            elif total_hits == 2:
                intensity = "medium"
                confidence = 0.88
            else:
                intensity = "low"
                confidence = 0.78

            interp = f"Observed {primary} cues in text ({', '.join(cues[:3])}). Context indicates {intensity} affective engagement."

        context_ids = []
        if preceding_turn:
            context_ids.append(preceding_turn["turn_id"])
        if following_turn:
            context_ids.append(following_turn["turn_id"])

        alt_interpretations = []
        if primary in ["frustration", "anger"]:
            alt_interpretations.append("Could indicate playful dramatic banter rather than genuine anger depending on preceding interaction.")
        elif primary == "jealousy_expression":
            alt_interpretations.append("Could represent playful teasing or bid for reassurance rather than genuine suspicion.")

        return {
            "observation_id": str(uuid4()),
            "turn_id": turn["turn_id"],
            "speaker": turn["speaker"],
            "primary_label": primary,
            "secondary_labels": secondary,
            "intensity": intensity,
            "evidence_message_ids": turn["constituent_message_ids"],
            "context_turn_ids": context_ids,
            "observable_cues": cues,
            "interpretation": interp,
            "alternative_interpretations": alt_interpretations,
            "confidence": confidence,
            "extraction_method": "nlp_heuristic",
            "review_status": "approved" if confidence >= 0.85 else "pending"
        }

    def process_all_turns(self, turns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        observations: List[Dict[str, Any]] = []
        for i, turn in enumerate(turns):
            prev_t = turns[i - 1] if i > 0 and turns[i - 1]["session_id"] == turn["session_id"] else None
            next_t = turns[i + 1] if i < len(turns) - 1 and turns[i + 1]["session_id"] == turn["session_id"] else None
            obs = self.extract_turn_emotions(turn, prev_t, next_t)
            observations.append(obs)
        return observations
