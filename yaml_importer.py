# yaml_importer.py
import yaml
from typing import Any, Dict, List
from sqlalchemy.orm import Session
from schemas import RuleSet, ExampleItem
from rulepack_dtos import RulePackCreate
from rulepack_repo import create_draft

def import_rulepack_yaml(db: Session, yaml_text: str, created_by: str | None = None):
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
