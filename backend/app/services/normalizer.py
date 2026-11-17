from typing import Dict, Tuple, Optional, Set
from backend.app.config import config

class SenderNormalizer:
    """
    Explicit sender normalizer for HerAI.
    Normalizes known participant identities into 'partner' and 'user'.
    Flags and reports unknown senders; never silently assigns unknown senders.
    """

    def __init__(self, mapping: Optional[Dict[str, str]] = None):
        self.mapping = mapping or config.sender_mapping
        self.unknown_senders: Set[str] = set()

    def normalize(self, raw_sender: str, is_system: bool = False) -> Tuple[str, bool]:
        """
        Returns (normalized_sender, is_known)
        """
        # Exact match
        if raw_sender in self.mapping:
            return self.mapping[raw_sender], True

        # Check clean representation (strip LRM, spaces, zero-width joiners)
        clean_sender = raw_sender.replace('\u200e', '').strip()
        if clean_sender in self.mapping:
            return self.mapping[clean_sender], True

        if is_system:
            return "system", True

        # Unknown sender
        self.unknown_senders.add(raw_sender)
        return raw_sender, False

    def get_unknown_senders(self) -> Set[str]:
        return self.unknown_senders
