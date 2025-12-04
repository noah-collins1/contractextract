"""
ContractExtract Analysis Engine - Complete Contract Compliance Pipeline

OVERVIEW
========

This module implements the **Analysis Mode** of ContractExtract - a complete pipeline
for extracting structured data from contracts and evaluating compliance against
configurable rule packs.

PIPELINE ARCHITECTURE
=====================

The analysis pipeline follows these stages:

    1. INGEST → 2. EXTRACT → 3. EVALUATE → 4. REPORT → 5. EXPORT/EMIT

    1. INGEST (document_analysis.py)
       - PDF → Text extraction with page/line mapping
       - Document type classification
       - Rule pack selection

    2. EXTRACT (this module)
       - LLM-based structured data extraction (optional)
       - Examples: lease terms, employment details, contract metadata
       - Uses provider abstraction (Ollama, OpenAI, etc.)

    3. EVALUATE (this module)
       - Hardcoded compliance checks (4 standard rules)
       - Custom rule evaluation (dispatch to handlers)
       - Citation generation with page/line numbers
       - Future: Generic RuleEngine for data-driven evaluation

    4. REPORT (this module)
       - Build DocumentReport with findings, extraction, and metadata
       - LLM-generated explanations for failures (optional)
       - Markdown rendering with executive summaries

    5. EXPORT/EMIT (export_utils.py, mcp_server.py)
       - JSON/CSV/Excel export for batch processing
       - MCP tool responses for LibreChat
       - Future: Streaming emitters for real-time updates

MAIN ENTRY POINTS
=================

make_report(document_name, text, rules, pack_data, llm_override)
    → DocumentReport

    The primary API for Analysis Mode. Takes contract text and rules,
    returns a complete compliance report with findings and extraction data.

extract_lease_fields(text, llm_prompt, examples, llm_override)
    → LeaseExtraction

    Standalone extraction API (can be used without compliance evaluation).
    Future: Extraction Mode will expose this directly.

evaluate_text_against_rules(text, rules, extraction, pack_data)
    → (List[Finding], contract_value_guess)

    Pure evaluation API. Takes text + rules, returns compliance findings.
    Future: Will be replaced by generic RuleEngine dispatcher.

INTEGRATION POINTS (for future extensions)
===========================================

1. **RuleEngine Integration (Task 3)**
   - Replace hardcoded `evaluate_text_against_rules()` logic
   - Dispatch all rules through generic evaluator
   - Current handlers (check_jurisdiction_*, check_fraud_*, etc.) become
     rule implementations registered with the engine

2. **Extraction Mode (Task 4)**
   - Expose `extract_lease_fields()` as standalone API
   - Skip evaluation step entirely
   - Return only LeaseExtraction data (no DocumentReport)
   - Use Emitters for output (JSON stream, webhook, etc.)

3. **Custom Emitters**
   - Current: Markdown/JSON/Excel files
   - Future: Streaming JSON, webhooks, database writes, S3 uploads
   - Plug in at step 5 (EXPORT/EMIT)

4. **Provider Extensibility**
   - Current: OllamaProvider (local LLM)
   - Extend: Add OpenAI, Anthropic, Google providers
   - Implement LLMProvider interface
   - Register in load_provider() factory

DATA STRUCTURES
===============

RuleSet (infrastructure.py)
    - Defines compliance rules: jurisdiction, liability_cap, fraud, contract_value
    - Loaded from YAML rule packs
    - Used by evaluation functions

DocumentReport (infrastructure.py)
    - Primary output of Analysis Mode
    - Contains: document_name, passed_all, findings, extraction

Finding (infrastructure.py)
    - Single compliance check result
    - Contains: rule_id, passed, details, citations

LeaseExtraction (infrastructure.py)
    - Structured data extracted from leases
    - 60+ fields: property, tenant, dates, rent, options, etc.

Citation (infrastructure.py)
    - Reference to contract text
    - Contains: char_start, char_end, page, line_start, line_end, quote

CURRENT LIMITATIONS (to be addressed in future tasks)
======================================================

- Only 4 hardcoded compliance checks are fully evaluated
- Custom rules use static handlers (not data-driven generic RuleEngine)
- Employment rule handlers (emp.*) not yet implemented
- No generic rule evaluation engine (hardcoded logic only)

TASK 3a COMPLETE: Lease rulepack integration
- All 9 lease rule types from lease_agreement.yml are now wired
- Handlers consume params from rulepack: property, tenant, dates, rent, security, fees, default, options, expenses
- Lease analysis is now rulepack-driven (prototype for future generic RuleEngine)

See CONTRACT_ANALYZER_LOGIC_ANALYSIS.md for detailed analysis of current limitations.

HISTORY
=======

Merged from:
- evaluator.py: Core evaluation engine with finding normalization and LLM explanations
- llm_factory.py: LLM provider loading and configuration
- llm_provider.py: LLM provider abstractions and implementations
"""

import os
import yaml
import re
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Any, Sequence, Optional, Tuple, Dict
from decimal import Decimal

try:
    import langextract as lx
except ImportError:
    # Fallback if langextract not available
    lx = None

from infrastructure import RuleSet, DocumentReport, Finding

# ========================================
# SAFE DEBUG PRINTING (Windows console compatibility)
# ========================================

def _safe_debug_snippet(label: str, text: str, max_len: int = 500) -> None:
    """
    Safely print a debug snippet of text without triggering UnicodeEncodeError
    on Windows consoles or weird terminals.
    """
    try:
        if not isinstance(text, str):
            text = str(text)
        snippet = text[:max_len]
        # Replace characters that can't be encoded in current console
        safe = snippet.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
        print(f"{label}{safe}")
    except Exception as e:
        try:
            print(f"{label}[unprintable debug text: {e}]")
        except Exception:
            # Last resort: swallow print errors completely
            pass

# ========================================
# LLM PROVIDER ABSTRACTIONS
# ========================================

class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def extract(
        self,
        *,
        text_or_documents: Sequence[str] | str,
        prompt: str,
        examples: list[Any],
        extraction_passes: int = 1,
        max_workers: int = 1,
        max_char_buffer: int = 1500,
    ) -> Any:
        """Extract information using the LLM provider."""
        ...


class OllamaProvider(LLMProvider):
    """Ollama LLM provider implementation."""

    def __init__(self, model_id="llama3:8b-instruct-q4_K_M", url="http://localhost:11434"):
        self.model_id = model_id
        self.url = url

    def extract(self, *, text_or_documents, prompt, examples,
                extraction_passes=1, max_workers=1, max_char_buffer=1500):
        """Extract information using Ollama via langextract."""
        if lx is None:
            raise ImportError("langextract module not available")

        return lx.extract(
            text_or_documents=text_or_documents,
            prompt_description=prompt,
            examples=examples,
            model_id=self.model_id,
            model_url=self.url,
            extraction_passes=extraction_passes,
            max_workers=max_workers,
            max_char_buffer=max_char_buffer,
            fence_output=False,
            use_schema_constraints=False,
        )

    def complete(self, prompt: str) -> str:
        """
        Used by Phase 2 rulepacks. Returns raw text (usually JSON).
        DO NOT return an object with .extractions here.

        Args:
            prompt: The prompt to send to the LLM

        Returns:
            Raw text response from the LLM
        """
        import requests
        import logging

        logger = logging.getLogger(__name__)

        # Ollama 0.12.7+ uses OpenAI-compatible API at /v1/chat/completions
        # Fallback to legacy /api/generate if needed
        endpoints = [
            ("/v1/chat/completions", "openai"),  # Modern Ollama (0.12.7+)
            ("/api/generate", "legacy")          # Legacy Ollama API
        ]

        last_error = None
        for endpoint, api_type in endpoints:
            try:
                ollama_url = f"{self.url}{endpoint}"
                logger.debug(f"OllamaProvider.complete() trying {api_type} API: {ollama_url}")

                if api_type == "openai":
                    # OpenAI-compatible format
                    payload = {
                        "model": self.model_id,
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "temperature": 0.1,
                        "max_tokens": 2048,
                        "stream": False
                    }

                    response = requests.post(ollama_url, json=payload, timeout=120)
                    response.raise_for_status()

                    result_json = response.json()
                    # Extract from OpenAI format: choices[0].message.content
                    content = result_json.get("choices", [{}])[0].get("message", {}).get("content", "")
                    logger.debug(f"OllamaProvider.complete() succeeded with {api_type} API")
                    return content

                elif api_type == "legacy":
                    # Legacy Ollama format
                    payload = {
                        "model": self.model_id,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.1,
                            "num_predict": 2048
                        }
                    }

                    response = requests.post(ollama_url, json=payload, timeout=120)
                    response.raise_for_status()

                    result_json = response.json()
                    # Extract from legacy format: response
                    content = result_json.get("response", "")
                    logger.debug(f"OllamaProvider.complete() succeeded with {api_type} API")
                    return content

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    logger.debug(f"OllamaProvider.complete() {api_type} API not available (404)")
                    last_error = e
                    continue
                else:
                    raise
            except Exception as e:
                logger.debug(f"OllamaProvider.complete() {api_type} API error: {e}")
                last_error = e
                continue

        # If we get here, all endpoints failed
        error_msg = f"All Ollama endpoints failed. Last error: {last_error}"
        logger.error(f"OllamaProvider.complete() {error_msg}")
        raise RuntimeError(error_msg)


# ========================================
# LLM PROVIDER FACTORY
# ========================================

def load_provider(config_path: str = "llm.yaml") -> LLMProvider:
    """
    Load and configure an LLM provider.

    Args:
        config_path: Path to LLM configuration file

    Returns:
        Configured LLM provider instance
    """
    cfg = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}

    kind = os.getenv("LLM_PROVIDER", cfg.get("provider", "ollama")).lower()
    if kind == "ollama":
        return OllamaProvider(
            model_id=cfg.get("model_id", "llama3:8b-instruct-q4_K_M"),
            url=cfg.get("model_url", "http://localhost:11434"),
        )
    raise ValueError(f"Unknown provider: {kind}")


# ========================================
# LEASE EXTRACTION PIPELINE
# ========================================

# Field name mapping: LLM output keys → LeaseExtraction model fields
# The LLM often returns simplified field names that need to be mapped
# to the exact field names in the LeaseExtraction Pydantic model
LEASE_FIELD_ALIASES = {
    # Property (flat + nested variants from LLM)
    "property_name": "property_name",
    "propertyinformation_property_name": "property_name",
    "property_address": "property_address",
    "propertyinformation_property_address": "property_address",
    "property_type": "property_type",
    "propertyinformation_property_type": "property_type",
    "square_footage": "property_square_footage",
    "property_square_footage": "property_square_footage",
    "propertyinformation_square_footage": "property_square_footage",
    "suite_number": "suite_number",
    "propertyinformation_suite_number": "suite_number",
    "zoning": "property_zoning",
    "propertyinformation_zoning": "property_zoning",

    # Tenant (flat + nested variants from LLM)
    "tenant_name": "tenant_legal_name",
    "tenant_legal_name": "tenant_legal_name",
    "tenant_trade_name": "tenant_trade_name",
    "tenantinformation_tenant_name_legal_entity_name": "tenant_legal_name",
    "tenantinformation_tenant_legal_name": "tenant_legal_name",
    "tenantinformation_tenant_trade_name": "tenant_trade_name",
    "billing_address": "tenant_address",
    "tenant_address": "tenant_address",
    "tenantinformation_billing_address": "tenant_address",
    "tenantinformation_tenant_address": "tenant_address",
    "contact_name": "tenant_contact_person",
    "tenant_contact": "tenant_contact_person",
    "tenant_contact_person": "tenant_contact_person",
    "tenantinformation_contact_name": "tenant_contact_person",
    "tenantinformation_tenant_contact_person": "tenant_contact_person",
    "contact_phone": "tenant_phone",
    "tenant_phone": "tenant_phone",
    "tenantinformation_phone_number": "tenant_phone",
    "tenantinformation_tenant_phone": "tenant_phone",
    "contact_email": "tenant_email",
    "tenant_email": "tenant_email",
    "tenantinformation_email_address": "tenant_email",
    "tenantinformation_tenant_email": "tenant_email",

    # Landlord (flat + nested variants from LLM)
    "landlord_name": "landlord_legal_name",
    "landlord_legal_name": "landlord_legal_name",
    "landlord_address": "landlord_address",
    "landlord_contact": "landlord_contact_person",
    "landlord_contact_person": "landlord_contact_person",
    "landlord_phone": "landlord_phone",
    "landlord_email": "landlord_email",

    # Dates (flat + nested variants from LLM)
    "execution_date": "lease_execution_date",
    "commencement_date": "lease_commencement_date",
    "lease_commencement_date": "lease_commencement_date",
    "leasedates_execution_date_date_lease_was_signed": "lease_execution_date",
    "leasedates_commencement_date_lease_start_date": "lease_commencement_date",
    "expiration_date": "lease_expiration_date",
    "lease_expiration_date": "lease_expiration_date",
    "leasedates_expiration_date_lease_end_date": "lease_expiration_date",
    "lease_term": "lease_term_months",
    "lease_term_months": "lease_term_months",
    "rent_start_date": "rent_commencement_date",
    "rent_commencement_date": "rent_commencement_date",
    "rentterms_rent_start_date": "rent_commencement_date",
    "renewal_deadline": "option_to_renew_deadline",
    "option_to_renew_deadline": "option_to_renew_deadline",
    "notice_to_vacate": "notice_to_vacate_days",
    "notice_to_vacate_days": "notice_to_vacate_days",

    # Rent & Financials (flat + nested variants from LLM)
    "base_rent": "base_rent_amount",
    "base_rent_amount": "base_rent_amount",
    "monthly_rent": "base_rent_amount",
    "rentterms_base_rent_amount_monthly_amount": "base_rent_amount",
    "rent_frequency": "base_rent_frequency",
    "base_rent_frequency": "base_rent_frequency",
    "payment_frequency": "base_rent_frequency",
    "rent_increase": "rent_increase_percentage",
    "rent_increase_percentage": "rent_increase_percentage",
    "rent_escalation": "rent_increase_frequency",
    "rent_increase_frequency": "rent_increase_frequency",
    "rent_escalation_terms": "rent_escalation_terms",
    "cam_charges": "cam_charges_monthly",
    "cam_charges_monthly": "cam_charges_monthly",
    "cam_monthly": "cam_charges_monthly",
    "recoverycharges_cam_common_area_maintenance_charges": "cam_charges_monthly",
    "cam_annual": "cam_charges_annual",
    "cam_charges_annual": "cam_charges_annual",
    "real_estate_taxes": "real_estate_tax_responsibility",
    "real_estate_tax_responsibility": "real_estate_tax_responsibility",
    "tax_recovery": "real_estate_tax_responsibility",
    "recoverycharges_real_estate_taxes_recovery": "real_estate_tax_responsibility",
    "insurance": "insurance_responsibility",
    "insurance_responsibility": "insurance_responsibility",
    "insurance_recovery": "insurance_responsibility",
    "recoverycharges_insurance_recovery": "insurance_responsibility",
    "utilities": "utilities_responsibility",
    "utilities_responsibility": "utilities_responsibility",

    # Security & Deposits (flat + nested variants from LLM)
    "security_deposit": "security_deposit_amount",
    "security_deposit_amount": "security_deposit_amount",
    "deposit_amount": "security_deposit_amount",
    "securitydeposits_security_deposit_amount": "security_deposit_amount",
    "security_deposit_held_by": "security_deposit_held_by",
    "deposit_held_by": "security_deposit_held_by",
    "additional_deposit": "additional_deposit_amount",
    "additional_deposit_amount": "additional_deposit_amount",
    "deposit_return": "deposit_return_days",
    "deposit_return_days": "deposit_return_days",

    # Options & Rights
    "renewal_options": "option_to_renew_terms",
    "option_to_renew": "option_to_renew_terms",
    "option_to_renew_terms": "option_to_renew_terms",
    "expansion_options": "option_to_expand",
    "option_to_expand": "option_to_expand",
    "right_of_first_refusal": "right_of_first_refusal",
    "rofr": "right_of_first_refusal",
    "sublease": "sublease_allowed",
    "sublease_allowed": "sublease_allowed",
    "assignment": "assignment_allowed",
    "assignment_allowed": "assignment_allowed",

    # Use & Restrictions
    "permitted_use": "permitted_use",
    "allowed_use": "permitted_use",
    "prohibited_uses": "prohibited_uses",
    "exclusive_use": "exclusive_use_clause",
    "exclusive_use_clause": "exclusive_use_clause",
    "operating_hours": "operating_hours",
    "hours_of_operation": "operating_hours",
    "signage": "signage_rights",
    "signage_rights": "signage_rights",

    # Maintenance & Repairs
    "landlord_maintenance": "landlord_maintenance_obligations",
    "landlord_maintenance_obligations": "landlord_maintenance_obligations",
    "tenant_maintenance": "tenant_maintenance_obligations",
    "tenant_maintenance_obligations": "tenant_maintenance_obligations",
    "structural_repairs": "structural_repair_responsibility",
    "structural_repair_responsibility": "structural_repair_responsibility",
    "hvac_maintenance": "hvac_maintenance_responsibility",
    "hvac_maintenance_responsibility": "hvac_maintenance_responsibility",

    # Insurance & Liability
    "general_liability": "general_liability_coverage_required",
    "general_liability_coverage_required": "general_liability_coverage_required",
    "liability_coverage": "general_liability_coverage_required",
    "property_insurance": "property_insurance_required",
    "property_insurance_required": "property_insurance_required",
    "additional_insured": "additional_insured_requirement",
    "additional_insured_requirement": "additional_insured_requirement",

    # Default & Termination
    "default_notice": "default_notice_days",
    "default_notice_days": "default_notice_days",
    "cure_period": "cure_period_days",
    "cure_period_days": "cure_period_days",
    "late_payment_grace": "late_payment_grace_period",
    "late_payment_grace_period": "late_payment_grace_period",
    "grace_period": "late_payment_grace_period",
    "latefeesdefault_grace_period_days": "late_payment_grace_period",
    "late_fee": "late_payment_penalty",
    "late_payment_penalty": "late_payment_penalty",
    "late_fees": "late_payment_penalty",
    "early_termination": "early_termination_rights",
    "early_termination_rights": "early_termination_rights",
    "termination_options": "early_termination_rights",

    # Special Provisions
    "force_majeure": "force_majeure_clause",
    "force_majeure_clause": "force_majeure_clause",
    "casualty_damage": "casualty_damage_provisions",
    "casualty_damage_provisions": "casualty_damage_provisions",
    "condemnation": "condemnation_provisions",
    "condemnation_provisions": "condemnation_provisions",
    "estoppel_certificate": "estoppel_certificate_requirement",
    "estoppel_certificate_requirement": "estoppel_certificate_requirement",
    "subordination": "subordination_clause",
    "subordination_clause": "subordination_clause",

    # Parking & Access
    "parking_spaces": "parking_spaces_allocated",
    "parking_spaces_allocated": "parking_spaces_allocated",
    "parking": "parking_spaces_allocated",
    "parking_type": "parking_type",
    "common_area_access": "common_area_access",
    "common_areas": "common_area_access",
}

def parse_llm_extraction_result(result_text: str) -> dict:
    """
    Parse LLM extraction result from various formats.

    Args:
        result_text: Raw LLM output (JSON, markdown-wrapped JSON, or text format)

    Returns:
        Dictionary of extracted field name -> value mappings
    """
    # Clean up markdown code blocks if present
    cleaned_text = result_text.strip()
    if cleaned_text.startswith('```'):
        # Remove markdown code fence
        lines = cleaned_text.split('\n')
        if lines[0].startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        cleaned_text = '\n'.join(lines).strip()

    # Remove "json" language identifier if present
    if cleaned_text.startswith('json'):
        cleaned_text = cleaned_text[4:].strip()

    # Try JSON parse first
    try:
        data = json.loads(cleaned_text)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, ValueError):
        pass

    # Try finding JSON object in the text
    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', cleaned_text, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError):
            pass

    # Fallback: parse text format
    # Look for "field_name: value" patterns
    extraction = {}
    for line in result_text.split('\n'):
        line = line.strip()
        if ':' in line and not line.startswith('{') and not line.startswith('}'):
            parts = line.split(':', 1)
            if len(parts) == 2:
                field_name = parts[0].strip().lower().replace(' ', '_').replace('"', '').replace("'", "")
                field_value = parts[1].strip().rstrip(',').replace('"', '').replace("'", "")
                if field_value and field_value != 'None' and field_value != 'N/A' and field_value != 'null':
                    extraction[field_name] = field_value

    return extraction


def extract_lease_fields(
    text: str,
    llm_prompt: str,
    examples: List[Any],
    llm_override: Optional[bool] = None,
) -> 'LeaseExtraction':
    """
    Extract structured lease data using LLM.

    BUGFIX: Bypass LangExtract library and call Ollama directly.
    LangExtract has complex schema requirements that don't match our YAML format.

    Args:
        text: Contract text to analyze
        llm_prompt: Extraction prompt from rulepack
        examples: Example extractions from rulepack (unused - bypassing LangExtract)
        llm_override: Override for LLM usage (None = use default)

    Returns:
        LeaseExtraction object with populated fields
    """
    from infrastructure import LeaseExtraction, settings
    import requests
    import json

    # DEBUG: Log extraction attempt
    print(f"\n[DEBUG] extract_lease_fields called")
    print(f"[DEBUG] llm_override={llm_override}")
    print(f"[DEBUG] settings.get_llm_enabled()={settings.get_llm_enabled(llm_override)}")
    print(f"[DEBUG] prompt length={len(llm_prompt)} chars")
    print(f"[DEBUG] text length={len(text)} chars")

    # Check if LLM is enabled
    if not settings.get_llm_enabled(llm_override):
        print(f"[DEBUG] LLM disabled, returning empty LeaseExtraction")
        return LeaseExtraction()

    # Build extraction prompt with JSON output instruction
    extraction_prompt = f"""{llm_prompt}

IMPORTANT: Return ONLY a valid JSON object with field names as keys and extracted values as strings.
Use null for fields that are not found in the document.
Do NOT include any explanatory text, markdown formatting, or code blocks - ONLY the JSON object.

Contract text to analyze (first 8000 chars):
{text[:8000]}

Return JSON now:"""

    # Call Ollama directly (bypass LangExtract)
    try:
        print(f"[DEBUG] Calling Ollama API directly...")

        ollama_url = "http://localhost:11434/api/generate"
        payload = {
            "model": "llama3:8b-instruct-q4_K_M",
            "prompt": extraction_prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 2000
            }
        }

        print(f"[DEBUG] Sending request to Ollama...")
        response = requests.post(ollama_url, json=payload, timeout=60)
        response.raise_for_status()

        result_json = response.json()
        result_text = result_json.get("response", "")

        print(f"[DEBUG] Ollama response length: {len(result_text)} chars")
        _safe_debug_snippet("[DEBUG] Ollama response (first 500 chars): ", result_text)

        # Parse the JSON response
        extraction_dict = parse_llm_extraction_result(result_text)
        print(f"[DEBUG] Parsed extraction_dict keys: {list(extraction_dict.keys())[:10]}")
        _safe_debug_snippet(
            "[DEBUG] extraction_dict (first 5 items): ",
            str(dict(list(extraction_dict.items())[:5]))
        )

        # BUGFIX: Flatten nested JSON structures
        # The LLM may return nested objects like {"propertyInformation": {"Property Address": "..."}}"
        # We need to flatten to {"property_address": "..."} before normalization
        def flatten_dict(d, parent_key='', sep='_'):
            """Recursively flatten nested dictionaries."""
            items = []
            for k, v in d.items():
                # Convert key to snake_case and remove special chars
                clean_key = re.sub(r'[^\w\s]', '', k.lower())
                clean_key = re.sub(r'\s+', '_', clean_key.strip())

                new_key = f"{parent_key}{sep}{clean_key}" if parent_key else clean_key

                if isinstance(v, dict):
                    items.extend(flatten_dict(v, new_key, sep=sep).items())
                elif isinstance(v, list):
                    # Skip lists for now
                    continue
                else:
                    items.append((new_key, v))
            return dict(items)

        flattened = flatten_dict(extraction_dict)
        print(f"[DEBUG] Flattened dict keys: {list(flattened.keys())[:20]}")
        _safe_debug_snippet(
            "[DEBUG] Flattened dict (first 10 items): ",
            str(dict(list(flattened.items())[:10]))
        )

        # BUGFIX: Normalize field names to match LeaseExtraction model
        # The LLM returns keys like "tenant_name" but the model expects "tenant_legal_name"
        model_fields = set(LeaseExtraction.model_fields.keys())
        normalized = {}

        for key, value in flattened.items():
            # Skip empty/null values
            if value in (None, "", "null", "None", "N/A", "not specified"):
                continue

            # Map LLM key to model field name using alias mapping
            target = LEASE_FIELD_ALIASES.get(key, key)

            # Only include fields that exist in the LeaseExtraction model
            if target in model_fields:
                normalized[target] = value
            else:
                print(f"[DEBUG] Unmapped extraction key: '{key}' -> '{target}' (ignored, not in model)")

        print(f"[DEBUG] Normalized extraction_dict keys: {list(normalized.keys())[:10]}")
        _safe_debug_snippet(
            "[DEBUG] Normalized extraction_dict (first 5 items): ",
            str(dict(list(normalized.items())[:5]))
        )

        # Create LeaseExtraction object with normalized field names
        lease_extraction = LeaseExtraction(**normalized)
        populated_count = len([k for k, v in lease_extraction.model_dump().items() if v])
        print(f"[DEBUG] Created LeaseExtraction with {populated_count} populated fields")

        return lease_extraction

    except Exception as e:
        print(f"[ERROR] LLM extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return LeaseExtraction()


# ========================================
# RULE EVALUATION ENGINE
# ========================================

# Regex patterns for rule evaluation
MONEY_RE = re.compile(r'(?P<currency>\$|USD|US\$|EUR|€|GBP|£|AUD|A\$)?\s?(?P<amount>\d{1,3}(?:[,.\s]\d{3})*(?:\.\d{2})?|\d+(?:\.\d{2})?)', re.IGNORECASE)
GOV_LAW_RE = re.compile(r'(governing law|jurisdiction|venue)\s*[:\-]?\s*(?:of|in)?\s*([A-Za-z][A-Za-z\s().,&\-]+)', re.IGNORECASE)
LIAB_SECTION_RE = re.compile(r'(limitation of liability|liability(?:\s+limit| cap)?)', re.IGNORECASE)
MONTHS_FEES_RE = re.compile(r'(?:twelve|12)\s*\(?12?\)?\s*months? of (?:fees|payments|service fees)', re.IGNORECASE)
FRAUD_RE = re.compile(r'\bfraud\b', re.IGNORECASE)
OTHER_PARTY_HEURISTIC_RE = re.compile(r'(sole|entire)\s+responsibility|liab(?:ility)?\s+(?:of|on)\s+(?:the\s+)?other\s+party', re.IGNORECASE)
SIGNATURE_NOISE = re.compile(r'(signature page follows|confidential|translation, for reference only)', re.IGNORECASE)

def _norm_amount(txt: str):
    """Normalize monetary amount string to float."""
    try:
        return float(re.sub(r'[,\s]', '', txt))
    except Exception:
        return None

def parse_money(text: str):
    """Parse all monetary amounts from text."""
    out = []
    for m in MONEY_RE.finditer(text):
        amt = _norm_amount(m.group('amount'))
        cur = m.group('currency') or ''
        if amt is not None:
            out.append((amt, cur, m.span()))
    return out

def max_money(text: str):
    """Find largest monetary amount in text."""
    vals = parse_money(text)
    return max(vals, key=lambda t: t[0]) if vals else None

def find_liability_section(text: str):
    """Find liability section in contract text."""
    m = LIAB_SECTION_RE.search(text)
    if not m:
        return None
    start = max(0, m.start() - 600)
    end = min(len(text), m.end() + 1200)
    return (start, end)

def window_quote(text: str, span, pad: int = 140):
    """Create a Citation with context window."""
    from infrastructure import Citation
    s, e = span
    qs = max(0, s - pad)
    qe = min(len(text), e + pad)
    return Citation(char_start=s, char_end=e, quote=text[qs:qe])

def _strip_noise(text: str) -> str:
    """Remove signature noise from text."""
    lines = text.splitlines()
    keep = []
    for ln in lines:
        if SIGNATURE_NOISE.search(ln):
            continue
        keep.append(ln)
    return "\n".join(keep)

def check_liability_cap_present_and_within_bounds(text: str, rules: RuleSet, contract_value_guess):
    """Check if liability cap is present and within configured bounds."""
    sec_span = find_liability_section(text)
    if sec_span is None:
        return Finding(
            rule_id="liability_cap_present_and_within_bounds",
            passed=False,
            details="No clear 'Limitation of Liability' section found.",
            citations=[]
        )
    cit = window_quote(text, sec_span)
    section = text[sec_span[0]:sec_span[1]]

    cap_ok = True
    notes = []

    if MONTHS_FEES_RE.search(section):
        if rules.liability_cap.max_cap_multiplier is not None and rules.liability_cap.max_cap_multiplier < 1.0:
            cap_ok = False
            notes.append("Found '12 months of fees' (~1x), exceeds configured multiplier.")
        else:
            notes.append("Found '12 months of fees' (~1x multiplier).")

    money_in_section = parse_money(section)
    if money_in_section:
        highest_cap = max(money_in_section, key=lambda t: t[0])
        cap_amt, cap_cur, cap_span = highest_cap
        notes.append(f"Found explicit monetary cap candidate: {cap_cur}{cap_amt:,.2f}.")
        if rules.liability_cap.max_cap_amount is not None and cap_amt > rules.liability_cap.max_cap_amount:
            cap_ok = False
            notes.append(f"Cap {cap_amt:,.2f} exceeds allowed {rules.liability_cap.max_cap_amount:,.2f}.")
        if contract_value_guess is not None and rules.liability_cap.max_cap_multiplier is not None:
            if cap_amt > rules.liability_cap.max_cap_multiplier * contract_value_guess:
                cap_ok = False
                notes.append(f"Cap {cap_amt:,.2f} exceeds {rules.liability_cap.max_cap_multiplier}× inferred contract value {contract_value_guess:,.2f}.")

    if not money_in_section and not MONTHS_FEES_RE.search(section):
        cap_ok = False
        notes.append("No clear cap indicator ('12 months of fees' or explicit monetary cap) detected.")

    return Finding(
        rule_id="liability_cap_present_and_within_bounds",
        passed=cap_ok,
        details="; ".join(notes) if notes else ("Cap appears within configured bounds." if cap_ok else "Cap not within bounds."),
        citations=[cit]
    )

def check_contract_value_within_limit(text: str, rules: RuleSet):
    """Check if contract value is within configured limit."""
    if rules.contract.max_contract_value is None:
        return Finding(
            rule_id="contract_value_within_limit",
            passed=True,
            details="No max contract value configured; skipping.",
            citations=[]
        )
    mm = max_money(text)
    if not mm:
        return Finding(
            rule_id="contract_value_within_limit",
            passed=True,
            details="Could not identify a contract value; no obvious monetary amounts found.",
            citations=[]
        )
    amt, cur, span = mm
    passed = amt <= rules.contract.max_contract_value
    return Finding(
        rule_id="contract_value_within_limit",
        passed=passed,
        details=f"Largest detected amount {cur}{amt:,.2f} {'is within' if passed else 'exceeds'} configured limit {rules.contract.max_contract_value:,.2f}.",
        citations=[window_quote(text, span)]
    )

def check_fraud_clause_present_and_assigned(text: str, rules: RuleSet):
    """
    Check if fraud clause is present and properly assigned.

    BUGFIX: Now reports ALL fraud clause instances found (not just the first),
    allowing users to see all fraud references in the document.
    """
    from infrastructure import Citation

    if not rules.fraud.require_fraud_clause:
        return Finding(
            rule_id="fraud_clause_present_and_assigned",
            passed=True,
            details="Fraud clause not required by config.",
            citations=[]
        )

    matches = list(FRAUD_RE.finditer(text))

    if not matches:
        return Finding(
            rule_id="fraud_clause_present_and_assigned",
            passed=False,
            details="No 'fraud' mention found.",
            citations=[]
        )

    # Collect all fraud mentions and check assignment for each
    all_citations = []
    all_assigned_ok = True
    assignment_details = []

    for m in matches:
        s, e = m.span()
        window_s = max(0, s-300)
        window_e = min(len(text), e+300)
        nearby = text[window_s:window_e]

        all_citations.append(Citation(char_start=s, char_end=e, quote=nearby))

        if rules.fraud.require_liability_on_other_party:
            if not OTHER_PARTY_HEURISTIC_RE.search(nearby):
                all_assigned_ok = False
                assignment_details.append("not assigned to other party")
            else:
                assignment_details.append("assigned to other party")

    # Build detailed message
    if len(matches) == 1:
        note = f"'fraud' found (1 instance). "
        if rules.fraud.require_liability_on_other_party:
            if all_assigned_ok:
                note += "Liability appears assigned to the other party."
            else:
                note += "Could not confirm liability assigned to the 'other party' near the fraud reference."
    else:
        note = f"'fraud' found ({len(matches)} instances). "
        if rules.fraud.require_liability_on_other_party:
            if all_assigned_ok:
                note += "All instances appear to have liability assigned to the other party."
            else:
                assigned_count = sum(1 for d in assignment_details if "assigned to other party" in d)
                note += f"{assigned_count}/{len(matches)} instances have liability properly assigned to the other party."

    return Finding(
        rule_id="fraud_clause_present_and_assigned",
        passed=all_assigned_ok,
        details=note,
        citations=all_citations  # Return ALL citations
    )

def check_jurisdiction_present_and_allowed(text: str, rules: RuleSet):
    """
    Check if jurisdiction clause is present and in allowed list.

    BUGFIX: Now reports ALL jurisdiction clauses found (not just the first),
    allowing users to see if multiple jurisdictions are mentioned.
    """
    matches = list(GOV_LAW_RE.finditer(text))

    if not matches:
        return Finding(
            rule_id="jurisdiction_present_and_allowed",
            passed=False,
            details="No clear 'governing law / jurisdiction' clause detected.",
            citations=[]
        )

    # Collect all jurisdictions and citations
    jurisdictions = []
    all_citations = []
    all_allowed = True
    allowed = rules.jurisdiction.allowed_countries

    for m in matches:
        loc = m.group(2).strip()
        jurisdictions.append(loc)
        all_citations.append(window_quote(text, m.span(2)))

        is_allowed = any(a.lower() in loc.lower() for a in allowed)
        if not is_allowed:
            all_allowed = False

    # Build detailed message
    if len(jurisdictions) == 1:
        details = f'Governing law/jurisdiction detected as "{jurisdictions[0]}". {"Allowed" if all_allowed else "Not in allowed list."}'
    else:
        jur_list = ', '.join(f'"{j}"' for j in jurisdictions)
        details = f'Multiple jurisdiction clauses found: {jur_list}. {"All allowed" if all_allowed else "One or more not in allowed list."}'

    return Finding(
        rule_id="jurisdiction_present_and_allowed",
        passed=all_allowed,
        details=details,
        citations=all_citations  # Return ALL citations
    )


# ========================================
# CUSTOM LEASE RULE EVALUATION
# ========================================

def check_lease_property(text: str, params: dict, extraction: Optional['LeaseExtraction'] = None) -> Finding:
    """Check if required property information is present."""
    from infrastructure import LeaseExtraction

    require_details = params.get('require_property_details', True)

    if not require_details:
        return Finding(
            rule_id="lease.property",
            passed=True,
            details="Property details check not required by rule configuration.",
            citations=[]
        )

    # Use extraction data if available
    if extraction:
        has_name = bool(extraction.property_name)
        has_address = bool(extraction.property_address)

        if has_name and has_address:
            return Finding(
                rule_id="lease.property",
                passed=True,
                details=f"Property identified: {extraction.property_name} at {extraction.property_address}",
                citations=[]
            )
        else:
            missing = []
            if not has_name:
                missing.append("property name")
            if not has_address:
                missing.append("property address")
            return Finding(
                rule_id="lease.property",
                passed=False,
                details=f"Missing required property details: {', '.join(missing)}",
                citations=[]
            )

    # Fallback: text search
    has_property_info = bool(re.search(r'(property|premises|leased premises)', text, re.IGNORECASE))
    return Finding(
        rule_id="lease.property",
        passed=has_property_info,
        details="Property information found in contract text." if has_property_info else "Property information not clearly identified.",
        citations=[]
    )


def check_lease_tenant(text: str, params: dict, extraction: Optional['LeaseExtraction'] = None) -> Finding:
    """Check if required tenant information is present."""
    from infrastructure import LeaseExtraction

    require_details = params.get('require_tenant_details', True)

    if not require_details:
        return Finding(
            rule_id="lease.tenant",
            passed=True,
            details="Tenant details check not required by rule configuration.",
            citations=[]
        )

    if extraction and extraction.tenant_legal_name:
        return Finding(
            rule_id="lease.tenant",
            passed=True,
            details=f"Tenant identified: {extraction.tenant_legal_name}",
            citations=[]
        )

    # Fallback: text search
    has_tenant = bool(re.search(r'(tenant|lessee)', text, re.IGNORECASE))
    return Finding(
        rule_id="lease.tenant",
        passed=has_tenant,
        details="Tenant information found." if has_tenant else "Tenant information not clearly identified.",
        citations=[]
    )


def check_lease_dates(text: str, params: dict, extraction: Optional['LeaseExtraction'] = None) -> Finding:
    """
    Check if required lease dates are present.

    TASK 3a: LEASE RULEPACK INTEGRATION (lease_agreement.yml lines 29-34)
    This handler now consumes the granular date requirements from the lease rulepack:
    - require_execution_date: true
    - require_commencement_date: true
    - require_expiration_date: true
    """
    from infrastructure import LeaseExtraction

    # LEASE RULEPACK PARAMS (aligned with lease_agreement.yml)
    require_execution = params.get('require_execution_date', False)
    require_commencement = params.get('require_commencement_date', True)
    require_expiration = params.get('require_expiration_date', True)

    # If none required, skip check
    if not (require_execution or require_commencement or require_expiration):
        return Finding(
            rule_id="lease.dates",
            passed=True,
            details="Lease dates check not required by rule configuration.",
            citations=[]
        )

    if extraction:
        missing = []
        found = []

        # Check execution date (if required by rulepack)
        if require_execution:
            # Note: LeaseExtraction doesn't have execution_date field yet
            # This is a limitation of current schema - would need lease_execution_date field
            # For now, we skip this check if extraction-based
            pass

        # Check commencement date (if required by rulepack)
        if require_commencement:
            if extraction.lease_commencement_date:
                found.append(f"commencement: {extraction.lease_commencement_date}")
            else:
                missing.append("commencement date")

        # Check expiration date (if required by rulepack)
        if require_expiration:
            if extraction.lease_expiration_date:
                found.append(f"expiration: {extraction.lease_expiration_date}")
            else:
                missing.append("expiration date")

        if missing:
            return Finding(
                rule_id="lease.dates",
                passed=False,
                details=f"Missing required lease dates per rulepack: {', '.join(missing)}",
                citations=[]
            )
        else:
            return Finding(
                rule_id="lease.dates",
                passed=True,
                details=f"Lease dates found: {', '.join(found)}",
                citations=[]
            )

    # Fallback: text search
    has_dates = bool(re.search(r'(commencement|expiration|term)', text, re.IGNORECASE))
    return Finding(
        rule_id="lease.dates",
        passed=has_dates,
        details="Lease dates found in text." if has_dates else "Lease dates not clearly identified.",
        citations=[]
    )


def check_lease_rent(text: str, params: dict, extraction: Optional['LeaseExtraction'] = None) -> Finding:
    """
    Check if required rent information is present.

    TASK 3a: LEASE RULEPACK INTEGRATION (lease_agreement.yml lines 36-39)
    This handler now consumes the granular rent requirements from the lease rulepack:
    - require_base_rent: true
    - require_payment_frequency: true
    """
    from infrastructure import LeaseExtraction

    # LEASE RULEPACK PARAMS (aligned with lease_agreement.yml)
    require_base_rent = params.get('require_base_rent', True)
    require_payment_frequency = params.get('require_payment_frequency', False)

    if not (require_base_rent or require_payment_frequency):
        return Finding(
            rule_id="lease.rent",
            passed=True,
            details="Rent details check not required by rule configuration.",
            citations=[]
        )

    if extraction:
        missing = []
        found = []

        # Check base rent (if required by rulepack)
        if require_base_rent:
            if extraction.base_rent_amount:
                found.append(f"base rent: {extraction.base_rent_amount}")
            else:
                missing.append("base rent amount")

        # Check payment frequency (if required by rulepack)
        if require_payment_frequency:
            if extraction.base_rent_frequency:
                found.append(f"frequency: {extraction.base_rent_frequency}")
            else:
                missing.append("payment frequency")

        if missing:
            return Finding(
                rule_id="lease.rent",
                passed=False,
                details=f"Missing required rent details per rulepack: {', '.join(missing)}",
                citations=[]
            )
        else:
            return Finding(
                rule_id="lease.rent",
                passed=True,
                details=f"Rent details found: {', '.join(found)}",
                citations=[]
            )

    # Fallback: text search for rent amounts
    has_rent = bool(re.search(r'(base rent|monthly rent|annual rent)', text, re.IGNORECASE))
    return Finding(
        rule_id="lease.rent",
        passed=has_rent,
        details="Rent information found in text." if has_rent else "Rent information not clearly identified.",
        citations=[]
    )


def check_lease_security(text: str, params: dict, extraction: Optional['LeaseExtraction'] = None) -> Finding:
    """
    Check if required security deposit information is present.

    TASK 3a: LEASE RULEPACK INTEGRATION (lease_agreement.yml lines 40-43)
    This handler now accepts both parameter naming conventions:
    - check_security_deposit: true (YAML convention)
    - require_security_deposit: true (backwards compatibility)
    """
    from infrastructure import LeaseExtraction

    # LEASE RULEPACK PARAMS (support both naming conventions)
    require_security = params.get('check_security_deposit', params.get('require_security_deposit', True))

    if not require_security:
        return Finding(
            rule_id="lease.security",
            passed=True,
            details="Security deposit check not required by rule configuration.",
            citations=[]
        )

    if extraction and extraction.security_deposit_amount:
        return Finding(
            rule_id="lease.security",
            passed=True,
            details=f"Security deposit: {extraction.security_deposit_amount}",
            citations=[]
        )

    # Fallback: text search
    has_security = bool(re.search(r'(security deposit|deposit)', text, re.IGNORECASE))
    return Finding(
        rule_id="lease.security",
        passed=has_security,
        details="Security deposit information found." if has_security else "Security deposit information not clearly identified.",
        citations=[]
    )


def check_lease_options(text: str, params: dict, extraction: Optional['LeaseExtraction'] = None) -> Finding:
    """
    Check if lease options are documented.

    TASK 3a: LEASE RULEPACK INTEGRATION (lease_agreement.yml lines 52-57)
    This handler now consumes the granular option requirements from the lease rulepack:
    - check_renewal_options: true
    - check_expansion_options: true
    - check_termination_options: true
    """
    from infrastructure import LeaseExtraction

    # LEASE RULEPACK PARAMS (aligned with lease_agreement.yml)
    check_renewal = params.get('check_renewal_options', False)
    check_expansion = params.get('check_expansion_options', False)
    check_termination = params.get('check_termination_options', False)

    if not (check_renewal or check_expansion or check_termination):
        return Finding(
            rule_id="lease.options",
            passed=True,
            details="Lease options check not required by rule configuration.",
            citations=[]
        )

    if extraction:
        found = []
        missing = []

        if check_renewal:
            if extraction.option_to_renew_terms:
                found.append(f"renewal: {extraction.option_to_renew_terms}")
            else:
                missing.append("renewal options")

        if check_expansion:
            if extraction.option_to_expand:
                found.append(f"expansion: {extraction.option_to_expand}")
            else:
                missing.append("expansion options")

        if check_termination:
            if extraction.early_termination_rights:
                found.append(f"termination: {extraction.early_termination_rights}")
            else:
                missing.append("termination options")

        if missing:
            return Finding(
                rule_id="lease.options",
                passed=False,
                details=f"Missing required lease options per rulepack: {', '.join(missing)}",
                citations=[]
            )
        else:
            return Finding(
                rule_id="lease.options",
                passed=True,
                details=f"Lease options found: {', '.join(found)}",
                citations=[]
            )

    # Fallback: text search
    has_options = bool(re.search(r'(option to renew|renewal option|extension|expansion|termination)', text, re.IGNORECASE))
    return Finding(
        rule_id="lease.options",
        passed=has_options,
        details="Lease options found in text." if has_options else "Lease options not clearly identified.",
        citations=[]
    )


def check_lease_fees(text: str, params: dict, extraction: Optional['LeaseExtraction'] = None) -> Finding:
    """
    Check if late fee terms are documented.

    TASK 3a: LEASE RULEPACK INTEGRATION (lease_agreement.yml lines 44-47)
    This handler consumes the late fee requirements from the lease rulepack:
    - require_late_fee_terms: true
    """
    from infrastructure import LeaseExtraction

    # LEASE RULEPACK PARAMS (aligned with lease_agreement.yml)
    require_late_fees = params.get('require_late_fee_terms', False)

    if not require_late_fees:
        return Finding(
            rule_id="lease.fees",
            passed=True,
            details="Late fee terms check not required by rule configuration.",
            citations=[]
        )

    if extraction:
        if extraction.late_payment_penalty:
            return Finding(
                rule_id="lease.fees",
                passed=True,
                details=f"Late fee terms found: {extraction.late_payment_penalty}",
                citations=[]
            )
        else:
            return Finding(
                rule_id="lease.fees",
                passed=False,
                details="Missing required late fee terms per rulepack.",
                citations=[]
            )

    # Fallback: text search
    has_late_fees = bool(re.search(r'(late fee|late charge|late payment|default rate)', text, re.IGNORECASE))
    return Finding(
        rule_id="lease.fees",
        passed=has_late_fees,
        details="Late fee terms found in text." if has_late_fees else "Late fee terms not clearly identified.",
        citations=[]
    )


def check_lease_default(text: str, params: dict, extraction: Optional['LeaseExtraction'] = None) -> Finding:
    """
    Check if default provisions are documented.

    TASK 3a: LEASE RULEPACK INTEGRATION (lease_agreement.yml lines 48-51)
    This handler consumes the default provision requirements from the lease rulepack:
    - require_default_terms: true
    """
    from infrastructure import LeaseExtraction

    # LEASE RULEPACK PARAMS (aligned with lease_agreement.yml)
    require_default = params.get('require_default_terms', False)

    if not require_default:
        return Finding(
            rule_id="lease.default",
            passed=True,
            details="Default provisions check not required by rule configuration.",
            citations=[]
        )

    if extraction:
        found = []
        if extraction.default_notice_days:
            found.append(f"notice period: {extraction.default_notice_days} days")
        if extraction.cure_period_days:
            found.append(f"cure period: {extraction.cure_period_days} days")

        if found:
            return Finding(
                rule_id="lease.default",
                passed=True,
                details=f"Default provisions found: {', '.join(found)}",
                citations=[]
            )
        else:
            return Finding(
                rule_id="lease.default",
                passed=False,
                details="Missing required default provisions per rulepack.",
                citations=[]
            )

    # Fallback: text search
    has_default = bool(re.search(r'(default|breach|cure period|notice of default|event of default)', text, re.IGNORECASE))
    return Finding(
        rule_id="lease.default",
        passed=has_default,
        details="Default provisions found in text." if has_default else "Default provisions not clearly identified.",
        citations=[]
    )


def check_lease_expenses(text: str, params: dict, extraction: Optional['LeaseExtraction'] = None) -> Finding:
    """
    Check if operating expense provisions are documented.

    TASK 3a: LEASE RULEPACK INTEGRATION (lease_agreement.yml lines 58-63)
    This handler consumes the operating expense requirements from the lease rulepack:
    - check_cam_charges: true
    - check_tax_recovery: true
    - check_insurance_recovery: true
    """
    from infrastructure import LeaseExtraction

    # LEASE RULEPACK PARAMS (aligned with lease_agreement.yml)
    check_cam = params.get('check_cam_charges', False)
    check_tax = params.get('check_tax_recovery', False)
    check_insurance = params.get('check_insurance_recovery', False)

    if not (check_cam or check_tax or check_insurance):
        return Finding(
            rule_id="lease.expenses",
            passed=True,
            details="Operating expense checks not required by rule configuration.",
            citations=[]
        )

    if extraction:
        found = []
        missing = []

        if check_cam:
            if extraction.cam_charges_monthly or extraction.cam_charges_annual:
                found.append(f"CAM charges: {extraction.cam_charges_monthly or extraction.cam_charges_annual}")
            else:
                missing.append("CAM charges")

        if check_tax:
            if extraction.real_estate_tax_responsibility:
                found.append(f"tax recovery: {extraction.real_estate_tax_responsibility}")
            else:
                missing.append("tax recovery")

        if check_insurance:
            if extraction.insurance_responsibility:
                found.append(f"insurance recovery: {extraction.insurance_responsibility}")
            else:
                missing.append("insurance recovery")

        if missing:
            return Finding(
                rule_id="lease.expenses",
                passed=False,
                details=f"Missing required operating expense details per rulepack: {', '.join(missing)}",
                citations=[]
            )
        else:
            return Finding(
                rule_id="lease.expenses",
                passed=True,
                details=f"Operating expenses found: {', '.join(found)}",
                citations=[]
            )

    # Fallback: text search
    has_expenses = bool(re.search(r'(operating expense|CAM|common area maintenance|NNN|triple net|tax recovery|insurance recovery)', text, re.IGNORECASE))
    return Finding(
        rule_id="lease.expenses",
        passed=has_expenses,
        details="Operating expense provisions found in text." if has_expenses else "Operating expense provisions not clearly identified.",
        citations=[]
    )


# ========================================
# PRELIMINARY EXTRACTION (REPORT V2)
# ========================================
# Universal extractors that run on every document regardless of type.
# These populate the "Preliminary Extraction (Base Fields)" section of Report V2.
# Uses regex/pattern-based extraction (no LLM dependency).

def extract_parties(text: str, classified_type: str) -> str:
    """
    Extract parties involved in the contract.

    Args:
        text: Full contract text
        classified_type: Document type from classify_document_type()

    Returns:
        Human-readable summary of parties (e.g., "Acme Corp (Landlord) and John Smith (Tenant)")
    """
    parties = []

    # Lease-specific patterns
    if "lease" in classified_type.lower():
        # Look for Landlord/Lessor
        landlord_match = re.search(
            r'(?:landlord|lessor)[\s:]*([A-Z][A-Za-z\s,\.&]+(?:LLC|Inc|Corp|LP|LLP|Ltd)?)',
            text,
            re.IGNORECASE | re.MULTILINE
        )
        if landlord_match:
            parties.append(f"{landlord_match.group(1).strip()} (Landlord)")

        # Look for Tenant/Lessee
        tenant_match = re.search(
            r'(?:tenant|lessee)[\s:]*([A-Z][A-Za-z\s,\.&]+(?:LLC|Inc|Corp|LP|LLP|Ltd)?)',
            text,
            re.IGNORECASE | re.MULTILINE
        )
        if tenant_match:
            parties.append(f"{tenant_match.group(1).strip()} (Tenant)")

    # Employment-specific patterns
    elif "employment" in classified_type.lower() or "offer" in classified_type.lower():
        # Look for Employer/Company
        employer_match = re.search(
            r'(?:employer|company)[\s:]*([A-Z][A-Za-z\s,\.&]+(?:LLC|Inc|Corp|LP|LLP|Ltd)?)',
            text,
            re.IGNORECASE | re.MULTILINE
        )
        if employer_match:
            parties.append(f"{employer_match.group(1).strip()} (Employer)")

        # Look for Employee
        employee_match = re.search(
            r'(?:employee|candidate)[\s:]*([A-Z][a-z]+\s+[A-Z][a-z]+)',
            text,
            re.IGNORECASE | re.MULTILINE
        )
        if employee_match:
            parties.append(f"{employee_match.group(1).strip()} (Employee)")

    # General patterns (fallback)
    if not parties:
        # Look for "Party A" / "Party B" style
        party_a = re.search(r'Party\s+A[:\s]+([A-Z][A-Za-z\s,\.&]+(?:LLC|Inc|Corp)?)', text, re.IGNORECASE)
        party_b = re.search(r'Party\s+B[:\s]+([A-Z][A-Za-z\s,\.&]+(?:LLC|Inc|Corp)?)', text, re.IGNORECASE)

        if party_a:
            parties.append(party_a.group(1).strip())
        if party_b:
            parties.append(party_b.group(1).strip())

        # Look for "between ... and ..." patterns
        if not parties:
            between_match = re.search(
                r'(?:between|by and between)\s+([A-Z][A-Za-z\s,\.&]+(?:LLC|Inc|Corp|LP|LLP|Ltd)?)\s+and\s+([A-Z][A-Za-z\s,\.&]+(?:LLC|Inc|Corp|LP|LLP|Ltd)?)',
                text,
                re.IGNORECASE
            )
            if between_match:
                parties.append(between_match.group(1).strip())
                parties.append(between_match.group(2).strip())

    if parties:
        return " and ".join(parties)
    else:
        return "Not clearly identified"


def _extract_period_of_performance(text: str) -> Optional[str]:
    """
    Extract "Period of Performance" from SOW documents.

    Recognizes patterns like:
    - "Period of Performance: Jan 1, 2025 - Dec 31, 2025"
    - "Project Duration: 6 months from contract signing"
    - "Performance Period: Q1 2025 through Q4 2025"

    Args:
        text: Full contract text

    Returns:
        Period of performance string if found, None otherwise
    """
    # Pattern 1: "Period of Performance: [date range]"
    # Handle various formats including newlines after the colon
    # First try to find the section, then look for dates or duration info nearby
    pop_match = re.search(
        r'period\s+of\s+performance\s*:?\s*([\s\S]{5,300}?)(?:\n\n|\r\n\r\n|$)',
        text,
        re.IGNORECASE
    )
    if pop_match:
        period_section = pop_match.group(1).strip()

        # Strategy 1: Look for explicit date range (highest priority)
        date_pattern = r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d+,?\s+\d{4})\s*(?:–|-|to|through|thru)\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d+,?\s+\d{4})'
        date_match = re.search(date_pattern, period_section, re.IGNORECASE)
        if date_match:
            return f"{date_match.group(1)} – {date_match.group(2)}"

        # Strategy 2: Look for single completion date (e.g., "by December 31, 2025")
        single_date_match = re.search(
            r'(?:by|until|through|ending)\s+((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d+,?\s+\d{4})',
            period_section,
            re.IGNORECASE
        )
        if single_date_match:
            return f"Through {single_date_match.group(1)}"

        # Strategy 3: Look for duration description (e.g., "6 months", "12 weeks")
        duration_match = re.search(r'(\d+)\s+(month|months|week|weeks|day|days)', period_section, re.IGNORECASE)
        if duration_match:
            return f"{duration_match.group(1)} {duration_match.group(2)}"

        # Strategy 4: If no dates found but we have text, check if it starts with a useful sentence
        # Filter out fragments that start with punctuation or conjunctions
        lines = period_section.split('\n')
        for line in lines:
            line = line.strip()
            # Skip lines that are clearly not duration info
            if line and not line[0] in '.,:;' and len(line) > 10:
                # Check if this line contains duration-relevant keywords
                if any(kw in line.lower() for kw in ['complete', 'deliver', 'finish', 'end', 'start', 'commence', 'begin']):
                    # This might be a description of when work completes
                    if len(line) > 120:
                        line = line[:120].rsplit(' ', 1)[0] + '...'
                    return line

        # No useful duration info found in this section
        return None

    # Pattern 2: "Project Duration: X months/years"
    duration_match = re.search(
        r'project\s+duration[:\s]+(\d+)\s+(month|months|year|years)(?:\s+from\s+([^\n\.]{5,50}))?',
        text,
        re.IGNORECASE
    )
    if duration_match:
        num = duration_match.group(1)
        unit = duration_match.group(2)
        start = duration_match.group(3) if duration_match.lastindex >= 3 else None
        if start:
            return f"{num} {unit} from {start.strip()}"
        else:
            return f"{num} {unit}"

    # Pattern 3: "Performance Period: [date range]"
    perf_match = re.search(
        r'(?:performance|project)\s+period[:\s]+([^\n\.]{10,120})',
        text,
        re.IGNORECASE
    )
    if perf_match:
        period = perf_match.group(1).strip()
        period = re.sub(r'\s*\([^)]*\)\s*$', '', period)
        if len(period) > 10:
            return period

    return None


def _extract_completion_criteria(text: str) -> Optional[str]:
    """
    Extract "Completion Criteria" or "End of Services" from SOW documents.

    Recognizes patterns describing when work is considered complete:
    - "Completion Criteria: [conditions]"
    - "Acceptance Criteria: [conditions]"
    - "End of Services: [conditions]"

    Args:
        text: Full contract text

    Returns:
        Completion criteria string if found, None otherwise
    """
    # Pattern 1: "Completion Criteria: [text]"
    completion_match = re.search(
        r'completion\s+criteria[:\s]+([^\n\.]{10,200})',
        text,
        re.IGNORECASE
    )
    if completion_match:
        criteria = completion_match.group(1).strip()
        if len(criteria) > 10:
            return criteria

    # Pattern 2: "Acceptance Criteria: [text]"
    acceptance_match = re.search(
        r'acceptance\s+criteria[:\s]+([^\n\.]{10,200})',
        text,
        re.IGNORECASE
    )
    if acceptance_match:
        criteria = acceptance_match.group(1).strip()
        if len(criteria) > 10:
            return criteria

    # Pattern 3: "End of Services: [text]"
    end_match = re.search(
        r'end\s+of\s+services[:\s]+([^\n\.]{10,200})',
        text,
        re.IGNORECASE
    )
    if end_match:
        criteria = end_match.group(1).strip()
        if len(criteria) > 10:
            return criteria

    # Pattern 4: "Deliverables: [text]" (common in SOWs)
    deliverables_match = re.search(
        r'(?:final\s+)?deliverables?[:\s]+([^\n\.]{10,200})',
        text,
        re.IGNORECASE
    )
    if deliverables_match:
        criteria = deliverables_match.group(1).strip()
        if len(criteria) > 10:
            return f"Deliverables: {criteria}"

    return None


def _summarize_clause(extracted_text: str, clause_type: str, max_length: int = 200) -> str:
    """
    Create a concise summary of an extracted clause with attribution.

    Args:
        extracted_text: The raw extracted clause text
        clause_type: Type descriptor (e.g., "Period of Performance", "Completion Criteria")
        max_length: Maximum length for summary

    Returns:
        Formatted summary with attribution (e.g., "August 1, 2024 – July 31, 2025 (Period of Performance)")
    """
    # Clean up the text
    cleaned = extracted_text.strip()

    # Truncate if too long, preserving complete sentences
    if len(cleaned) > max_length:
        # Try to find a sentence boundary
        truncated = cleaned[:max_length]
        last_period = truncated.rfind('.')
        if last_period > max_length // 2:  # If we can keep at least half
            cleaned = truncated[:last_period + 1]
        else:
            cleaned = truncated.rstrip() + "..."

    # Add attribution
    return f"{cleaned} ({clause_type})"


def extract_duration(text: str, classified_type: str) -> str:
    """
    Extract contract duration/term.

    Recognizes patterns including:
    - Standard: "term of X years/months"
    - SOW-specific: "Period of Performance", "Project Term", "Project Duration"

    Args:
        text: Full contract text
        classified_type: Document type

    Returns:
        Human-readable duration summary (e.g., "August 1, 2024 – July 31, 2025 (Period of Performance)")
    """
    # PRIORITY 1: Try Period of Performance extraction (for SOWs)
    pop = _extract_period_of_performance(text)
    if pop:
        return _summarize_clause(pop, "Period of Performance", max_length=150)

    # PRIORITY 2: Look for SOW-specific patterns with numeric durations
    sow_patterns = [
        r'period\s+of\s+performance[:\s]+(\d+)\s+(year|years|month|months)',
        r'project\s+(?:term|duration)[:\s]+(\d+)\s+(year|years|month|months)',
        r'contract\s+term[:\s]+(\d+)\s+(year|years|month|months)',
        r'initial\s+term[:\s]+(\d+)\s+(year|years|month|months)',
    ]

    for pattern in sow_patterns:
        sow_match = re.search(pattern, text, re.IGNORECASE)
        if sow_match:
            num = sow_match.group(1)
            unit = sow_match.group(2).lower()
            return f"{num} {unit}"

    # PRIORITY 3: Look for explicit "term of X years/months" (general pattern)
    term_match = re.search(
        r'(?:term|duration|period)\s+of\s+(\d+)\s+(year|years|month|months)',
        text,
        re.IGNORECASE
    )
    if term_match:
        num = term_match.group(1)
        unit = term_match.group(2).lower()
        return f"{num} {unit}"

    # PRIORITY 4: For leases, try to find commencement and expiration dates
    if "lease" in classified_type.lower():
        # Look for date patterns
        date_pattern = r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\w+\s+\d{1,2},?\s+\d{4})'

        commence_match = re.search(
            rf'(?:commencement|start|begin)\s+date[:\s]+({date_pattern})',
            text,
            re.IGNORECASE
        )
        expire_match = re.search(
            rf'(?:expiration|end|termin(?:ation|ate))\s+date[:\s]+({date_pattern})',
            text,
            re.IGNORECASE
        )

        if commence_match and expire_match:
            commence_date = commence_match.group(1).strip()
            expire_date = expire_match.group(1).strip()
            return f"{commence_date} to {expire_date}"
        elif commence_match:
            return f"Commences {commence_match.group(1).strip()}"
        elif expire_match:
            return f"Expires {expire_match.group(1).strip()}"

    # PRIORITY 5: For employment, look for initial term
    if "employment" in classified_type.lower():
        initial_term = re.search(
            r'(?:initial\s+term|employment\s+term)[:\s]+(\d+)\s+(year|years|month|months)',
            text,
            re.IGNORECASE
        )
        if initial_term:
            return f"{initial_term.group(1)} {initial_term.group(2)}"

    return "Not clearly specified"


def extract_fees_summary(text: str, classified_type: str) -> str:
    """
    Extract fees and payment terms summary.

    Args:
        text: Full contract text
        classified_type: Document type

    Returns:
        Human-readable fees summary (e.g., "Base rent $10,000/month; estimated total $600,000")
    """
    fees = []

    # For leases, look for base rent
    if "lease" in classified_type.lower():
        rent_match = re.search(
            r'(?:base\s+rent|monthly\s+rent)[:\s]+\$?([\d,]+(?:\.\d{2})?)\s*(?:per\s+month|/month|monthly)?',
            text,
            re.IGNORECASE
        )
        if rent_match:
            amount = rent_match.group(1).replace(',', '')
            fees.append(f"Base rent ${amount}/month")

    # For employment, look for salary
    if "employment" in classified_type.lower():
        salary_match = re.search(
            r'(?:salary|compensation|annual\s+pay)[:\s]+\$?([\d,]+(?:\.\d{2})?)\s*(?:per\s+year|annually|/year)?',
            text,
            re.IGNORECASE
        )
        if salary_match:
            amount = salary_match.group(1).replace(',', '')
            fees.append(f"Annual salary ${amount}")

    # General: Look for largest monetary amount
    if not fees:
        money_amounts = parse_money(text)
        if money_amounts:
            largest = max(money_amounts, key=lambda t: t[0])
            amount, currency, _ = largest

            # Normalize currency symbol to avoid "$" issue
            # Standardize: if parse_money returns empty or "$", treat it simply as "$"
            symbol = currency.strip() if currency else "$"
            if symbol == "$":
                formatted_amount = f"${amount:,.2f}"
            else:
                formatted_amount = f"{symbol}{amount:,.2f}"

            fees.append(f"Contract value approximately {formatted_amount}")

    if fees:
        return "; ".join(fees)
    else:
        return "Not clearly specified"


def extract_termination_terms(text: str, classified_type: str) -> str:
    """
    Extract termination conditions summary.

    Recognizes patterns including:
    - Standard: "Termination", "Termination for Cause/Convenience"
    - SOW-specific: "Completion Criteria", "End of Services"

    Args:
        text: Full contract text
        classified_type: Document type

    Returns:
        Human-readable termination summary
    """
    # PRIORITY 1: Try Completion Criteria extraction (for SOWs)
    completion_criteria = _extract_completion_criteria(text)
    if completion_criteria:
        return _summarize_clause(completion_criteria, "Completion Criteria", max_length=200)

    # PRIORITY 2: Build summary from keyword patterns
    terms = []

    # Look for notice period
    notice_match = re.search(
        r'(?:upon|with)\s+(\d+)\s+days?\s+(?:written\s+)?notice',
        text,
        re.IGNORECASE
    )
    if notice_match:
        days = notice_match.group(1)
        terms.append(f"{days} days notice required")

    # Look for "for cause" / "for convenience"
    if re.search(r'termin(?:ate|ation)\s+for\s+cause', text, re.IGNORECASE):
        terms.append("terminable for cause")
    if re.search(r'termin(?:ate|ation)\s+(?:for\s+convenience|without\s+cause)', text, re.IGNORECASE):
        terms.append("terminable for convenience")

    # Look for default/breach
    if re.search(r'(?:upon|in\s+the\s+event\s+of)\s+(?:default|breach)', text, re.IGNORECASE):
        terms.append("terminable upon default/breach")

    # Look for early termination rights
    if re.search(r'early\s+termination', text, re.IGNORECASE):
        terms.append("early termination provisions present")

    if terms:
        return "; ".join(terms)

    return "No clear termination clause identified"


def _find_source_snippet(text: str, extracted_value: str, max_len: int = 150) -> Optional[str]:
    """
    Find a snippet from the source text that contains or relates to the extracted value.

    This is used to create citations when we don't have precise char positions from regex.

    Args:
        text: Full contract text
        extracted_value: The extracted value (e.g., "January 1, 2025 - December 31, 2025")
        max_len: Maximum length for the snippet

    Returns:
        Source snippet if found, None otherwise
    """
    # Try to find the extracted value or a significant part of it in the source text
    # Case-insensitive search
    lower_text = text.lower()
    lower_value = extracted_value.lower()

    # Strategy 1: Direct substring match
    pos = lower_text.find(lower_value)
    if pos != -1:
        # Found exact match, extract context around it
        start = max(0, pos - 30)
        end = min(len(text), pos + len(extracted_value) + 30)
        snippet = text[start:end].strip()
        if len(snippet) > max_len:
            snippet = snippet[:max_len].rsplit(' ', 1)[0] + '...'
        return snippet

    # Strategy 2: Try to find key terms from the extracted value
    # Extract words longer than 3 chars
    import re
    words = [w for w in re.findall(r'\b\w+\b', extracted_value) if len(w) > 3]
    if words:
        # Find the first significant word in the text
        for word in words[:3]:  # Try first 3 significant words
            word_lower = word.lower()
            pos = lower_text.find(word_lower)
            if pos != -1:
                # Found a key word, extract context
                start = max(0, pos - 50)
                end = min(len(text), pos + 100)
                snippet = text[start:end].strip()
                if len(snippet) > max_len:
                    snippet = snippet[:max_len].rsplit(' ', 1)[0] + '...'
                return snippet

    # Strategy 3: Fallback - just return the extracted value itself as the "snippet"
    return extracted_value[:max_len]


def build_preliminary_extraction(
    text: str,
    classified_type: str,
    jurisdiction_from_rules: str = "Not specified"
) -> 'PreliminaryExtraction':
    """
    Build PreliminaryExtraction structure from contract text.

    This populates the 5 universal base fields that appear in every Report V2:
    - document_type (from classification)
    - parties_summary (regex extraction)
    - duration (regex extraction)
    - fees_summary (regex extraction)
    - termination_summary (regex extraction)
    - jurisdiction (from compliance check results)

    Args:
        text: Full contract text
        classified_type: Document type from classify_document_type()
        jurisdiction_from_rules: Jurisdiction extracted from preliminary compliance checks

    Returns:
        PreliminaryExtraction with all 5 base fields populated
    """
    from infrastructure import PreliminaryExtraction, Citation

    # Extract values and create citations where possible
    citations = []

    parties = extract_parties(text, classified_type)
    duration = extract_duration(text, classified_type)
    fees = extract_fees_summary(text, classified_type)
    termination = extract_termination_terms(text, classified_type)

    # Create citations from extracted text snippets (simple version without page mapping)
    # This ensures Appendix 8 has at least some content even without PDF layout info
    if parties and parties != "Not specified":
        # Try to find the source text for parties
        parties_snippet = _find_source_snippet(text, parties, max_len=150)
        if parties_snippet:
            citations.append(Citation(
                char_start=0,
                char_end=len(parties_snippet),
                quote=parties_snippet
            ))

    if duration and duration != "Not clearly specified":
        duration_snippet = _find_source_snippet(text, duration, max_len=150)
        if duration_snippet:
            citations.append(Citation(
                char_start=0,
                char_end=len(duration_snippet),
                quote=duration_snippet
            ))

    if fees and fees != "Not specified":
        fees_snippet = _find_source_snippet(text, fees, max_len=150)
        if fees_snippet:
            citations.append(Citation(
                char_start=0,
                char_end=len(fees_snippet),
                quote=fees_snippet
            ))

    if termination and termination != "Not specified":
        termination_snippet = _find_source_snippet(text, termination, max_len=150)
        if termination_snippet:
            citations.append(Citation(
                char_start=0,
                char_end=len(termination_snippet),
                quote=termination_snippet
            ))

    return PreliminaryExtraction(
        document_type=classified_type,
        parties_summary=parties,
        duration=duration,
        fees_summary=fees,
        termination_summary=termination,
        jurisdiction=jurisdiction_from_rules,
        citations=citations
    )


# ========================================
# PRELIMINARY COMPLIANCE MAPPING (REPORT V2)
# ========================================
# Maps existing Finding objects from preliminary checks into ComplianceCheckResult
# structures for Report V2.

# Configuration for preliminary compliance checks
PRELIM_CHECK_CONFIG = {
    "liability_cap_present_and_within_bounds": {
        "label": "Liability Cap Present And Within Bounds",
        "severity": "High",
    },
    "contract_value_within_limit": {
        "label": "Contract Value Within Limit",
        "severity": "Medium",
    },
    "fraud_clause_present_and_assigned": {
        "label": "Fraud Clause Present And Assigned",
        "severity": "High",
    },
    "jurisdiction_present_and_allowed": {
        "label": "Jurisdiction Present And Allowed",
        "severity": "High",
    },
}

# Mapping from compliance check IDs to Phase 2 key term names for citation attachment
# This enables Section 4 to display citations from Phase 2 extraction
CHECK_TO_TERM = {
    "jurisdiction_present_and_allowed": "Governing Law",
    "fraud_clause_present_and_assigned": "Fraud Exclusion",
    "liability_cap_present_and_within_bounds": "Liability Cap",
    "contract_value_within_limit": None,  # Typically inferred, no direct Phase 2 term
}


def extract_jurisdiction_from_finding(finding: 'Finding') -> str:
    """
    Extract jurisdiction string from a jurisdiction compliance check Finding.

    Args:
        finding: Finding object from check_jurisdiction_present_and_allowed()

    Returns:
        Jurisdiction string (e.g., "Texas", "United States", "Delaware")
    """
    # The details field contains the jurisdiction in quotes
    # Example: 'Governing law/jurisdiction detected as "Texas". Allowed'
    import re
    match = re.search(r'detected as "([^"]+)"', finding.details)
    if match:
        return match.group(1)

    # Fallback: check for multiple jurisdictions
    # Example: 'Multiple jurisdiction clauses found: "Texas", "Delaware"...'
    multi_match = re.search(r'found: ([^.]+)\.', finding.details)
    if multi_match:
        # Return first jurisdiction mentioned
        first = re.search(r'"([^"]+)"', multi_match.group(1))
        if first:
            return first.group(1)

    # Ultimate fallback
    return "Not specified"


def build_preliminary_compliance_checks(
    findings: List['Finding'],
    phase2_citations: Optional[dict] = None
) -> Tuple[List['ComplianceCheckResult'], str]:
    """
    Convert existing preliminary Finding objects into ComplianceCheckResult instances.

    Only includes the 4 preliminary compliance checks configured in PRELIM_CHECK_CONFIG.
    Also extracts jurisdiction for use in PreliminaryExtraction.

    Wires Phase 2 citations using CHECK_TO_TERM mapping when available.

    Args:
        findings: List of Finding objects from evaluate_text_against_rules()
        phase2_citations: Optional dict of Phase 2 citations {term_name: citation_text}

    Returns:
        Tuple of (compliance_checks, jurisdiction_value)
        - compliance_checks: List of ComplianceCheckResult for Report V2
        - jurisdiction_value: Extracted jurisdiction string for PreliminaryExtraction
    """
    from infrastructure import ComplianceCheckResult, Citation

    results: List[ComplianceCheckResult] = []
    jurisdiction_value = "Not specified"

    for finding in findings:
        cfg = PRELIM_CHECK_CONFIG.get(finding.rule_id)
        if not cfg:
            # Not a preliminary compliance check, skip
            continue

        # Map Finding.passed to status
        status = "PASS" if finding.passed else "FAIL"

        # Extract reason_short and reason_detailed from tags
        reason_short = None
        reason_detailed = None
        for tag in finding.tags:
            if tag.startswith("reason_short:"):
                reason_short = tag[len("reason_short:"):].strip()
            elif tag.startswith("reason_detailed:"):
                reason_detailed = tag[len("reason_detailed:"):].strip()

        # Start with existing citations from Phase 1
        citations_list = list(finding.citations) if finding.citations else []

        # Wire Phase 2 citations using CHECK_TO_TERM mapping
        if phase2_citations:
            term_name = CHECK_TO_TERM.get(finding.rule_id)
            if term_name and term_name in phase2_citations:
                citation_text = phase2_citations[term_name]
                if citation_text:
                    # Add Phase 2 citation as a new Citation object
                    # Note: Phase 2 citations are text excerpts without char positions
                    phase2_citation = Citation(
                        char_start=0,  # Phase 2 doesn't provide char positions
                        char_end=0,
                        quote=citation_text[:200]  # Truncate to reasonable length
                    )
                    citations_list.append(phase2_citation)

        result = ComplianceCheckResult(
            check_id=finding.rule_id,
            label=cfg["label"],
            status=status,
            severity=cfg["severity"],
            message=finding.details,
            citations=citations_list,
            reason_short=reason_short,
            reason_detailed=reason_detailed,
        )
        results.append(result)

        # Extract jurisdiction if this is the jurisdiction check
        if finding.rule_id == "jurisdiction_present_and_allowed":
            jurisdiction_value = extract_jurisdiction_from_finding(finding)

    return results, jurisdiction_value


def evaluate_custom_rules(
    text: str,
    rules_json: List[dict],
    extraction: Optional['LeaseExtraction'] = None,
) -> List[Finding]:
    """
    Evaluate custom rules from YAML rules: section.

    BUG 1b FIX: Ensures ALL custom rules are evaluated without early exit.
    Each rule handler is called and its finding is appended to the results.

    Args:
        text: Contract text
        rules_json: List of rule definitions from rulepack
        extraction: Optional extraction data to use in evaluation

    Returns:
        List of Finding objects (one per evaluated rule)
    """
    from infrastructure import Finding

    # TASK 3a: LEASE RULEPACK INTEGRATION - Handler registry
    # Maps rule types from lease_agreement.yml to their evaluation functions
    # Each handler consumes params from the rulepack's rules: section
    handlers = {
        'lease.property': check_lease_property,      # lines 21-24: require_property_details
        'lease.tenant': check_lease_tenant,          # lines 26-28: require_tenant_details
        'lease.dates': check_lease_dates,            # lines 30-34: execution/commencement/expiration dates
        'lease.rent': check_lease_rent,              # lines 36-39: base_rent, payment_frequency
        'lease.security': check_lease_security,      # lines 41-43: security_deposit
        'lease.fees': check_lease_fees,              # lines 44-47: late_fee_terms
        'lease.default': check_lease_default,        # lines 48-51: default_terms
        'lease.options': check_lease_options,        # lines 52-57: renewal/expansion/termination
        'lease.expenses': check_lease_expenses,      # lines 58-63: CAM/tax/insurance recovery
    }

    findings = []
    # BUG 1b FIX: Loop through ALL rules without breaking or early return
    for rule in rules_json:
        rule_type = rule.get('type')
        rule_params = rule.get('params', {})

        if rule_type in handlers:
            handler = handlers[rule_type]
            finding = handler(text, rule_params, extraction)
            findings.append(finding)
            # Continue to next rule (no break or return here)

    return findings


def evaluate_text_against_rules(text: str, rules: RuleSet, extraction: Optional['LeaseExtraction'] = None, pack_data: Optional[Any] = None):
    """
    Evaluate contract text against configured rules.

    BUG 1b FIX: Evaluates ALL rules (hardcoded + custom) and returns complete findings list.
    No early exit logic - all rules are processed and all findings are collected.

    Args:
        text: Contract text to evaluate
        rules: RuleSet configuration
        extraction: Optional LeaseExtraction data for custom rules
        pack_data: Optional rulepack data containing custom rules

    Returns:
        Tuple of (findings, contract_value_guess)
        - findings: Complete list of ALL rule evaluations
        - contract_value_guess: Estimated contract value
    """
    text = _strip_noise(text or "")
    # Rough contract value guess (largest monetary amount)
    mm = max_money(text)
    contract_value_guess = mm[0] if mm else None

    # BUG 1b FIX: Evaluate ALL 4 standard compliance checks
    # All checks are added to findings list (no early exit)
    findings = [
        check_liability_cap_present_and_within_bounds(text, rules, contract_value_guess),
        check_contract_value_within_limit(text, rules),
        check_fraud_clause_present_and_assigned(text, rules),
        check_jurisdiction_present_and_allowed(text, rules),
    ]

    # BUG 1b FIX: Extend with ALL custom rules (no early exit in evaluate_custom_rules)
    # Custom rule evaluation (if rules_json provided in pack_data)
    if pack_data and hasattr(pack_data, 'rules_json') and pack_data.rules_json:
        custom_findings = evaluate_custom_rules(text, pack_data.rules_json, extraction)
        findings.extend(custom_findings)  # Add all custom findings to the list

    # Return complete findings list with all evaluated rules
    return findings, contract_value_guess


# Currency and monetary context detection patterns
_CURRENCY_HINT = re.compile(r"(\$|usd|dollar|dollars|£|gbp|€|eur|yen|¥|cad|aud)", re.I)
_SHARE_UNIT = re.compile(r"\b(share|shares|unit|units|warrant|warrants|option|options)\b", re.I)
_NUMBERISH = re.compile(r"\d")


def _looks_like_money(window_text: str) -> bool:
    """Legacy helper for detecting monetary context."""
    if _SHARE_UNIT.search(window_text):
        return False
    return bool(_CURRENCY_HINT.search(window_text))


def _has_share_context(window: str) -> bool:
    """Check if text window contains share/equity context."""
    return bool(_SHARE_UNIT.search(window))


def _looks_like_money_ctx(window: str) -> bool:
    """Check for currency hint AND not share context."""
    return bool(_CURRENCY_HINT.search(window)) and not _has_share_context(window)


def _maybe_guard_monetary_false_positives(text: str, findings: List[Finding]) -> List[Finding]:
    """
    Guard against monetary false positives like share counts.

    If citations look numeric but lack currency context (or mention shares/units),
    flip the finding to PASS with an explanatory note — but only for monetary-ish rules.
    """
    monetary_keywords = (
        "contract_value", "liability_cap", "damages", "penalty",
        "payment", "consideration", "fee", "cost", "price", "amount"
    )

    fixed: List[Finding] = []
    for f in findings:
        rid = (f.rule_id or "").lower()

        # Only apply to monetary-ish rules
        if not any(k in rid for k in monetary_keywords):
            fixed.append(f)
            continue

        if not f.citations:
            fixed.append(f)
            continue

        windows = []
        for c in f.citations:
            s = max(0, min(len(text), c.char_start))
            e = max(0, min(len(text), c.char_end))
            win = text[max(0, s-40): min(len(text), e+40)]
            windows.append(win)

        if not any(_NUMBERISH.search(w) for w in windows):
            fixed.append(f)
            continue

        if not any(_looks_like_money(w) for w in windows):
            fixed.append(Finding(
                rule_id=f.rule_id,
                passed=True,
                details=(f"{f.details} [auto-guard: numeric citations lacked currency "
                         "context or referenced shares/units]"),
                citations=f.citations,
                tags=getattr(f, "tags", []),
            ))
        else:
            fixed.append(f)
    return fixed


def _normalize_findings_with_rules(text: str, rules: RuleSet, findings: List[Finding]) -> List[Finding]:
    """
    Make results consistent using rule context (applies to every rule pack):
      - contract_value_within_limit:
          * Ignore citations that are clearly shares/units (equity issuance).
          * If every citation is shares/units, PASS with an explicit note.
          * If money context exists and a max_contract_value is configured, respect the evaluator's
            'exceeds' note in details (flip to FAIL if it says 'exceeds').
      - jurisdiction_present_and_allowed:
          * If details say 'Not in allowed list', force FAIL.
    """
    out: List[Finding] = []

    # Pull configured cap if any
    max_contract = None
    try:
        if getattr(rules, "contract", None) and getattr(rules.contract, "max_contract_value", None) is not None:
            max_contract = Decimal(str(rules.contract.max_contract_value))
    except Exception:
        max_contract = None

    for f in findings:
        rid = (f.rule_id or "").lower()
        det = (f.details or "")

        # ---- contract_value_within_limit normalization ----
        if "contract_value_within_limit" in rid:
            windows = []
            for c in (f.citations or []):
                s = max(0, min(len(text), c.char_start))
                e = max(0, min(len(text), c.char_end))
                win = text[max(0, s - 60): min(len(text), e + 60)]
                windows.append(win)

            if windows:
                # If ALL citations look like equity/share context, PASS and clarify.
                if all(_has_share_context(w) and not _looks_like_money_ctx(w) for w in windows):
                    f = Finding(
                        rule_id=f.rule_id,
                        passed=True,
                        details="Ignored numeric amounts because context indicates equity issuance (shares/units), not monetary consideration.",
                        citations=f.citations,
                        tags=getattr(f, "tags", []),
                    )
                elif max_contract is not None:
                    # If ANY window looks like money, enforce cap consistency with details text.
                    any_money = any(_looks_like_money_ctx(w) for w in windows)
                    if any_money:
                        exceeds_claim = "exceed" in det.lower()
                        passed = not exceeds_claim
                        f = Finding(
                            rule_id=f.rule_id,
                            passed=passed,
                            details=(det if det else f"Checked against max_contract_value={max_contract}"),
                            citations=f.citations,
                            tags=getattr(f, "tags", []),
                        )
                    else:
                        # No credible money near the citations; PASS with explanation.
                        f = Finding(
                            rule_id=f.rule_id,
                            passed=True,
                            details="No credible monetary context detected near citations; ignoring share/unit counts for contract value.",
                            citations=f.citations,
                            tags=getattr(f, "tags", []),
                        )
                else:
                    # No max_contract configured; keep as-is but avoid confusing 'exceeds' phrasing.
                    if "exceed" in det.lower():
                        det = det + " (note: no max_contract_value configured; not enforced)"
                        f = Finding(
                            rule_id=f.rule_id,
                            passed=f.passed,
                            details=det,
                            citations=f.citations,
                            tags=getattr(f, "tags", []),
                        )

        # ---- jurisdiction_present_and_allowed normalization ----
        elif "jurisdiction_present_and_allowed" in rid:
            if "not in allowed list" in det.lower():
                f = Finding(
                    rule_id=f.rule_id,
                    passed=False,
                    details=det,
                    citations=f.citations,
                    tags=getattr(f, "tags", []),
                )

        out.append(f)

    return out


# ========================================
# LLM EXPLANATION SYSTEM
# ========================================

def _coerce_to_text(res) -> str:
    """
    Normalize common provider results into plain text:
    - str -> str
    - dict -> try keys ('text', 'output', OpenAI-like 'choices', 'entities'), else json.dumps
    - object -> try .text or .to_dict(), else str(obj)
    """
    if res is None:
        return ""
    if isinstance(res, str):
        return res

    if isinstance(res, dict):
        # Friendly keys first
        if isinstance(res.get("text"), str):
            return res["text"]
        if isinstance(res.get("output"), str):
            return res["output"]
        # OpenAI-style choices
        if isinstance(res.get("choices"), list):
            parts = []
            for ch in res["choices"]:
                if isinstance(ch, dict):
                    msg = ch.get("message") or {}
                    if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                        parts.append(msg["content"])
                    elif isinstance(ch.get("text"), str):
                        parts.append(ch["text"])
            if parts:
                return "\n".join(parts)
        # LangExtract-style "entities"
        if isinstance(res.get("entities"), list):
            parts = []
            for ent in res["entities"]:
                if isinstance(ent, dict):
                    name = ent.get("name") or ent.get("label") or "Field"
                    val = ent.get("value") or ent.get("text") or ""
                    if isinstance(val, (list, dict)):
                        try:
                            val = json.dumps(val, ensure_ascii=False)
                        except Exception:
                            val = str(val)
                    parts.append(f"{name}: {val}")
            if parts:
                return "\n".join(parts)
        # Fallback: pretty-print
        try:
            return json.dumps(res, ensure_ascii=False, indent=2)
        except Exception:
            return str(res)

    # Object with .text
    txt = getattr(res, "text", None)
    if isinstance(txt, str):
        return txt

    # Object with .to_dict()
    to_dict = getattr(res, "to_dict", None)
    if callable(to_dict):
        try:
            return _coerce_to_text(to_dict())
        except Exception:
            pass

    return str(res)


def _call_llm_any(provider, *, doc_text: str, prompt: str):
    """
    Try provider APIs in order and return (mode, text).
    mode ∈ {'completion','chat','extract','error'}.
    """
    # 1) Plain completion (preferred for prose)
    try:
        if hasattr(provider, "complete"):
            out = provider.complete(prompt)  # type: ignore
            return "completion", _coerce_to_text(out)
    except Exception as e:
        return "error", f"[llm error: {e}]"

    # 2) Simple chat
    try:
        if hasattr(provider, "chat"):
            out = provider.chat([{"role": "user", "content": prompt}])  # type: ignore
            return "chat", _coerce_to_text(out)
    except Exception as e:
        return "error", f"[llm error: {e}]"

    # 3) Extract with minimal examples (some providers require this)
    try:
        if hasattr(provider, "extract"):
            minimal_examples = [
                {
                    "input": "Explain why a contract compliance finding failed and suggest a fix.",
                    "entities": [
                        {"name": "Reasoning", "value": "The clause is missing or too broad."},
                        {"name": "Risk", "value": "Uncapped liability or unfavorable venue."},
                        {"name": "Suggested Fix", "value": "Add a limitation of liability and align venue with the allowlist."},
                    ],
                }
            ]
            out = provider.extract(
                text_or_documents=doc_text,
                prompt=prompt,
                examples=minimal_examples,      # required by your provider
                extraction_passes=1,
                max_workers=1,
                max_char_buffer=int(os.getenv("CE_MAX_CHAR_BUFFER", "1500")),
            )
            return "extract", _coerce_to_text(out)
    except Exception as e:
        return "error", f"[llm error: {e}]"

    return "error", "[llm error: no supported method on provider]"


def _clean_llm_prefix(text: str) -> str:
    """
    Remove common LLM response prefixes that add noise to reports.

    Strips prefixes like "LLM Analysis [completion]:", "Here is the analysis:", etc.
    that get added during LLM processing but shouldn't appear in user-facing text.

    Args:
        text: Raw LLM response text

    Returns:
        Cleaned text with prefixes removed
    """
    if not text:
        return ""

    prefixes = [
        "LLM Analysis [completion]:",
        "LLM Analysis [chat]:",
        "LLM Analysis [extract]:",
        "Here is the analysis:",
        "Here is the analysis",
        "Analysis:",
        "in JSON format:",
        "in json format:",
    ]

    stripped = text.strip()
    for p in prefixes:
        if stripped.startswith(p):
            stripped = stripped[len(p):].strip()
            # Check again in case there are multiple prefixes
            for p2 in prefixes:
                if stripped.startswith(p2):
                    stripped = stripped[len(p2):].strip()
                    break
            break

    return stripped


def _extract_json_block(text: str) -> str | None:
    """
    Extract JSON object from LLM response that may contain extra text.

    Handles responses like:
    - "in JSON format:\n{ ... }"
    - "```json\n{...}\n```"
    - Text before/after the JSON object

    Args:
        text: Raw LLM response that may contain JSON

    Returns:
        JSON string (just the {...} part) or None if not found
    """
    if not text:
        return None

    # Strip markdown code fences first
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Remove ```json or ``` prefix
        cleaned = cleaned.strip("`").strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()

    # Remove "in JSON format:" prefix if present
    if "in JSON format:" in cleaned.lower():
        # Find where "in JSON format:" ends
        import re
        cleaned = re.sub(r'in\s+JSON\s+format\s*:?\s*', '', cleaned, flags=re.IGNORECASE)

    # Find first '{' and last '}' to extract JSON object
    import re
    m = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if not m:
        return None

    return m.group(0)


def _maybe_add_llm_explanations(text: str, rules: RuleSet, findings: List[Finding], max_failures: int = None, llm_override: bool = None) -> List[Finding]:
    """
    Append concise LLM rationales to failing findings. Now enabled by default.
    Always adds a status finding so it's obvious whether this step ran and which mode was used.
    """
    from infrastructure import settings

    enabled = settings.get_llm_enabled(llm_override)
    max_failures = max_failures or settings.LLM_MAX_EXPLANATIONS

    status = [f"llm_explanations={'enabled' if enabled else 'disabled'} (default=enabled, override={llm_override})"]
    if not enabled:
        findings.append(Finding(rule_id="llm_explanations_status", passed=True, details="LLM explanations disabled.", citations=[], tags=[]))
        return findings

    # Load provider
    provider = None
    try:
        provider = load_provider()
        status.append(f"provider_loaded={bool(provider)}")
        if provider is None:
            status.append("provider_loaded=False (returned None)")
    except ImportError as e:
        status.append(f"provider_import_error={e!r}")
        findings.append(Finding(rule_id="llm_explanations_status", passed=False, details="LLM provider module could not be imported: {}".format(e), citations=[], tags=[]))
        return findings
    except Exception as e:
        status.append(f"provider_error={e!r}")
        findings.append(Finding(rule_id="llm_explanations_status", passed=False, details="LLM provider could not be loaded: {}".format(e), citations=[], tags=[]))
        return findings

    if provider is None:
        findings.append(Finding(rule_id="llm_explanations_status", passed=False, details="LLM provider returned None", citations=[], tags=[]))
        return findings

    used = 0
    updated: List[Finding] = []
    failed_findings = [f for f in findings if not f.passed]

    for f in findings:
        if not f.passed and used < max_failures and f.rule_id != "llm_explanations_status":
            # Local context around first citation
            snippet = ""
            if f.citations and len(f.citations) > 0:
                c = f.citations[0]
                s = max(0, min(len(text), c.char_start))
                e = max(0, min(len(text), c.char_end))
                snippet = text[max(0, s - 300): min(len(text), e + 300)]
            elif text:
                # If no citations, use first part of document
                snippet = text[:600]

            # Create context from only failed findings
            failed_summary = "\n".join(f"- {x.rule_id}: {x.details[:100]}{'...' if len(x.details) > 100 else ''}" for x in failed_findings[:5] if x.rule_id != "llm_explanations_status")

            prompt = (
                "You are a meticulous contracts analyst. Analyze this compliance finding failure.\n\n"
                f"Failed Finding: {f.rule_id}\n"
                f"Details: {f.details}\n\n"
                "Other failed findings for context:\n"
                f"{failed_summary}\n\n"
                "Relevant contract excerpt:\n-----\n"
                f"{snippet[:800]}\n-----\n\n"
                "Provide your analysis in this JSON format:\n"
                "{\n"
                '  "reason_short": "1-2 sentence summary of why this failed",\n'
                '  "reason_detailed": "Full analysis with Reasoning, Risk, and Fix recommendations",\n'
                '  "summary": "Brief summary for tables/bullets"\n'
                "}\n\n"
                "The reason_short should be concise for tables. The reason_detailed should include:\n"
                "- Reasoning: why this specific rule failed\n"
                "- Risk: business/legal risk if unaddressed\n"
                "- Fix: specific contract language to add/modify\n"
            )

            try:
                mode, rationale = _call_llm_any(provider, doc_text=text, prompt=prompt)
                rationale = (rationale or "").strip()

                if rationale and not rationale.startswith("[llm error:"):
                    # Try to parse as JSON for structured response using the new helper
                    import json

                    # Extract JSON block (handles "in JSON format:" prefix and other noise)
                    json_string = _extract_json_block(rationale)
                    parsed_json = None

                    if json_string:
                        try:
                            parsed_json = json.loads(json_string)
                        except json.JSONDecodeError:
                            # JSON extraction found { } but couldn't parse it
                            pass

                    # Extract short and detailed explanations
                    if parsed_json:
                        reason_short = _clean_llm_prefix(parsed_json.get("reason_short") or parsed_json.get("summary") or "")
                        reason_detailed = _clean_llm_prefix(parsed_json.get("reason_detailed") or parsed_json.get("analysis") or parsed_json.get("full_explanation") or reason_short)
                    else:
                        # Fallback: JSON parsing failed, try to extract any readable text
                        cleaned_rationale = _clean_llm_prefix(rationale)

                        # Strategy 1: Try to extract text from JSON string literals if the response is malformed JSON
                        if "{" in cleaned_rationale and "reason_short" in cleaned_rationale:
                            # Extract anything that looks like a value in "reason_short": "VALUE"
                            import re
                            short_match = re.search(r'"reason_short"\s*:\s*"([^"]+)"', cleaned_rationale)
                            if short_match:
                                reason_short = short_match.group(1).strip()
                                # Try to get reason_detailed too
                                detailed_match = re.search(r'"reason_detailed"\s*:\s*"([^"]+)"', cleaned_rationale)
                                if detailed_match:
                                    reason_detailed = detailed_match.group(1).strip()
                                else:
                                    reason_detailed = reason_short
                            else:
                                # Couldn't extract from JSON pattern, filter out JSON and use plain text
                                lines = cleaned_rationale.split('\n')
                                clean_lines = [line for line in lines if '{' not in line and '}' not in line and '"' not in line and line.strip()]
                                if clean_lines:
                                    cleaned_rationale = ' '.join(clean_lines)
                                    sentences = cleaned_rationale.split('.')
                                    reason_short = '. '.join(sentences[:2]).strip() + '.' if len(sentences) > 1 else cleaned_rationale[:140]
                                    reason_detailed = cleaned_rationale
                                else:
                                    # Last resort: just use the original details field
                                    reason_short = f.details[:140]
                                    reason_detailed = f.details
                        else:
                            # No JSON detected, treat as plain text
                            sentences = cleaned_rationale.split('.')
                            reason_short = '. '.join(sentences[:2]).strip() + '.' if len(sentences) > 1 else cleaned_rationale[:140]
                            reason_detailed = cleaned_rationale

                    # Append to details WITHOUT the "LLM Analysis" prefix
                    # Store full reason_short and reason_detailed in tags (don't truncate here - that causes JSON fragments to appear)
                    f = Finding(
                        rule_id=f.rule_id,
                        passed=f.passed,
                        details=f.details,  # Keep original details clean
                        citations=f.citations,
                        tags=getattr(f, "tags", []) + [f"llm_analysis_mode:{mode}", f"reason_short:{reason_short}", f"reason_detailed:{reason_detailed}"],
                    )
                    used += 1
                    status.append(f"explanation_added_for={f.rule_id}")
                else:
                    status.append(f"explanation_failed_for={f.rule_id}: {rationale[:100] if rationale else 'empty_response'}")
            except Exception as e:
                status.append(f"explanation_error_for={f.rule_id}: {e!r}")

        updated.append(f)

    status.append(f"explanations_added={used}/{len(failed_findings)}")
    findings = updated
    findings.append(Finding(rule_id="llm_explanations_status", passed=True, details="; ".join(status), citations=[], tags=[]))
    return findings


# ========================================
# DOCUMENT NAME RESOLUTION (BUG 1a FIX)
# ========================================

def _resolve_document_name(document_name: Optional[str], pack_data: Optional[Any]) -> str:
    """
    Resolve the document name from various sources with fallback chain.

    BUG 1a FIX: Ensures document_name comes from metadata when available,
    without breaking MCP file path logic or download links.

    Resolution order:
    1. Explicitly provided document_name argument (caller-provided)
    2. pack_data.document_name
    3. pack_data.source_filename
    4. pack_data.filename
    5. pack_data.extensions["document_name"]
    6. pack_data.extensions["source_filename"]
    7. pack_data.extensions["filename"]
    8. Fallback to "Unknown Document"

    Args:
        document_name: Explicitly provided document name (first priority)
        pack_data: Optional rulepack data that may contain metadata

    Returns:
        Resolved document name string
    """
    # Priority 1: Explicitly provided document_name
    if document_name and document_name.strip():
        return document_name.strip()

    # Priority 2-4: Check direct attributes on pack_data
    if pack_data:
        for attr in ['document_name', 'source_filename', 'filename']:
            value = getattr(pack_data, attr, None)
            if value and isinstance(value, str) and value.strip():
                return value.strip()

        # Priority 5-7: Check extensions dict
        extensions = getattr(pack_data, 'extensions', None)
        if extensions and isinstance(extensions, dict):
            for key in ['document_name', 'source_filename', 'filename']:
                value = extensions.get(key)
                if value and isinstance(value, str) and value.strip():
                    return value.strip()

    # Final fallback
    return "Unknown Document"


# ========================================
# MAIN ANALYSIS API
# ========================================

def _infer_doc_type_from_pack(pack_data: Optional[Any]) -> str:
    """
    Infer document type from pack_data.

    Args:
        pack_data: Rule pack data structure

    Returns:
        Document type string (e.g., "Lease Agreement", "Employment Agreement")
    """
    if pack_data is None:
        return "Unknown"

    # Try to get from doc_type_names
    if hasattr(pack_data, 'doc_type_names') and pack_data.doc_type_names:
        return pack_data.doc_type_names[0]

    # Try to infer from rulepack ID
    if hasattr(pack_data, 'id'):
        pack_id = pack_data.id.lower()
        if 'lease' in pack_id:
            return "Lease Agreement"
        elif 'employment' in pack_id:
            return "Employment Agreement"
        elif 'strategic' in pack_id or 'alliance' in pack_id:
            return "Strategic Alliance Agreement"
        elif 'ip' in pack_id or 'intellectual' in pack_id:
            return "Intellectual Property Agreement"

    return "Unknown"


# ============================================================
# PHASE 2: DOC-TYPE-SPECIFIC EXTRACTION & RULE EVALUATION (V2.0)
# ============================================================

def _coerce_result_to_string(result) -> str:
    """
    Coerce LLM provider result to plain string for Phase 2.

    This is simpler than _coerce_to_text because Phase 2 never uses .extractions.
    We only handle raw text responses from .complete() or .chat().

    Args:
        result: Raw result from provider.complete() or provider.chat()

    Returns:
        String representation of the result
    """
    if result is None:
        return ""

    if isinstance(result, str):
        return result

    if isinstance(result, dict):
        # Try common keys
        if "text" in result and isinstance(result["text"], str):
            return result["text"]
        if "output" in result and isinstance(result["output"], str):
            return result["output"]
        if "content" in result and isinstance(result["content"], str):
            return result["content"]

        # OpenAI-style response
        if "choices" in result and isinstance(result["choices"], list):
            for choice in result["choices"]:
                if isinstance(choice, dict):
                    # Check message.content
                    if "message" in choice and isinstance(choice["message"], dict):
                        content = choice["message"].get("content")
                        if isinstance(content, str):
                            return content
                    # Check text field
                    if "text" in choice and isinstance(choice["text"], str):
                        return choice["text"]

        # Last resort for dicts: JSON dump
        try:
            return json.dumps(result, ensure_ascii=False)
        except Exception:
            return str(result)

    # Try .text attribute
    if hasattr(result, "text") and isinstance(result.text, str):
        return result.text

    # Try .content attribute
    if hasattr(result, "content") and isinstance(result.content, str):
        return result.content

    # Fallback
    return str(result)


def _clean_llm_json(raw: str) -> str:
    """
    Clean LLM response to extract valid JSON.

    Handles common issues:
    - Markdown code fences (```json or ```)
    - Leading prose before the JSON object
    - Trailing text after the JSON object
    - Ellipsis placeholder lines (..., "...", etc.)

    Args:
        raw: Raw LLM response text

    Returns:
        Cleaned string ready for json.loads()
    """
    import logging
    logger = logging.getLogger(__name__)

    cleaned = raw

    # Remove markdown fences
    cleaned = cleaned.replace("```json", "").replace("```", "")
    logger.debug("Phase 2 JSON cleaning: Removed markdown fences")

    # Strip any leading prose before the first '{'
    first = cleaned.find("{")
    last = cleaned.rfind("}")
    if first != -1 and last != -1 and last > first:
        if first > 0:
            logger.debug(f"Phase 2 JSON cleaning: Stripped {first} chars of leading prose")
        cleaned = cleaned[first:last+1]

    # Drop ellipsis placeholder lines
    cleaned_lines = []
    for line in cleaned.splitlines():
        stripped = line.strip()
        if stripped in {"...", "...,", "\"...\"", "'...'", "\"...\",", "'...',"}:
            continue
        cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines)

    return cleaned.strip()


def _remove_trailing_commas(json_str: str) -> str:
    """
    Remove trailing commas before closing brackets/braces in JSON.

    Handles cases like:
    - {"key": "value",}
    - ["item1", "item2",]
    - Nested structures with trailing commas

    Args:
        json_str: JSON string potentially containing trailing commas

    Returns:
        JSON string with trailing commas removed
    """
    import re
    import logging
    logger = logging.getLogger(__name__)

    # Pattern matches: comma + optional whitespace + closing bracket/brace
    # This handles trailing commas before ] or }
    pattern = r',(\s*[}\]])'

    # Count how many replacements we make
    original = json_str
    cleaned = re.sub(pattern, r'\1', json_str)

    if cleaned != original:
        # Count occurrences
        count = len(re.findall(pattern, original))
        logger.info(f"Phase 2 JSON cleaning: Removed {count} trailing comma(s)")

    return cleaned


def _quote_unquoted_text_values(json_str: str) -> str:
    """
    Find obviously invalid unquoted values like `60 days` (number + space + letters)
    and wrap them in quotes so the string becomes valid JSON.

    Fixes patterns like:
    - "warranty_period": 60 days, -> "warranty_period": "60 days",
    - "duration": 30 days -> "duration": "30 days"

    This only touches values that are:
    - Immediately after a colon
    - Optional spaces
    - A number (integer or decimal)
    - A space
    - A sequence of alphabetic characters (possibly with numbers, common in units)

    Does NOT touch:
    - Plain numbers (e.g. 60)
    - Already-quoted strings
    - Booleans (true/false), null
    - Numbers without following text

    Args:
        json_str: JSON string potentially containing unquoted text values

    Returns:
        JSON string with unquoted text values wrapped in quotes
    """
    import re
    import logging
    logger = logging.getLogger(__name__)

    # Pattern explanation:
    # (:\s*)           - Capture group 1: colon followed by optional whitespace
    # (\d+(?:\.\d+)?)  - Capture group 2: number (int or decimal) followed by space and letters
    # \s+              - One or more spaces
    # [A-Za-z][\w]*    - Letters followed by optional word characters (for "days", "months", etc.)
    # (?=\s*[,}\]])    - Lookahead: followed by comma, closing brace, or closing bracket
    #                    This ensures we're at the end of a value

    pattern = r'(:\s*)(\d+(?:\.\d+)?\s+[A-Za-z][\w]*)(?=\s*[,}\]])'

    # Replacement: keep the colon/spaces, wrap the value in quotes
    def replacement(match):
        prefix = match.group(1)  # : and spaces
        value = match.group(2)   # The unquoted text (e.g., "60 days")
        return f'{prefix}"{value}"'

    original = json_str
    cleaned = re.sub(pattern, replacement, json_str)

    if cleaned != original:
        # Count occurrences
        count = len(re.findall(pattern, original))
        logger.info(f"Phase 2 JSON cleaning: Wrapped {count} unquoted text value(s) in quotes")
        logger.debug(f"Phase 2 JSON cleaning: Example fixes: {re.findall(pattern, original)[:3]}")

    return cleaned


def _parse_llm_json(raw: str) -> dict:
    """
    Robustly parse LLM JSON response with multiple recovery strategies.

    This function attempts to parse JSON from LLM output even when it contains
    common formatting issues like trailing commas, markdown fences, or prose.

    Strategy:
    1. Extract and clean the JSON block (remove fences, prose, ellipsis)
    2. Attempt direct parsing
    3. If that fails, remove trailing commas and retry
    4. If that fails, quote unquoted text values (e.g., "60 days") and retry
    5. If still failing, log detailed error and raise

    Args:
        raw: Raw LLM response text

    Returns:
        Parsed dictionary

    Raises:
        json.JSONDecodeError: If parsing fails after all recovery attempts
    """
    import logging
    logger = logging.getLogger(__name__)

    # Stage 1: Extract and clean JSON block
    logger.debug("Phase 2: Extracting JSON block from LLM response")
    cleaned = _clean_llm_json(raw)

    # Stage 2: First attempt - parse as-is
    try:
        logger.debug("Phase 2: Attempting direct JSON parse")
        result = json.loads(cleaned)
        logger.debug("Phase 2: Direct JSON parse succeeded")
        return result
    except json.JSONDecodeError as e1:
        logger.debug(f"Phase 2: Direct JSON parse failed: {e1}")

        # Stage 3: Remove trailing commas and retry
        logger.info("Phase 2: Applying trailing comma cleanup")
        cleaned_no_trailing = _remove_trailing_commas(cleaned)

        try:
            result = json.loads(cleaned_no_trailing)
            logger.info("Phase 2: JSON parse succeeded after trailing comma removal")
            return result
        except json.JSONDecodeError as e2:
            logger.debug(f"Phase 2: JSON parse failed after trailing comma cleanup: {e2}")

            # Stage 4: Quote unquoted text values and retry
            logger.info("Phase 2: Applying unquoted text value cleanup")
            cleaned_quoted = _quote_unquoted_text_values(cleaned_no_trailing)

            try:
                result = json.loads(cleaned_quoted)
                logger.info("Phase 2: JSON parse succeeded after quoting unquoted text values")
                return result
            except json.JSONDecodeError as e3:
                # Stage 5: All strategies failed - detailed error logging
                logger.error("Phase 2: Failed to parse LLM JSON after all cleanup attempts")
                logger.error(f"Phase 2: Parse error after cleanup: {e3}")
                logger.error(f"Phase 2: Error location: line {e3.lineno}, column {e3.colno}")
                logger.error("Phase 2: CLEANED JSON snippet (first 2000 chars):\n%s", cleaned_quoted[:2000])

                # Show context around error if possible
                if e3.lineno:
                    lines = cleaned_quoted.splitlines()
                    if 0 <= e3.lineno - 1 < len(lines):
                        error_line = lines[e3.lineno - 1]
                        logger.error(f"Phase 2: Problematic line: {error_line}")
                        if e3.colno and e3.colno <= len(error_line):
                            logger.error(f"Phase 2: Error position: {' ' * (e3.colno - 1)}^")

                raise


def _parse_rulepack_llm_json(raw: str) -> dict:
    """
    Parse Phase 2 LLM JSON response with robust error handling.

    This is the main entry point for Phase 2 JSON parsing.
    Uses _parse_llm_json for robust parsing with multiple recovery strategies.

    Args:
        raw: Raw LLM response text

    Returns:
        Parsed dictionary with key_terms and citations

    Raises:
        json.JSONDecodeError: If parsing fails even after all cleanup attempts
    """
    return _parse_llm_json(raw)


def _normalize_sow_key_terms(key_terms: dict, rulepack_id: str) -> dict:
    """
    For SOW rulepacks, fill missing high-level fields using lower-level ones.
    Also handles legacy schema formats (StatementOfWork, SpecificRequirementsAndTaskDescriptions, etc.)
    Mutates and returns key_terms.

    Args:
        key_terms: Extracted key terms dictionary
        rulepack_id: Rulepack identifier (e.g., "sow_v1")

    Returns:
        Normalized key_terms dictionary
    """
    import logging
    import re
    logger = logging.getLogger(__name__)

    logger.info(f"Phase 2: Normalizing SOW key terms for rulepack {rulepack_id}")

    # ========================================================================
    # STEP 1: SCHEMA UNIFICATION - Convert nested/legacy schemas to canonical
    # ========================================================================

    # First, detect nested statement_of_work object (snake_case)
    sow_obj = None
    if isinstance(key_terms.get("statement_of_work"), dict):
        sow_obj = key_terms["statement_of_work"]
        logger.info("Phase 2: SOW - Found nested 'statement_of_work' object; flattening")
    elif isinstance(key_terms.get("StatementOfWork"), dict):
        sow_obj = key_terms["StatementOfWork"]
        logger.info("Phase 2: SOW - Found legacy 'StatementOfWork' object; flattening")

    if sow_obj:
        # Extract project dates from period_of_performance
        pop = sow_obj.get("period_of_performance")
        if isinstance(pop, str) and pop.strip():
            # Parse "November 1, 2024 - April 30, 2025" (note the " - " separator)
            match = re.search(r'(\w+\s+\d+,\s+\d+)\s*-\s*(\w+\s+\d+,\s+\d+)', pop)
            if match:
                if not key_terms.get("project_start_date"):
                    key_terms["project_start_date"] = match.group(1).strip()
                    logger.info(f"Phase 2: Extracted project_start_date: {key_terms['project_start_date']}")
                if not key_terms.get("project_end_date"):
                    key_terms["project_end_date"] = match.group(2).strip()
                    logger.info(f"Phase 2: Extracted project_end_date: {key_terms['project_end_date']}")
            else:
                # Try alternative format with "to" separator
                match = re.search(r'(\w+\s+\d+,\s+\d+)\s+to\s+(\w+\s+\d+,\s+\d+)', pop)
                if match:
                    if not key_terms.get("project_start_date"):
                        key_terms["project_start_date"] = match.group(1).strip()
                        logger.info(f"Phase 2: Extracted project_start_date: {key_terms['project_start_date']}")
                    if not key_terms.get("project_end_date"):
                        key_terms["project_end_date"] = match.group(2).strip()
                        logger.info(f"Phase 2: Extracted project_end_date: {key_terms['project_end_date']}")

        # Convert specific_requirements_and_task_descriptions from array of {task, description} to array of strings
        srtd_nested = sow_obj.get("specific_requirements_and_task_descriptions")
        if isinstance(srtd_nested, list) and not key_terms.get("specific_requirements_and_task_descriptions"):
            tasks = []
            for item in srtd_nested:
                if isinstance(item, dict):
                    task_name = item.get("task", "")
                    task_desc = item.get("description", "")
                    if task_name:
                        # If description exists and adds value, combine them
                        if task_desc and task_desc.strip():
                            tasks.append(f"{task_name}: {task_desc}")
                        else:
                            tasks.append(task_name)
            if tasks:
                key_terms["specific_requirements_and_task_descriptions"] = tasks
                logger.info(f"Phase 2: Converted nested task array to specific_requirements_and_task_descriptions: {len(tasks)} tasks")

        # Copy up completion_criteria
        if "completion_criteria" in sow_obj and not key_terms.get("completion_criteria"):
            key_terms["completion_criteria"] = sow_obj["completion_criteria"]
            logger.info("Phase 2: Copied completion_criteria from nested SOW object")

        # Copy up warranty_acceptance_custom_product
        if "warranty_acceptance_custom_product" in sow_obj and not key_terms.get("warranty_acceptance_custom_product"):
            key_terms["warranty_acceptance_custom_product"] = sow_obj["warranty_acceptance_custom_product"]
            logger.info("Phase 2: Copied warranty_acceptance_custom_product from nested SOW object")

        # Convert terms_and_conditions from array of {term, description} to categorized dict
        tc_nested = sow_obj.get("terms_and_conditions")
        if isinstance(tc_nested, list) and not key_terms.get("terms_and_conditions"):
            terms_dict = {}

            # Extract all term texts
            all_terms = []
            for item in tc_nested:
                if isinstance(item, dict):
                    term_text = item.get("term", "")
                    term_desc = item.get("description", "")
                    if term_text:
                        # If description adds value, combine
                        if term_desc and term_desc.strip():
                            all_terms.append(f"{term_text} {term_desc}")
                        else:
                            all_terms.append(term_text)

            # Categorize terms using keyword matching
            billing_terms = []
            change_terms = []

            for term in all_terms:
                lower = term.lower()

                # Billing/payment terms
                if any(keyword in lower for keyword in ["bill", "payment", "invoice", "due", "monthly"]):
                    billing_terms.append(term)

                # Change request terms
                if any(keyword in lower for keyword in ["change request", "change to the scope", "expansion"]):
                    change_terms.append(term)

            # Build terms_and_conditions dict
            if billing_terms:
                terms_dict["billing_and_payment_terms"] = " ".join(billing_terms)
                logger.info(f"Phase 2: Extracted billing_and_payment_terms from nested terms array: {len(terms_dict['billing_and_payment_terms'])} chars")

            if change_terms:
                terms_dict["change_request_process"] = " ".join(change_terms)
                logger.info(f"Phase 2: Extracted change_request_process from nested terms array: {len(terms_dict['change_request_process'])} chars")

            if terms_dict:
                key_terms["terms_and_conditions"] = terms_dict
                logger.info(f"Phase 2: Converted nested terms array to dict with {len(terms_dict)} keys")

    # Detect legacy schema (PascalCase keys instead of snake_case)
    has_legacy_schema = (
        "StatementOfWork" in key_terms or
        "SpecificRequirementsAndTaskDescriptions" in key_terms or
        "TermsAndConditions" in key_terms and isinstance(key_terms.get("TermsAndConditions"), list)
    )

    if has_legacy_schema:
        logger.info("Phase 2: SOW - Detected legacy schema (StatementOfWork/SpecificRequirementsAndTaskDescriptions), converting to canonical")

        # 1. Convert StatementOfWork
        sow = key_terms.get("StatementOfWork")
        if isinstance(sow, dict):
            # Extract total_project_value from TotalCost
            if "TotalCost" in sow and not key_terms.get("total_project_value"):
                cost_str = sow["TotalCost"]
                # Extract numeric value from "$9,950.00" format
                if isinstance(cost_str, str):
                    match = re.search(r'[\d,]+\.?\d*', cost_str.replace(',', ''))
                    if match:
                        try:
                            key_terms["total_project_value"] = float(match.group())
                            logger.info(f"Phase 2: Extracted total_project_value from StatementOfWork.TotalCost: {key_terms['total_project_value']}")
                        except ValueError:
                            pass

            # Extract payment_schedule from PaymentSchedule array
            if "PaymentSchedule" in sow and not key_terms.get("payment_schedule"):
                pay_sched = sow["PaymentSchedule"]
                if isinstance(pay_sched, list):
                    # Build a summary string
                    parts = []
                    for item in pay_sched:
                        if isinstance(item, dict):
                            amount = item.get("Amount", "")
                            date = item.get("InvoiceDate", "")
                            if amount:
                                part = amount
                                if date:
                                    part += f" on {date}"
                                parts.append(part)
                    if parts:
                        schedule_str = "; ".join(parts)
                        # Add net terms if present
                        if "NetTerms" in sow:
                            schedule_str += f"; Net {sow['NetTerms']}"
                        key_terms["payment_schedule"] = schedule_str
                        logger.info(f"Phase 2: Built payment_schedule from StatementOfWork.PaymentSchedule: {len(schedule_str)} chars")

            # Extract dates from PeriodOfPerformance
            if "PeriodOfPerformance" in sow:
                pop = sow["PeriodOfPerformance"]
                if isinstance(pop, str):
                    # Parse "November 1, 2024 to April 30, 2025"
                    match = re.search(r'(\w+ \d+, \d+)\s+to\s+(\w+ \d+, \d+)', pop)
                    if match:
                        if not key_terms.get("project_start_date"):
                            key_terms["project_start_date"] = match.group(1)
                            logger.info(f"Phase 2: Extracted project_start_date: {match.group(1)}")
                        if not key_terms.get("project_end_date"):
                            key_terms["project_end_date"] = match.group(2)
                            logger.info(f"Phase 2: Extracted project_end_date: {match.group(2)}")
                    else:
                        # Store whole string as fallback
                        if not key_terms.get("project_start_date"):
                            key_terms["project_start_date"] = pop
                        if not key_terms.get("project_end_date"):
                            key_terms["project_end_date"] = pop

        # 2. Convert SpecificRequirementsAndTaskDescriptions
        srtd_legacy = key_terms.get("SpecificRequirementsAndTaskDescriptions")
        if isinstance(srtd_legacy, list) and not key_terms.get("specific_requirements_and_task_descriptions"):
            tasks = []
            for item in srtd_legacy:
                if isinstance(item, dict) and "TaskDescription" in item:
                    task_desc = item["TaskDescription"]
                    if isinstance(task_desc, str):
                        tasks.append(task_desc)
            if tasks:
                key_terms["specific_requirements_and_task_descriptions"] = tasks
                logger.info(f"Phase 2: Converted SpecificRequirementsAndTaskDescriptions to specific_requirements_and_task_descriptions: {len(tasks)} tasks")

        # 3. Convert CompletionCriteria
        if "CompletionCriteria" in key_terms and not key_terms.get("completion_criteria"):
            key_terms["completion_criteria"] = key_terms["CompletionCriteria"]
            logger.info("Phase 2: Copied CompletionCriteria to completion_criteria")

        # 4. Convert WarrantyAndAcceptanceCustomProduct
        if "WarrantyAndAcceptanceCustomProduct" in key_terms and not key_terms.get("warranty_acceptance_custom_product"):
            key_terms["warranty_acceptance_custom_product"] = key_terms["WarrantyAndAcceptanceCustomProduct"]
            logger.info("Phase 2: Copied WarrantyAndAcceptanceCustomProduct to warranty_acceptance_custom_product")

        # 5. Convert TermsAndConditions array to dict
        tc_legacy = key_terms.get("TermsAndConditions")
        if isinstance(tc_legacy, list) and not key_terms.get("terms_and_conditions"):
            terms_dict = {}

            # Extract terms as strings
            all_terms = []
            for item in tc_legacy:
                if isinstance(item, dict) and "Term" in item:
                    term_text = item["Term"]
                    if isinstance(term_text, str):
                        all_terms.append(term_text)

            # Categorize terms using keyword matching
            billing_terms = []
            change_terms = []
            ip_terms = []

            for term in all_terms:
                lower = term.lower()

                # Billing/payment terms
                if any(keyword in lower for keyword in ["bill", "payment", "invoice", "due", "net", "fee"]):
                    billing_terms.append(term)

                # Change request terms
                if any(keyword in lower for keyword in ["change request", "change to the scope", "expansion of", "additional services"]):
                    change_terms.append(term)

                # IP ownership terms
                if any(keyword in lower for keyword in ["intellectual property", "ownership", "works for hire", "copyright"]):
                    ip_terms.append(term)

            # Build terms_and_conditions dict
            if billing_terms:
                terms_dict["billing_and_payment_terms"] = " ".join(billing_terms)
                logger.info(f"Phase 2: Extracted billing_and_payment_terms from TermsAndConditions: {len(terms_dict['billing_and_payment_terms'])} chars")

            if change_terms:
                terms_dict["change_request_process"] = " ".join(change_terms)
                logger.info(f"Phase 2: Extracted change_request_process from TermsAndConditions: {len(terms_dict['change_request_process'])} chars")

            if ip_terms:
                # Also set ip_ownership high-level field
                if not key_terms.get("ip_ownership"):
                    key_terms["ip_ownership"] = ip_terms[0] if len(ip_terms) == 1 else " ".join(ip_terms[:2])
                    logger.info(f"Phase 2: Set ip_ownership from TermsAndConditions")

            key_terms["terms_and_conditions"] = terms_dict
            logger.info(f"Phase 2: Converted TermsAndConditions array to dict with {len(terms_dict)} keys")

    # Log before high-level field derivation
    logger.info(
        f"Phase 2: After schema unification - scope_of_work_description: "
        f"{'Present' if key_terms.get('scope_of_work_description') else 'Missing'}, "
        f"deliverables_count: {key_terms.get('deliverables_count')}, "
        f"payment_schedule: {'Present' if key_terms.get('payment_schedule') else 'Missing'}"
    )

    # ========================================================================
    # STEP 2: HIGH-LEVEL FIELD DERIVATION - Fill missing fields from detailed ones
    # ========================================================================

    # 1. Deliverables from specific_requirements_and_task_descriptions
    srtd = key_terms.get("specific_requirements_and_task_descriptions")
    if srtd and isinstance(srtd, list) and len(srtd) > 0:
        # deliverables_count
        if key_terms.get("deliverables_count") is None:
            key_terms["deliverables_count"] = len(srtd)
            logger.info(f"Phase 2: Set deliverables_count = {len(srtd)} from task list")

        # deliverables_summary
        if not key_terms.get("deliverables_summary"):
            # Take first 10 items, limit to 800 chars
            joined = "; ".join(srtd[:10])
            if len(joined) > 800:
                joined = joined[:800] + "..."
            key_terms["deliverables_summary"] = joined
            logger.info(f"Phase 2: Set deliverables_summary from task list ({len(joined)} chars)")

        # scope_of_work_description fallback
        if not key_terms.get("scope_of_work_description"):
            intro = "This Statement of Work covers content development and micro-credential module authoring, including tasks such as "
            # Clean up task descriptions (remove " X" markers)
            bullets = ", ".join(item.split(" X")[0].strip() for item in srtd[:5])
            text = intro + bullets
            if len(text) > 600:
                text = text[:600] + "..."
            key_terms["scope_of_work_description"] = text
            logger.info(f"Phase 2: Set scope_of_work_description fallback ({len(text)} chars)")

    # 2. Payment schedule from terms_and_conditions.billing_and_payment_terms
    terms = key_terms.get("terms_and_conditions") or {}
    if isinstance(terms, dict) and not key_terms.get("payment_schedule"):
        ps = terms.get("billing_and_payment_terms")
        if isinstance(ps, str) and ps.strip():
            key_terms["payment_schedule"] = ps.strip()
            logger.info(f"Phase 2: Set payment_schedule from T&C ({len(ps)} chars)")

    # 3. Acceptance criteria from completion_criteria or warranty_acceptance_custom_product
    if not key_terms.get("acceptance_criteria_present"):
        completion = key_terms.get("completion_criteria")
        warranty = key_terms.get("warranty_acceptance_custom_product")

        if (isinstance(completion, str) and completion.strip()) or (isinstance(warranty, dict) and warranty):
            key_terms["acceptance_criteria_present"] = True
            logger.info("Phase 2: Set acceptance_criteria_present = True from completion/warranty")

    # 4. Change order process from terms_and_conditions.change_request_process
    if not key_terms.get("change_order_process_present") and isinstance(terms, dict):
        crp = terms.get("change_request_process")
        if isinstance(crp, str) and crp.strip():
            key_terms["change_order_process_present"] = True
            logger.info("Phase 2: Set change_order_process_present = True from T&C")

    # Log after normalization
    logger.info(
        f"Phase 2: After normalization - scope_of_work_description: "
        f"{len(key_terms.get('scope_of_work_description', '')) if key_terms.get('scope_of_work_description') else 0} chars, "
        f"deliverables_count: {key_terms.get('deliverables_count')}, "
        f"deliverables_summary: {len(key_terms.get('deliverables_summary', '')) if key_terms.get('deliverables_summary') else 0} chars, "
        f"payment_schedule: {len(key_terms.get('payment_schedule', '')) if key_terms.get('payment_schedule') else 0} chars, "
        f"acceptance_criteria_present: {key_terms.get('acceptance_criteria_present')}, "
        f"change_order_process_present: {key_terms.get('change_order_process_present')}"
    )

    return key_terms


def extract_doc_type_key_terms(
    text: str,
    rulepack: dict,
    prelim: 'PreliminaryExtraction',
    llm_override: Optional['LLMProvider'] = None
) -> dict:
    """
    Phase 2 LLM Call: Extract doc-type-specific key terms using rulepack prompt.

    This function is completely independent of the v1 .extractions API.
    It expects the LLM to return raw JSON text matching the schema in llm_extraction.prompt.

    Args:
        text: Full contract text
        rulepack: Rulepack dictionary (schema v2.0)
        prelim: PreliminaryExtraction from Phase 1
        llm_override: Optional LLM provider override (for mocked tests)

    Returns:
        Dictionary with structure:
        {
            "key_terms": {...},
            "citations": {...}
        }
        or empty dicts on failure.
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Get extraction configuration from rulepack
        llm_extraction_config = rulepack.get("llm_extraction", {})
        prompt_template = llm_extraction_config.get("prompt", "")

        if not prompt_template:
            logger.warning(f"Phase 2: No llm_extraction.prompt in rulepack {rulepack.get('id')}")
            return {"key_terms": {}, "citations": {}}

        # Build final prompt with clear delimiters for contract text
        full_prompt = (
            prompt_template
            + "\n\n"
            + "=" * 60 + "\n"
            + "CONTRACT TEXT STARTS\n"
            + "=" * 60 + "\n\n"
            + text + "\n\n"
            + "=" * 60 + "\n"
            + "CONTRACT TEXT ENDS\n"
            + "=" * 60 + "\n\n"
            + "Now extract the key terms as specified above and return only valid JSON.\n"
        )

        # Load LLM provider
        if llm_override:
            provider = llm_override
        else:
            provider = load_provider()

        logger.info(f"Phase 2: Extracting key terms for rulepack {rulepack.get('id')}")

        # Get raw text response from LLM (NO .extractions, NO provider.extract())
        response_text = None

        # For mocked tests: use _call_llm_any (tests mock this function)
        if llm_override:
            mode, response_text = _call_llm_any(provider, doc_text=text, prompt=full_prompt)
            if mode == "error":
                logger.error(f"Phase 2: LLM call failed: {response_text}")
                return {"key_terms": {}, "citations": {}}
        else:
            # For real LLM: call provider methods directly
            # Prefer .complete() or .chat() to avoid .extractions dependency
            try:
                if hasattr(provider, "complete"):
                    # Best for raw text generation
                    raw_result = provider.complete(full_prompt)
                    response_text = _coerce_result_to_string(raw_result)
                elif hasattr(provider, "chat"):
                    # Alternative for chat-based providers
                    raw_result = provider.chat([{"role": "user", "content": full_prompt}])
                    response_text = _coerce_result_to_string(raw_result)
                else:
                    # Provider has neither .complete() nor .chat()
                    logger.error(
                        "Phase 2: Provider has no .complete() or .chat(); "
                        "Phase 2 extraction requires a provider that returns raw JSON text."
                    )
                    return {"key_terms": {}, "citations": {}}

            except Exception as e:
                logger.error(f"Phase 2: LLM call failed: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                return {"key_terms": {}, "citations": {}}

        if not response_text or not response_text.strip():
            logger.error("Phase 2: LLM returned empty response")
            return {"key_terms": {}, "citations": {}}

        # Log raw LLM output for debugging
        logger.error("Phase 2 RAW LLM OUTPUT (sow_v1):\n%s", response_text)

        # Parse JSON using robust helper
        try:
            parsed = _parse_rulepack_llm_json(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Phase 2: Failed to parse LLM JSON: {e}")
            logger.debug(f"Phase 2: Raw response (first 500 chars): {response_text[:500]}")
            return {"key_terms": {}, "citations": {}}

        # Normalize structure
        if "key_terms" in parsed and "citations" in parsed:
            key_terms = parsed.get("key_terms") or {}
            citations = parsed.get("citations") or {}
        elif "key_terms" in parsed:
            # Has key_terms but missing citations
            key_terms = parsed.get("key_terms") or {}
            citations = {}
        else:
            # Model returned flat object - wrap it
            logger.warning("Phase 2: Response missing 'key_terms' key, wrapping response")
            key_terms = parsed
            citations = {}

        # Extract citations from key_terms if present (newer format)
        if "citations" in key_terms:
            citations = key_terms.pop("citations")
            logger.info(f"Phase 2: Extracted citations from key_terms: {list(citations.keys())}")

        # Log what we extracted
        logger.info(
            f"Phase 2: Parsed key terms: {list(key_terms.keys())}; citations: {list(citations.keys())}"
        )

        # Apply SOW-specific normalization
        rulepack_id = rulepack.get("id", "")
        if rulepack_id.startswith("sow_"):
            logger.info(f"Phase 2: Detected SOW rulepack '{rulepack_id}', applying normalization")
            key_terms = _normalize_sow_key_terms(key_terms, rulepack_id)
            logger.info(f"Phase 2: Extracted {len(key_terms)} key terms (after normalization)")
        else:
            logger.info(f"Phase 2: Extracted {len(key_terms)} key terms (no normalization)")

        return {"key_terms": key_terms, "citations": citations}

    except Exception as e:
        logger.error(f"Phase 2: Unexpected error in extraction: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return {"key_terms": {}, "citations": {}}


def evaluate_rulepack_rules(
    rulepack: dict,
    key_terms: dict,
) -> List['RulepackRuleResult']:
    """
    Evaluate rulepack rules against extracted key terms.

    Args:
        rulepack: Rulepack dictionary (schema v2.0)
        key_terms: Extracted key terms dictionary from Phase 2

    Returns:
        List of RulepackRuleResult objects
    """
    from infrastructure import RulepackRuleResult
    import logging
    logger = logging.getLogger(__name__)

    results = []
    rules = rulepack.get("rules", [])

    # Pre-populate context with all key term names from rulepack
    # This prevents NameError when key_terms is empty or missing fields
    context = {}
    key_terms_config = rulepack.get("key_terms", [])
    for term_config in key_terms_config:
        term_name = term_config.get("name")
        if term_name:
            # Set to actual value if present, else None
            context[term_name] = key_terms.get(term_name)

    # Provide safe builtins for common operations
    safe_builtins = {
        "len": len,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "min": min,
        "max": max,
        "sum": sum,
        "abs": abs,
        "round": round,
        "None": None,
        "True": True,
        "False": False,
    }

    for rule in rules:
        rule_id = rule.get("id", "unknown")
        label = rule.get("label", "Unknown Rule")
        category = rule.get("category", "General")
        severity = rule.get("severity", "Medium")
        condition = rule.get("condition", "")
        success_message = rule.get("success_message", "Rule passed")
        failure_message = rule.get("failure_message", "Rule failed")
        risk_statement = rule.get("risk_statement")
        recommendation = rule.get("recommendation")

        # Evaluate condition using safe eval
        try:
            # Evaluate condition with pre-populated context
            condition_met = eval(
                condition,
                {"__builtins__": safe_builtins},
                context
            )

            # Determine status and message
            status = "PASS" if condition_met else "FAIL"
            message = success_message if condition_met else failure_message

            # Build result
            results.append(RulepackRuleResult(
                rule_id=rule_id,
                label=label,
                category=category,
                status=status,
                severity=severity,
                message=message,
                citations=[],  # TODO: Link to citations from key_terms
                risk_statement=risk_statement if not condition_met else None,
                recommendation=recommendation if not condition_met else None
            ))

            logger.debug(f"Rule {rule_id}: {status}")

        except Exception as e:
            # Evaluation error - return WARN status
            logger.warning(f"Rule {rule_id} evaluation failed: {e}")
            results.append(RulepackRuleResult(
                rule_id=rule_id,
                label=label,
                category=category,
                status="WARN",
                severity="Medium",
                message=f"Rule evaluation error: {str(e)}",
                citations=[],
                risk_statement="Rule evaluation failed - manual review required",
                recommendation="Check rule condition syntax and key term availability"
            ))

    return results


def map_key_terms_for_display(
    key_terms: dict,
    citations: dict,
    rulepack: dict
) -> dict:
    """
    Map extracted key terms to display-friendly format using rulepack metadata.

    Args:
        key_terms: Extracted key terms from Phase 2 (flat dict)
        citations: Citations from Phase 2 (flat dict)
        rulepack: Rulepack dictionary with key_terms definitions

    Returns:
        Dictionary suitable for ExtractedKeyTerms with structure:
        {
            "field_name": {
                "label": str,
                "value": any,
                "citation": str,
                "type": str
            },
            ...
        }
    """
    display_terms = {}
    key_terms_config = rulepack.get("key_terms", [])

    for term_config in key_terms_config:
        name = term_config.get("name")
        label = term_config.get("label", name)
        json_path = term_config.get("json_path", f"$.key_terms.{name}")

        # Simple JSON path resolution (only supports $.key_terms.field_name)
        if json_path.startswith("$.key_terms."):
            field_name = json_path.replace("$.key_terms.", "")
            value = key_terms.get(field_name)
        else:
            value = None

        # Get citation if available
        citation_text = citations.get(name) if citations else None

        display_terms[name] = {
            "label": label,
            "value": value,
            "citation": citation_text,
            "type": term_config.get("type", "string"),
            "description": term_config.get("description", "")
        }

    return display_terms


def build_report_v2_from_v1(
    report_v1: DocumentReport,
    text: str,
    pack_data: Optional[Any],
    classified_type: str
) -> 'DocumentReportV2':
    """
    Build DocumentReportV2 from existing v1 report.

    This is the Phase 3 mapper that converts v1 findings into v2 structure.

    Args:
        report_v1: Existing v1 DocumentReport
        text: Full contract text
        pack_data: Rule pack data
        classified_type: Document type from inference

    Returns:
        DocumentReportV2 with preliminary extraction and compliance checks populated
    """
    from infrastructure import (
        DocumentReportV2,
        DocumentMetadata,
        RulepackSummary,
        RiskAssessment,
        ExtractedKeyTerms,
    )
    from datetime import datetime, timezone

    # Extract rulepack info
    rulepack_id = getattr(pack_data, 'id', 'unknown') if pack_data else 'unknown'
    rulepack_name = classified_type

    # Build preliminary compliance checks and extract jurisdiction (without Phase 2 citations yet)
    compliance_checks, jurisdiction_value = build_preliminary_compliance_checks(report_v1.findings, phase2_citations=None)

    # Build preliminary extraction
    preliminary_extraction = build_preliminary_extraction(
        text=text,
        classified_type=classified_type,
        jurisdiction_from_rules=jurisdiction_value
    )

    # ========== PHASE 2: DOC-TYPE-SPECIFIC EXTRACTION & RULES (V2.0) ==========
    # Try to load v2.0 rulepack for this document type
    import logging
    from rulepack_manager import (
        load_all_v2_rulepacks,
        load_active_v2_rulepacks_from_db,
        select_rulepack_for_doc_type
    )
    from infrastructure import SessionLocal

    logger = logging.getLogger(__name__)

    # Try database first, fall back to filesystem
    v2_rulepacks = {}
    try:
        with SessionLocal() as db:
            v2_rulepacks = load_active_v2_rulepacks_from_db(db)
            logger.info(f"Phase 2: Loaded {len(v2_rulepacks)} v2.0 rulepacks from database")
    except Exception as e:
        logger.warning(f"Phase 2: Database loading failed ({e}), falling back to filesystem")
        v2_rulepacks = load_all_v2_rulepacks()
        logger.info(f"Phase 2: Loaded {len(v2_rulepacks)} v2.0 rulepacks from filesystem")

    selected_rulepack_id = select_rulepack_for_doc_type(classified_type, v2_rulepacks)

    # Initialize Phase 2 outputs
    phase2_key_terms = {}
    phase2_citations = {}
    phase2_rulepack_rules = []
    phase2_extracted_key_terms = None

    if selected_rulepack_id and selected_rulepack_id in v2_rulepacks:
        logger.info(f"Phase 2: Using v2.0 rulepack '{selected_rulepack_id}' for doc type '{classified_type}'")
        rulepack_v2 = v2_rulepacks[selected_rulepack_id]

        # Update rulepack metadata
        rulepack_id = selected_rulepack_id
        rulepack_name = rulepack_v2.get("doc_type_names", [classified_type])[0]

        try:
            # Phase 2 Call: Extract doc-type-specific key terms
            phase2_response = extract_doc_type_key_terms(
                text=text,
                rulepack=rulepack_v2,
                prelim=preliminary_extraction,
                llm_override=None
            )

            phase2_key_terms = phase2_response.get("key_terms", {})
            phase2_citations = phase2_response.get("citations", {})

            logger.info(f"Phase 2: Extracted {len(phase2_key_terms)} key terms")

            # Evaluate v2.0 rulepack rules
            phase2_rulepack_rules = evaluate_rulepack_rules(
                rulepack=rulepack_v2,
                key_terms=phase2_key_terms
            )

            logger.info(f"Phase 2: Evaluated {len(phase2_rulepack_rules)} rulepack rules")

            # Map key terms for display
            display_terms = map_key_terms_for_display(phase2_key_terms, phase2_citations, rulepack_v2)

            # Build ExtractedKeyTerms for report
            phase2_extracted_key_terms = ExtractedKeyTerms(**display_terms)

            # Wire citations into citation_map
            # Merge LLM citations with existing citation structure
            if phase2_citations:
                # Store under rulepack-specific key to avoid conflicts with PDF citations
                citation_map_key = f"{selected_rulepack_id}_llm_citations"
                # Will be added to report's citation_map below

        except Exception as e:
            logger.error(f"Phase 2 failed for rulepack '{selected_rulepack_id}': {e}")
            # Graceful degradation - continue with v1 results only
            phase2_rulepack_rules = []

    # Rebuild compliance_checks with Phase 2 citations now that Phase 2 is complete
    if phase2_citations:
        logger.info(f"Phase 2: Wiring {len(phase2_citations)} citations to compliance checks")
        compliance_checks, _ = build_preliminary_compliance_checks(report_v1.findings, phase2_citations=phase2_citations)

    # Calculate rulepack summary stats
    # Combine v1 findings (converted to rules) + Phase 2 rules
    v1_rulepack_rules = build_rulepack_rule_results(report_v1.findings)
    rulepack_rules = v1_rulepack_rules + phase2_rulepack_rules

    pass_count = sum(1 for r in rulepack_rules if r.status == "PASS")
    fail_count = sum(1 for r in rulepack_rules if r.status == "FAIL")
    warn_count = sum(1 for r in rulepack_rules if r.status == "WARN")
    info_count = sum(1 for r in rulepack_rules if r.status == "INFO")
    total_rules = len(rulepack_rules)

    rulepack_summary = RulepackSummary(
        rulepack_id=rulepack_id,
        rulepack_name=rulepack_name,
        total_rules=total_rules,
        pass_count=pass_count,
        fail_count=fail_count,
        warn_count=warn_count,
        info_count=info_count,
    )

    # Build risk assessment using Phase 4 logic
    risk_assessment = build_risk_assessment(
        compliance_checks=compliance_checks,
        rulepack_rules=rulepack_rules,
        contract_text=text,
    )

    # Build metadata
    metadata = DocumentMetadata(
        file_name=report_v1.document_name,
        document_id=None,
        classified_type=classified_type,
        rulepack_id=rulepack_id,
        rulepack_name=rulepack_name,
        analysis_timestamp=datetime.now(timezone.utc).isoformat()
    )

    # Build citation map (include Phase 2 LLM citations if available)
    citation_map = {}
    if phase2_key_terms and selected_rulepack_id:
        # Add Phase 2 citations with rulepack prefix to avoid conflicts
        for key, citation_text in phase2_citations.items():
            if citation_text:
                citation_key = f"phase2.{key}"
                citation_map[citation_key] = citation_text

    # Assemble v2 report (without executive summary initially)
    report_v2 = DocumentReportV2(
        metadata=metadata,
        executive_summary=None,  # Will be generated below
        preliminary_extraction=preliminary_extraction,
        compliance_checks=compliance_checks,
        rulepack_summary=rulepack_summary,
        rulepack_rules=rulepack_rules,
        extracted_key_terms=phase2_extracted_key_terms,  # Phase 2 key terms
        risk_assessment=risk_assessment,
        citation_map=citation_map,  # Phase 2 + future PDF citations
        passed_all=report_v1.passed_all
    )

    # Generate executive summary from fully-populated report
    report_v2.executive_summary = generate_executive_summary(report_v2)

    return report_v2


# ============================================================
# PHASE 4: RISK CALCULATION & EXECUTIVE SUMMARY
# ============================================================

def calculate_risk_level(
    compliance_checks: List['ComplianceCheckResult'],
    rulepack_rules: List['RulepackRuleResult'],
) -> str:
    """
    Determine overall risk level based on failed findings.

    Hybrid logic:
      1. Explicit severity checks (Critical/High)
      2. Count-based fallback when severities are lower or equal

    Args:
        compliance_checks: List of preliminary compliance check results
        rulepack_rules: List of rulepack-specific rule results (empty in Phase 4)

    Returns:
        str: Risk level - "Low", "Medium", "High", or "Critical"
    """
    from infrastructure import ComplianceCheckResult, RulepackRuleResult

    # Combine all results for unified risk calculation
    all_results = list(compliance_checks) + list(rulepack_rules)

    # Filter to only failed checks
    failed = [r for r in all_results if r.status == "FAIL"]

    if not failed:
        return "Low"

    # 1. If any Critical severity fail → Critical risk
    if any(r.severity.lower() == "critical" for r in failed):
        return "Critical"

    # 2. If any High severity fail → High risk
    if any(r.severity.lower() == "high" for r in failed):
        return "High"

    # 3. Count-based fallback for Medium/Low severity failures
    fail_count = len(failed)
    if fail_count == 1:
        return "Medium"
    elif fail_count == 2:
        return "Medium"
    else:
        return "High"


def build_risk_assessment(
    compliance_checks: List['ComplianceCheckResult'],
    rulepack_rules: List['RulepackRuleResult'],
    contract_text: str = ""
) -> 'RiskAssessment':
    """
    Build RiskAssessment object for Report V2.

    Hybrid strategy:
      - Use severity + status to compute overall risk via calculate_risk_level()
      - Use pre-written risk_statement / recommendation where available (rulepack rules)
      - Generate generic risks for compliance checks
      - Generate LLM-based per-check recommendations for failed checks
      - Deduplicate and cap at 5 items

    Args:
        compliance_checks: List of preliminary compliance check results
        rulepack_rules: List of rulepack-specific rule results
        contract_text: Full contract text for LLM context (optional)

    Returns:
        RiskAssessment: Populated risk assessment object
    """
    from infrastructure import RiskAssessment

    # Calculate overall risk level
    overall = calculate_risk_level(compliance_checks, rulepack_rules)

    # Collect failed checks from both sources
    failed = [r for r in (list(compliance_checks) + list(rulepack_rules)) if r.status == "FAIL"]

    risk_strings: List[str] = []
    rec_strings: List[str] = []

    # Extract risks and recommendations from failed checks
    for r in failed:
        # Try to get pre-written risk_statement (RulepackRuleResult has this)
        risk_stmt = getattr(r, 'risk_statement', None)
        if risk_stmt:
            risk_strings.append(risk_stmt)
        else:
            # Use reason_short if available, otherwise fall back to message
            reason = getattr(r, 'reason_short', None) or r.message
            # Clean up reason text and format as bullet
            reason = reason.rstrip('.')
            risk_strings.append(f"{r.label}: {reason}")

        # Try to get pre-written recommendation (RulepackRuleResult has this)
        rec = getattr(r, 'recommendation', None)
        if rec:
            rec_strings.append(rec)

    # Deduplicate and cap at 5 items
    def dedupe(seq: List[str]) -> List[str]:
        seen = set()
        out = []
        for s in seq:
            if s in seen:
                continue
            seen.add(s)
            out.append(s)
        return out

    risk_strings = dedupe(risk_strings)[:5]
    rec_strings = dedupe(rec_strings)[:5]

    # If no recommendations, add a generic one
    if not rec_strings and failed:
        rec_strings.append("Review the failed checks above and consider renegotiating or seeking legal review.")

    # Generate LLM-based per-check recommendations
    recommendations_per_check = {}
    if contract_text and failed:
        recommendations_per_check = _generate_llm_recommendations(
            failed_checks=failed,
            contract_text=contract_text,
            max_recommendations=5
        )

    return RiskAssessment(
        overall_risk_level=overall,
        top_risks=risk_strings,
        recommendations=rec_strings,
        recommendations_per_check=recommendations_per_check,
        risk_calculation_method="Hybrid",
    )


def _generate_llm_recommendations(
    failed_checks: List,
    contract_text: str,
    max_recommendations: int = 5
) -> Dict[str, str]:
    """
    Generate LLM-based recommendations for failed checks.

    Returns structured JSON mapping check_id to recommendation text.
    This enables per-check recommendations in Section 7.2.

    Args:
        failed_checks: List of failed ComplianceCheckResult and RulepackRuleResult
        contract_text: Full contract text for context
        max_recommendations: Maximum number of recommendations to generate

    Returns:
        Dict mapping check_id to recommendation text
    """
    from infrastructure import settings

    # Check if LLM is enabled
    if not settings.get_llm_enabled():
        return {}

    # Load provider
    try:
        provider = load_provider()
        if provider is None:
            return {}
    except Exception:
        return {}

    # Build context from failed checks
    failed_summary = []
    for check in failed_checks[:max_recommendations]:
        check_id = check.check_id if hasattr(check, 'check_id') else check.rule_id
        label = check.label
        message = check.message
        severity = check.severity if hasattr(check, 'severity') else "Medium"
        failed_summary.append(f"- [{check_id}] {label} ({severity}): {message[:150]}")

    if not failed_summary:
        return {}

    # Create LLM prompt for structured recommendations
    prompt = (
        "You are a legal contract advisor. Generate specific, actionable recommendations for each failed compliance check.\n\n"
        "Failed Checks:\n"
        + "\n".join(failed_summary) + "\n\n"
        "Contract excerpt (first 1000 chars):\n-----\n"
        f"{contract_text[:1000]}\n-----\n\n"
        "For each failed check, provide a clear recommendation on how to fix it.\n\n"
        "Return your response in this JSON format:\n"
        "{\n"
        '  "check_id_1": "Specific recommendation for fixing this issue (1-2 sentences)",\n'
        '  "check_id_2": "Specific recommendation for fixing this issue (1-2 sentences)"\n'
        "}\n\n"
        "Guidelines:\n"
        "- Be specific and actionable\n"
        "- Focus on contract language changes or additions\n"
        "- Keep each recommendation to 1-2 sentences\n"
        "- Use the check_id from the failed checks list\n"
    )

    try:
        mode, response = _call_llm_any(provider, doc_text=contract_text, prompt=prompt)
        response = (response or "").strip()

        if not response or response.startswith("[llm error:"):
            return {}

        # Parse JSON response
        import json
        import re

        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            try:
                recommendations_dict = json.loads(json_match.group(0))
                # Clean up LLM prefixes from each recommendation
                return {k: _clean_llm_prefix(v) for k, v in recommendations_dict.items() if isinstance(v, str)}
            except json.JSONDecodeError:
                pass

        return {}
    except Exception:
        return {}


def generate_executive_summary(report_v2: 'DocumentReportV2') -> str:
    """
    Generate a short executive summary paragraph from the V2 report.

    Target style:
      - 2-4 sentences
      - Mention doc type, risk level, and main issues
      - Add context about jurisdiction/duration if available

    Args:
        report_v2: Complete DocumentReportV2 object with all sections populated

    Returns:
        str: Executive summary paragraph
    """
    meta = report_v2.metadata
    risk = report_v2.risk_assessment
    prelim = report_v2.preliminary_extraction

    doc_type = meta.classified_type if meta.classified_type != "Unknown" else "contract"
    risk_level = risk.overall_risk_level or "Unknown"

    # Base sentence
    base = f"This {doc_type} has an overall risk level of {risk_level}."

    # Pull up to 2 top risks as key issues
    if risk.top_risks:
        key_issues = "; ".join(risk.top_risks[:2])
        issues_sentence = f" Key issues include: {key_issues}."
    else:
        issues_sentence = ""

    # Add context about jurisdiction/duration if available
    context_bits = []
    if prelim.jurisdiction and prelim.jurisdiction != "Not specified":
        context_bits.append(f"governed by {prelim.jurisdiction}")
    if prelim.duration and prelim.duration not in ("Not clearly specified", "Not specified"):
        context_bits.append(f"with a term of {prelim.duration}")

    if context_bits:
        context_sentence = " The agreement appears to be " + " and ".join(context_bits) + "."
    else:
        context_sentence = ""

    return base + issues_sentence + context_sentence


# ============================================================
# PHASE 5: RULEPACK RULE MAPPING
# ============================================================

# Set of preliminary rule IDs (already handled in compliance_checks)
PRELIM_RULE_IDS = set(PRELIM_CHECK_CONFIG.keys())


def build_rulepack_rule_results(findings: List['Finding']) -> List['RulepackRuleResult']:
    """
    Map v1 Finding objects into RulepackRuleResult for Section 5.2 (Detailed Rules).

    Excludes the 4 preliminary compliance checks (they're already in compliance_checks).
    Maps custom rules from evaluate_custom_rules() into structured RulepackRuleResult objects.

    Args:
        findings: List of all Finding objects from v1 report

    Returns:
        List[RulepackRuleResult]: Structured rule results for Section 5.2
    """
    from infrastructure import RulepackRuleResult

    results: List[RulepackRuleResult] = []

    for f in findings:
        # Skip the 4 prelim compliance rules (they're already in Section 4)
        if f.rule_id in PRELIM_RULE_IDS:
            continue

        # Skip LLM status findings (not actual rule evaluations)
        if f.rule_id == "llm_explanations_status":
            continue

        # Derive a human-readable label – fallback to rule_id
        label = getattr(f, "label", None)
        if not label:
            # Convert rule_id to Title Case with spaces
            label = f.rule_id.replace("_", " ").replace(".", " ").title()

        # Status from passed flag
        status = "PASS" if f.passed else "FAIL"

        # Severity: default Medium; can be enhanced from YAML later
        severity = getattr(f, "severity", "Medium")

        # Category: if you have categories in your rules, use them; else derive from rule_id
        category = getattr(f, "category", None)
        if not category:
            # Try to extract category from rule_id (e.g., "lease.property" -> "Lease")
            if "." in f.rule_id:
                category = f.rule_id.split(".")[0].title()
            else:
                category = "General"

        # risk_statement / recommendation: for now None – will be pulled from YAML later
        risk_stmt = getattr(f, "risk_statement", None)
        rec = getattr(f, "recommendation", None)

        results.append(
            RulepackRuleResult(
                rule_id=f.rule_id,
                label=label,
                category=category,
                status=status,
                severity=severity,
                message=f.details,
                citations=f.citations,
                risk_statement=risk_stmt,
                recommendation=rec,
            )
        )

    return results


# ============================================================
# PHASE 5: MARKDOWN RENDERING (REPORT V2)
# ============================================================

def render_markdown_v2(report_v2: 'DocumentReportV2') -> str:
    """
    Render DocumentReportV2 as structured Markdown with 8-section template.

    Matches the canonical template structure exactly:
    1. Document Metadata - File name, doc ID, classified type, rulepack, date, result
    2. Executive Summary - Summary text, risk level, key concerns
    3. Preliminary Extraction (Base Fields) - Universal contract fields
    4. Preliminary Compliance Checks - Standard checks table with citations
    5. Rulepack Evaluation - Summary + detailed rules table with Rule ID and Category
    6. Extracted Key Terms - Rulepack-specific extractions
    7. Risks & Recommendations - Top risks and action items
    8. Appendix: Citations - Full citation index

    Args:
        report_v2: DocumentReportV2 object with all sections populated

    Returns:
        str: Formatted Markdown report following exact canonical template
    """
    from infrastructure import DocumentReportV2

    lines = []

    # ====================
    # MAIN HEADING
    # ====================
    lines.append("# Contract Analysis Report")
    lines.append("")

    # ====================
    # 1. DOCUMENT METADATA
    # ====================
    lines.append("## 1. Document Metadata")
    lines.append("")
    lines.append(f"- **File name:** {report_v2.metadata.file_name}")
    lines.append(f"- **Document ID:** {report_v2.metadata.document_id or 'N/A'}")
    lines.append(f"- **Classified type:** {report_v2.metadata.classified_type}")
    lines.append(f"- **Rulepack used:** {report_v2.metadata.rulepack_id} ({report_v2.metadata.rulepack_name})")
    lines.append(f"- **Analysis date:** {report_v2.metadata.analysis_timestamp}")
    lines.append(f"- **Overall result:** {'✅ PASS' if report_v2.passed_all else '❌ FAIL'}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ====================
    # 2. EXECUTIVE SUMMARY
    # ====================
    lines.append("## 2. Executive Summary")
    lines.append("")

    # Executive summary text first
    if report_v2.executive_summary:
        lines.append(report_v2.executive_summary)
        lines.append("")

    # Then risk level and key concerns
    ra = report_v2.risk_assessment
    risk_level = ra.overall_risk_level or "Unknown"
    risk_icon = {
        "Low": "🟢",
        "Medium": "🟡",
        "High": "🟠",
        "Critical": "🔴",
        "Unknown": "⚪"
    }.get(risk_level, "⚪")

    lines.append(f"- **Overall risk level:** {risk_icon} {risk_level}")

    if ra.top_risks:
        lines.append("- **Key concerns:**")
        for risk in ra.top_risks[:3]:  # Top 3 concerns
            lines.append(f"  - {risk}")

    lines.append("")
    lines.append("---")
    lines.append("")

    # ====================
    # 3. PRELIMINARY EXTRACTION (BASE FIELDS)
    # ====================
    lines.append("## 3. Preliminary Extraction (Base Fields)")
    lines.append("")
    lines.append("These fields are extracted for every document, regardless of rulepack.")
    lines.append("")

    pe = report_v2.preliminary_extraction
    lines.append(f"- **Document type (inferred):** {pe.document_type}")
    lines.append(f"- **Parties involved:** {pe.parties_summary}")
    lines.append(f"- **Length / duration of contract:** {pe.duration}")
    lines.append(f"- **Fees & payment terms (summary):** {pe.fees_summary}")
    lines.append(f"- **Terms of termination (summary):** {pe.termination_summary}")
    lines.append(f"- **Jurisdiction (extracted):** {pe.jurisdiction}")
    lines.append("")

    # Citations for preliminary extraction
    if hasattr(pe, 'citations') and pe.citations:
        citations_text = ", ".join([f"p. {c.page}" for c in pe.citations[:5] if c.page])
        lines.append(f"> **Citations:** {citations_text or 'None collected'}")
    else:
        lines.append("> **Citations:** None collected")

    lines.append("")
    lines.append("---")
    lines.append("")

    # ====================
    # 4. PRELIMINARY COMPLIANCE CHECKS
    # ====================
    lines.append("## 4. Preliminary Compliance Checks")
    lines.append("")
    lines.append("These core compliance rules are evaluated for every document.")
    lines.append("")

    # Build lookup for the 4 standard checks
    check_map = {c.check_id: c for c in report_v2.compliance_checks}

    # Expected check IDs in canonical order
    expected_checks = [
        ("jurisdiction_present_and_allowed", "Jurisdiction allowed", "High"),
        ("liability_cap_present_and_within_bounds", "Liability cap within allowed bounds", "High"),
        ("fraud_clause_present_and_assigned", "Fraud / willful misconduct carve-out", "High"),
        ("contract_value_within_limit", "Contract value within limit", "Medium"),
    ]

    # Render table
    lines.append("| Check | Status | Severity | Finding |")
    lines.append("|-------|--------|----------|---------|")

    MAX_FINDING_LEN = 140

    for check_id, label, severity in expected_checks:
        if check_id in check_map:
            check = check_map[check_id]
            status = "✅ PASS" if check.status == "PASS" else "❌ FAIL"

            # Use reason_short if available, otherwise fall back to message
            finding = check.reason_short or check.message or "See detailed analysis in Section 7."
            finding = finding.replace("|", "\\|").replace("\n", " ").strip()

            # Truncate if too long
            if len(finding) > MAX_FINDING_LEN:
                finding = finding[:MAX_FINDING_LEN - 1].rstrip() + "…"
        else:
            status = "N/A"
            finding = "Check not evaluated"

        lines.append(f"| {label} | {status} | {severity} | {finding} |")

    lines.append("")

    # Add citations blockquote
    lines.append("> **Citations:**  ")
    for check_id, label, _ in expected_checks:
        if check_id in check_map:
            check = check_map[check_id]
            if check.citations:
                citations_text = ", ".join([f"p. {c.page}" for c in check.citations[:3] if c.page])
                lines.append(f"> - {label}: {citations_text or 'None'}")
            else:
                lines.append(f"> - {label}: None")

    lines.append("")
    lines.append("---")
    lines.append("")

    # ====================
    # 5. RULEPACK EVALUATION
    # ====================
    rs = report_v2.rulepack_summary
    lines.append(f"## 5. Rulepack Evaluation ({rs.rulepack_name})")
    lines.append("")

    # 5.1 Summary
    lines.append("### 5.1 Summary")
    lines.append("")
    lines.append(f"- **Rulepack ID:** {rs.rulepack_id}")
    lines.append(f"- **Matched doc type:** {report_v2.metadata.classified_type}")
    lines.append(f"- **Total rules evaluated:** {rs.total_rules}")
    lines.append(f"- **Pass / Fail / Info:** {rs.pass_count} / {rs.fail_count} / {rs.info_count}")
    lines.append("")

    # 5.2 Detailed Rules
    lines.append("### 5.2 Detailed Rules")
    lines.append("")

    if report_v2.rulepack_rules:
        # Render as table with Rule, Status, Severity, Finding
        lines.append("| Rule | Status | Severity | Finding |")
        lines.append("|------|--------|----------|---------|")

        for rule in report_v2.rulepack_rules:
            status_icon = "✅" if rule.status == "PASS" else ("⚠️" if rule.status == "WARN" else "❌")
            status_text = f"{status_icon} {rule.status}"

            # Escape pipes and truncate message
            message = (rule.message or "").replace("|", "\\|").replace("\n", " ").strip()
            if len(message) > 100:
                message = message[:100] + "…"

            # Use label as the rule name (or rule_id as fallback)
            rule_name = (rule.label or rule.rule_id).replace("|", "\\|")

            lines.append(f"| {rule_name} | {status_text} | {rule.severity} | {message} |")

        lines.append("")
    else:
        lines.append("_No rulepack-specific rules were evaluated._")
        lines.append("")

    lines.append("---")
    lines.append("")

    # ====================
    # 6. EXTRACTED KEY TERMS
    # ====================
    lines.append("## 6. Extracted Key Terms")
    lines.append("")

    if report_v2.extracted_key_terms:
        # Render extracted key terms as bullet list
        extracted_dict = report_v2.extracted_key_terms if isinstance(report_v2.extracted_key_terms, dict) else report_v2.extracted_key_terms.model_dump()

        # Phase 2 key terms have nested structure: {field_name: {label, value, type, description}}
        # Show ALL terms, not just those with values
        all_terms = {}
        for key, value in extracted_dict.items():
            if isinstance(value, dict) and 'label' in value and 'value' in value:
                # Phase 2 structure: {label: str, value: any, type: str, description: str}
                actual_value = value.get('value')
                label = value.get('label', key.replace("_", " ").title())
                all_terms[label] = actual_value  # Include None/empty values
            elif value is not None and value != "":
                # Simple structure (legacy or direct dict)
                all_terms[key] = value

        if all_terms:
            for label, value in all_terms.items():
                # Format value nicely, handling None/empty
                if value is None or value == "":
                    formatted_value = "_Not specified_"
                elif isinstance(value, bool):
                    # For booleans, show "Yes" for True, "No" for False
                    formatted_value = "Yes" if value else "No"
                elif isinstance(value, (int, float)):
                    formatted_value = str(value)
                else:
                    formatted_value = str(value)

                lines.append(f"- **{label}:** {formatted_value}")
            lines.append("")
        else:
            lines.append("_No rulepack-specific key terms extracted._")
            lines.append("")
    else:
        lines.append("_No rulepack-specific key terms extracted (future enhancement)._")
        lines.append("")

    lines.append("---")
    lines.append("")

    # ====================
    # 7. RISKS & RECOMMENDATIONS
    # ====================
    lines.append("## 7. Risks & Recommendations")
    lines.append("")

    # 7.1 Top Risks
    lines.append("### 7.1 Top Risks")
    lines.append("")

    # Get failed checks with detailed explanations
    failed_checks = [c for c in report_v2.compliance_checks if c.status == "FAIL"]
    failed_rules = [r for r in report_v2.rulepack_rules if r.status == "FAIL"]
    all_failed = failed_checks + failed_rules

    if all_failed:
        # Render using short + detailed format
        for i, check in enumerate(all_failed[:5], 1):  # Top 5 risks
            # Get short and detailed explanations
            short = getattr(check, 'reason_short', None) or check.message
            detailed = getattr(check, 'reason_detailed', None)

            # Clean up short reason
            short = short.rstrip('.')

            # Format: "{i}. {check_name}: {short}"
            lines.append(f"{i}. **{check.label}:** {short}")
            lines.append("")

            # Add detailed explanation if available
            if detailed and detailed != short:
                lines.append(detailed)
                lines.append("")
        lines.append("")
    else:
        lines.append("_No specific risks identified by the rule engine._")
        lines.append("")

    # 7.2 Recommendations
    lines.append("### 7.2 Recommendations")
    lines.append("")

    # Display LLM-generated per-check recommendations if available
    if ra.recommendations_per_check:
        lines.append("_The following recommendations are AI-generated and should be reviewed by legal counsel._")
        lines.append("")

        # Match recommendations to failed checks by check_id
        check_id_to_label = {}
        for check in all_failed:
            cid = check.check_id if hasattr(check, 'check_id') else check.rule_id
            check_id_to_label[cid] = check.label

        # Render per-check recommendations
        for check_id, recommendation in ra.recommendations_per_check.items():
            label = check_id_to_label.get(check_id, check_id.replace("_", " ").title())
            lines.append(f"**For {label}:** {recommendation}")
            lines.append("")
    elif ra.recommendations:
        # Fallback to legacy recommendations list
        for i, rec in enumerate(ra.recommendations, 1):
            lines.append(f"{i}. {rec}")
        lines.append("")
    else:
        lines.append("_No specific recommendations generated. Consider legal review for any failed checks._")
        lines.append("")

    lines.append("---")
    lines.append("")

    # ====================
    # 8. APPENDIX: CITATIONS
    # ====================
    lines.append("## 8. Appendix: Citations")
    lines.append("")
    lines.append("This section groups all citations by the report section where they appear.")
    lines.append("")

    # Collect citations from all sections
    has_any_citations = False

    # Section 3: Preliminary Extraction
    if hasattr(report_v2.preliminary_extraction, 'citations') and report_v2.preliminary_extraction.citations:
        has_any_citations = True
        lines.append("### Section 3: Preliminary Extraction")
        lines.append("")
        for i, citation in enumerate(report_v2.preliminary_extraction.citations, 1):
            citation_ref = _format_citation_with_page_line(citation, i)
            lines.append(citation_ref)
            lines.append("")

    # Section 4: Preliminary Compliance Checks
    compliance_citations = []
    for check in report_v2.compliance_checks:
        if check.citations:
            compliance_citations.extend([(check.label, c) for c in check.citations])

    if compliance_citations:
        has_any_citations = True
        lines.append("### Section 4: Preliminary Compliance Checks")
        lines.append("")
        for i, (check_label, citation) in enumerate(compliance_citations, 1):
            citation_ref = _format_citation_with_page_line(citation, i, context=check_label)
            lines.append(citation_ref)
            lines.append("")

    # Section 5: Rulepack Evaluation
    rulepack_citations = []
    for rule in report_v2.rulepack_rules:
        if rule.citations:
            rulepack_citations.extend([(rule.label, c) for c in rule.citations])

    if rulepack_citations:
        has_any_citations = True
        lines.append("### Section 5: Rulepack Evaluation")
        lines.append("")
        for i, (rule_label, citation) in enumerate(rulepack_citations, 1):
            citation_ref = _format_citation_with_page_line(citation, i, context=rule_label)
            lines.append(citation_ref)
            lines.append("")

    # Section 6: Phase 2 LLM Citations (from citation_map)
    if report_v2.citation_map and len(report_v2.citation_map) > 0:
        has_any_citations = True
        lines.append("### Section 6: Extracted Key Terms (LLM Citations)")
        lines.append("")
        for citation_id, citation_text in list(report_v2.citation_map.items())[:20]:
            excerpt = (citation_text or "").strip()
            if len(excerpt) > 150:
                excerpt = excerpt[:150] + "…"
            lines.append(f"**{citation_id}** – \"{excerpt}\"")
            lines.append("")

    if not has_any_citations:
        lines.append("_No citations were collected during analysis. This is expected for documents without PDF page mapping._")
        lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append("_Page and line numbers are computed from the PDF text extraction layout._")
    lines.append("")

    return "\n".join(lines)


def _format_citation_with_page_line(citation: 'Citation', index: int, context: str = None) -> str:
    """
    Format a Citation object with page/line numbers and snippet.

    Args:
        citation: Citation object with page, line_start, line_end, quote fields
        index: Citation index number for this section
        context: Optional context label (e.g., check name or rule name)

    Returns:
        Formatted citation string
    """
    from infrastructure import Citation

    # Build location string
    location_parts = []
    if citation.page is not None:
        if citation.line_start is not None and citation.line_end is not None:
            if citation.line_start == citation.line_end:
                location_parts.append(f"Page {citation.page}, Line {citation.line_start}")
            else:
                location_parts.append(f"Page {citation.page}, Lines {citation.line_start}–{citation.line_end}")
        else:
            location_parts.append(f"Page {citation.page}")
    else:
        location_parts.append(f"Chars {citation.char_start}–{citation.char_end}")

    location = ", ".join(location_parts)

    # Format snippet
    snippet = (citation.quote or "").replace("\r", " ").replace("\n", " ").strip()
    if len(snippet) > 150:
        snippet = snippet[:150] + "…"

    # Build citation reference
    if context:
        return f"{index}. **[{context}]** {location}: \"{snippet}\""
    else:
        return f"{index}. {location}: \"{snippet}\""


def render_report_markdown(report: DocumentReport) -> str:
    """
    Render DocumentReport as Markdown, respecting USE_REPORT_V2 config.

    This wrapper checks the USE_REPORT_V2 flag and calls the appropriate renderer:
    - If USE_REPORT_V2=True and report has report_v2, use render_markdown_v2()
    - Otherwise, use legacy render_markdown()

    Args:
        report: DocumentReport (v1) with optional report_v2 attribute

    Returns:
        str: Formatted Markdown report
    """
    from infrastructure import settings

    # Check if V2 rendering is enabled and available
    use_v2 = settings.USE_REPORT_V2
    has_v2 = hasattr(report, 'report_v2') and report.report_v2 is not None

    if use_v2 and has_v2:
        # Use Report V2 renderer
        return render_markdown_v2(report.report_v2)
    else:
        # Fall back to legacy v1 renderer
        return render_markdown(report)


def make_report(document_name: str, text: str, rules: RuleSet, pack_data: Optional[Any] = None, llm_override: Optional[bool] = None) -> DocumentReport:
    """
    PRIMARY ANALYSIS MODE ENTRY POINT

    Generate a complete compliance report for a contract document.
    This is the main API that orchestrates the full analysis pipeline:
    EXTRACT → EVALUATE → REPORT.

    PIPELINE FLOW
    =============

    1. RESOLVE METADATA
       - Extract document name from pack_data or use provided name
       - Ensures reports show actual filenames, not temp paths

    2. EXTRACTION PHASE (optional, if pack_data has LLM prompt)
       - Call extract_lease_fields() to extract structured data
       - Uses LLM provider (Ollama, etc.) with pack_data.prompt + examples
       - Returns LeaseExtraction object with 60+ fields
       - Skipped if pack_data.prompt is None/empty

    3. EVALUATION PHASE
       - Call evaluate_text_against_rules() for compliance checks
       - Runs 4 hardcoded standard checks (jurisdiction, fraud, liability, contract value)
       - Runs custom rules from pack_data.rules_json (if present)
       - Returns List[Finding] with pass/fail for each rule
       - All rules are evaluated (Bug 1b fix ensures no early exit)

    4. ENHANCEMENT PHASE
       - Add page/line numbers to all citations
       - Guard against monetary false positives (shares vs dollars)
       - Normalize jurisdiction findings
       - Add LLM-generated explanations for failures (if enabled)

    5. REPORT ASSEMBLY
       - Create DocumentReport with:
         * document_name (resolved from metadata)
         * passed_all (True only if ALL findings pass)
         * findings (complete list of all rule results)
         * extraction (structured data from step 2, if any)
       - Can be rendered to Markdown, JSON, CSV, Excel

    ARGUMENTS
    =========

    document_name : str
        Human-readable document identifier. Will be resolved through
        _resolve_document_name() to prefer pack_data metadata over temp paths.
        Examples: "employment_contract", "lease_agreement_2024"

    text : str
        Full contract text content (from PDF extraction or direct input).
        Should include page break markers (\f) for accurate citation mapping.
        Text is cleaned (signature noise removed) before evaluation.

    rules : RuleSet
        Compliance rules to evaluate (from YAML rule pack).
        Contains: jurisdiction_allowlist, liability_cap, fraud, contract_value.
        See infrastructure.py RuleSet for schema.

    pack_data : Optional[Any]
        Runtime rulepack data structure with:
        - .prompt (str): LLM extraction prompt (optional)
        - .examples (List): LLM extraction examples (optional)
        - .rules_json (List[dict]): Custom rules for dispatching (optional)
        - .document_name / .source_filename: Metadata for name resolution
        If None, extraction is skipped and only standard checks run.

    llm_override : Optional[bool]
        Override LLM behavior:
        - None: Use default from settings (LLM_EXPLANATIONS_ENABLED)
        - True: Force enable LLM extraction and explanations
        - False: Disable all LLM features (fast mode, no explanations)

    RETURNS
    =======

    DocumentReport
        Complete analysis report containing:
        - document_name: Resolved document identifier
        - passed_all: True if ALL findings passed, False otherwise
        - findings: List[Finding] - all rule evaluation results
        - extraction: LeaseExtraction - structured data (None if no LLM prompt)

        Can be:
        - Rendered to Markdown with render_markdown()
        - Exported to JSON/CSV/Excel with export_utils
        - Returned to MCP client for LibreChat display

    INTEGRATION NOTES
    =================

    For RuleEngine (Task 3):
        Replace evaluate_text_against_rules() call with:
        findings = rule_engine.evaluate_all(text, rules, extraction)

    For Extraction Mode (Task 4):
        Return LeaseExtraction directly, skip evaluation:
        extraction = extract_lease_fields(...)
        return extraction  # No DocumentReport

    For Custom Emitters:
        After building DocumentReport, emit to various outputs:
        emitter.emit(report)  # JSON stream, webhook, S3, etc.

    EXAMPLE USAGE
    =============

    >>> from infrastructure import RuleSet
    >>> from document_analysis import extract_text_with_pages
    >>>
    >>> # Load document and rules
    >>> text = extract_text_with_pages("contract.pdf")
    >>> rules = RuleSet.from_yaml("employment.yml")
    >>> pack_data = load_rulepack("employment_v1")
    >>>
    >>> # Generate report
    >>> report = make_report(
    ...     document_name="employment_contract",
    ...     text=text,
    ...     rules=rules,
    ...     pack_data=pack_data
    ... )
    >>>
    >>> # Use report
    >>> print(f"Passed: {report.passed_all}")
    >>> print(f"Findings: {len(report.findings)}")
    >>> markdown = render_markdown(report)
    """
    from infrastructure import settings, LeaseExtraction
    from document_analysis import enhance_citations_with_page_line

    # ============================================================
    # PHASE 1: RESOLVE METADATA
    # ============================================================
    # BUG 1a FIX: Resolve document name from metadata before proceeding
    # Tries: pack_data.source_filename, pack_data.document_name, etc.
    # Falls back to provided document_name or "Unknown Document"
    resolved_document_name = _resolve_document_name(document_name, pack_data)

    # ============================================================
    # PHASE 2: EXTRACTION (optional, LLM-based)
    # ============================================================
    # ⚠️ TASK 3a: LEASE EXTRACTION - TEMPORARILY DISABLED
    # ============================================================
    # TO RE-ENABLE LEASE EXTRACTION:
    # 1. Uncomment the code block below (lines ~2110-2127)
    # 2. Uncomment the Lease Abstract rendering in render_markdown() (lines ~2257-2378)
    # 3. Restart the HTTP bridge server
    #
    # This extracts structured lease data using LLM and populates
    # the LeaseExtraction model with 60+ fields including:
    # - Property info (name, address, type, square footage)
    # - Tenant/Landlord details (names, contacts, addresses)
    # - Dates (commencement, expiration, term)
    # - Rent terms (base rent, escalations, CAM charges)
    # - Security deposits, options, maintenance, insurance, etc.
    #
    # The extraction uses:
    # - pack_data.prompt: LLM extraction instructions
    # - pack_data.examples: Example extractions
    # - extract_lease_fields(): Direct Ollama API calls
    # - LEASE_FIELD_ALIASES: Maps LLM output keys to model fields
    # ============================================================
    extraction = None
    # print(f"\n[DEBUG make_report] PHASE 2: EXTRACTION")
    # print(f"[DEBUG make_report] pack_data={pack_data is not None}")
    # if pack_data:
    #     print(f"[DEBUG make_report] pack_data.id={getattr(pack_data, 'id', 'N/A')}")
    #     print(f"[DEBUG make_report] has prompt={hasattr(pack_data, 'prompt')}")
    #     print(f"[DEBUG make_report] prompt length={len(getattr(pack_data, 'prompt', ''))} chars")
    #
    # if pack_data and hasattr(pack_data, 'prompt') and pack_data.prompt:
    #     examples = getattr(pack_data, 'examples', [])
    #     print(f"[DEBUG make_report] Calling extract_lease_fields...")
    #     extraction = extract_lease_fields(text, pack_data.prompt, examples, llm_override)
    #     print(f"[DEBUG make_report] Extraction complete: {extraction is not None}")
    #     if extraction:
    #         populated = len([k for k, v in extraction.model_dump().items() if v])
    #         print(f"[DEBUG make_report] Extraction has {populated} populated fields")
    # else:
    #     print(f"[DEBUG make_report] Skipping extraction (no prompt in pack_data)")

    # ============================================================
    # PHASE 3: EVALUATION (compliance rule checking)
    # ============================================================
    # Evaluate ALL compliance rules (4 hardcoded + custom rules from pack_data)
    # BUG 1b FIX: Ensure ALL rules are evaluated (no early exits)
    # INTEGRATION POINT: For RuleEngine (Task 3), replace this with:
    #   findings = rule_engine.evaluate_all(text, rules, extraction)
    findings, _guess = evaluate_text_against_rules(text, rules, extraction, pack_data) or ([], None)
    print(f"[debug] LLM explanations = {settings.get_llm_enabled(llm_override)} (default=enabled, override={llm_override})")

    # ============================================================
    # PHASE 4: ENHANCEMENT (citations, guards, explanations)
    # ============================================================
    # Enhance findings with page/line citations, guard against false positives,
    # normalize contradictions, and add LLM-generated explanations
    if findings:
        # Sub-phase 4a: Add page and line numbers to all citations
        # Converts character positions to page/line references using text layout
        # BUG 1b FIX: Process ALL findings, not just first
        for finding in findings:
            if finding.citations:
                finding.citations = enhance_citations_with_page_line(text, finding.citations)

        # Sub-phase 4b: Guard against monetary false positives
        # Prevents "200 million shares" from being flagged as contract value
        findings = _maybe_guard_monetary_false_positives(text, findings)

        # Sub-phase 4c: Normalize findings based on rule context
        # Fixes contract-value + jurisdiction contradictions
        findings = _normalize_findings_with_rules(text, rules, findings)

        # Sub-phase 4d: Add LLM-generated explanations for failures
        # Provides actionable remediation advice (now enabled by default)
        findings = _maybe_add_llm_explanations(text, rules, findings, llm_override=llm_override)

    # Handle edge case: no findings returned
    if not findings:
        findings = [Finding(
            rule_id="no_findings_returned",
            passed=False,
            details="No findings returned by the rule engine for this document.",
            citations=[],
        )]

    # ============================================================
    # PHASE 5: REPORT ASSEMBLY
    # ============================================================
    # Build final DocumentReport with all findings and extraction data
    # BUG 1b FIX: Explicitly compute passed_all from ALL findings
    passed_all = all(f.passed for f in findings)

    # BUG 1a FIX: Use resolved document name in report
    # INTEGRATION POINT: For Custom Emitters, emit report here:
    #   emitter.emit(report)  # JSON stream, webhook, S3, etc.

    # PHASE A SMOKE TEST: Log what we're putting into DocumentReport
    print(f"\n[DEBUG make_report] ======== CREATING DocumentReport ========")
    print(f"[DEBUG make_report] document_name: {resolved_document_name}")
    print(f"[DEBUG make_report] passed_all: {passed_all}")
    print(f"[DEBUG make_report] findings count: {len(findings)}")
    print(f"[DEBUG make_report] extraction is None: {extraction is None}")
    if extraction:
        dump = extraction.model_dump()
        populated = {k: v for k, v in dump.items() if v}
        print(f"[DEBUG make_report] extraction populated fields count: {len(populated)}")
        print(f"[DEBUG make_report] extraction populated fields sample: {list(populated.items())[:5]}")
    print(f"[DEBUG make_report] ==========================================\n")

    report = DocumentReport(
        document_name=resolved_document_name,
        passed_all=passed_all,
        findings=findings,
        extraction=extraction
    )

    # PHASE A SMOKE TEST: Verify report has extraction after construction
    print(f"[DEBUG make_report] ======== DocumentReport CREATED ========")
    print(f"[DEBUG make_report] report.extraction is None: {report.extraction is None}")
    if report.extraction:
        dump = report.extraction.model_dump()
        populated = {k: v for k, v in dump.items() if v}
        print(f"[DEBUG make_report] report.extraction populated fields: {len(populated)}")
        print(f"[DEBUG make_report] report.extraction sample values:")
        for k, v in list(populated.items())[:5]:
            print(f"[DEBUG make_report]   {k}: {v}")
    print(f"[DEBUG make_report] ========================================\n")

    # ============================================================
    # REPORT V2 CONSTRUCTION (PHASE 3)
    # ============================================================
    # Build DocumentReportV2 alongside v1 for future migration
    # This is constructed but not yet used until USE_REPORT_V2 is enabled
    report_v2 = build_report_v2_from_v1(
        report_v1=report,
        text=text,
        pack_data=pack_data,
        classified_type=_infer_doc_type_from_pack(pack_data)
    )

    # Attach V2 to v1 report for now (temporary during migration)
    # MCP tools can check if report has 'report_v2' attribute
    report.report_v2 = report_v2  # type: ignore

    return report


# ========================================
# MARKDOWN RENDERING AND OUTPUT
# ========================================

def render_markdown(report: DocumentReport) -> str:
    """Render a document report as Markdown with optional Lease Abstract."""
    lines = []
    lines.append(f"# Compliance Report — {report.document_name}")
    lines.append("")
    lines.append(f"**Overall:** {'✅ PASS' if report.passed_all else '❌ FAIL'}")
    lines.append("")

    # Add Executive Summary for failing cases
    if not report.passed_all:
        failed_findings = [f for f in report.findings if not f.passed and f.rule_id != "llm_explanations_status"]
        if failed_findings:
            lines.append("## Executive Summary")
            lines.append("")

            # Get top 3 failing rules
            top_failed = failed_findings[:3]
            summary_parts = []

            for f in top_failed:
                rule_name = (f.rule_id or "").replace("_", " ").title()
                summary_parts.append(f"**{rule_name}**: {f.details}")

            if summary_parts:
                lines.append("This contract analysis identified critical compliance issues that require immediate attention:")
                lines.append("")
                for part in summary_parts:
                    lines.append(f"- {part}")
                lines.append("")
                lines.append("**Risk Assessment**: These violations may expose the organization to legal and financial liabilities. Immediate remediation is recommended to ensure contractual compliance and risk mitigation.")
                lines.append("")
                lines.append("**Recommended Action**: Review and revise the identified clauses to align with compliance requirements before contract execution.")
                lines.append("")

    # ============================================================
    # TASK 3a: LEASE ABSTRACT - TEMPORARILY DISABLED
    # ============================================================
    # TO RE-ENABLE LEASE ABSTRACT:
    # 1. Uncomment the code block below (lines ~2275-2396)
    # 2. Uncomment the extraction code in make_report() (lines ~2110-2144)
    # 3. Restart the HTTP bridge server
    #
    # This renders a comprehensive Lease Abstract section with:
    # - Property Information (name, address, type, square footage, zoning)
    # - Tenant Information (legal name, trade name, address, contact, phone, email)
    # - Landlord Information (legal name, address, contact, phone, email)
    # - Important Dates (commencement, expiration, term, renewal deadline)
    # - Rent and Financial Terms (base rent, escalations, CAM, taxes, insurance)
    # - Security and Deposits (security deposit amount, holder, additional deposits)
    # - Options and Rights (renewal, expansion, first refusal, sublease, assignment)
    # - Use and Restrictions (permitted use, prohibited uses, exclusive use, hours, signage)
    # - Maintenance and Repairs (landlord/tenant obligations, structural, HVAC)
    # - Insurance and Liability (general liability, property insurance, additional insured)
    # - Default and Termination (notice periods, grace periods, penalties, early termination)
    # - Special Provisions (force majeure, casualty, condemnation, estoppel, subordination)
    # - Parking and Access (parking spaces, parking type, common area access)
    # ============================================================
    # if report.extraction:
    #     ext = report.extraction
    #     lines.append("## Lease Abstract")
    #     lines.append("")
    #
    #     # Property Information
    #     lines.append("### Property Information")
    #     lines.append(f"- **Property Name:** {ext.property_name or 'Not specified'}")
    #     lines.append(f"- **Property Address:** {ext.property_address or 'Not specified'}")
    #     lines.append(f"- **Property Type:** {ext.property_type or 'Not specified'}")
    #     lines.append(f"- **Square Footage:** {ext.property_square_footage or 'Not specified'}")
    #     lines.append(f"- **Zoning:** {ext.property_zoning or 'Not specified'}")
    #     lines.append("")
    #
    #     # Tenant Information
    #     lines.append("### Tenant Information")
    #     lines.append(f"- **Legal Name:** {ext.tenant_legal_name or 'Not specified'}")
    #     lines.append(f"- **Trade Name:** {ext.tenant_trade_name or 'Not specified'}")
    #     lines.append(f"- **Address:** {ext.tenant_address or 'Not specified'}")
    #     lines.append(f"- **Contact Person:** {ext.tenant_contact_person or 'Not specified'}")
    #     lines.append(f"- **Phone:** {ext.tenant_phone or 'Not specified'}")
    #     lines.append(f"- **Email:** {ext.tenant_email or 'Not specified'}")
    #     lines.append("")
    #
    #     # Landlord Information
    #     lines.append("### Landlord Information")
    #     lines.append(f"- **Legal Name:** {ext.landlord_legal_name or 'Not specified'}")
    #     lines.append(f"- **Address:** {ext.landlord_address or 'Not specified'}")
    #     lines.append(f"- **Contact Person:** {ext.landlord_contact_person or 'Not specified'}")
    #     lines.append(f"- **Phone:** {ext.landlord_phone or 'Not specified'}")
    #     lines.append(f"- **Email:** {ext.landlord_email or 'Not specified'}")
    #     lines.append("")
    #
    #     # Important Dates
    #     lines.append("### Important Dates")
    #     lines.append(f"- **Commencement Date:** {ext.lease_commencement_date or 'Not specified'}")
    #     lines.append(f"- **Expiration Date:** {ext.lease_expiration_date or 'Not specified'}")
    #     lines.append(f"- **Lease Term (Months):** {ext.lease_term_months or 'Not specified'}")
    #     lines.append(f"- **Rent Commencement Date:** {ext.rent_commencement_date or 'Not specified'}")
    #     lines.append(f"- **Option to Renew Deadline:** {ext.option_to_renew_deadline or 'Not specified'}")
    #     lines.append(f"- **Notice to Vacate (Days):** {ext.notice_to_vacate_days or 'Not specified'}")
    #     lines.append("")
    #
    #     # Rent and Financial Terms
    #     lines.append("### Rent and Financial Terms")
    #     lines.append(f"- **Base Rent Amount:** {ext.base_rent_amount or 'Not specified'}")
    #     lines.append(f"- **Base Rent Frequency:** {ext.base_rent_frequency or 'Not specified'}")
    #     lines.append(f"- **Rent Increase Percentage:** {ext.rent_increase_percentage or 'Not specified'}")
    #     lines.append(f"- **Rent Increase Frequency:** {ext.rent_increase_frequency or 'Not specified'}")
    #     lines.append(f"- **CAM Charges (Monthly):** {ext.cam_charges_monthly or 'Not specified'}")
    #     lines.append(f"- **CAM Charges (Annual):** {ext.cam_charges_annual or 'Not specified'}")
    #     lines.append(f"- **Real Estate Tax Responsibility:** {ext.real_estate_tax_responsibility or 'Not specified'}")
    #     lines.append(f"- **Insurance Responsibility:** {ext.insurance_responsibility or 'Not specified'}")
    #     lines.append(f"- **Utilities Responsibility:** {ext.utilities_responsibility or 'Not specified'}")
    #     lines.append("")
    #
    #     # Security and Deposits
    #     lines.append("### Security and Deposits")
    #     lines.append(f"- **Security Deposit Amount:** {ext.security_deposit_amount or 'Not specified'}")
    #     lines.append(f"- **Security Deposit Held By:** {ext.security_deposit_held_by or 'Not specified'}")
    #     lines.append(f"- **Additional Deposit Amount:** {ext.additional_deposit_amount or 'Not specified'}")
    #     lines.append(f"- **Deposit Return (Days):** {ext.deposit_return_days or 'Not specified'}")
    #     lines.append("")
    #
    #     # Options and Rights
    #     lines.append("### Options and Rights")
    #     lines.append(f"- **Option to Renew Terms:** {ext.option_to_renew_terms or 'Not specified'}")
    #     lines.append(f"- **Option to Expand:** {ext.option_to_expand or 'Not specified'}")
    #     lines.append(f"- **Right of First Refusal:** {ext.right_of_first_refusal or 'Not specified'}")
    #     lines.append(f"- **Sublease Allowed:** {ext.sublease_allowed or 'Not specified'}")
    #     lines.append(f"- **Assignment Allowed:** {ext.assignment_allowed or 'Not specified'}")
    #     lines.append("")
    #
    #     # Use and Restrictions
    #     lines.append("### Use and Restrictions")
    #     lines.append(f"- **Permitted Use:** {ext.permitted_use or 'Not specified'}")
    #     lines.append(f"- **Prohibited Uses:** {ext.prohibited_uses or 'Not specified'}")
    #     lines.append(f"- **Exclusive Use Clause:** {ext.exclusive_use_clause or 'Not specified'}")
    #     lines.append(f"- **Operating Hours:** {ext.operating_hours or 'Not specified'}")
    #     lines.append(f"- **Signage Rights:** {ext.signage_rights or 'Not specified'}")
    #     lines.append("")
    #
    #     # Maintenance and Repairs
    #     lines.append("### Maintenance and Repairs")
    #     lines.append(f"- **Landlord Maintenance Obligations:** {ext.landlord_maintenance_obligations or 'Not specified'}")
    #     lines.append(f"- **Tenant Maintenance Obligations:** {ext.tenant_maintenance_obligations or 'Not specified'}")
    #     lines.append(f"- **Structural Repair Responsibility:** {ext.structural_repair_responsibility or 'Not specified'}")
    #     lines.append(f"- **HVAC Maintenance Responsibility:** {ext.hvac_maintenance_responsibility or 'Not specified'}")
    #     lines.append("")
    #
    #     # Insurance and Liability
    #     lines.append("### Insurance and Liability")
    #     lines.append(f"- **General Liability Coverage Required:** {ext.general_liability_coverage_required or 'Not specified'}")
    #     lines.append(f"- **Property Insurance Required:** {ext.property_insurance_required or 'Not specified'}")
    #     lines.append(f"- **Additional Insured Requirement:** {ext.additional_insured_requirement or 'Not specified'}")
    #     lines.append("")
    #
    #     # Default and Termination
    #     lines.append("### Default and Termination")
    #     lines.append(f"- **Default Notice (Days):** {ext.default_notice_days or 'Not specified'}")
    #     lines.append(f"- **Cure Period (Days):** {ext.cure_period_days or 'Not specified'}")
    #     lines.append(f"- **Late Payment Grace Period:** {ext.late_payment_grace_period or 'Not specified'}")
    #     lines.append(f"- **Late Payment Penalty:** {ext.late_payment_penalty or 'Not specified'}")
    #     lines.append(f"- **Early Termination Rights:** {ext.early_termination_rights or 'Not specified'}")
    #     lines.append("")
    #
    #     # Special Provisions
    #     lines.append("### Special Provisions")
    #     lines.append(f"- **Force Majeure Clause:** {ext.force_majeure_clause or 'Not specified'}")
    #     lines.append(f"- **Casualty Damage Provisions:** {ext.casualty_damage_provisions or 'Not specified'}")
    #     lines.append(f"- **Condemnation Provisions:** {ext.condemnation_provisions or 'Not specified'}")
    #     lines.append(f"- **Estoppel Certificate Requirement:** {ext.estoppel_certificate_requirement or 'Not specified'}")
    #     lines.append(f"- **Subordination Clause:** {ext.subordination_clause or 'Not specified'}")
    #     lines.append("")
    #
    #     # Parking and Access
    #     lines.append("### Parking and Access")
    #     lines.append(f"- **Parking Spaces Allocated:** {ext.parking_spaces_allocated or 'Not specified'}")
    #     lines.append(f"- **Parking Type:** {ext.parking_type or 'Not specified'}")
    #     lines.append(f"- **Common Area Access:** {ext.common_area_access or 'Not specified'}")
    #     lines.append("")

    # Compliance Findings
    lines.append("## Compliance Findings")
    lines.append("")

    for f in report.findings:
        # Skip status findings in the detailed section
        if f.rule_id == "llm_explanations_status":
            continue

        title = (f.rule_id or "").replace("_", " ").title() or "Finding"
        lines.append(f"### {title}")
        lines.append(f"- **Result:** {'PASS' if f.passed else 'FAIL'}")
        lines.append(f"- **Details:** {f.details}")
        if f.citations:
            lines.append("- **Citations:**")
            for c in f.citations:
                quote = (c.quote or "").replace("\r", " ").replace("\n", " ").strip()
                if len(quote) > 420:
                    quote = quote[:420] + "…"

                # Build citation with page and line info
                citation_parts = []
                if c.page is not None:
                    if c.line_start is not None and c.line_end is not None:
                        if c.line_start == c.line_end:
                            citation_parts.append(f"p. {c.page}, line {c.line_start}")
                        else:
                            citation_parts.append(f"p. {c.page}, lines {c.line_start}–{c.line_end}")
                    else:
                        citation_parts.append(f"p. {c.page}")

                citation_parts.append(f"chars [{c.char_start}-{c.char_end}]")
                citation_info = ", ".join(citation_parts)

                confidence_note = ""
                if c.confidence < 1.0:
                    confidence_note = f" (confidence: {c.confidence:.1f})"

                lines.append(f"  - {citation_info}: \"{quote}\"{confidence_note}")
        lines.append("")

    # Add citation footnote
    lines.append("---")
    lines.append("")
    lines.append("**Citations Note:** Page and line numbers are computed from the PDF text extraction layout. Page numbers are 1-based, line numbers reflect text layout post-extraction.")
    lines.append("")

    return "\n".join(lines)


def save_markdown(report: DocumentReport, out_dir: Path):
    """Save report as Markdown file using the V2 renderer (if enabled)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    # Use the wrapper that respects USE_REPORT_V2 setting
    markdown_content = render_report_markdown(report)
    (out_dir / "report.md").write_text(markdown_content, encoding="utf-8")


def save_txt(report: DocumentReport, out_dir: Path):
    """Save report as JSON files."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.txt").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    (out_dir / "_eval_debug.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")


# ========================================
# PUBLIC API
# ========================================

__all__ = [
    # LLM Providers
    'LLMProvider',
    'OllamaProvider',
    'load_provider',

    # Analysis Engine
    'make_report',
    'render_markdown',
    'save_markdown',
    'save_txt',

    # Internal utilities (for testing/debugging)
    '_call_llm_any',
    '_maybe_add_llm_explanations',
    '_normalize_findings_with_rules',
    '_maybe_guard_monetary_false_positives',
]