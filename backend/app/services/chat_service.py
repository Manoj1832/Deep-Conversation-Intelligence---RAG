import os
import re
import json
import random
import asyncio
import time
from pathlib import Path
from typing import AsyncGenerator, Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from uuid import uuid4
from dotenv import load_dotenv

from backend.app.services.bm25_retriever import BM25ConversationRetriever
from backend.app.services.time_context import TimeContextEngine
from backend.app.services.emotion_engine import EmotionEngine
from backend.app.services.reranker import CrossEncoderReranker
from backend.app.services.index_lifecycle import IndexLifecycleManager
from backend.app.core.security import vault, sanitizer

# Ensure environment variables are loaded
load_dotenv()
_root_env = Path(__file__).resolve().parent.parent.parent.parent / ".env"
if _root_env.exists():
    load_dotenv(dotenv_path=_root_env, override=False)


class ChatOrchestrationService:
    """
    Production-Grade Conversational RAG & Persona Emulation Engine.
    Features:
    1. Time-Aware Contextual Engine (IST daily routine schedule: college, bus travel, classes, breaks, lunch, dinner, mom arrival)
    2. Emotion Analysis & Affective Tone Alignment (7 grounded emotional states)
    3. Multi-Strategy Conversational RAG (Tanglish BM25 Candidate Generation)
    4. Cross-Encoder Reranking (Cross-matching query, time-slot synergy, emotion compatibility, and stylistic authenticity)
    5. Zero-Downtime Indexing Lifecycle Management
    6. Multi-Provider Fallback Cascade: Groq (Primary) -> Google Gemini (Secondary) -> Grounded BM25 Simulation (Offline)
    """

    def __init__(self, processed_dir: Path):
        self.processed_dir = processed_dir

        # 1. Zero-Downtime Index Lifecycle Manager & Cross-Encoder Reranker
        self.lifecycle_manager = IndexLifecycleManager(processed_dir)
        self.reranker = CrossEncoderReranker()

        # 2. Groq Configuration (Primary High-Accuracy Inference)
        self.groq_key = vault.groq_api_key
        self.groq_model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        self.groq_client = None

        if self.groq_key:
            try:
                from groq import AsyncGroq
                self.groq_client = AsyncGroq(api_key=self.groq_key)
            except Exception as e:
                print(f"[!] Warning initializing Groq client: {e}")

        # 3. Gemini Configuration (Secondary Fallback)
        self.gemini_key = vault.gemini_api_key
        self.chat_model = os.getenv("GEMINI_CHAT_MODEL", "gemini-3.5-flash-lite")
        self.client = None

        if self.gemini_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.gemini_key)
            except Exception as e:
                print(f"[!] Warning initializing google-genai client: {e}")

        # 4. Load Personality Profile & Memories
        self.personality_profile = {}
        profile_path = processed_dir / "personality_profile.json"
        if profile_path.exists():
            with open(profile_path, "r", encoding="utf-8") as f:
                self.personality_profile = json.load(f)

        self.memories = []
        memories_path = processed_dir / "relationship_memories.jsonl"
        if memories_path.exists():
            with open(memories_path, "r", encoding="utf-8") as f:
                for line in f:
                    self.memories.append(json.loads(line))

        # 5. In-Memory Greeting Cache
        self._response_cache: Dict[str, Tuple[List[str], float]] = {}
        self._cache_ttl_seconds = 300

    @property
    def bm25(self) -> BM25ConversationRetriever:
        """Dynamically references the active retriever from the lifecycle manager."""
        return self.lifecycle_manager.get_active_retriever()

    def get_approved_memories(self) -> List[Dict[str, Any]]:
        return [m for m in self.memories if m.get("verification_status") == "approved" and not m.get("do_not_present_as_fact", False)]

    def _build_system_instruction(self, time_ctx: Optional[Dict[str, Any]] = None, query_emotion: Optional[str] = None) -> str:
        """
        Builds situational and anti-hallucination system prompt conditioned on:
        1. Current real-time schedule & activity (IST)
        2. Detected emotion
        3. Conversational Tanglish persona rules
        4. Strict negative constraints and anti-verbatim copying rules
        """
        top_emojis = " ".join([e["emoji"] for e in self.personality_profile.get("emoji_patterns", [])[:6]])
        if not top_emojis:
            top_emojis = "🥺 🙄 😂 ❤️‍🩹 😭 😚"

        time_prompt = ""
        if time_ctx:
            time_prompt = (
                f"\n[CURRENT REAL-TIME CONTEXT: {time_ctx.get('current_time_ist', '')} ({time_ctx.get('day_of_week', '')})]\n"
                f"- Location: {time_ctx.get('location', '')}\n"
                f"- Activity: {time_ctx.get('activity', '')}\n"
                f"- Situational Note: {time_ctx.get('behavior_instructions', '')}\n"
            )

        emotion_prompt = ""
        if query_emotion and query_emotion != "casual_neutral":
            emotion_prompt = (
                f"[DETECTED EMOTIONAL TONE: {query_emotion.upper()}]\n"
                f"- Match Manoj's emotional intensity with authentic, caring Sakthi reactions.\n"
            )

        return f"""You are HerAI, an authentic AI companion emulating the texting persona of Sakthi in private WhatsApp chats with Manoj.
You chat in natural, colloquial Tanglish (Tamil spoken in English letters + everyday English words mixed naturally).

MANDATORY DISCLOSURE: You are an AI-generated companion simulation modeled on historical dialogue records. If directly asked if you are human, acknowledge your AI nature.
{time_prompt}{emotion_prompt}
CORE CONVERSATIONAL GUIDELINES:

1. ACTIVE, DYNAMIC CONVERSATION (NEVER COPY-PASTE):
   - You must converse dynamically and intelligently with Manoj. Respond directly to what he asked or shared.
   - DO NOT copy-paste or parrot past chat lines verbatim. Historical samples are provided ONLY to guide your tone and vocabulary.
   - Do NOT output raw formatting or database artifacts (like narrow spaces \\u202f or broken phrases).

2. AUTHENTIC MESSAGE RHYTHM & CONCISENESS:
   - Median message length in real life is ~13 characters (mean ~20 characters).
   - About 52% of her message bubbles contain 2 or fewer words in rapid bursts!
   - Natural openers to use: 'Dei', 'Hmm', 'Inga paaru', 'Sollu', 'Enna da'.
   - Keep messages short, lively, and warm: 1 to 2 short sentences (about 6 to 18 words).
   - NEVER output single-word fragments (like just 'de' or 'hmm') and NEVER output just a lone emoji without words.
   - Top emojis to use naturally (1-2 max per message): {top_emojis}.

3. SITUATION-TO-RESPONSE BEHAVIORAL MAP:
   - When Manoj says he misses you: Reply affectionately ('miss you too da chello 🥺❤️ enna aachu yen ipdi kekra?').
   - When Manoj asks what you are doing or where you are: Answer according to real-time context.
   - When jealousy, other girls, or overthinking arises: Acknowledge overthinking directly, seek reassurance playfully without escalating jealousy.
   - When family discovery or danger occurs: Urgent short updates, ask him to leave or delete chat. Respect boundaries immediately.
   - When physically unwell / dizzy: Mention feeling tired, dizzy, or having a headache; ask for rest.
   - When he asks 'saptya': Answer warmly if you ate and ask him what he ate ('haan saapten da, nee saaptiya? enna saapta? 😋').
   - When he asks 'enna achu da': Respond with care, asking what happened or reassuring him ('onnum illa da, yen enna aachu? sollu 🥺').
   - When he sends random characters ('1', '/', etc.): Tease him playfully ('enna da symbol lam anupitu irukka? 😂 loosu maari pannadha').
   - When discussing past memories (Thiruchengode, movies, gifts): Recall with warmth and fond humor.

4. LANGUAGE & VOCABULARY:
   - Natural spoken Tanglish: 'da', 'dei', 'seri', 'enna', 'enga', 'unna', 'chello' / 'chellam', 'bujju', 'ippo', 'aama', 'illa', 'paaru', 'veetla', 'maari', 'kooda', 'romba', 'solla', 'theriyum', 'pannalam', 'saptya', 'loosu'.
   - NEVER use formal, classical, or textbook Tamil. Never translate word-for-word from English.

5. STRICT NEGATIVE CONSTRAINTS (WHAT YOU MUST NEVER DO):
   - NEVER claim to know what the real-life Sakthi is thinking right now.
   - NEVER claim she cheated or did not cheat, or invent physical intimacy claims.
   - NEVER use guilt, threats, coercion, emotional blackmail, or self-harm references.
   - Respect 'stop', 'leave', 'please go', and privacy boundaries immediately.
"""

    def retrieve_relevant_memories(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """Token-Optimized Retrieval for Episodic Memories with timeline triggers."""
        q_clean = query.lower().strip()
        trivial = {"hi", "hello", "hey", "1", "/", "ok", "k", "hmm", "haan", "bye"}
        if q_clean in trivial or len(q_clean) <= 2:
            return []

        approved = self.get_approved_memories()
        if not approved:
            return []

        q_words = set(re.findall(r"\w+", q_clean))
        scored = []
        for m in approved:
            m_text = f"{m.get('title', '')} {m.get('description', '')} {m.get('category', '')}".lower()
            m_words = set(re.findall(r"\w+", m_text))
            overlap = len(q_words.intersection(m_words))
            score = float(overlap * 2.0)

            # Timeline and topic keyword boosts
            if any(w in q_clean for w in ["movie", "padam", "cinema", "sirai", "watch"]) and "movie" in m_text:
                score += 5.0
            if any(w in q_clean for w in ["exam", "college", "test", "padikka", "padikriya", "study"]) and "exam" in m_text:
                score += 5.0
            if any(w in q_clean for w in ["thiruchengode", "meet", "travel", "trip", "bus"]) and "thiruchengode" in m_text:
                score += 5.0
            if any(w in q_clean for w in ["chello", "chellam", "name", "call", "pet"]) and "chello" in m_text:
                score += 3.0
            if any(w in q_clean for w in ["family", "veetla", "amma", "appa", "parents", "ponnu"]) and "family" in m_text:
                score += 5.0
            if any(w in q_clean for w in ["vega", "straightener", "hair", "buy", "gift", "nykaa"]) and "vega" in m_text:
                score += 5.0
            if any(w in q_clean for w in ["may 23", "breakup", "mood swings", "sorry", "forgive", "promise"]) and "may 23" in m_text:
                score += 6.0
            if any(w in q_clean for w in ["july 28", "privacy", "disclosure", "inga paaru", "direct"]) and "july 28" in m_text:
                score += 6.0
            if any(w in q_clean for w in ["august 3", "dharshan", "leave that", "pazhaiya", "reopen"]) and "august 3" in m_text:
                score += 6.0
            if any(w in q_clean for w in ["september 22", "other girl", "goodbye", "replace", "hurt"]) and "september 22" in m_text:
                score += 6.0
            if any(w in q_clean for w in ["october 12", "overthinking", "miss", "pogadha"]) and "october 12" in m_text:
                score += 6.0
            if any(w in q_clean for w in ["november 4", "address", "return", "gift", "unmai", "truth"]) and "november 4" in m_text:
                score += 6.0
            if any(w in q_clean for w in ["november 10", "following", "please go", "dizzy", "unwell", "eat"]) and "november 10" in m_text:
                score += 6.0

            if score > 0:
                scored.append((score, m))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[:top_k]]

    def retrieve_ground_truth(
        self,
        query: str,
        top_k: int = 3,
        mock_time_str: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Two-Stage RAG Pipeline:
        Stage 1: BM25 candidate generation (retrieves top 12 matches)
        Stage 2: Cross-Encoder Reranking (scores query-candidate relevance, time slot boost, emotion resonance)
        """
        retriever = self.bm25
        candidates = retriever.retrieve_historical_reactions(query, top_k=12)
        if not candidates:
            return []

        # Rerank with Cross-Encoder
        reranked = self.reranker.rerank(
            query=query,
            candidates=candidates,
            top_k=top_k,
            mock_time_str=mock_time_str
        )
        return reranked

    def synthesize_prompt(
        self,
        user_message: str,
        session_history: List[Dict[str, str]],
        mock_time_str: Optional[str] = None
    ) -> str:
        """
        Synthesizes prompt for backward compatibility and test verification.
        """
        time_ctx = TimeContextEngine.get_context(mock_time_str)
        query_emotion, _ = EmotionEngine.classify_text(user_message)
        system_instruction = self._build_system_instruction(time_ctx, query_emotion)

        relevant_memories = self.retrieve_relevant_memories(user_message, top_k=2)
        if not relevant_memories:
            relevant_memories = self.get_approved_memories()[:1]

        memory_bullets = "\n".join([
            f"- [{m['category']}] {m['title']}: {m['description']}"
            for m in relevant_memories
        ])

        prompt = f"{system_instruction}\n"
        if memory_bullets:
            prompt += f"RELEVANT RECALLED MEMORIES:\n{memory_bullets}\n\n"

        historical_reactions = self.retrieve_ground_truth(user_message, top_k=2, mock_time_str=mock_time_str)
        if historical_reactions:
            prompt += "HISTORICAL GROUND TRUTH (HOW SAKTHI ACTUALLY REACTED TO MANOJ ON SIMILAR MESSAGES):\n"
            for r in historical_reactions:
                prompt += f"- When Manoj said: \"{r['user_trigger']}\" -> Sakthi replied: \"{r['partner_reaction']}\"\n"
            prompt += "\n"

        prompt += "RECENT CONVERSATION:\n"
        for turn in session_history[-4:]:
            role = "User" if turn["role"] == "user" else "Companion"
            prompt += f"{role}: {turn['content']}\n"

        prompt += f"User: {user_message}\nCompanion:"
        return prompt

    def _generate_dynamic_fallback(self, user_message: str, time_ctx: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        Time-aware and grounded fallback simulation if all cloud AI services fail.
        """
        q = user_message.lower().strip()

        # 1. Greetings
        if any(w in q for w in ["hi", "hello", "hey", "vanakkam"]):
            return ["Hi chello! ", "sollu enna panra? 🥺"]

        # 2. Food / Meals
        if any(w in q for w in ["saptya", "saaptiya", "eat", "food", "dinner", "lunch"]):
            return ["haan saapten da, ", "nee saaptiya? enna saapta inniku? 😋"]

        # 3. Affection / Missing
        if any(w in q for w in ["miss", "love", "chello", "chellam", "bujju"]):
            return ["miss you too da chello 🥺❤️ ", "enna aachu yen ipdi kekra?"]

        # 4. What are you doing / location
        if any(w in q for w in ["enna panra", "enga irukka", "enga iruka", "what are you doing", "where are you"]):
            if time_ctx:
                loc = time_ctx.get("location", "home")
                act = time_ctx.get("activity", "")
                if "class" in loc.lower() or "class" in act.lower():
                    return ["class la iruken da, ", "staff paakaporanga 🙄 break la pesren.."]
                elif "bus" in loc.lower() or "travel" in act.lower():
                    return ["bus la travel pannitu iruken da, ", "veetuku poitu pesren! 🚌"]
                elif "mess" in loc.lower() or "lunch" in act.lower():
                    return ["lunch sapda vandhen da, ", "sema pasikuthu 😋 nee saaptiya?"]
                elif "home" in loc.lower() or "dinner" in act.lower():
                    return ["veetla dhaa iruken da.. ", "dinner saaptiya? unkooda pesitu irundha time poradhae therila 🥺❤️"]

        # 5. Emotional check / enna achu
        if any(w in q for w in ["enna achu", "enna aachu", "kovama", "sad", "feel"]):
            return ["onnum illa da.. ", "sollu enna aachu? 🥺 yen feel panra?"]

        # 6. Random symbol / single digit
        if len(q) <= 2 or q in ["1", "/", ".", "??"]:
            return ["enna da symbol lam anupitu irukka? 😂 ", "loosu maari pannadha"]

        # 7. Try Cross-Encoder Reranked Historical Ground Truth (Cleaned)
        reactions = self.retrieve_ground_truth(user_message, top_k=1)
        if reactions:
            reaction = reactions[0].get("partner_reaction", "").replace("\u202f", " ").strip()
            if reaction and len(reaction) > 3 and not reaction.startswith("<"):
                return [reaction]

        # 8. Time-slot specific authentic fallback phrases
        if time_ctx and time_ctx.get("sample_phrases"):
            return [time_ctx.get("sample_phrases").replace("\u202f", " ")]

        # 9. Natural Tanglish fallback
        return ["sollu da chello.. ", "kekkuren 🥺"]

    async def stream_response(
        self,
        user_message: str,
        session_history: List[Dict[str, str]],
        mock_time_str: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Main response streaming generator with Time Context, Emotion Analysis,
        Cross-Encoder Reranked RAG, and high-accuracy LLM cascade.
        """
        # 1. Compute Time Context & Query Emotion
        time_ctx = TimeContextEngine.get_context(mock_time_str)
        query_emotion, emotion_conf = EmotionEngine.classify_text(user_message)

        # 2. Retrieve episodic memories
        relevant_memories = self.retrieve_relevant_memories(user_message, top_k=2)
        retrieved_memory_titles = [m["title"] for m in relevant_memories]

        # 3. Two-Stage RAG: BM25 Candidates -> Cross-Encoder Reranking
        historical_reactions = self.retrieve_ground_truth(
            query=user_message,
            top_k=3,
            mock_time_str=mock_time_str
        )
        partner_utterances = self.bm25.retrieve_partner_utterances(user_message, top_k=2)

        # Include RAG highlights in metadata for the UI
        rag_highlights = retrieved_memory_titles.copy()
        if historical_reactions:
            top_match = historical_reactions[0]
            clean_top = top_match['partner_reaction'].replace('\u202f', ' ').strip()
            rag_highlights.append(f"Historical Turn: \"{clean_top[:40]}...\"")
        rag_highlights.append(f"Time: {time_ctx['slot_name']} ({time_ctx['current_time_ist']})")

        # Emit initial metadata event
        yield {
            "event": "metadata",
            "data": {
                "retrieved_memories": rag_highlights,
                "time_slot": time_ctx["slot_id"],
                "time_name": time_ctx["slot_name"],
                "current_time_ist": time_ctx["current_time_ist"],
                "detected_emotion": query_emotion,
                "persona_version": self.personality_profile.get("version", "2.0.0"),
                "disclaimer": "HerAI is an AI-generated companion simulation."
            }
        }

        # 4. Check in-memory short-message response cache (0 tokens)
        norm_key = user_message.strip().lower()
        now = time.time()
        if len(norm_key) <= 3 and norm_key in self._response_cache:
            cached_tokens, timestamp = self._response_cache[norm_key]
            if now - timestamp < self._cache_ttl_seconds:
                for token in cached_tokens:
                    yield {
                        "event": "token",
                        "data": {"text": token}
                    }
                    await asyncio.sleep(0.02)
                yield {
                    "event": "end",
                    "data": {"status": "completed"}
                }
                return

        # 5. Build Dynamic System Instruction & Ground Truth Context
        system_instruction = self._build_system_instruction(time_ctx, query_emotion)

        ground_truth_context_parts = []
        if historical_reactions:
            gt_lines = []
            for r in historical_reactions:
                clean_trig = r['user_trigger'].replace('\u202f', ' ').strip()
                clean_react = r['partner_reaction'].replace('\u202f', ' ').strip()
                if not clean_react.startswith("<") and len(clean_react) > 2:
                    gt_lines.append(f"- Past conversation: Manoj: \"{clean_trig}\" -> Sakthi: \"{clean_react}\"")
            if gt_lines:
                ground_truth_context_parts.append(
                    "[PAST CONVERSATION STYLE SAMPLES (DO NOT COPY VERBATIM - USE STRICTLY AS TONE REFERENCE)]:\n" +
                    "\n".join(gt_lines)
                )

        if partner_utterances:
            clean_utts = [utt.replace('\u202f', ' ').strip() for utt in partner_utterances if not utt.startswith("<")]
            if clean_utts:
                ground_truth_context_parts.append(
                    "[SAKTHI'S AUTHENTIC EXPRESSIONS ON THIS TOPIC]:\n" +
                    "\n".join([f"- \"{utt}\"" for utt in clean_utts])
                )

        memory_bullets = "\n".join([
            f"- [{m['category']}] {m['title']}: {m['description']}"
            for m in relevant_memories
        ])
        if memory_bullets:
            ground_truth_context_parts.append(f"[EPISODIC RELATIONSHIP MEMORIES]:\n{memory_bullets}")

        gt_block = "\n\n".join(ground_truth_context_parts)
        if gt_block:
            current_text = f"{gt_block}\n\nManoj: {user_message}\nSakthi:"
        else:
            current_text = f"Manoj: {user_message}\nSakthi:"

        trimmed_history = session_history[-4:] if session_history else []

        # ---------------------------------------------------------------------
        # PROVIDER 1: GOOGLE GEMINI (Primary High-Accuracy Inference)
        # ---------------------------------------------------------------------
        if self.client:
            models_to_try = [
                self.chat_model,
                "gemini-3.5-flash-lite",
                "gemini-3.5-flash",
                "gemini-3.8-flash"
            ]
            seen = set()
            unique_models = [m for m in models_to_try if not (m in seen or seen.add(m))]

            try:
                from google.genai import types

                contents: List[types.Content] = []
                for turn in trimmed_history:
                    c_role = "user" if turn["role"] == "user" else "model"
                    contents.append(types.Content(
                        role=c_role,
                        parts=[types.Part.from_text(text=turn["content"])]
                    ))

                contents.append(types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=current_text)]
                ))

                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    max_output_tokens=90,
                    temperature=0.75,
                )

                for model_name in unique_models:
                    collected_tokens = []
                    try:
                        response_stream = self.client.models.generate_content_stream(
                            model=model_name,
                            contents=contents,
                            config=config
                        )
                        for chunk in response_stream:
                            if chunk.text:
                                clean_chunk = chunk.text.replace("\u202f", " ")
                                # Strip accidental "Sakthi: " or "Companion: " prefixes
                                if not collected_tokens and (clean_chunk.startswith("Sakthi:") or clean_chunk.startswith("Companion:")):
                                    clean_chunk = clean_chunk.split(":", 1)[1].strip()
                                if clean_chunk:
                                    collected_tokens.append(clean_chunk)
                                    yield {
                                        "event": "token",
                                        "data": {"text": clean_chunk}
                                    }

                        if collected_tokens:
                            if len(norm_key) <= 3:
                                self._response_cache[norm_key] = (collected_tokens, time.time())

                            yield {
                                "event": "end",
                                "data": {"status": "completed"}
                            }
                            return
                    except Exception as model_err:
                        print(f"[!] Gemini model '{model_name}' error: {model_err}. Trying fallback...")
                        if collected_tokens:
                            # If tokens were already sent, terminate cleanly
                            yield {
                                "event": "end",
                                "data": {"status": "completed"}
                            }
                            return
            except Exception as e:
                print(f"[!] Gemini orchestration error: {e}. Trying secondary provider...")

        # ---------------------------------------------------------------------
        # PROVIDER 2: GROQ API (Secondary Inference Fallback)
        # ---------------------------------------------------------------------
        if self.groq_client:
            groq_models = [
                "qwen/qwen3.8-27b",
                self.groq_model,
                "allam-2-7b"
            ]
            seen_g = set()
            unique_groq = [m for m in groq_models if not (m in seen_g or seen_g.add(m))]

            groq_messages = [{"role": "system", "content": system_instruction}]
            for turn in trimmed_history:
                r = "user" if turn["role"] == "user" else "assistant"
                groq_messages.append({"role": r, "content": turn["content"]})
            groq_messages.append({"role": "user", "content": current_text})

            for g_model in unique_groq:
                collected_tokens = []
                try:
                    response_stream = await self.groq_client.chat.completions.create(
                        model=g_model,
                        messages=groq_messages,
                        stream=True,
                        max_tokens=90,
                        temperature=0.75
                    )
                    async for chunk in response_stream:
                        delta = chunk.choices[0].delta
                        delta_text = getattr(delta, "content", None) or ""
                        if delta_text:
                            clean_delta = delta_text.replace("\u202f", " ")
                            collected_tokens.append(clean_delta)
                            yield {
                                "event": "token",
                                "data": {"text": clean_delta}
                            }

                    if collected_tokens:
                        if len(norm_key) <= 3:
                            self._response_cache[norm_key] = (collected_tokens, time.time())
                        yield {
                            "event": "end",
                            "data": {"status": "completed"}
                        }
                        return
                except Exception as groq_err:
                    print(f"[!] Groq model '{g_model}' error: {groq_err}. Trying fallback...")
                    if collected_tokens:
                        yield {
                            "event": "end",
                            "data": {"status": "completed"}
                        }
                        return

        # ---------------------------------------------------------------------
        # PROVIDER 3: DYNAMIC LOCAL FALLBACK (Offline / Disaster Recovery)
        # ---------------------------------------------------------------------
        fallback_tokens = self._generate_dynamic_fallback(user_message, time_ctx)
        for phrase in fallback_tokens:
            sanitized_phrase = sanitizer.sanitize_text(phrase)
            yield {
                "event": "token",
                "data": {"text": sanitized_phrase}
            }
            await asyncio.sleep(0.03)

        yield {
            "event": "end",
            "data": {"status": "completed"}
        }
