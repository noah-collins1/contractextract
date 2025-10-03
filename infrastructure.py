"""
Consolidated infrastructure module for ContractExtract.
Contains all configuration, database, schema, and telemetry functionality.
"""

import os
import sys
import logging
import warnings
from typing import List, Optional
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from pydantic import BaseModel, Field

# ==================== CONFIGURATION ====================

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

# ==================== DATABASE ====================

# Use settings for database URL
DATABASE_URL = settings.DATABASE_URL

engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)
Base = declarative_base()

def init_db():
    """Initialize database tables. Import models as needed."""
    # Note: Import models in function to avoid circular imports
    try:
        from rulepack_manager import RulePackRecord  # Import from consolidated module
    except ImportError:
        # Legacy import for transition period
        try:
            from models_rulepack import RulePackRecord
        except ImportError:
            pass
    Base.metadata.create_all(bind=engine)

# ==================== SCHEMAS ====================

# ---------- Rule configuration objects ----------
class JurisdictionConfig(BaseModel):
    allowed_countries: List[str] = Field(
        default_factory=lambda: [
            "United States", "US", "USA",
            "Canada",
            "European Union", "EU",
            "Australia", "AUS",
        ]
    )

class LiabilityCapPolicy(BaseModel):
    # Enforce at least one: amount or multiplier (or both). If both provided, both must pass.
    max_cap_amount: Optional[float] = None        # e.g., 1_000_000.00 (in contract currency)
    max_cap_multiplier: Optional[float] = 1.0     # e.g., 1.0 = 1x total contract value

class ContractPolicy(BaseModel):
    # If set, the document's inferred "contract value" must not exceed this
    max_contract_value: Optional[float] = None

class FraudPolicy(BaseModel):
    require_fraud_clause: bool = True
    # Very basic heuristic: fraud liability should be assigned to "other party"
    require_liability_on_other_party: bool = True

class RuleSet(BaseModel):
    name: str = "placeholder_ruleset_v1"
    jurisdiction: JurisdictionConfig = JurisdictionConfig()
    liability_cap: LiabilityCapPolicy = LiabilityCapPolicy()
    contract: ContractPolicy = ContractPolicy()
    fraud: FraudPolicy = FraudPolicy()

# ---------- Findings / Citations ----------
class Citation(BaseModel):
    char_start: int
    char_end: int
    quote: str
    # Page and line information (1-based for UI display)
    page: Optional[int] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    # Confidence level for citation accuracy (1.0 = high confidence)
    confidence: float = 1.0

class Finding(BaseModel):
    # Was Literal[...] — now free-form so any rule pack can emit its own IDs.
    rule_id: str
    passed: bool
    details: str
    citations: List[Citation] = Field(default_factory=list)
    # Optional metadata for future-proofing (not required by current pipeline)
    tags: List[str] = Field(default_factory=list)

class DocumentReport(BaseModel):
    document_name: str
    passed_all: bool
    findings: List[Finding]

# ---------- RulePack / Examples ----------
class ExampleExtraction(BaseModel):
    label: str
    span: str
    attributes: dict = Field(default_factory=dict)

class ExampleItem(BaseModel):
    text: str
    extractions: List[ExampleExtraction] = Field(default_factory=list)

class RulePack(BaseModel):
    id: str
    doc_type_names: List[str] = Field(default_factory=list)
    rules: RuleSet = RuleSet()
    prompt: str = ""
    examples: List[ExampleItem] = Field(default_factory=list)

# ==================== TELEMETRY ====================

def go_quiet(default_level="ERROR"):
    """
    Silence 3rd-party telemetry/log spam while keeping:
      - your print(...) statements
      - real warnings/errors
    Call as the FIRST thing in your app, before importing big libs.
    """
    # --- Environment flags to quiet libraries ---
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("ABSL_LOGGING_MIN_SEVERITY", "3")  # absl
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")       # TF/XLA
    os.environ.setdefault("TQDM_DISABLE", "1")               # tqdm progress bars
    os.environ.setdefault("OTEL_SDK_DISABLED", "true")       # OpenTelemetry
    os.environ.setdefault("OTEL_LOG_LEVEL", "error")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")   # HF Hub
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
    os.environ.setdefault("GRPC_VERBOSITY", "ERROR")
    os.environ.pop("GRPC_TRACE", None)                       # ensure off
    os.environ.setdefault("OPENAI_LOG", "error")             # if openai sdk present

    # --- Ensure stdout uses UTF-8 on Windows (prevents charmap noise) ---
    if sys.platform.startswith("win"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    # --- Force global logging config ---
    # Keep root at ERROR by default (tunable via CE_LOG_LEVEL)
    lvl_name = os.getenv("CE_LOG_LEVEL", default_level).upper()
    lvl = getattr(logging, lvl_name, logging.ERROR)
    logging.basicConfig(
        level=lvl,
        format="%(levelname)s %(name)s: %(message)s",
        force=True,  # override prior handlers from libs
    )

    # --- Silence noisy third-party loggers hard ---
    noisy = [
        # networking / http
        "urllib3", "urllib3.connectionpool", "httpx", "requests",
        # AI/ML frameworks
        "transformers", "accelerate", "torch", "tensorflow", "jax", "jaxlib", "absl",
        # tracing/telemetry
        "opentelemetry", "opentelemetry.sdk", "opentelemetry.exporter",
        # LLM frameworks
        "langchain", "langchain_core", "langsmith",
        # PDF stack
        "pdfminer", "pdfminer.six",
        # web servers (if you run FastAPI later)
        "uvicorn", "uvicorn.error", "uvicorn.access", "gunicorn",
    ]
    for name in noisy:
        lg = logging.getLogger(name)
        lg.setLevel(logging.CRITICAL)
        lg.propagate = False

    # urllib3 TLS warnings, etc.
    try:
        import urllib3
        urllib3.disable_warnings()
    except Exception:
        pass

    # Convert Python warnings -> logging, then silence by default
    logging.captureWarnings(True)
    warnings.simplefilter("ignore")

    # OPTIONAL: keep YOUR app logger chatty if you prefer (only your messages)
    # (Use logger = logging.getLogger("contractextract") in your code)
    app_logger = logging.getLogger("contractextract")
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False
    if not app_logger.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setLevel(logging.INFO)
        h.setFormatter(logging.Formatter("%(message)s"))
        app_logger.addHandler(h)