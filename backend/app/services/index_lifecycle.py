"""
Data Lifecycle & Zero-Downtime Indexing Manager for HerAI.
Provides seamless, uninterrupted RAG indexing with zero request downtime.

Features:
- Atomic pointer swapping: active index is never locked or blocked during rebuilds.
- Background asynchronous or synchronous index rebuilding.
- Automatic health verification & warm-up query before activating new index version.
- Persistent index metadata registry (versioning, document counts, latency benchmarks).
"""

import threading
import time
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from backend.app.services.bm25_retriever import BM25ConversationRetriever
from backend.app.services.time_context import IST


class IndexLifecycleManager:
    """
    Manages the lifecycle and zero-downtime updates of conversational retrieval indexes.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(IndexLifecycleManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, processed_dir: Optional[Path] = None):
        if getattr(self, "_initialized", False):
            return

        self.processed_dir = processed_dir or Path("data/processed")
        self.metadata_file = self.processed_dir / "index_metadata.json"

        self._version = 1
        self._status = "INITIALIZING"
        self._last_reindex_timestamp = None
        self._reindex_lock = threading.Lock()
        
        # Load or initialize the active retriever
        self._active_retriever = BM25ConversationRetriever(self.processed_dir)
        self._load_or_create_metadata()
        self._status = "READY"
        self._initialized = True

    def get_active_retriever(self) -> BM25ConversationRetriever:
        """
        Thread-safe instant access to the active retriever without blocking.
        """
        return self._active_retriever

    def _load_or_create_metadata(self):
        """Loads version metadata or writes default if missing."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    self._version = meta.get("version_number", 1)
                    self._last_reindex_timestamp = meta.get("last_reindexed_at")
                    return
            except Exception:
                pass

        self._record_metadata(version=1, build_time_ms=0.0)

    def _record_metadata(self, version: int, build_time_ms: float):
        self._version = version
        self._last_reindex_timestamp = datetime.now(IST).isoformat()
        
        interaction_count = len(self._active_retriever.interactions)
        utterance_count = len(self._active_retriever.partner_utterances)

        meta = {
            "version": f"v1.{version}.0",
            "version_number": version,
            "last_reindexed_at": self._last_reindex_timestamp,
            "total_interactions_indexed": interaction_count,
            "total_partner_utterances_indexed": utterance_count,
            "build_duration_ms": round(build_time_ms, 2),
            "status": "HEALTHY"
        }

        try:
            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
        except Exception as e:
            print(f"[!] Warning writing index metadata: {e}")

    def reindex_sync(self) -> Dict[str, Any]:
        """
        Rebuilds index in background shadow buffer, runs warm-up query,
        and atomically swaps the active pointer with zero downtime.
        """
        with self._reindex_lock:
            self._status = "REINDEXING"
            start_t = time.perf_counter()

            # 1. Build new index in isolated instance (shadow index)
            new_retriever = BM25ConversationRetriever(self.processed_dir)

            # 2. Run warm-up verification query to ensure index is healthy
            warmup_res = new_retriever.retrieve_historical_reactions("saptya da?", top_k=2)
            if not warmup_res and len(new_retriever.interactions) > 0:
                self._status = "READY"
                raise RuntimeError("Index validation check failed on warm-up query.")

            build_time_ms = (time.perf_counter() - start_t) * 1000.0

            # 3. ATOMIC SWAP: Replace the active pointer instantaneously
            self._active_retriever = new_retriever
            self._version += 1
            self._record_metadata(self._version, build_time_ms)
            self._status = "READY"

            return {
                "success": True,
                "version": f"v1.{self._version}.0",
                "interactions_indexed": len(new_retriever.interactions),
                "utterances_indexed": len(new_retriever.partner_utterances),
                "build_time_ms": round(build_time_ms, 2),
                "warmup_sample_found": len(warmup_res) > 0
            }

    def trigger_reindex_async(self):
        """Launches zero-downtime index rebuild in a non-blocking background thread."""
        worker = threading.Thread(target=self.reindex_sync, daemon=True)
        worker.start()

    def get_status(self) -> Dict[str, Any]:
        """Returns health and status report of the indexing engine."""
        return {
            "status": self._status,
            "current_version": f"v1.{self._version}.0",
            "last_reindexed_at": self._last_reindex_timestamp,
            "active_interactions_count": len(self._active_retriever.interactions),
            "active_utterances_count": len(self._active_retriever.partner_utterances)
        }
