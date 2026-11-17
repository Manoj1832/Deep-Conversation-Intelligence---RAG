import re
from typing import List, Dict, Any
from collections import Counter

class StyleAnalyzer:
    """
    Analyzes message styling, punctuation patterns, capitalization habits,
    and emoji behavior from partner messages.
    """

    EMOJI_RE = re.compile(
        r'('
        r'\u2764\ufe0f\u200d\U0001fa79|'
        r'[\U0001f300-\U0001f64f]|'
        r'[\U0001f680-\U0001f6ff]|'
        r'[\U0001f900-\U0001f9ff]|'
        r'[\U0001fa00-\U0001faff]|'
        r'[\u2600-\u26ff]|'
        r'[\u2700-\u27bf]'
        r')'
    )

    def analyze(self, partner_messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        text_messages = [m for m in partner_messages if m.get("message_type") == "text"]

        total_msgs = len(text_messages)
        if total_msgs == 0:
            return {}

        lowercase_starts = 0
        trailing_dots = 0
        exclamations = 0
        questions = 0
        char_lengths = []
        emojis_collected = []
        evidence_samples: Dict[str, List[str]] = {
            "lowercase": [],
            "burst": [],
            "questions": [],
            "emojis": []
        }

        for m in text_messages:
            body = m["body"].strip()
            msg_id = str(m["id"])
            char_lengths.append(len(body))

            if body and body[0].islower():
                lowercase_starts += 1
                if len(evidence_samples["lowercase"]) < 5:
                    evidence_samples["lowercase"].append(msg_id)

            if ".." in body or "..." in body:
                trailing_dots += 1

            if "!" in body:
                exclamations += 1

            if "?" in body:
                questions += 1
                if len(evidence_samples["questions"]) < 5:
                    evidence_samples["questions"].append(msg_id)

            found_emojis = self.EMOJI_RE.findall(body)
            if found_emojis:
                emojis_collected.extend(found_emojis)
                if len(evidence_samples["emojis"]) < 5:
                    evidence_samples["emojis"].append(msg_id)

        emoji_counter = Counter(emojis_collected)
        top_emojis = [{"emoji": e, "count": c} for e, c in emoji_counter.most_common(15)]

        avg_len = sum(char_lengths) / total_msgs if total_msgs else 0

        return {
            "total_messages": total_msgs,
            "average_character_length": round(avg_len, 1),
            "lowercase_start_percentage": round((lowercase_starts / total_msgs) * 100, 2),
            "trailing_ellipsis_percentage": round((trailing_dots / total_msgs) * 100, 2),
            "question_percentage": round((questions / total_msgs) * 100, 2),
            "exclamation_percentage": round((exclamations / total_msgs) * 100, 2),
            "top_emojis": top_emojis,
            "total_emojis_used": len(emojis_collected),
            "evidence_samples": evidence_samples
        }
