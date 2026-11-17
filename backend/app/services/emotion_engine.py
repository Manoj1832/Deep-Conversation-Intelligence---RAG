"""
Emotion Analysis & Classification Engine for HerAI.
Grounded in empirical analysis of 24,971 WhatsApp messages between Manoj and Sakthi.

Classifies messages into 7 core emotional states:
1. affectionate (loving, pet names, missing each other)
2. playful_teasing (roasts, friendly banter, playful insults)
3. caring_routine (food checks, safety, health reminders)
4. anxious_tense (fear of family catching them, phone checks, tension)
5. irritated_angry (pouting, frustration, 'kovam', silent treatment)
6. sad_vulnerable (crying, hurt, emotional honesty, feeling low)
7. casual_neutral (regular updates, logistics, acknowledgments)
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Any, Tuple
from collections import Counter

EMOTION_PATTERNS: Dict[str, List[str]] = {
    "affectionate": [
        r"🥺", r"❤️‍🩹", r"❤️", r"😚", r"🥰", r"😘", r"🥹", r"🫂",
        r"\bchello\b", r"\bchellam\b", r"\bbujju\b", r"\bkutty\b", r"\bthangam\b",
        r"\bmiss u\b", r"\bmiss you\b", r"\blove u\b", r"\blove you\b",
        r"\bhug\b", r"\bkiss\b", r"\bmuah\b", r"\benkooda\b", r"\bunna vitu\b",
        r"\bkonjam kooda vittu kuduka\b", r"\bchella\b"
    ],
    "playful_teasing": [
        r"🙄", r"😂", r"🤣", r"😜", r"😏",
        r"\bdei\b", r"\bnaayae\b", r"\bpo da\b", r"\bmooditu\b", r"\bkilipan\b",
        r"\bcomedy\b", r"\bvaaya\b", r"\bloosu\b", r"\bpaithiyam\b", r"\bvetti\b",
        r"\bover ah\b", r"\bsiripu\b", r"\bthiruttu\b", r"\bkedi\b"
    ],
    "caring_routine": [
        r"\bsaptya\b", r"\bsaaptiya\b", r"\bsapda\b", r"\bsaapdu\b", r"\bsapten\b",
        r"\btake care\b", r"\bpathiram\b", r"\bpaathu po\b", r"\bodambu\b",
        r"\btablet\b", r"\bmedicine\b", r"\bthunginiya\b", r"\bthookam\b",
        r"\bkudichiya\b", r"\btea kudichiya\b", r"\bbriyani\b", r"\bbiriyani\b",
        r"\bfood\b", r"\btiffin\b"
    ],
    "anxious_tense": [
        r"😭", r"😨", r"😰",
        r"\bbayam\b", r"\bbayama\b", r"\bmaatikitom\b", r"\bmatitom\b",
        r"\bphone check\b", r"\bveetla\b", r"\bamma.*kovam\b", r"\bproblem\b",
        r"\btension\b", r"\bpidichitangala\b", r"\bthreat\b", r"\bcheck pannanga\b",
        r"\bpolamburanga\b"
    ],
    "irritated_angry": [
        r"😒", r"😤", r"😡", r"😠",
        r"\bkovam\b", r"\bkovama\b", r"\bpesatha\b", r"\bpesaatha\b", r"\bblock\b",
        r"\birritate\b", r"\bleave it\b", r"\bunaku puriyathu\b", r"\bvenam\b",
        r"\bmoodila\b", r"\bpesa thonala\b", r"\bkadupula\b"
    ],
    "sad_vulnerable": [
        r"💔", r"😢",
        r"\bazhudhuten\b", r"\bazhugai\b", r"\bvalikuthu\b", r"\bmudiyala\b",
        r"\bswelling\b", r"\beye.*swelling\b", r"\bkastama\b", r"\bpain\b",
        r"\btrust illa\b", r"\benga veetla accept pannavae maatanga\b"
    ]
}

EMOTION_LABELS = [
    "affectionate",
    "playful_teasing",
    "caring_routine",
    "anxious_tense",
    "irritated_angry",
    "sad_vulnerable",
    "casual_neutral"
]


class EmotionEngine:
    """
    Categorizes messages into authentic emotional dimensions
    and tracks emotional profiles across the conversation corpus.
    """

    @classmethod
    def classify_text(cls, text: str) -> Tuple[str, float]:
        """
        Classifies emotional state of text.
        Returns: (primary_emotion, confidence_score)
        """
        if not text or not text.strip():
            return ("casual_neutral", 0.5)

        text_lower = text.lower()
        counts = Counter()

        for emotion, patterns in EMOTION_PATTERNS.items():
            for pat in patterns:
                matches = len(re.findall(pat, text_lower))
                if matches > 0:
                    counts[emotion] += matches

        if not counts:
            return ("casual_neutral", 0.7)

        top_emotion, top_count = counts.most_common(1)[0]
        total_hits = sum(counts.values())
        confidence = min(0.95, 0.6 + (top_count / total_hits) * 0.35)
        return (top_emotion, round(confidence, 2))

    @classmethod
    def generate_corpus_analysis(cls, messages_file: Path) -> Dict[str, Any]:
        """
        Analyzes the full 24,971 message corpus and outputs structured emotional intelligence.
        """
        if not messages_file.exists():
            return {}

        partner_emotions = Counter()
        user_emotions = Counter()
        hourly_partner_emotions: Dict[int, Counter] = {h: Counter() for h in range(24)}

        total_partner = 0
        total_user = 0

        with open(messages_file, "r", encoding="utf-8") as f:
            for line in f:
                m = json.loads(line)
                if m.get("is_system_message") or m.get("message_type") != "text":
                    continue
                body = m.get("body", "").strip()
                if not body:
                    continue

                emotion, _ = cls.classify_text(body)
                sender = m.get("sender")

                if sender == "partner":
                    partner_emotions[emotion] += 1
                    total_partner += 1
                    ts_str = m.get("timestamp")
                    if ts_str:
                        try:
                            # Parse hour
                            h = int(ts_str[11:13])
                            hourly_partner_emotions[h][emotion] += 1
                        except Exception:
                            pass
                else:
                    user_emotions[emotion] += 1
                    total_user += 1

        partner_dist = {
            e: {
                "count": partner_emotions[e],
                "percentage": round((partner_emotions[e] / max(1, total_partner)) * 100, 2)
            }
            for e in EMOTION_LABELS
        }

        user_dist = {
            e: {
                "count": user_emotions[e],
                "percentage": round((user_emotions[e] / max(1, total_user)) * 100, 2)
            }
            for e in EMOTION_LABELS
        }

        return {
            "version": "1.0.0",
            "total_analyzed_partner_messages": total_partner,
            "total_analyzed_user_messages": total_user,
            "partner_emotion_distribution": partner_dist,
            "user_emotion_distribution": user_dist,
            "dominant_partner_emotion": partner_emotions.most_common(1)[0][0] if partner_emotions else "casual_neutral",
            "hourly_partner_emotions": {
                h: dict(hourly_partner_emotions[h]) for h in range(24)
            }
        }
