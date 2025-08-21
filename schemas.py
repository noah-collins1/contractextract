# schemas.py
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class JurisdictionConfig(BaseModel):
    allowed_countries: List[str] = Field(default_factory=lambda: ["United States", "US", "USA", "Canada", "European Union", "EU", "Australia", "AUS"])

class LiabilityCapPolicy(BaseModel):
    # Enforce at least one: amount or multiplier (or both). If both provided, both must pass.
    max_cap_amount: Optional[float] = None   # e.g., 1_000_000.00 (in contract currency)
    max_cap_multiplier: Optional[float] = 1.0  # e.g., 1.0 = 1x total contract value (12 months of fees)

class ContractPolicy(BaseModel):
    # If set, the document’s inferred “contract value” must not exceed this
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

class Finding(BaseModel):
    rule_id: Literal[
        "liability_cap_present_and_within_bounds",
        "contract_value_within_limit",
        "fraud_clause_present_and_assigned",
        "jurisdiction_present_and_allowed"
    ]
    passed: bool
    details: str
    citations: List[Citation] = Field(default_factory=list)

class DocumentReport(BaseModel):
    document_name: str
    passed_all: bool
    findings: List[Finding]
