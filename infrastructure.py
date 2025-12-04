"""
Consolidated infrastructure module for ContractExtract.
Contains all configuration, database, schema, and telemetry functionality.
"""

import os
import sys
import logging
import warnings
from typing import List, Optional, Dict
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

    # Report Version Configuration
    # V2 uses the new 8-section markdown template with enhanced metadata and risk assessment
    USE_REPORT_V2: bool = os.getenv("USE_REPORT_V2", "true").lower() in ("1", "true", "yes", "on")

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

class LeaseExtraction(BaseModel):
    """Structured lease agreement data extraction."""
    # Property Information
    property_name: Optional[str] = None
    property_address: Optional[str] = None
    property_type: Optional[str] = None
    property_square_footage: Optional[str] = None
    property_zoning: Optional[str] = None

    # Tenant Information
    tenant_legal_name: Optional[str] = None
    tenant_trade_name: Optional[str] = None
    tenant_address: Optional[str] = None
    tenant_contact_person: Optional[str] = None
    tenant_phone: Optional[str] = None
    tenant_email: Optional[str] = None

    # Landlord Information
    landlord_legal_name: Optional[str] = None
    landlord_address: Optional[str] = None
    landlord_contact_person: Optional[str] = None
    landlord_phone: Optional[str] = None
    landlord_email: Optional[str] = None

    # Important Dates
    lease_commencement_date: Optional[str] = None
    lease_expiration_date: Optional[str] = None
    lease_term_months: Optional[str] = None
    rent_commencement_date: Optional[str] = None
    option_to_renew_deadline: Optional[str] = None
    notice_to_vacate_days: Optional[str] = None

    # Rent and Financial Terms
    base_rent_amount: Optional[str] = None
    base_rent_frequency: Optional[str] = None
    rent_increase_percentage: Optional[str] = None
    rent_increase_frequency: Optional[str] = None
    cam_charges_monthly: Optional[str] = None
    cam_charges_annual: Optional[str] = None
    real_estate_tax_responsibility: Optional[str] = None
    insurance_responsibility: Optional[str] = None
    utilities_responsibility: Optional[str] = None

    # Security and Deposits
    security_deposit_amount: Optional[str] = None
    security_deposit_held_by: Optional[str] = None
    additional_deposit_amount: Optional[str] = None
    deposit_return_days: Optional[str] = None

    # Options and Rights
    option_to_renew_terms: Optional[str] = None
    option_to_expand: Optional[str] = None
    right_of_first_refusal: Optional[str] = None
    sublease_allowed: Optional[str] = None
    assignment_allowed: Optional[str] = None

    # Use and Restrictions
    permitted_use: Optional[str] = None
    prohibited_uses: Optional[str] = None
    exclusive_use_clause: Optional[str] = None
    operating_hours: Optional[str] = None
    signage_rights: Optional[str] = None

    # Maintenance and Repairs
    landlord_maintenance_obligations: Optional[str] = None
    tenant_maintenance_obligations: Optional[str] = None
    structural_repair_responsibility: Optional[str] = None
    hvac_maintenance_responsibility: Optional[str] = None

    # Insurance and Liability
    general_liability_coverage_required: Optional[str] = None
    property_insurance_required: Optional[str] = None
    additional_insured_requirement: Optional[str] = None

    # Default and Termination
    default_notice_days: Optional[str] = None
    cure_period_days: Optional[str] = None
    late_payment_grace_period: Optional[str] = None
    late_payment_penalty: Optional[str] = None
    early_termination_rights: Optional[str] = None

    # Special Provisions
    force_majeure_clause: Optional[str] = None
    casualty_damage_provisions: Optional[str] = None
    condemnation_provisions: Optional[str] = None
    estoppel_certificate_requirement: Optional[str] = None
    subordination_clause: Optional[str] = None

    # Parking and Access
    parking_spaces_allocated: Optional[str] = None
    parking_type: Optional[str] = None
    common_area_access: Optional[str] = None

class DocumentReport(BaseModel):
    document_name: str
    passed_all: bool
    findings: List[Finding]
    extraction: Optional[LeaseExtraction] = None
    report_v2: Optional['DocumentReportV2'] = None  # Temporary migration field for Phase 3


# ==================== REPORT V2 MODELS ====================
# New structured report format with preliminary extraction, risk assessment,
# and enhanced formatting for LibreChat MCP integration

class PreliminaryExtraction(BaseModel):
    """
    Base fields extracted from every document, regardless of document type.
    These are universal extractions that appear in Section 3 of Report V2.
    """
    document_type: str = Field(default="Unknown", description="Classified document type (from classify_document_type)")
    parties_summary: str = Field(default="Not identified", description="Human-readable summary of parties involved")
    duration: str = Field(default="Not specified", description="Contract length/duration summary")
    fees_summary: str = Field(default="Not specified", description="Fees and payment terms summary")
    termination_summary: str = Field(default="Not specified", description="Termination conditions summary")
    jurisdiction: str = Field(default="Not specified", description="Jurisdiction/governing law extracted")
    citations: List[Citation] = Field(default_factory=list, description="Citations supporting these extractions")


class ComplianceCheckResult(BaseModel):
    """
    Result of a single preliminary compliance check.
    Maps to Section 4 (Preliminary Compliance Checks) in Report V2.
    """
    check_id: str = Field(description="Unique ID for this check (e.g., 'jurisdiction_allowed')")
    label: str = Field(description="Human-readable label (e.g., 'Jurisdiction allowed')")
    status: str = Field(description="Status: PASS, FAIL, WARN, INFO")
    severity: str = Field(default="Medium", description="Severity: Critical, High, Medium, Low")
    message: str = Field(description="Human-readable details/explanation")
    citations: List[Citation] = Field(default_factory=list, description="Citations supporting this check")

    # Short and detailed explanations (for LLM-generated analysis)
    reason_short: Optional[str] = Field(default=None, description="1-2 sentence summary (for tables, bullets)")
    reason_detailed: Optional[str] = Field(default=None, description="Full paragraph explanation (for Section 7)")


class RulepackRuleResult(BaseModel):
    """
    Result of evaluating a single rule from a document-specific rulepack.
    Maps to Section 5.2 (Detailed Rules) table rows in Report V2.
    """
    rule_id: str = Field(description="Unique rule ID (e.g., 'lease.property')")
    label: str = Field(description="Human-readable rule label")
    category: str = Field(default="General", description="Rule category (e.g., 'Dates', 'Financial', 'Compliance')")
    status: str = Field(description="Status: PASS, FAIL, WARN, INFO")
    severity: str = Field(default="Medium", description="Severity: Critical, High, Medium, Low")
    message: str = Field(description="Human-readable result details")
    citations: List[Citation] = Field(default_factory=list, description="Citations supporting this rule")
    risk_statement: Optional[str] = Field(default=None, description="Pre-written risk statement from YAML")
    recommendation: Optional[str] = Field(default=None, description="Pre-written recommendation from YAML")

    # Short and detailed explanations (for LLM-generated analysis)
    reason_short: Optional[str] = Field(default=None, description="1-2 sentence summary (for tables, bullets)")
    reason_detailed: Optional[str] = Field(default=None, description="Full paragraph explanation (for Section 7)")


class RulepackSummary(BaseModel):
    """
    Summary statistics for rulepack evaluation.
    Maps to Section 5.1 (Summary) in Report V2.
    """
    rulepack_id: str = Field(description="Rulepack identifier (e.g., 'lease_agreement_v1')")
    rulepack_name: str = Field(description="Human-readable rulepack name")
    total_rules: int = Field(default=0, description="Total rules evaluated")
    pass_count: int = Field(default=0, description="Number of rules that passed")
    fail_count: int = Field(default=0, description="Number of rules that failed")
    warn_count: int = Field(default=0, description="Number of warnings")
    info_count: int = Field(default=0, description="Number of informational findings")


class RiskAssessment(BaseModel):
    """
    Overall risk assessment and recommendations for the document.
    Maps to Section 7 (Risks & Recommendations) in Report V2.
    """
    overall_risk_level: str = Field(default="Unknown", description="Overall risk: Low, Medium, High, Critical")
    top_risks: List[str] = Field(default_factory=list, description="Top 3-5 risks (rule-based + LLM-generated)")
    recommendations: List[str] = Field(default_factory=list, description="Top 3-5 recommendations (legacy format)")
    recommendations_per_check: Dict[str, str] = Field(default_factory=dict, description="LLM-generated recommendations mapped to check_id")
    risk_calculation_method: str = Field(default="Hybrid", description="How risk was calculated: Explicit, Count-based, Weighted, Hybrid")


class ExtractedKeyTerms(BaseModel):
    """
    Document-specific key terms extracted based on rulepack.
    Maps to Section 6 (Extracted Key Terms) in Report V2.
    This is flexible - different rulepacks populate different fields.
    """
    model_config = {'extra': 'allow'}  # Allow rulepack-specific fields

    # Common fields (may or may not be populated depending on doc type)
    property_address: Optional[str] = None
    lease_term: Optional[str] = None
    base_rent: Optional[str] = None
    salary: Optional[str] = None
    role_title: Optional[str] = None
    non_compete_duration: Optional[str] = None
    # ... more fields can be added dynamically by rulepacks


class DocumentMetadata(BaseModel):
    """
    Document metadata for Section 1 in Report V2.
    """
    file_name: str = Field(description="Original file name")
    document_id: Optional[str] = Field(default=None, description="Unique document identifier")
    classified_type: str = Field(description="Document type from classification")
    rulepack_id: str = Field(description="Rulepack ID used for analysis")
    rulepack_name: str = Field(description="Human-readable rulepack name")
    analysis_timestamp: str = Field(description="ISO timestamp of analysis")


class DocumentReportV2(BaseModel):
    """
    Version 2 of the document analysis report with enhanced structure.

    This is the top-level container for all report data and maps directly
    to the 8-section report template:

    1. Document Metadata
    2. Executive Summary
    3. Preliminary Extraction (Base Fields)
    4. Preliminary Compliance Checks
    5. Rulepack Evaluation
    6. Extracted Key Terms
    7. Risks & Recommendations
    8. Appendix: Citations

    Usage:
        report = DocumentReportV2(
            metadata=DocumentMetadata(...),
            preliminary_extraction=PreliminaryExtraction(...),
            compliance_checks=[...],
            rulepack_summary=RulepackSummary(...),
            rulepack_rules=[...],
            risk_assessment=RiskAssessment(...),
            extracted_key_terms=ExtractedKeyTerms(...),
        )

        markdown = render_markdown_v2(report)
    """
    # Section 1: Metadata
    metadata: DocumentMetadata

    # Section 2: Executive Summary (generated from risk_assessment)
    executive_summary: Optional[str] = Field(default=None, description="Brief summary paragraph")

    # Section 3: Preliminary Extraction
    preliminary_extraction: PreliminaryExtraction

    # Section 4: Preliminary Compliance Checks
    compliance_checks: List[ComplianceCheckResult] = Field(default_factory=list)

    # Section 5: Rulepack Evaluation
    rulepack_summary: RulepackSummary
    rulepack_rules: List[RulepackRuleResult] = Field(default_factory=list)

    # Section 6: Extracted Key Terms (rulepack-specific)
    extracted_key_terms: Optional[ExtractedKeyTerms] = None

    # Section 7: Risks & Recommendations
    risk_assessment: RiskAssessment

    # Section 8: Citation Map (all citations consolidated)
    citation_map: dict = Field(default_factory=dict, description="Map of citation_id -> citation text")

    # Overall status
    passed_all: bool = Field(description="True if all checks passed")


# ---------- RulePack / Examples ----------
class ExampleExtraction(BaseModel):
    """
    Schema for example extractions compatible with LangExtract library.

    The LangExtract library expects these specific fields:
    - extraction_text: The text that was extracted
    - extraction_class: The type/category of the extraction (same as label)
    - label: The type/category of the extraction
    - span: Optional location information

    BUGFIX: LangExtract dynamically adds fields like 'token_interval' during processing.
    We allow extra fields to prevent validation errors.
    """
    model_config = {'extra': 'allow'}  # Allow LangExtract to add dynamic fields

    extraction_text: str  # BUGFIX: LangExtract requires this field
    extraction_class: str  # BUGFIX: LangExtract requires this field (same as label)
    label: str
    span: Optional[str] = None
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
    rules_json: List[dict] = Field(default_factory=list)  # BUGFIX (Task 3a): Custom lease rules

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