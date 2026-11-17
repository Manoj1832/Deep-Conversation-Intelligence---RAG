import json
import re
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, defaultdict
from typing import Dict, Any, List

class ConversationIntelligenceEngine:
    """
    Phase 3: Conversation Intelligence Engine.
    Analyzes turn-taking rhythms, response latencies, Tanglish/Tamil code-switching,
    emoji behavior, and temporal dynamics from validated Phase 2 outputs.
    """

    TAMIL_UNICODE_RE = re.compile(r'[\u0B80-\u0BFF]')
    EMOJI_RE = re.compile(
        r'('
        r'\u2764\ufe0f\u200d\U0001fa79|'  # ❤️‍🩹
        r'[\U0001f300-\U0001f64f]|'        # Emoticons / Symbols
        r'[\U0001f680-\U0001f6ff]|'        # Transport & map
        r'[\U0001f900-\U0001f9ff]|'        # Supplemental symbols
        r'[\U0001fa00-\U0001faff]|'        # Symbols & pictographs
        r'[\u2600-\u26ff]|'                # Misc symbols
        r'[\u2700-\u27bf]'                 # Dingbats
        r')'
    )

    COMMON_TANGLISH_KEYWORDS = {
        'da', 'di', 'seri', 'enga', 'unna', 'veetla', 'chello', 'ippo', 'aama',
        'illa', 'enna', 'solla', 'panra', 'panna', 'teriyum', 'teriya', 'maatan',
        'maatanga', 'dhaa', 'paaru', 'kitta', 'kooda', 'avanga', 'namma', 'edukura',
        'takkunu', 'poga', 'vanthu', 'vandhu', 'irukka', 'irukken', 'maiirum', 'maari',
        'ponnu', 'paiyan', 'ketturukka', 'poturuvan', 'distrub', 'paravala', 'chellam'
    }

    def __init__(self, processed_dir: Path):
        self.processed_dir = processed_dir
        self.messages_path = processed_dir / "messages.jsonl"
        self.sessions_path = processed_dir / "sessions.jsonl"

    def analyze(self) -> Dict[str, Any]:
        if not self.messages_path.exists() or not self.sessions_path.exists():
            raise FileNotFoundError("Phase 2 outputs (messages.jsonl / sessions.jsonl) not found.")

        messages: List[Dict[str, Any]] = []
        with open(self.messages_path, "r", encoding="utf-8") as f:
            for line in f:
                messages.append(json.loads(line))

        sessions: List[Dict[str, Any]] = []
        with open(self.sessions_path, "r", encoding="utf-8") as f:
            for line in f:
                sessions.append(json.loads(line))

        # 1. Turn-Taking and Latency Metrics
        partner_msgs = [m for m in messages if m["sender"] == "partner"]
        user_msgs = [m for m in messages if m["sender"] == "user"]

        latencies_seconds: List[float] = []
        partner_burst_lengths: List[int] = []
        user_burst_lengths: List[int] = []

        current_sender = None
        current_burst = 0

        for i in range(len(messages)):
            m = messages[i]
            sender = m["sender"]

            if sender == current_sender:
                current_burst += 1
            else:
                if current_sender == "partner":
                    partner_burst_lengths.append(current_burst)
                elif current_sender == "user":
                    user_burst_lengths.append(current_burst)
                current_sender = sender
                current_burst = 1

            if i > 0:
                prev_m = messages[i - 1]
                if prev_m["sender"] != m["sender"]:
                    t_curr = datetime.fromisoformat(m["timestamp"])
                    t_prev = datetime.fromisoformat(prev_m["timestamp"])
                    diff = (t_curr - t_prev).total_seconds()
                    if 0 < diff <= 14400:  # within 4 hours
                        latencies_seconds.append(diff)

        if current_sender == "partner":
            partner_burst_lengths.append(current_burst)
        elif current_sender == "user":
            user_burst_lengths.append(current_burst)

        latencies_sorted = sorted(latencies_seconds)
        median_latency = latencies_sorted[len(latencies_sorted) // 2] if latencies_sorted else 0
        p90_latency = latencies_sorted[int(len(latencies_sorted) * 0.90)] if latencies_sorted else 0

        avg_partner_burst = sum(partner_burst_lengths) / len(partner_burst_lengths) if partner_burst_lengths else 1.0
        avg_user_burst = sum(user_burst_lengths) / len(user_burst_lengths) if user_burst_lengths else 1.0

        # 2. Vocabulary & Tanglish Analysis
        partner_words: List[str] = []
        partner_tanglish_count = 0
        partner_tamil_unicode_count = 0
        partner_emojis: List[str] = []

        for m in partner_msgs:
            body = m["body"]
            if self.TAMIL_UNICODE_RE.search(body):
                partner_tamil_unicode_count += 1
            
            # Emojis
            emojis_found = self.EMOJI_RE.findall(body)
            partner_emojis.extend(emojis_found)

            # Words
            tokens = re.findall(r'[a-zA-Z]+', body.lower())
            partner_words.extend(tokens)
            for t in tokens:
                if t in self.COMMON_TANGLISH_KEYWORDS:
                    partner_tanglish_count += 1

        total_partner_words = len(partner_words)
        unique_partner_words = len(set(partner_words))
        ttr = unique_partner_words / total_partner_words if total_partner_words else 0.0

        word_freq = Counter(partner_words)
        top_vocab = [{"word": w, "count": c} for w, c in word_freq.most_common(40)]
        tanglish_freq = {w: word_freq[w] for w in self.COMMON_TANGLISH_KEYWORDS if w in word_freq}

        emoji_freq = Counter(partner_emojis)
        top_emojis = [{"emoji": e, "count": c, "percentage": round((c / len(partner_emojis)) * 100, 2)}
                      for e, c in emoji_freq.most_common(20)] if partner_emojis else []

        # 3. Message Length & Syntactic Distribution
        partner_text_msgs = [m for m in partner_msgs if m["message_type"] == "text"]
        char_lengths = [len(m["body"]) for m in partner_text_msgs]
        avg_char_length = sum(char_lengths) / len(char_lengths) if char_lengths else 0.0

        short_msgs = sum(1 for l in char_lengths if l <= 25)
        medium_msgs = sum(1 for l in char_lengths if 25 < l <= 100)
        long_msgs = sum(1 for l in char_lengths if l > 100)

        lowercase_starts = sum(1 for m in partner_text_msgs if m["body"] and m["body"][0].islower())
        lowercase_pct = round((lowercase_starts / len(partner_text_msgs)) * 100, 2) if partner_text_msgs else 0.0

        trailing_dots = sum(1 for m in partner_text_msgs if m["body"].rstrip().endswith(".."))
        question_marks = sum(1 for m in partner_text_msgs if "?" in m["body"])

        # 4. Temporal Activity
        hour_counts = Counter()
        for m in partner_msgs:
            dt = datetime.fromisoformat(m["timestamp"])
            hour_counts[dt.hour] += 1

        peak_hours = [h for h, _ in hour_counts.most_common(5)]

        result = {
            "version": "3.0.0",
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "corpus_summary": {
                "total_messages": len(messages),
                "total_sessions": len(sessions),
                "partner_messages": len(partner_msgs),
                "user_messages": len(user_msgs),
                "partner_ratio": round(len(partner_msgs) / len(messages), 4)
            },
            "turn_dynamics": {
                "median_response_latency_seconds": round(median_latency, 1),
                "p90_response_latency_seconds": round(p90_latency, 1),
                "partner_average_burst_messages": round(avg_partner_burst, 2),
                "user_average_burst_messages": round(avg_user_burst, 2)
            },
            "linguistic_patterns": {
                "type_token_ratio": round(ttr, 4),
                "total_words_analyzed": total_partner_words,
                "unique_words_count": unique_partner_words,
                "tanglish_token_occurrences": partner_tanglish_count,
                "tamil_unicode_messages_count": partner_tamil_unicode_count,
                "top_tanglish_keywords": tanglish_freq,
                "top_vocabulary": top_vocab[:25]
            },
            "emoji_patterns": {
                "total_emojis_used": len(partner_emojis),
                "unique_emojis_count": len(emoji_freq),
                "top_emojis": top_emojis
            },
            "syntactic_style": {
                "average_message_length_chars": round(avg_char_length, 1),
                "short_messages_count": short_msgs,
                "short_messages_percentage": round((short_msgs / len(partner_text_msgs)) * 100, 2) if partner_text_msgs else 0,
                "medium_messages_count": medium_msgs,
                "long_messages_count": long_msgs,
                "lowercase_start_percentage": lowercase_pct,
                "messages_with_questions": question_marks,
                "messages_with_trailing_dots": trailing_dots
            },
            "temporal_distribution": {
                "peak_hours_utc": sorted(peak_hours),
                "hourly_breakdown": {h: hour_counts[h] for h in range(24)}
            }
        }

        # Write output file
        out_path = self.processed_dir / "conversation_intelligence.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        return result

if __name__ == "__main__":
    engine = ConversationIntelligenceEngine(Path("/home/manoj/Documents/HerAI/data/processed"))
    data = engine.analyze()
    print("[+] Phase 3 Conversation Intelligence Engine Complete!")
    print(f"    Total words analyzed: {data['linguistic_patterns']['total_words_analyzed']}")
    print(f"    Type-Token Ratio: {data['linguistic_patterns']['type_token_ratio']}")
    print(f"    Median response latency: {data['turn_dynamics']['median_response_latency_seconds']}s")
    print(f"    Partner avg burst: {data['turn_dynamics']['partner_average_burst_messages']} msgs")
    print(f"    Top 5 Emojis: {[e['emoji'] for e in data['emoji_patterns']['top_emojis'][:5]]}")
