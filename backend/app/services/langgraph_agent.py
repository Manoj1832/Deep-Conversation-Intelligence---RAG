import os
import re
import json
import time
import asyncio
import logging
from pathlib import Path
from typing import TypedDict, List, Dict, Any, Optional, AsyncGenerator
from datetime import datetime, timezone
from uuid import uuid4

from langgraph.graph import StateGraph, START, END

from backend.app.services.time_context import TimeContextEngine
from backend.app.services.emotion_engine import EmotionEngine
from backend.app.core.security import sanitizer

logger = logging.getLogger("herai.langgraph")


class ConversationState(TypedDict, total=False):
    """
    Production State schema for HerAI LangGraph Conversational Agent.
    """
    # Session identity
    session_id: str
    user_id: str
    user_message: str
    session_history: List[Dict[str, str]]
    mock_time_str: Optional[str]

    # Context enrichment
    time_ctx: Dict[str, Any]
    detected_emotion: str
    emotion_confidence: float
    retrieved_memories: List[Dict[str, Any]]
    rag_highlights: List[str]
    historical_reactions: List[Dict[str, Any]]
    partner_utterances: List[str]
    system_instruction: str
    ground_truth_block: str
    current_prompt: str

    # Response generation
    response_tokens: List[str]
    full_response: str
    generation_provider: str
    error: Optional[str]

    # Continual Self-Learning / Memory Updates
    extracted_memories: List[Dict[str, Any]]
    learned_memory_count: int
    memory_update_status: str


class LangGraphConversationAgent:
    """
    Production-scale LangGraph Conversation & Continual Learning Engine.
    Orchestrates:
    1. Node 'enrich_context': Time context, emotion detection, and 2-stage RAG retrieval
    2. Node 'generate_response': LLM generation with multi-provider cascade
    3. Node 'self_learn_memory': Continual learning loop that extracts new facts,
       preferences, and relationship milestones from every interaction, updates
       memory stores and Qdrant in real-time.
    """

    def __init__(
        self,
        chat_orchestrator,
        memory_resolver=None,
        memory_indexer=None,
        processed_dir: Optional[Path] = None
    ):
        self.orchestrator = chat_orchestrator
        self.resolver = memory_resolver
        self.indexer = memory_indexer
        self.processed_dir = processed_dir or getattr(chat_orchestrator, "processed_dir", None)
        self.memories_file = self.processed_dir / "relationship_memories.jsonl" if self.processed_dir else None

        # Build and compile the LangGraph workflow
        self.workflow = self._build_graph()
        self.app = self.workflow.compile()

    def _build_graph(self) -> StateGraph:
        """Constructs the LangGraph state machine with cyclic continual learning."""
        builder = StateGraph(ConversationState)

        # Register nodes
        builder.add_node("enrich_context", self._node_enrich_context)
        builder.add_node("generate_response", self._node_generate_response)
        builder.add_node("self_learn_memory", self._node_self_learn_memory)

        # Wire linear progression with memory commitment
        builder.add_edge(START, "enrich_context")
        builder.add_edge("enrich_context", "generate_response")
        builder.add_edge("generate_response", "self_learn_memory")
        builder.add_edge("self_learn_memory", END)

        return builder

    # -------------------------------------------------------------------------
    # NODE 1: ENRICH CONTEXT
    # -------------------------------------------------------------------------
    def _node_enrich_context(self, state: ConversationState) -> Dict[str, Any]:
        """
        Gathers real-time IST time context, classifies user emotion, and fetches
        episodic memories and BM25/Cross-Encoder historical dialogue precedents.
        """
        user_message = state.get("user_message", "")
        mock_time_str = state.get("mock_time_str")

        # 1. Real-time IST context & emotion
        time_ctx = TimeContextEngine.get_context(mock_time_str)
        query_emotion, emotion_conf = EmotionEngine.classify_text(user_message)

        # 2. Episodic memory retrieval
        relevant_memories = self.orchestrator.retrieve_relevant_memories(user_message, top_k=2)
        if not relevant_memories:
            relevant_memories = self.orchestrator.get_approved_memories()[:1]

        # 3. Two-Stage RAG: BM25 Candidates -> Cross-Encoder Reranking
        historical_reactions = self.orchestrator.retrieve_ground_truth(
            query=user_message,
            top_k=3,
            mock_time_str=mock_time_str
        )
        partner_utterances = self.orchestrator.bm25.retrieve_partner_utterances(user_message, top_k=2)

        # 4. RAG Highlights metadata
        retrieved_memory_titles = [m.get("title", "") for m in relevant_memories if m.get("title")]
        rag_highlights = retrieved_memory_titles.copy()
        if historical_reactions:
            clean_top = historical_reactions[0].get("partner_reaction", "").replace("\u202f", " ").strip()
            rag_highlights.append(f"Historical Turn: \"{clean_top[:40]}...\"")
        rag_highlights.append(f"Time: {time_ctx.get('slot_name')} ({time_ctx.get('current_time_ist')})")

        # 5. Build prompt contexts
        system_instruction = self.orchestrator._build_system_instruction(time_ctx, query_emotion)

        ground_truth_context_parts = []
        if historical_reactions:
            gt_lines = []
            for r in historical_reactions:
                clean_trig = r.get("user_trigger", "").replace("\u202f", " ").strip()
                clean_react = r.get("partner_reaction", "").replace("\u202f", " ").strip()
                if not clean_react.startswith("<") and len(clean_react) > 2:
                    gt_lines.append(f"- Past conversation: Manoj: \"{clean_trig}\" -> Sakthi: \"{clean_react}\"")
            if gt_lines:
                ground_truth_context_parts.append(
                    "[PAST CONVERSATION STYLE SAMPLES (DO NOT COPY VERBATIM - USE STRICTLY AS TONE REFERENCE)]:\n" +
                    "\n".join(gt_lines)
                )

        if partner_utterances:
            clean_utts = [utt.replace("\u202f", " ").strip() for utt in partner_utterances if not utt.startswith("<")]
            if clean_utts:
                ground_truth_context_parts.append(
                    "[SAKTHI'S AUTHENTIC EXPRESSIONS ON THIS TOPIC]:\n" +
                    "\n".join([f"- \"{utt}\"" for utt in clean_utts])
                )

        memory_bullets = "\n".join([
            f"- [{m.get('category', 'general')}] {m.get('title', '')}: {m.get('description', '')}"
            for m in relevant_memories
        ])
        if memory_bullets:
            ground_truth_context_parts.append(f"[EPISODIC RELATIONSHIP MEMORIES]:\n{memory_bullets}")

        gt_block = "\n\n".join(ground_truth_context_parts)
        if gt_block:
            current_prompt = f"{gt_block}\n\nManoj: {user_message}\nSakthi:"
        else:
            current_prompt = f"Manoj: {user_message}\nSakthi:"

        return {
            "time_ctx": time_ctx,
            "detected_emotion": query_emotion,
            "emotion_confidence": emotion_conf,
            "retrieved_memories": relevant_memories,
            "rag_highlights": rag_highlights,
            "historical_reactions": historical_reactions,
            "partner_utterances": partner_utterances,
            "system_instruction": system_instruction,
            "ground_truth_block": gt_block,
            "current_prompt": current_prompt,
        }

    # -------------------------------------------------------------------------
    # NODE 2: GENERATE RESPONSE
    # -------------------------------------------------------------------------
    def _node_generate_response(self, state: ConversationState) -> Dict[str, Any]:
        """
        Executes generation via multi-provider cascade (Gemini -> Groq -> Local Fallback).
        Assembles full token list and output text.
        """
        user_message = state.get("user_message", "")
        system_instruction = state.get("system_instruction", "")
        current_prompt = state.get("current_prompt", user_message)
        session_history = state.get("session_history", [])
        time_ctx = state.get("time_ctx", {})

        trimmed_history = session_history[-4:] if session_history else []
        norm_key = user_message.strip().lower()

        # Check in-memory short response cache
        now = time.time()
        if len(norm_key) <= 3 and norm_key in self.orchestrator._response_cache:
            cached_tokens, timestamp = self.orchestrator._response_cache[norm_key]
            if now - timestamp < self.orchestrator._cache_ttl_seconds:
                full_text = "".join(cached_tokens)
                return {
                    "response_tokens": cached_tokens,
                    "full_response": full_text,
                    "generation_provider": "cache",
                }

        # 1. Try Gemini
        if self.orchestrator.client:
            models = [
                self.orchestrator.chat_model,
                "gemini-3.5-flash-lite",
                "gemini-3.5-flash"
            ]
            for m_name in models:
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
                        parts=[types.Part.from_text(text=current_prompt)]
                    ))

                    config = types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        max_output_tokens=90,
                        temperature=0.75,
                    )
                    res = self.orchestrator.client.models.generate_content(
                        model=m_name,
                        contents=contents,
                        config=config
                    )
                    res_text = res.text.replace("\u202f", " ").strip() if res.text else ""
                    if res_text.startswith("Sakthi:") or res_text.startswith("Companion:"):
                        res_text = res_text.split(":", 1)[1].strip()
                    if res_text:
                        tokens = [res_text]
                        return {
                            "response_tokens": tokens,
                            "full_response": res_text,
                            "generation_provider": f"gemini:{m_name}",
                        }
                except Exception as err:
                    logger.warning(f"Gemini generation error with {m_name}: {err}")

        # 2. Try Groq (synchronous bridge)
        if self.orchestrator.groq_key:
            try:
                from groq import Groq
                sync_groq = Groq(api_key=self.orchestrator.groq_key)
                groq_models = ["qwen/qwen3.8-27b", self.orchestrator.groq_model, "allam-2-7b"]
                groq_messages = [{"role": "system", "content": system_instruction}]
                for turn in trimmed_history:
                    r = "user" if turn["role"] == "user" else "assistant"
                    groq_messages.append({"role": r, "content": turn["content"]})
                groq_messages.append({"role": "user", "content": current_prompt})

                for g_model in groq_models:
                    try:
                        completion = sync_groq.chat.completions.create(
                            model=g_model,
                            messages=groq_messages,
                            max_tokens=90,
                            temperature=0.75
                        )
                        c_text = completion.choices[0].message.content or ""
                        c_text = c_text.replace("\u202f", " ").strip()
                        if c_text.startswith("Sakthi:") or c_text.startswith("Companion:"):
                            c_text = c_text.split(":", 1)[1].strip()
                        if c_text:
                            return {
                                "response_tokens": [c_text],
                                "full_response": c_text,
                                "generation_provider": f"groq:{g_model}",
                            }
                    except Exception as g_err:
                        logger.warning(f"Groq {g_model} failed: {g_err}")
            except Exception as e:
                logger.warning(f"Groq sync client error: {e}")

        # 3. Dynamic Fallback
        fallback_tokens = self.orchestrator._generate_dynamic_fallback(user_message, time_ctx)
        sanitized = [sanitizer.sanitize_text(t) for t in fallback_tokens]
        full_text = "".join(sanitized)
        return {
            "response_tokens": sanitized,
            "full_response": full_text,
            "generation_provider": "local_fallback",
        }

    # -------------------------------------------------------------------------
    # NODE 3: SELF-LEARN MEMORY (CONTINUAL TRAINING LOOP)
    # -------------------------------------------------------------------------
    def _node_self_learn_memory(self, state: ConversationState) -> Dict[str, Any]:
        """
        Continual Learning Engine: Analyzes each conversation turn, extracts newly
        disclosed facts/preferences/emotional updates, deduplicates against existing
        memories, and updates relationship_memories.jsonl, runtime memory lists,
        MemoryResolver, and Vector Index.
        """
        user_message = state.get("user_message", "").strip()
        full_response = state.get("full_response", "").strip()
        session_id = state.get("session_id", "live_session")
        user_id = state.get("user_id", "user_default")

        # Skip trivial or empty exchanges
        if len(user_message) < 4:
            return {
                "extracted_memories": [],
                "learned_memory_count": 0,
                "memory_update_status": "skipped_trivial",
            }

        trivial_words = {"hi", "hello", "hey", "vanakkam", "ok", "k", "hmm", "haan", "bye", "seri", "dei", "loosu"}
        if user_message.lower().strip() in trivial_words:
            return {
                "extracted_memories": [],
                "learned_memory_count": 0,
                "memory_update_status": "skipped_trivial",
            }

        # Step 1: Detect candidate memory
        candidate_memory = self._extract_memory_candidate(user_message, full_response)
        if not candidate_memory:
            return {
                "extracted_memories": [],
                "learned_memory_count": 0,
                "memory_update_status": "no_new_facts",
            }

        # Step 2: Deduplication against existing memories
        is_duplicate = self._is_duplicate_memory(candidate_memory)
        if is_duplicate:
            logger.info(f"Skipping duplicate memory: {candidate_memory.get('title')}")
            return {
                "extracted_memories": [],
                "learned_memory_count": 0,
                "memory_update_status": "skipped_duplicate",
            }

        # Step 3: Package full memory record
        new_memory: Dict[str, Any] = {
            "memory_id": str(uuid4()),
            "category": candidate_memory.get("category", "daily_life"),
            "title": candidate_memory.get("title", "Learned Conversational Detail"),
            "description": candidate_memory.get("description", user_message),
            "event_date": candidate_memory.get("event_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "is_fact": True,
            "fact_type": "continual_learning",
            "provenance": "conversation_learning",
            "do_not_present_as_fact": False,
            "source_message_ids": [f"turn:{session_id}:{int(time.time())}"],
            "confidence": round(float(candidate_memory.get("confidence", 0.88)), 2),
            "verification_status": "approved",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "owner_id": user_id,
        }

        # Step 4: Persist to storage & update active stores
        self._commit_learned_memory(new_memory)

        return {
            "extracted_memories": [new_memory],
            "learned_memory_count": 1,
            "memory_update_status": "stored_successfully",
        }

    def _extract_memory_candidate(self, user_message: str, response_text: str) -> Optional[Dict[str, Any]]:
        """
        Hybrid extraction: attempts lightweight LLM structured extraction, falling
        back to high-precision Tanglish pattern extraction.
        """
        # Approach A: LLM structured extraction if Groq or Gemini is available
        llm_candidate = self._extract_via_llm(user_message, response_text)
        if llm_candidate:
            return llm_candidate

        # Approach B: Pattern-based heuristic extraction
        return self._extract_via_patterns(user_message)

    def _extract_via_llm(self, user_message: str, response_text: str) -> Optional[Dict[str, Any]]:
        """Extracts structured memory via fast model call."""
        prompt = (
            "You are an expert conversational memory extractor for a personal relationship AI assistant.\n"
            "Analyze this single dialogue turn:\n"
            f"User (Manoj): \"{user_message}\"\n"
            f"Companion (Sakthi): \"{response_text}\"\n\n"
            "Task: Determine if Manoj shared any NEW personal fact, preference, schedule/event, emotional disclosure, "
            "dietary habit, or personal life update that should be remembered.\n"
            "Ignore trivial greetings ('hi', 'how are you', 'hmm'), generic teasing, or single-word banter.\n"
            "If a meaningful fact/preference exists, output JSON only:\n"
            "{\n"
            '  "has_memory": true,\n'
            '  "category": "user_preferences" | "daily_life" | "shared_moments" | "emotional_milestones" | "affection_patterns",\n'
            '  "title": "Clear concise title (3-6 words)",\n'
            '  "description": "Specific detail of what Manoj or Sakthi shared",\n'
            '  "confidence": 0.85\n'
            "}\n"
            "If no meaningful fact was shared, output: {\"has_memory\": false}"
        )

        # 1. Try Groq for super-fast (<300ms) extraction
        if self.orchestrator.groq_key:
            try:
                from groq import Groq
                sync_groq = Groq(api_key=self.orchestrator.groq_key)
                res = sync_groq.chat.completions.create(
                    model="qwen/qwen3.8-27b",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=150,
                    response_format={"type": "json_object"}
                )
                raw = res.choices[0].message.content or "{}"
                data = json.loads(raw)
                if data.get("has_memory") and data.get("title") and data.get("description"):
                    return data
            except Exception as e:
                logger.debug(f"LLM memory extraction via Groq skipped: {e}")

        # 2. Try Gemini
        if self.orchestrator.client:
            try:
                from google.genai import types
                res = self.orchestrator.client.models.generate_content(
                    model="gemini-3.5-flash-lite",
                    contents=[prompt],
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=150,
                        response_mime_type="application/json"
                    )
                )
                if res.text:
                    data = json.loads(res.text)
                    if data.get("has_memory") and data.get("title") and data.get("description"):
                        return data
            except Exception as e:
                logger.debug(f"LLM memory extraction via Gemini skipped: {e}")

        return None

    def _extract_via_patterns(self, user_message: str) -> Optional[Dict[str, Any]]:
        """
        Pattern-based Tanglish conversational fact extractor.
        Captures food, routines, emotional disclosures, gifts, and preferences.
        """
        text = user_message.lower().strip()

        # Food & Meals: "naan ... saapten", "dinner ...", "lunch ..."
        food_match = re.search(r"(?:naan|naanum)?\s*(.*?)\s*(?:saapten|sapten|eaten|saapada poren)", text)
        if food_match and len(food_match.group(1).strip()) > 2:
            food_item = food_match.group(1).strip()
            if not any(f in food_item for f in ["ippo", "adhan", "onnum", "kooda"]):
                return {
                    "category": "user_preferences",
                    "title": f"Meal Update: {food_item.title()}",
                    "description": f"Manoj shared that he ate or is having {food_item}.",
                    "confidence": 0.88,
                }

        # Likes & Preferences: "enakku ... pudikkum", "i love ...", "favorite ..."
        like_match = re.search(r"(?:enakku|enaku)\s+(.*?)\s+(?:romba\s+)?(?:pudikkum|pidikkum|fav|favorite)", text)
        if like_match and len(like_match.group(1).strip()) > 2:
            item = like_match.group(1).strip()
            return {
                "category": "user_preferences",
                "title": f"Preference: Likes {item.title()}",
                "description": f"Manoj expressed a personal preference for {item}.",
                "confidence": 0.90,
            }

        # Dislikes: "enakku ... pudikadhu", "pidikadhu", "don't like"
        dislike_match = re.search(r"(?:enakku|enaku)\s+(.*?)\s+(?:pudikadhu|pidikadhu|pudikaadhu)", text)
        if dislike_match and len(dislike_match.group(1).strip()) > 2:
            item = dislike_match.group(1).strip()
            return {
                "category": "user_preferences",
                "title": f"Dislike: Dislikes {item.title()}",
                "description": f"Manoj expressed that he dislikes {item}.",
                "confidence": 0.90,
            }

        # Daily Routine / Life Updates: "office poren", "college poren", "gym", "exam irukku"
        if any(w in text for w in ["exam", "test", "semester", "padikka"]):
            return {
                "category": "daily_life",
                "title": "Academic / Exam Schedule",
                "description": f"Manoj discussed upcoming exams, tests, or studying: '{user_message}'.",
                "confidence": 0.86,
            }

        if any(w in text for w in ["gym", "workout", "exercise"]):
            return {
                "category": "daily_life",
                "title": "Fitness Routine Update",
                "description": f"Manoj mentioned working out or going to the gym: '{user_message}'.",
                "confidence": 0.88,
            }

        if any(w in text for w in ["trip", "travel", "tour", "poren", "kelamburen"]) and len(text) > 10:
            return {
                "category": "daily_life",
                "title": "Travel & Plans Update",
                "description": f"Manoj mentioned travel or leaving for a place: '{user_message}'.",
                "confidence": 0.85,
            }

        # Emotional Milestones & Affection
        if any(w in text for w in ["miss you", "miss u", "romba miss", "love you", "love u"]):
            return {
                "category": "affection_patterns",
                "title": "Mutual Affection & Missing",
                "description": f"Manoj expressed missing and affection: '{user_message}'.",
                "confidence": 0.89,
            }

        if any(w in text for w in ["tired", "headache", "dizzy", "udambu mudiyala", "fever"]):
            return {
                "category": "daily_life",
                "title": "Health & Wellbeing Update",
                "description": f"Manoj shared that he is physically tired or unwell: '{user_message}'.",
                "confidence": 0.91,
            }

        return None

    def _is_duplicate_memory(self, candidate: Dict[str, Any]) -> bool:
        """
        Deduplicates against existing memories using title and description token similarity.
        """
        all_memories = self.orchestrator.memories
        if not all_memories and self.resolver:
            all_memories = list(self.resolver.memories_by_id.values())

        if not all_memories:
            return False

        c_title = candidate.get("title", "").lower().strip()
        c_desc = candidate.get("description", "").lower().strip()
        c_words = set(re.findall(r"\w+", f"{c_title} {c_desc}"))
        if not c_words:
            return True

        stopwords = {
            "the", "that", "this", "and", "is", "a", "an", "manoj", "sakthi", "shared",
            "expressed", "he", "she", "really", "from", "with", "user", "companion",
            "detail", "update", "routine", "mentioned"
        }
        c_key = {w for w in c_words if w not in stopwords and len(w) > 2}

        for m in all_memories:
            m_title = m.get("title", "").lower().strip()
            m_desc = m.get("description", "").lower().strip()
            m_words = set(re.findall(r"\w+", f"{m_title} {m_desc}"))
            if not m_words:
                continue

            # Exact title match
            if c_title and c_title == m_title:
                return True

            # Jaccard overlap
            intersection = len(c_words.intersection(m_words))
            union = len(c_words.union(m_words))
            jaccard = intersection / max(union, 1)

            if jaccard >= 0.45:
                return True

            # Content keyword overlap (captures rephrased memories about the same entities)
            if c_key:
                m_key = {w for w in m_words if w not in stopwords and len(w) > 2}
                if m_key:
                    overlap_ratio = len(c_key.intersection(m_key)) / max(min(len(c_key), len(m_key)), 1)
                    if overlap_ratio >= 0.50:
                        return True

        return False

    def _commit_learned_memory(self, new_memory: Dict[str, Any]) -> None:
        """
        Persists the newly learned memory across all levels:
        1. Appends to data/processed/relationship_memories.jsonl
        2. Appends to active chat_orchestrator in-memory list
        3. Registers in MemoryResolver
        4. Indexes into Qdrant MemoryIndexer (if connected)
        """
        # 1. Disk persistence
        if self.memories_file:
            try:
                with open(self.memories_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(new_memory, ensure_ascii=False) + "\n")
                logger.info(f"Learned memory saved to disk: {new_memory.get('title')}")
            except Exception as e:
                logger.error(f"Failed to persist learned memory to disk: {e}")

        # 2. Update orchestrator in-memory cache
        try:
            self.orchestrator.memories.append(new_memory)
        except Exception as e:
            logger.warning(f"Could not append to orchestrator memories: {e}")

        # 3. Update memory resolver
        if self.resolver:
            try:
                self.resolver.memories_by_id[new_memory["memory_id"]] = new_memory
            except Exception as e:
                logger.warning(f"Could not update memory resolver: {e}")

        # 4. Update Qdrant vector index
        if self.indexer:
            try:
                self.indexer.index_memories([new_memory])
            except Exception as e:
                logger.debug(f"Qdrant indexer skipped for new memory: {e}")

    # -------------------------------------------------------------------------
    # PUBLIC HIGH-LEVEL INVOCATION APIS
    # -------------------------------------------------------------------------
    def run_turn(
        self,
        user_message: str,
        session_history: Optional[List[Dict[str, str]]] = None,
        session_id: str = "default_session",
        user_id: str = "user_default",
        mock_time_str: Optional[str] = None
    ) -> ConversationState:
        """
        Executes a complete, synchronous conversational turn through the compiled LangGraph.
        """
        initial_state: ConversationState = {
            "session_id": session_id,
            "user_id": user_id,
            "user_message": user_message,
            "session_history": session_history or [],
            "mock_time_str": mock_time_str,
            "response_tokens": [],
            "full_response": "",
            "extracted_memories": [],
            "learned_memory_count": 0,
        }
        return self.app.invoke(initial_state)

    async def stream_conversation_turn(
        self,
        user_message: str,
        session_history: Optional[List[Dict[str, str]]] = None,
        session_id: str = "default_session",
        user_id: str = "user_default",
        mock_time_str: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Production Streaming SSE Generator integrating LangGraph Context Enrichment,
        Real-Time Token Streaming, and Post-Turn Self-Learning Memory Updates.
        """
        initial_state: ConversationState = {
            "session_id": session_id,
            "user_id": user_id,
            "user_message": user_message,
            "session_history": session_history or [],
            "mock_time_str": mock_time_str,
            "response_tokens": [],
            "full_response": "",
            "extracted_memories": [],
            "learned_memory_count": 0,
        }

        # Step 1: Run Node 1 (Enrich Context)
        enriched_state = self._node_enrich_context(initial_state)
        merged_state: ConversationState = {**initial_state, **enriched_state}

        # Emit Metadata event
        yield {
            "event": "metadata",
            "data": {
                "retrieved_memories": merged_state.get("rag_highlights", []),
                "time_slot": merged_state.get("time_ctx", {}).get("slot_id"),
                "time_name": merged_state.get("time_ctx", {}).get("slot_name"),
                "current_time_ist": merged_state.get("time_ctx", {}).get("current_time_ist"),
                "detected_emotion": merged_state.get("detected_emotion"),
                "persona_version": self.orchestrator.personality_profile.get("version", "2.0.0"),
                "workflow_engine": "langgraph-2.0",
                "disclaimer": "HerAI is an AI-generated companion simulation."
            }
        }

        # Step 2: Stream Token Generation
        collected_tokens = []
        try:
            async for token_event in self.orchestrator.stream_response(
                user_message,
                session_history or [],
                mock_time_str=mock_time_str
            ):
                if token_event.get("event") == "token":
                    t = token_event.get("data", {}).get("text", "")
                    if t:
                        collected_tokens.append(t)
                        yield token_event
                elif token_event.get("event") == "end":
                    pass  # We will yield final end event after continual learning
        except Exception as e:
            logger.error(f"Error streaming tokens: {e}")
            yield {
                "event": "error",
                "data": {"detail": "Token generation interrupted"}
            }

        full_reply = "".join(collected_tokens)
        merged_state["response_tokens"] = collected_tokens
        merged_state["full_response"] = full_reply

        # Step 3: Run Node 3 (Continual Learning & Memory Update)
        try:
            learn_results = self._node_self_learn_memory(merged_state)
            extracted = learn_results.get("extracted_memories", [])
            for m in extracted:
                yield {
                    "event": "memory_learned",
                    "data": {
                        "memory": {
                            "memory_id": m.get("memory_id"),
                            "category": m.get("category"),
                            "title": m.get("title"),
                            "description": m.get("description"),
                            "confidence": m.get("confidence"),
                        }
                    }
                }
        except Exception as learn_err:
            logger.warning(f"Self-learning memory update encountered an error: {learn_err}")
            learn_results = {"learned_memory_count": 0}

        # Step 4: Emit Final Completion
        yield {
            "event": "end",
            "data": {
                "status": "completed",
                "tokens_generated": len(collected_tokens),
                "learned_memories": learn_results.get("learned_memory_count", 0),
            }
        }
