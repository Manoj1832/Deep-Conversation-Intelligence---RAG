from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

class MemoryResolver:
    """
    Handles memory versioning, correction, and updates.
    Maintains provenance and prevents destructive overrides.
    """

    def __init__(self, memories: List[Dict[str, Any]]):
        # memory_id -> memory_dict
        self.memories_by_id = {m["memory_id"]: m for m in memories}
        self.history: List[Dict[str, Any]] = []

    def update_memory(self, memory_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if memory_id not in self.memories_by_id:
            return None

        current = self.memories_by_id[memory_id]
        # Record audit snapshot before update
        self.history.append({
            "action": "update",
            "memory_id": memory_id,
            "previous_state": dict(current),
            "updated_at": datetime.now(timezone.utc).isoformat()
        })

        allowed_fields = {"title", "description", "event_date", "confidence", "verification_status"}
        for k, v in updates.items():
            if k in allowed_fields:
                current[k] = v

        current["updated_at"] = datetime.now(timezone.utc).isoformat()
        return current

    def delete_memory(self, memory_id: str) -> bool:
        if memory_id not in self.memories_by_id:
            return False

        current = self.memories_by_id.pop(memory_id)
        self.history.append({
            "action": "delete",
            "memory_id": memory_id,
            "deleted_state": current,
            "deleted_at": datetime.now(timezone.utc).isoformat()
        })
        return True

    def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        return self.memories_by_id.get(memory_id)

    def list_memories(self, category: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        res = list(self.memories_by_id.values())
        if category:
            res = [m for m in res if m.get("category") == category]
        if status:
            res = [m for m in res if m.get("verification_status") == status]
        return res
