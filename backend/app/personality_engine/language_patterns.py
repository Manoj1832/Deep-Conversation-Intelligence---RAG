import re
from typing import List, Dict, Any, Tuple
from collections import Counter

class LanguagePatternsExtractor:
    """
    Extracts empirical language patterns from partner messages:
    - Code switching rates (Tanglish / English)
    - Frequent colloquial expressions & vocabulary
    - Informal spelling tendencies
    - Greetings and signoffs
    """

    GREETINGS = {"hey", "heyy", "heyyy", "hi", "hii", "hiii", "vanakkam", "morning", "gm", "gn", "bye"}
    SIGNOFFS = {"bye", "byee", "byeee", "goodnight", "gn", "night", "talk soon", "tc"}

    def extract(self, partner_messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        text_messages = [m for m in partner_messages if m.get("message_type") == "text"]

        total_words = 0
        word_counter = Counter()
        greetings_found = Counter()
        signoffs_found = Counter()
        evidence_samples: Dict[str, List[str]] = {
            "greetings": [],
            "signoffs": [],
            "colloquialisms": []
        }

        for m in text_messages:
            body = m["body"].strip()
            msg_id = str(m["id"])
            lower = body.lower()
            tokens = re.findall(r'[a-zA-Z]+', lower)
            total_words += len(tokens)
            word_counter.update(tokens)

            # Check greetings (first token or short message)
            if tokens and tokens[0] in self.GREETINGS:
                greetings_found[tokens[0]] += 1
                if len(evidence_samples["greetings"]) < 5:
                    evidence_samples["greetings"].append(msg_id)

            # Check signoffs (last token or short message)
            if tokens and tokens[-1] in self.SIGNOFFS:
                signoffs_found[tokens[-1]] += 1
                if len(evidence_samples["signoffs"]) < 5:
                    evidence_samples["signoffs"].append(msg_id)

        top_colloquials = [
            {"word": w, "count": c}
            for w, c in word_counter.most_common(30)
            if len(w) > 1
        ]

        return {
            "total_words_analyzed": total_words,
            "top_colloquial_vocabulary": top_colloquials,
            "observed_greetings": dict(greetings_found.most_common(10)),
            "observed_signoffs": dict(signoffs_found.most_common(10)),
            "evidence_samples": evidence_samples
        }
