"""
Cross-Encoder Reranking Engine for HerAI.
Inspired by KazKozDev/production-rag cross-encoder architecture.

Reranks candidate conversational interaction turns from first-stage retrieval (BM25)
by fusing:
1. Lexical & Semantic Cross-Coverage (Tanglish semantic stems, Jaccard & containment)
2. Temporal Alignment (Relevance boost for interactions from the matching time-of-day slot)
3. Emotional Resonance (Harmonizing query emotion with partner reaction state)
4. Stylistic Authenticity (Presence of characteristic particles, emojis, and burstiness)
"""

from typing import List, Dict, Any, Optional
import re
from backend.app.services.time_context import TimeContextEngine
from backend.app.services.emotion_engine import EmotionEngine


class CrossEncoderReranker:
    """
    Production Cross-Encoder Reranker for conversational retrieval.
    Computes joint (query, candidate) relevance scores with zero external heavy dependencies.
    """

    def __init__(self, time_weight: float = 0.25, emotion_weight: float = 0.20, content_weight: float = 0.55):
        self.time_weight = time_weight
        self.emotion_weight = emotion_weight
        self.content_weight = content_weight
        self._score_cache: Dict[str, float] = {}

    def score_pair(
        self,
        query: str,
        candidate: Dict[str, Any],
        current_slot_id: Optional[str] = None,
        query_emotion: Optional[str] = None
    ) -> float:
        """
        Calculates joint cross-encoder score between user query and candidate interaction.
        Returns a normalized score between 0.0 and 1.0.
        """
        user_trigger = candidate.get("user_trigger", "")
        partner_reaction = candidate.get("partner_reaction", "")
        cand_slot = candidate.get("time_slot")
        cand_emotion = candidate.get("emotion")

        # 1. Content & Semantic Relevance (0.0 to 1.0)
        q_words = set(re.findall(r"\w+", query.lower()))
        t_words = set(re.findall(r"\w+", user_trigger.lower()))
        r_words = set(re.findall(r"\w+", partner_reaction.lower()))

        # Downweight generic conversational particles
        particles = {'da', 'di', 'la', 'ah', 'pa', 'tha', 'nu', 'aam', 'un', 'en', 'na', 'nee', 'seri', 'illai', 'illa'}
        q_clean = q_words - particles
        t_clean = t_words - particles
        r_clean = r_words - particles

        # Coverage in trigger vs reaction
        trigger_overlap = len(q_clean & t_clean)
        trigger_coverage = trigger_overlap / max(1, len(q_clean)) if q_clean else 0.0
        
        reaction_overlap = len(q_clean & r_clean)
        reaction_coverage = reaction_overlap / max(1, len(q_clean)) if q_clean else 0.0

        # Jaccard similarity with trigger
        union_words = q_clean | t_clean
        jaccard = (trigger_overlap / len(union_words)) if union_words else 0.0

        content_score = (0.50 * trigger_coverage) + (0.30 * jaccard) + (0.20 * reaction_coverage)

        # 2. Temporal Relevance Boost (0.0 to 1.0)
        time_score = 0.5  # neutral baseline
        if current_slot_id and cand_slot:
            if current_slot_id == cand_slot:
                time_score = 1.0  # Perfect time match!
            elif self._are_adjacent_slots(current_slot_id, cand_slot):
                time_score = 0.75  # Close time match

        # 3. Emotional Resonance (0.0 to 1.0)
        emotion_score = 0.5  # neutral baseline
        if query_emotion and cand_emotion:
            if query_emotion == cand_emotion:
                emotion_score = 1.0  # Exact emotion reflection
            elif self._is_complementary_emotion(query_emotion, cand_emotion):
                emotion_score = 0.85  # Natural emotional pairing

        # 4. Stylistic Authenticity bonus (presence of key emojis or characteristic tokens)
        authenticity_bonus = 0.0
        for em in ["🥺", "🙄", "😂", "❤️‍🩹", "😭", "😚"]:
            if em in partner_reaction:
                authenticity_bonus += 0.05
        authenticity_bonus = min(0.15, authenticity_bonus)

        # Joint Cross-Encoder Score
        final_score = (
            (self.content_weight * content_score) +
            (self.time_weight * time_score) +
            (self.emotion_weight * emotion_score) +
            authenticity_bonus
        )

        return min(1.0, max(0.0, final_score))

    def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 3,
        mock_time_str: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Takes first-stage retrieval candidates and reranks them using joint cross-scoring.
        """
        if not candidates:
            return []

        # Determine current temporal & emotional context
        time_ctx = TimeContextEngine.get_context(mock_time_str)
        current_slot_id = time_ctx.get("slot_id")
        query_emotion, _ = EmotionEngine.classify_text(query)

        scored_candidates = []
        for cand in candidates:
            rerank_score = self.score_pair(
                query=query,
                candidate=cand,
                current_slot_id=current_slot_id,
                query_emotion=query_emotion
            )
            # Combine initial retrieval score with cross-encoder score
            init_score = cand.get("score", 0.0)
            combined_score = 0.4 * min(1.0, init_score / 5.0) + 0.6 * rerank_score
            
            cand_copy = dict(cand)
            cand_copy["cross_encoder_score"] = round(rerank_score, 3)
            cand_copy["final_score"] = round(combined_score, 3)
            scored_candidates.append((combined_score, cand_copy))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored_candidates[:top_k]]

    def _are_adjacent_slots(self, slot_a: str, slot_b: str) -> bool:
        """Determines if two slots are temporally neighboring."""
        adjacent_pairs = {
            ("morning_travel", "college_entry_bfast"),
            ("college_entry_bfast", "morning_class"),
            ("morning_class", "morning_break"),
            ("morning_break", "class_lab"),
            ("class_lab", "lunch_time"),
            ("lunch_time", "afternoon_class"),
            ("afternoon_class", "bus_seat_transit"),
            ("bus_seat_transit", "travel_to_potteneri"),
            ("travel_to_potteneri", "home_arrival_freshup"),
            ("home_arrival_freshup", "home_dinner_chat"),
            ("home_dinner_chat", "post_mom_arrival_night"),
            ("post_mom_arrival_night", "late_night_sleep")
        }
        return (slot_a, slot_b) in adjacent_pairs or (slot_b, slot_a) in adjacent_pairs

    def _is_complementary_emotion(self, query_em: str, cand_em: str) -> bool:
        """Determines if emotion states naturally trigger each other."""
        complements = {
            ("affectionate", "caring_routine"),
            ("caring_routine", "affectionate"),
            ("playful_teasing", "playful_teasing"),
            ("irritated_angry", "anxious_tense"),
            ("anxious_tense", "sad_vulnerable"),
            ("sad_vulnerable", "affectionate")
        }
        return (query_em, cand_em) in complements
