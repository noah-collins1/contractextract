"""
Centralized settings module for ContractExtract.
Single source of truth for all configuration values.
"""

import os
from typing import Optional
from decimal import Decimal

class ContractExtractSettings:
    """Centralized configuration for ContractExtract system."""

    # Database Configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:1219@localhost:5432/contractextract")

    # LLM Configuration - NOW ALWAYS ENABLED BY DEFAULT
    LLM_EXPLANATIONS_ENABLED: bool = True  # Default: always on
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")
    LLM_MAX_TOKENS_PER_RUN: int = int(os.getenv("LLM_MAX_TOKENS_PER_RUN", "10000"))
    LLM_TIMEOUT_SECONDS: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
    LLM_MAX_EXPLANATIONS: int = int(os.getenv("LLM_MAX_EXPLANATIONS", "5"))

    # Document Processing Configuration
    CE_MAX_CHAR_BUFFER: int = int(os.getenv("CE_MAX_CHAR_BUFFER", "1500"))
    CE_MAX_WORKERS_EXTRACT: int = int(os.getenv("CE_MAX_WORKERS_EXTRACT", "1"))
    CE_CHUNK_TARGET: int = int(os.getenv("CE_CHUNK_TARGET", "9000"))
    CE_MAX_WORKERS: int = int(os.getenv("CE_MAX_WORKERS", "1"))

    # Document Type Detection Configuration
    DOC_TYPE_CONFIDENCE_THRESHOLD: float = float(os.getenv("DOC_TYPE_CONFIDENCE_THRESHOLD", "0.65"))
    DOC_TYPE_USE_LLM_FALLBACK: bool = os.getenv("DOC_TYPE_USE_LLM_FALLBACK", "true").lower() in ("1", "true", "yes", "on")

    # Citation Configuration
    CITATION_CONTEXT_CHARS: int = int(os.getenv("CITATION_CONTEXT_CHARS", "300"))
    CITATION_MAX_QUOTE_LENGTH: int = int(os.getenv("CITATION_MAX_QUOTE_LENGTH", "420"))

    # API Configuration
    API_ENABLE_TIMING_LOGS: bool = os.getenv("API_ENABLE_TIMING_LOGS", "true").lower() in ("1", "true", "yes", "on")

    # Legacy Bridge Configuration
    USE_V1_BRIDGE: bool = os.getenv("USE_V1_BRIDGE", "0") == "1"

    @classmethod
    def get_llm_enabled(cls, override: Optional[bool] = None) -> bool:
        """
        Get LLM explanation enabled status with optional per-request override.

        Args:
            override: Per-request override. If None, uses default setting.

        Returns:
            bool: Whether LLM explanations should be enabled
        """
        if override is not None:
            return override
        return cls.LLM_EXPLANATIONS_ENABLED

    @classmethod
    def get_llm_budget_remaining(cls, tokens_used: int) -> int:
        """
        Get remaining LLM token budget for current run.

        Args:
            tokens_used: Tokens already consumed in this run

        Returns:
            int: Remaining tokens available (0 if budget exceeded)
        """
        remaining = cls.LLM_MAX_TOKENS_PER_RUN - tokens_used
        return max(0, remaining)

    @classmethod
    def should_use_llm_fallback(cls, confidence_score: float) -> bool:
        """
        Determine if LLM fallback should be used for document type detection.

        Args:
            confidence_score: Rules-based confidence score (0.0-1.0)

        Returns:
            bool: Whether to use LLM fallback
        """
        return (cls.DOC_TYPE_USE_LLM_FALLBACK and
                confidence_score < cls.DOC_TYPE_CONFIDENCE_THRESHOLD)

# Create singleton instance
settings = ContractExtractSettings()