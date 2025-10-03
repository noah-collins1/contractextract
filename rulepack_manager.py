"""
Consolidated Rule Pack Management Module
Complete data access layer for rule pack storage, retrieval, and processing.

Merged from:
- models_rulepack.py: SQLAlchemy database models
- rulepack_dtos.py: Pydantic data transfer objects
- rulepack_repo.py: Database CRUD operations
- rulepack_loader.py: Runtime loading helpers
- yaml_importer.py: YAML import/export logic
"""

import yaml
from typing import List, Optional, Any, Dict, Literal
from sqlalchemy import (
    Column, String, Integer, Text, Enum, TIMESTAMP, text, func,
    PrimaryKeyConstraint, select, update
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, Session
from pydantic import BaseModel, Field, validator

from infrastructure import Base, RuleSet, ExampleItem, RulePack as RuntimeRulePack

# ========================================
# DATABASE MODELS
# ========================================

RulePackStatusEnum = Enum("draft", "active", "deprecated", name="rulepack_status")

class RulePackRecord(Base):
    """SQLAlchemy model for rule pack storage with composite primary key."""

    __tablename__ = "rule_packs"

    # Composite PK: (id, version)
    id: Mapped[str] = mapped_column(String(128))
    version: Mapped[int] = mapped_column(Integer)
    __table_args__ = (
        PrimaryKeyConstraint("id", "version", name="rule_packs_pk"),
    )

    status: Mapped[str] = mapped_column(RulePackStatusEnum, nullable=False, default="draft")
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1.0")

    # Core routing + content
    doc_type_names: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)           # list[str]
    ruleset_json: Mapped[dict]   = mapped_column(JSONB, nullable=False, default=dict)           # RuleSet as dict
    rules_json: Mapped[dict]     = mapped_column(JSONB, nullable=False, default=list)           # list[rule-objects] (optional types)
    llm_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_examples_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)        # list[ExampleItem]

    # Extensions (optional)
    extensions_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    extensions_schema_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Provenance / notes
    raw_yaml: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)

    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ========================================
# DATA TRANSFER OBJECTS (DTOs)
# ========================================

Status = Literal["draft", "active", "deprecated"]

class RulePackCreate(BaseModel):
    """DTO for creating new rule packs."""

    id: str
    schema_version: str = "1.0"
    doc_type_names: List[str] = Field(default_factory=list)
    rules: RuleSet = RuleSet()
    # future extensible list of typed rules (optional)
    rules_json: List[Dict[str, Any]] = Field(default_factory=list)
    llm_prompt: Optional[str] = None
    examples: List[ExampleItem] = Field(default_factory=list)

    extensions: Optional[Dict[str, Any]] = None
    extensions_schema: Optional[Dict[str, Any]] = None

    raw_yaml: Optional[str] = None
    notes: Optional[str] = None
    created_by: Optional[str] = None

    @validator("doc_type_names")
    def not_empty(cls, v):
        if not v:
            raise ValueError("doc_type_names must contain at least one title/alias")
        return v


class RulePackUpdate(BaseModel):
    """DTO for updating draft rule packs."""

    # Only for drafts
    schema_version: Optional[str] = None
    doc_type_names: Optional[List[str]] = None
    rules: Optional[RuleSet] = None
    rules_json: Optional[List[Dict[str, Any]]] = None
    llm_prompt: Optional[str] = None
    examples: Optional[List[ExampleItem]] = None
    extensions: Optional[Dict[str, Any]] = None
    extensions_schema: Optional[Dict[str, Any]] = None
    raw_yaml: Optional[str] = None
    notes: Optional[str] = None


class RulePackRead(BaseModel):
    """DTO for reading rule pack data."""

    id: str
    version: int
    status: Status
    schema_version: str
    doc_type_names: List[str]
    rules: RuleSet
    rules_json: List[Dict[str, Any]]
    llm_prompt: Optional[str]
    examples: List[ExampleItem]
    extensions: Optional[Dict[str, Any]] = None
    extensions_schema: Optional[Dict[str, Any]] = None
    raw_yaml: Optional[str] = None
    notes: Optional[str] = None
    created_by: Optional[str] = None


# ========================================
# CONVERSION UTILITIES
# ========================================

def _to_read(r: RulePackRecord) -> RulePackRead:
    """Convert database record to read DTO."""
    return RulePackRead(
        id=r.id,
        version=r.version,
        status=r.status,
        schema_version=r.schema_version,
        doc_type_names=list(r.doc_type_names or []),
        rules=RuleSet.parse_obj(r.ruleset_json or {}),
        rules_json=list(r.rules_json or []),
        llm_prompt=r.llm_prompt,
        examples=[ExampleItem.parse_obj(x) for x in (r.llm_examples_json or [])],
        extensions=r.extensions_json,
        extensions_schema=r.extensions_schema_json,
        raw_yaml=r.raw_yaml,
        notes=r.notes,
        created_by=r.created_by,
    )


def _to_runtime(r: RulePackRecord) -> RuntimeRulePack:
    """Convert database record to runtime rule pack."""
    return RuntimeRulePack(
        id=r.id,
        doc_type_names=list(r.doc_type_names or []),
        rules=RuleSet.parse_obj(r.ruleset_json or {}),
        prompt=r.llm_prompt or "",
        examples=[ExampleItem.parse_obj(x) for x in (r.llm_examples_json or [])],
    )


def _next_version_for_id(db: Session, pack_id: str) -> int:
    """Get the next available version number for a rule pack ID."""
    q = select(RulePackRecord.version).where(RulePackRecord.id == pack_id)
    versions = [row[0] for row in db.execute(q).all()]
    return (max(versions) + 1) if versions else 1


# ========================================
# CRUD OPERATIONS
# ========================================

def create_draft(db: Session, payload: RulePackCreate) -> RulePackRead:
    """Create a new draft rule pack."""
    version = _next_version_for_id(db, payload.id)
    rec = RulePackRecord(
        id=payload.id,
        version=version,
        status="draft",
        schema_version=payload.schema_version,
        doc_type_names=payload.doc_type_names,
        ruleset_json=payload.rules.dict(),
        rules_json=payload.rules_json,
        llm_prompt=payload.llm_prompt,
        llm_examples_json=[x.dict() for x in payload.examples],
        extensions_json=payload.extensions,
        extensions_schema_json=payload.extensions_schema,
        raw_yaml=payload.raw_yaml,
        notes=payload.notes,
        created_by=payload.created_by,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return _to_read(rec)


def update_draft(db: Session, pack_id: str, version: int, patch: RulePackUpdate) -> RulePackRead:
    """Update a draft rule pack with new data."""
    rec = db.get(RulePackRecord, {"id": pack_id, "version": version})
    if not rec:
        raise ValueError(f"Rule pack {pack_id}@{version} not found")
    if rec.status != "draft":
        raise ValueError("Only drafts can be updated")

    if patch.schema_version is not None:
        rec.schema_version = patch.schema_version
    if patch.doc_type_names is not None:
        if not patch.doc_type_names:
            raise ValueError("doc_type_names cannot be empty")
        rec.doc_type_names = patch.doc_type_names
    if patch.rules is not None:
        rec.ruleset_json = patch.rules.dict()
    if patch.rules_json is not None:
        rec.rules_json = patch.rules_json
    if patch.llm_prompt is not None:
        rec.llm_prompt = patch.llm_prompt
    if patch.examples is not None:
        rec.llm_examples_json = [x.dict() for x in patch.examples]
    if patch.extensions is not None:
        rec.extensions_json = patch.extensions
    if patch.extensions_schema is not None:
        rec.extensions_schema_json = patch.extensions_schema
    if patch.raw_yaml is not None:
        rec.raw_yaml = patch.raw_yaml
    if patch.notes is not None:
        rec.notes = patch.notes

    db.commit()
    db.refresh(rec)
    return _to_read(rec)


def publish_pack(db: Session, pack_id: str, version: int) -> RulePackRead:
    """Publish a draft rule pack to active status."""
    rec = db.get(RulePackRecord, {"id": pack_id, "version": version})
    if not rec:
        raise ValueError(f"Rule pack {pack_id}@{version} not found")
    if rec.status != "draft":
        raise ValueError("Only drafts can be published")

    # Deprecate prior active versions for this id
    db.query(RulePackRecord)\
      .filter(RulePackRecord.id == pack_id, RulePackRecord.status == "active")\
      .update({RulePackRecord.status: "deprecated"})
    # Promote this one
    rec.status = "active"
    db.commit()
    db.refresh(rec)
    return _to_read(rec)


def deprecate_pack(db: Session, pack_id: str, version: int) -> RulePackRead:
    """Deprecate a rule pack."""
    rec = db.get(RulePackRecord, {"id": pack_id, "version": version})
    if not rec:
        raise ValueError(f"Rule pack {pack_id}@{version} not found")
    rec.status = "deprecated"
    db.commit()
    db.refresh(rec)
    return _to_read(rec)


def get_pack(db: Session, pack_id: str, version: Optional[int] = None, status: Optional[str] = None) -> RulePackRead:
    """Get a specific rule pack by ID and optional version/status."""
    if version is not None:
        rec = db.get(RulePackRecord, {"id": pack_id, "version": version})
        if not rec:
            raise ValueError(f"{pack_id}@{version} not found")
        return _to_read(rec)

    q = select(RulePackRecord).where(RulePackRecord.id == pack_id)
    if status:
        q = q.where(RulePackRecord.status == status)
    else:
        q = q.where(RulePackRecord.status == "active")
    rec = db.execute(q.order_by(RulePackRecord.version.desc())).scalars().first()
    if not rec:
        raise ValueError(f"{pack_id} not found")
    return _to_read(rec)


def list_packs(db: Session, status: Optional[str] = None) -> List[RulePackRead]:
    """List all rule packs, optionally filtered by status."""
    q = select(RulePackRecord)
    if status:
        q = q.where(RulePackRecord.status == status)
    rows = db.execute(q.order_by(RulePackRecord.id, RulePackRecord.version)).scalars().all()
    return [_to_read(r) for r in rows]


def load_active_rulepacks(db: Session) -> List[RuntimeRulePack]:
    """Load all active rule packs for runtime evaluation."""
    q = select(RulePackRecord).where(RulePackRecord.status == "active")
    rows = db.execute(q).scalars().all()
    return [_to_runtime(r) for r in rows]


# ========================================
# RUNTIME LOADING HELPERS
# ========================================

def load_packs_for_runtime(db: Session) -> Dict[str, RuntimeRulePack]:
    """Load active rule packs as a dictionary keyed by pack ID."""
    packs = load_active_rulepacks(db)
    return {p.id: p for p in packs}


def select_pack_for_text(db: Session, text: str) -> RuntimeRulePack:
    """
    Select the best rule pack for a given text using document type detection.

    Note: This imports from document_analysis to avoid circular imports.
    Consider moving this function if circular dependencies become an issue.
    """
    packs = load_active_rulepacks(db)
    by_id = {p.id: p for p in packs}

    # Use document type detection (avoiding circular import)
    from document_analysis import guess_doc_type_id
    pack_id = guess_doc_type_id(text, by_id) or (packs[0].id if packs else None)

    if not pack_id:
        raise RuntimeError("No active rule packs available")
    return by_id[pack_id]


# ========================================
# YAML IMPORT/EXPORT
# ========================================

def import_rulepack_yaml(db: Session, yaml_text: str, created_by: str | None = None) -> RulePackRead:
    """
    Import a rule pack from YAML text.

    Args:
        db: Database session
        yaml_text: YAML content as string
        created_by: Optional creator identifier

    Returns:
        Created draft rule pack
    """
    raw = yaml.safe_load(yaml_text) or {}

    # Expected keys (mirror your current YAML loader structure)
    # id, doc_type_names, jurisdiction_allowlist, liability_cap, contract, fraud, prompt, examples
    rules = RuleSet(
        jurisdiction={"allowed_countries": raw.get("jurisdiction_allowlist", [])},
        liability_cap=raw.get("liability_cap", {}) or {},
        contract=raw.get("contract", {}) or {},
        fraud=raw.get("fraud", {}) or {},
    )

    examples_yaml = raw.get("examples", []) or []
    examples = [ExampleItem.parse_obj(e) for e in examples_yaml]

    payload = RulePackCreate(
        id=raw["id"],
        schema_version=raw.get("schema_version", "1.0"),
        doc_type_names=raw.get("doc_type_names", []) or [],
        rules=rules,
        llm_prompt=raw.get("prompt") or None,
        examples=examples,
        # optional
        rules_json=raw.get("rules", []) or [],
        extensions=raw.get("extensions"),
        extensions_schema=raw.get("extensions_schema"),
        raw_yaml=yaml_text,
        created_by=created_by,
        notes=raw.get("notes"),
    )

    return create_draft(db, payload)


def export_rulepack_to_yaml(db: Session, pack_id: str, version: Optional[int] = None) -> str:
    """
    Export a rule pack to YAML format.

    Args:
        db: Database session
        pack_id: Rule pack identifier
        version: Optional version (defaults to latest)

    Returns:
        YAML string representation
    """
    pack = get_pack(db, pack_id, version)

    # If we have raw_yaml stored, return that
    if pack.raw_yaml:
        return pack.raw_yaml

    # Otherwise, reconstruct YAML from data
    yaml_data = {
        "id": pack.id,
        "schema_version": pack.schema_version,
        "doc_type_names": pack.doc_type_names,
        "jurisdiction_allowlist": pack.rules.jurisdiction.get("allowed_countries", []),
        "liability_cap": pack.rules.liability_cap.dict() if pack.rules.liability_cap else {},
        "contract": pack.rules.contract.dict() if pack.rules.contract else {},
        "fraud": pack.rules.fraud.dict() if pack.rules.fraud else {},
        "prompt": pack.llm_prompt or "",
        "examples": [ex.dict() for ex in pack.examples],
    }

    # Add optional fields if present
    if pack.rules_json:
        yaml_data["rules"] = pack.rules_json
    if pack.extensions:
        yaml_data["extensions"] = pack.extensions
    if pack.extensions_schema:
        yaml_data["extensions_schema"] = pack.extensions_schema
    if pack.notes:
        yaml_data["notes"] = pack.notes

    return yaml.dump(yaml_data, default_flow_style=False, sort_keys=False)


# ========================================
# VALIDATION HELPERS
# ========================================

def validate_rulepack_structure(yaml_text: str) -> Dict[str, Any]:
    """
    Validate rule pack YAML structure without importing to database.

    Args:
        yaml_text: YAML content to validate

    Returns:
        Validation result with success status and any errors
    """
    try:
        data = yaml.safe_load(yaml_text)
        if not data:
            return {"valid": False, "error": "Empty YAML content"}

        # Check required fields
        required_fields = ["id", "doc_type_names"]
        missing = [field for field in required_fields if field not in data]
        if missing:
            return {
                "valid": False,
                "error": f"Missing required fields: {', '.join(missing)}",
                "missing_fields": missing
            }

        # Validate data types
        if not isinstance(data["id"], str) or not data["id"].strip():
            return {"valid": False, "error": "'id' must be a non-empty string"}

        if not isinstance(data["doc_type_names"], list) or not data["doc_type_names"]:
            return {"valid": False, "error": "'doc_type_names' must be a non-empty list"}

        return {
            "valid": True,
            "pack_id": data["id"],
            "doc_type_names": data["doc_type_names"],
            "schema_version": data.get("schema_version", "1.0")
        }

    except yaml.YAMLError as e:
        return {"valid": False, "error": f"Invalid YAML syntax: {str(e)}"}
    except Exception as e:
        return {"valid": False, "error": f"Validation failed: {str(e)}"}


# ========================================
# PUBLIC API
# ========================================

__all__ = [
    # Database Models
    'RulePackRecord',
    'RulePackStatusEnum',

    # DTOs
    'RulePackCreate',
    'RulePackUpdate',
    'RulePackRead',
    'Status',

    # CRUD Operations
    'create_draft',
    'update_draft',
    'publish_pack',
    'deprecate_pack',
    'get_pack',
    'list_packs',
    'load_active_rulepacks',

    # Runtime Loading
    'load_packs_for_runtime',
    'select_pack_for_text',

    # YAML Import/Export
    'import_rulepack_yaml',
    'export_rulepack_to_yaml',
    'validate_rulepack_structure',

    # Utility Functions
    '_to_read',
    '_to_runtime',
]