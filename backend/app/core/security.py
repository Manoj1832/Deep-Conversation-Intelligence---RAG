import os
import re
from typing import Optional, Dict, Any


class SensitiveDataVault:
    """
    Object-Oriented Encapsulation for Sensitive Credentials & Secrets.
    
    Adheres to OOP Principles:
    - Encapsulation: Sensitive keys stored in private dunder attributes (__secret_key, etc.)
    - Data Hiding: Cannot be accessed without managed properties
    - Masking: __repr__ and __str__ explicitly scrub and mask credentials to prevent
      accidental exposure in logs, terminal outputs, error traces, or API serializations.
    """
    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        groq_api_key: Optional[str] = None,
        jwt_secret_key: Optional[str] = None,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        qdrant_url: Optional[str] = None,
        qdrant_api_key: Optional[str] = None
    ):
        self.__gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        self.__groq_api_key = groq_api_key or os.getenv("GROQ_API_KEY", "")
        self.__jwt_secret_key = jwt_secret_key or os.getenv("JWT_SECRET_KEY", "herai-super-secret-production-key-2026")
        self.__supabase_url = supabase_url or os.getenv("SUPABASE_URL", "")
        self.__supabase_key = supabase_key or os.getenv("SUPABASE_KEY", "")
        self.__qdrant_url = qdrant_url or os.getenv("QDRANT_URL", "")
        self.__qdrant_api_key = qdrant_api_key or os.getenv("QDRANT_API_KEY", "")

    # Property Getters (Encapsulation)
    @property
    def gemini_api_key(self) -> str:
        return self.__gemini_api_key

    @property
    def groq_api_key(self) -> str:
        return self.__groq_api_key

    @property
    def jwt_secret_key(self) -> str:
        return self.__jwt_secret_key

    @property
    def supabase_url(self) -> str:
        return self.__supabase_url

    @property
    def supabase_key(self) -> str:
        return self.__supabase_key

    @property
    def qdrant_url(self) -> str:
        return self.__qdrant_url

    @property
    def qdrant_api_key(self) -> str:
        return self.__qdrant_api_key

    @staticmethod
    def _mask_value(val: str, visible_chars: int = 4) -> str:
        if not val:
            return "[NOT SET]"
        if len(val) <= visible_chars * 2:
            return "********"
        return f"{val[:visible_chars]}...{val[-visible_chars:]}"

    def __repr__(self) -> str:
        return (
            f"<SensitiveDataVault "
            f"gemini_api_key={self._mask_value(self.__gemini_api_key)} "
            f"groq_api_key={self._mask_value(self.__groq_api_key)} "
            f"jwt_secret_key=******** "
            f"supabase_url={self._mask_value(self.__supabase_url)} "
            f"qdrant_url={self._mask_value(self.__qdrant_url)}>"
        )

    def __str__(self) -> str:
        return self.__repr__()


class DataSanitizer:
    """
    Object-Oriented PII Sanitizer & Masker.
    Protects private phone numbers, raw file paths, email addresses, and auth tokens.
    """
    # Regex patterns for Indian/international phone numbers, emails, and sensitive paths
    PHONE_REGEX = re.compile(r'(\+?91[\s\-]?)?[6-9]\d{9}')
    EMAIL_REGEX = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
    FILE_PATH_REGEX = re.compile(r'(/home/[^/\s]+|C:\\[^\\\s]+)')
    BEARER_REGEX = re.compile(r'Bearer\s+[A-Za-z0-9\-._~+/]+=*', re.IGNORECASE)

    @classmethod
    def sanitize_text(cls, text: str) -> str:
        if not text or not isinstance(text, str):
            return text
        sanitized = cls.PHONE_REGEX.sub("[PHONE_REDACTED]", text)
        sanitized = cls.EMAIL_REGEX.sub("[EMAIL_REDACTED]", sanitized)
        sanitized = cls.BEARER_REGEX.sub("Bearer [TOKEN_REDACTED]", sanitized)
        sanitized = cls.FILE_PATH_REGEX.sub("[SYSTEM_PATH]", sanitized)
        return sanitized

    @classmethod
    def sanitize_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Deeply traverses dictionary and cleans sensitive values."""
        clean = {}
        for k, v in data.items():
            if isinstance(v, str):
                clean[k] = cls.sanitize_text(v)
            elif isinstance(v, dict):
                clean[k] = cls.sanitize_dict(v)
            elif isinstance(v, list):
                clean[k] = [
                    cls.sanitize_dict(item) if isinstance(item, dict)
                    else (cls.sanitize_text(item) if isinstance(item, str) else item)
                    for item in v
                ]
            else:
                clean[k] = v
        return clean


# Global singleton instance for application use
vault = SensitiveDataVault()
sanitizer = DataSanitizer()
