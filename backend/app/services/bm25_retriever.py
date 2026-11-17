import re
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from rank_bm25 import BM25Okapi

from backend.app.services.time_context import TimeContextEngine, IST
from backend.app.services.emotion_engine import EmotionEngine

# Common Tanglish spelling variants and colloquial roots
TANGLISH_STEM_MAP = {
    # Food / eating
    'saptya': 'saapt', 'saaptiya': 'saapt', 'saapta': 'saapt', 'saptiya': 'saapt',
    'sapda': 'saapt', 'saapda': 'saapt', 'saaptan': 'saapt', 'saptu': 'saapt',
    'saapadu': 'saapt', 'food': 'saapt', 'dinner': 'saapt', 'lunch': 'saapt',
    'biriyani': 'saapt', 'briyani': 'saapt', 'tiffin': 'saapt', 'breakfast': 'saapt',
    'curd': 'saapt', 'curdrice': 'saapt', 'rice': 'saapt', 'mushroom': 'saapt',
    # Doing / activity
    'panra': 'pann', 'pandren': 'pann', 'pandriya': 'pann', 'panna': 'pann',
    'panreenga': 'pann', 'pannitu': 'pann', 'panren': 'pann',
    # State / being
    'iruka': 'irukk', 'irukkiya': 'irukk', 'iruken': 'irukk', 'iruntha': 'irukk',
    'irundhen': 'irukk', 'irukku': 'irukk', 'irukka': 'irukk',
    # Emotion / anger
    'kovama': 'kovam', 'kovam': 'kovam', 'kovapadaadha': 'kovam', 'kobam': 'kovam',
    # Affection / pet names
    'chello': 'chello', 'chellam': 'chello', 'chella': 'chello', 'bujju': 'chello',
    'kutty': 'chello', 'thangam': 'chello', 'bujji': 'chello', 'baby': 'chello',
    # Movies / entertainment
    'padam': 'movie', 'cinema': 'movie', 'film': 'movie', 'sirai': 'movie',
    'theatre': 'movie', 'watch': 'movie', 'paaru': 'paaru', 'paatha': 'paaru',
    # Locations & Meetings
    'thiruchengode': 'thirichngode', 'thirichngode': 'thirichngode', 'potteneri': 'potteneri',
    'meet': 'meet', 'paakalaam': 'meet', 'paakalam': 'meet', 'vara': 'meet',
    # Communication
    'call': 'call', 'pesu': 'pesu', 'pesalaam': 'pesu', 'pesanum': 'pesu',
    'message': 'msg', 'msg': 'msg', 'delete': 'delete', 'chat': 'chat',
    # Studies / college / travel
    'exam': 'exam', 'college': 'clg', 'clg': 'clg', 'test': 'exam', 'padikka': 'exam',
    'padikriya': 'exam', 'study': 'exam', 'marks': 'exam', 'bus': 'bus', 'seat': 'bus',
    # Relationships & family
    'veedu': 'veetla', 'veetla': 'veetla', 'amma': 'family', 'appa': 'family',
    'parents': 'family', 'family': 'family', 'ponnu': 'family', 'paiyan': 'family',
    # Feelings
    'miss': 'miss', 'love': 'love', 'u': 'you', 'care': 'care', 'bayama': 'bayam',
    'bayam': 'bayam', 'azhudhuten': 'cry', 'cry': 'cry', 'kanna': 'cry', 'azhugai': 'cry'
}

# Conversational particles in colloquial Tamil (very frequent, low topical entropy)
PARTICLES = {
    'da', 'di', 'la', 'ah', 'pa', 'tha', 'nu', 'aam', 'un', 'en', 'na', 'nee',
    'seri', 'illai', 'illa', 'aama', 'ama', 'romba', 'konjam', 'aprom', 'dhaa'
}

def normalize_tanglish_tokens(text: str) -> List[str]:
    """
    Tokenizes text into normalized Tanglish semantic stems while downweighting particles.
    """
    words = re.findall(r'\w+', text.lower())
    content_words = [w for w in words if w not in PARTICLES]
    target_words = content_words if content_words else words

    tokens = []
    for w in target_words:
        stem = TANGLISH_STEM_MAP.get(w, w)
        tokens.append(stem)
    return tokens


class BM25ConversationRetriever:
    """
    High-Precision BM25 Conversational Ground Truth Retriever.
    Indexes all 24,971 historical messages and ~3,400 user->partner interaction turns.
    Enriched with time slot classification and emotional analysis.
    """

    def __init__(self, processed_dir: Path):
        self.processed_dir = processed_dir
        self.messages_file = processed_dir / "messages.jsonl"
        self.interactions: List[Dict[str, Any]] = []
        self.partner_utterances: List[str] = []
        
        self.bm25_interactions: Optional[BM25Okapi] = None
        self.bm25_partner: Optional[BM25Okapi] = None

        if self.messages_file.exists():
            self._load_and_index()

    def _determine_slot_from_ts(self, ts_str: Optional[str]) -> str:
        """Helper to tag interaction with its empirical schedule time slot."""
        if not ts_str:
            return "home_dinner_chat"
        try:
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            # Convert to IST if naive or UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=IST)
            else:
                dt = dt.astimezone(IST)
            slot = TimeContextEngine.get_slot_for_time(dt)
            return slot.slot_id
        except Exception:
            return "home_dinner_chat"

    def _load_and_index(self):
        with open(self.messages_file, "r", encoding="utf-8") as f:
            messages = [json.loads(line) for line in f]

        # 1. Collect standalone partner utterances (filtered)
        self.partner_utterances = [
            m["body"].strip() for m in messages
            if m.get("sender") == "partner"
            and not m.get("is_system_message")
            and m.get("message_type") == "text"
            and m.get("body", "").strip()
        ]

        # 2. Group sequential messages by sender within sessions into conversational bursts
        bursts = []
        for m in messages:
            if m.get("is_system_message") or m.get("message_type") != "text":
                continue
            body = m.get("body", "").strip()
            if not body:
                continue
            sender = m.get("sender")
            sid = m.get("session_id")
            ts = m.get("timestamp")

            if bursts and bursts[-1]["sender"] == sender and bursts[-1]["session_id"] == sid:
                bursts[-1]["messages"].append(body)
            else:
                bursts.append({
                    "sender": sender,
                    "session_id": sid,
                    "timestamp": ts,
                    "messages": [body]
                })

        # 3. Form interaction turn pairs: (User Burst -> Immediate Subsequent Partner Reaction Burst)
        self.interactions = []
        for i in range(len(bursts) - 1):
            b1 = bursts[i]
            b2 = bursts[i + 1]
            if b1["sender"] == "user" and b2["sender"] == "partner" and b1["session_id"] == b2["session_id"]:
                user_combined = " ".join(b1["messages"])
                partner_combined = " ".join(b2["messages"])
                time_slot = self._determine_slot_from_ts(b1.get("timestamp"))
                emotion, _ = EmotionEngine.classify_text(partner_combined)

                self.interactions.append({
                    "user_trigger": user_combined,
                    "partner_reaction": partner_combined,
                    "partner_burst_messages": b2["messages"],
                    "timestamp": b1["timestamp"],
                    "time_slot": time_slot,
                    "emotion": emotion
                })

        # 4. Build BM25 index on interaction pairs
        interaction_corpus = [
            normalize_tanglish_tokens(it["user_trigger"]) + normalize_tanglish_tokens(it["partner_reaction"])
            for it in self.interactions
        ]
        self.bm25_interactions = BM25Okapi(interaction_corpus)

        # 5. Build BM25 index on partner utterances
        partner_corpus = [
            normalize_tanglish_tokens(utt)
            for utt in self.partner_utterances
        ]
        self.bm25_partner = BM25Okapi(partner_corpus)

    def retrieve_historical_reactions(
        self,
        query: str,
        top_k: int = 5,
        slot_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieves real situations where Manoj sent something similar and how Sakthi reacted.
        Returns top candidates with scores, time slots, and emotions.
        """
        if not self.bm25_interactions or not self.interactions:
            return []

        q_clean = query.strip()
        if len(q_clean) <= 1:
            return []

        tokens = normalize_tanglish_tokens(q_clean)
        if not tokens:
            return []

        scores = self.bm25_interactions.get_scores(tokens)
        candidate_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

        results = []
        for idx in candidate_indices:
            score = scores[idx]
            if score <= 0.2:  # Threshold
                break

            it = self.interactions[idx]
            if slot_filter and it.get("time_slot") != slot_filter:
                # Still include with slightly modified rank if needed, or skip
                pass

            results.append({
                "user_trigger": it["user_trigger"],
                "partner_reaction": it["partner_reaction"],
                "partner_burst": it["partner_burst_messages"],
                "score": round(float(score), 2),
                "timestamp": it.get("timestamp"),
                "time_slot": it.get("time_slot"),
                "emotion": it.get("emotion")
            })

            if len(results) >= top_k:
                break

        return results

    def retrieve_partner_utterances(self, query: str, top_k: int = 3) -> List[str]:
        """
        Retrieves authentic single partner messages on the same topic.
        """
        if not self.bm25_partner or not self.partner_utterances:
            return []

        tokens = normalize_tanglish_tokens(query)
        if not tokens:
            return []

        scores = self.bm25_partner.get_scores(tokens)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0.3:
                results.append(self.partner_utterances[idx])

        return results
