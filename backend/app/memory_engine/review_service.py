from typing import Dict, Any, Optional
from datetime import datetime, timezone
from backend.app.memory_engine.resolver import MemoryResolver

class MemoryReviewService:
    """
    Manages human review workflow for relationship memories.
    Transitions states between 'pending_review', 'approved', and 'rejected'.
    """

    def __init__(self, resolver: MemoryResolver):
        self.resolver = resolver
        self.review_logs = []

    def approve_memory(self, memory_id: str, reviewer: str = "user") -> Optional[Dict[str, Any]]:
        mem = self.resolver.get_memory(memory_id)
        if not mem:
            return None

        mem["verification_status"] = "approved"
        mem["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.review_logs.append({
            "memory_id": memory_id,
            "action": "approved",
            "reviewer": reviewer,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        return mem

    def reject_memory(self, memory_id: str, reason: str = "", reviewer: str = "user") -> Optional[Dict[str, Any]]:
        mem = self.resolver.get_memory(memory_id)
        if not mem:
            return None

        mem["verification_status"] = "rejected"
        mem["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.review_logs.append({
            "memory_id": memory_id,
            "action": "rejected",
            "reason": reason,
            "reviewer": reviewer,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        return mem
