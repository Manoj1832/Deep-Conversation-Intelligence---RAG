from typing import List, Dict, Any, Optional
import os
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

class MemoryIndexer:
    """
    Qdrant vector indexer for relationship memories.
    Indexes only memories eligible for retrieval (verification_status == 'approved').
    Deletes removed memories from Qdrant index.
    Includes automatic fallback to local memory store if cluster connection fails.
    """

    COLLECTION_NAME = "herai_memories"
    VECTOR_DIM = 768

    def __init__(self, qdrant_url: Optional[str] = None, api_key: Optional[str] = None):
        self.url = qdrant_url or os.getenv("QDRANT_URL")
        self.api_key = api_key or os.getenv("QDRANT_API_KEY")

        if self.url and self.api_key:
            try:
                self.client = QdrantClient(url=self.url, api_key=self.api_key, timeout=5.0, check_compatibility=False)
                self._ensure_collection(raise_on_error=True)
            except Exception as e:
                print(f"[!] Qdrant connection error: {e}. Switching to in-memory fallback store.")
                self.client = QdrantClient(":memory:")
                self._ensure_collection(raise_on_error=False)
        else:
            self.client = QdrantClient(":memory:")
            self._ensure_collection(raise_on_error=False)

    def _ensure_collection(self, raise_on_error: bool = False):
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == self.COLLECTION_NAME for c in collections)
            if not exists:
                self.client.create_collection(
                    collection_name=self.COLLECTION_NAME,
                    vectors_config=VectorParams(size=self.VECTOR_DIM, distance=Distance.COSINE)
                )
        except Exception as e:
            if raise_on_error:
                raise e
            print(f"[!] Collection init warning: {e}")

    def index_approved_memories(self, memories: List[Dict[str, Any]]) -> int:
        approved = [m for m in memories if m.get("verification_status") == "approved"]
        if not approved:
            return 0

        points = []
        for i, m in enumerate(approved):
            vec = [(hash(f"{m['title']}_{j}") % 1000) / 1000.0 for j in range(self.VECTOR_DIM)]
            point = PointStruct(
                id=m["memory_id"],
                vector=vec,
                payload={
                    "memory_id": m["memory_id"],
                    "owner_id": m.get("owner_id", "user_default"),
                    "category": m["category"],
                    "title": m["title"],
                    "description": m["description"],
                    "confidence": m["confidence"],
                    "event_date": m.get("event_date")
                }
            )
            points.append(point)

        try:
            self.client.upsert(collection_name=self.COLLECTION_NAME, points=points)
        except Exception as e:
            print(f"[!] Error upserting to remote Qdrant: {e}. Falling back to in-memory store.")
            self.client = QdrantClient(":memory:")
            self._ensure_collection(raise_on_error=False)
            self.client.upsert(collection_name=self.COLLECTION_NAME, points=points)

        return len(points)

    def delete_from_index(self, memory_id: str) -> None:
        try:
            self.client.delete(
                collection_name=self.COLLECTION_NAME,
                points_selector=[memory_id]
            )
        except Exception as e:
            print(f"[!] Failed to delete vector point {memory_id}: {e}")
