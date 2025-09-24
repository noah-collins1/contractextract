"""
Comprehensive MCP Tools for ContractExtract - Full API coverage with LLM rule pack management.
"""
from typing import List, Dict, Any, Optional, Union
import logging
import os
import io
import json
import hashlib
from pathlib import Path

# Import business logic
from db import SessionLocal, init_db
from rulepack_loader import load_packs_for_runtime
from schemas import RulePack as RuntimeRulePack
from ingest import ingest_bytes_to_text
from evaluator import make_report, save_markdown, save_txt
from doc_type import guess_doc_type_id

# Import database models and operations
from models_rulepack import RulePackRecord
from yaml_importer import import_rulepack_yaml
from rulepack_repo import publish_pack
from rulepack_dtos import RulePackRead, RulePackUpdate
from schemas import RuleSet, ExampleItem

# Import bridge client for optional v1 LangExtract integration
from bridge_client import remote_extract

log = logging.getLogger("contractextract.mcp")


# ========================================
# RULE PACK MANAGEMENT TOOLS
# ========================================

def list_all_rulepacks() -> List[Dict[str, Any]]:
    """
    List ALL rule packs in the database (any status/version).
    Returns detailed information for LLM to understand current state.
    """
    try:
        with SessionLocal() as db:
            rows = db.query(RulePackRecord).order_by(
                RulePackRecord.id.asc(), RulePackRecord.version.asc()
            ).all()

            result = []
            for r in rows:
                result.append({
                    "id": r.id,
                    "version": r.version,
                    "status": r.status,
                    "doc_type_names": list(r.doc_type_names or []),
                    "created_by": r.created_by,
                    "notes": r.notes or ""
                })

            log.info(f"MCP list_all_rulepacks: found {len(result)} total packs")
            return result
    except Exception as e:
        log.error(f"MCP list_all_rulepacks failed: {e}")
        raise ValueError(f"Failed to list rule packs: {str(e)}")


def list_active_rulepacks() -> List[Dict[str, Any]]:
    """
    List only active rule packs (for runtime evaluation).
    """
    try:
        with SessionLocal() as db:
            packs_dict = load_packs_for_runtime(db)
            result = []
            for pack_id, pack in packs_dict.items():
                version = getattr(pack, 'version', 1)
                result.append({
                    "name": pack_id,
                    "version": str(version),
                    "doc_type_names": list(getattr(pack, 'doc_type_names', []))
                })
            log.info(f"MCP list_active_rulepacks: found {len(result)} active packs")
            return result
    except Exception as e:
        log.error(f"MCP list_active_rulepacks failed: {e}")
        return []


def get_rulepack_details(pack_id: str, version: Optional[int] = None) -> Dict[str, Any]:
    """
    Get detailed information for a specific rule pack version.
    If version is None, gets the latest version.
    """
    try:
        with SessionLocal() as db:
            query = db.query(RulePackRecord).filter(RulePackRecord.id == pack_id)

            if version is not None:
                query = query.filter(RulePackRecord.version == version)
            else:
                query = query.order_by(RulePackRecord.version.desc())

            rec = query.first()

            if rec is None:
                raise ValueError(f"Rule pack '{pack_id}' not found")

            # Convert to detailed response
            result = {
                "id": rec.id,
                "version": rec.version,
                "status": rec.status,
                "schema_version": rec.schema_version,
                "doc_type_names": list(rec.doc_type_names or []),
                "rules": rec.ruleset_json or {},
                "rules_json": list(rec.rules_json or []),
                "llm_prompt": rec.llm_prompt or "",
                "llm_examples": rec.llm_examples_json or [],
                "extensions": rec.extensions_json,
                "extensions_schema": rec.extensions_schema_json,
                "raw_yaml": rec.raw_yaml or "",
                "notes": rec.notes or "",
                "created_by": rec.created_by or ""
            }

            log.info(f"MCP get_rulepack_details: retrieved {pack_id}@{rec.version}")
            return result

    except Exception as e:
        log.error(f"MCP get_rulepack_details failed for '{pack_id}': {e}")
        raise ValueError(f"Failed to get rule pack details: {str(e)}")


def get_rulepack_yaml(pack_id: str, version: Optional[int] = None) -> str:
    """
    Get the raw YAML content for a rule pack.
    """
    try:
        with SessionLocal() as db:
            query = db.query(RulePackRecord).filter(RulePackRecord.id == pack_id)

            if version is not None:
                query = query.filter(RulePackRecord.version == version)
            else:
                query = query.order_by(RulePackRecord.version.desc())

            rec = query.first()

            if rec is None:
                raise ValueError(f"Rule pack '{pack_id}' not found")

            yaml_content = rec.raw_yaml or ""
            log.info(f"MCP get_rulepack_yaml: retrieved YAML for {pack_id}@{rec.version}")
            return yaml_content

    except Exception as e:
        log.error(f"MCP get_rulepack_yaml failed for '{pack_id}': {e}")
        raise ValueError(f"Failed to get rule pack YAML: {str(e)}")


def list_rulepack_versions(pack_id: str) -> List[Dict[str, Any]]:
    """
    List all versions for a given rule pack id.
    """
    try:
        with SessionLocal() as db:
            rows = (
                db.query(RulePackRecord)
                .filter(RulePackRecord.id == pack_id)
                .order_by(RulePackRecord.version.asc())
                .all()
            )

            if not rows:
                raise ValueError(f"No rule pack found with id '{pack_id}'")

            result = []
            for r in rows:
                result.append({
                    "id": r.id,
                    "version": r.version,
                    "status": r.status,
                    "doc_type_names": list(r.doc_type_names or []),
                    "notes": r.notes or ""
                })

            log.info(f"MCP list_rulepack_versions: found {len(result)} versions for {pack_id}")
            return result

    except Exception as e:
        log.error(f"MCP list_rulepack_versions failed for '{pack_id}': {e}")
        raise ValueError(f"Failed to list versions for rule pack '{pack_id}': {str(e)}")


# ========================================
# RULE PACK CREATION AND EDITING TOOLS
# ========================================

def create_rulepack_from_yaml(yaml_content: str, created_by: str = "mcp-llm") -> Dict[str, Any]:
    """
    Create a new rule pack from YAML content.
    The YAML must contain an 'id' field and proper structure.
    Returns the created draft rule pack details.
    """
    try:
        with SessionLocal() as db:
            draft = import_rulepack_yaml(db, yaml_text=yaml_content, created_by=created_by)

            result = {
                "id": draft.id,
                "version": draft.version,
                "status": "draft",
                "doc_type_names": list(getattr(draft, "doc_type_names", [])),
                "message": f"Draft rule pack '{draft.id}' created successfully"
            }

            log.info(f"MCP create_rulepack_from_yaml: created {draft.id}@{draft.version}")
            return result

    except Exception as e:
        log.error(f"MCP create_rulepack_from_yaml failed: {e}")
        raise ValueError(f"Failed to create rule pack from YAML: {str(e)}")


def update_rulepack_yaml(pack_id: str, version: int, yaml_content: str) -> Dict[str, Any]:
    """
    Update a draft rule pack with new YAML content.
    Only draft rule packs can be edited.
    """
    try:
        with SessionLocal() as db:
            rec = (
                db.query(RulePackRecord)
                .filter(RulePackRecord.id == pack_id, RulePackRecord.version == version)
                .one_or_none()
            )

            if rec is None:
                raise ValueError(f"Rule pack {pack_id}@{version} not found")

            if rec.status != "draft":
                raise ValueError(f"Only draft rule packs can be edited. Current status: {rec.status}")

            # Parse and update the rule pack
            from yaml_importer import _parse_yaml_to_update, _apply_update_to_record

            # Helper function to parse YAML (similar to app.py logic)
            import yaml
            raw = yaml.safe_load(yaml_content) or {}

            rules = RuleSet(
                jurisdiction={"allowed_countries": raw.get("jurisdiction_allowlist", [])},
                liability_cap=raw.get("liability_cap", {}) or {},
                contract=raw.get("contract", {}) or {},
                fraud=raw.get("fraud", {}) or {},
            )
            examples_yaml = raw.get("examples", []) or []
            examples = [ExampleItem.parse_obj(e) for e in examples_yaml]

            upd = RulePackUpdate(
                schema_version=raw.get("schema_version"),
                doc_type_names=raw.get("doc_type_names") or None,
                rules=rules,
                rules_json=(raw.get("rules") or []),
                llm_prompt=raw.get("prompt") or None,
                examples=examples,
                extensions=raw.get("extensions"),
                extensions_schema=raw.get("extensions_schema"),
                raw_yaml=yaml_content,
                notes=raw.get("notes"),
            )

            # Apply update
            if upd.schema_version is not None:
                rec.schema_version = upd.schema_version
            if upd.doc_type_names is not None:
                rec.doc_type_names = list(upd.doc_type_names)
            if upd.rules is not None:
                rec.ruleset_json = upd.rules.dict()
            if upd.rules_json is not None:
                rec.rules_json = list(upd.rules_json)
            if upd.llm_prompt is not None:
                rec.llm_prompt = upd.llm_prompt
            if upd.examples is not None:
                rec.llm_examples_json = [e.dict() for e in upd.examples]
            if upd.extensions is not None:
                rec.extensions_json = upd.extensions
            if upd.extensions_schema is not None:
                rec.extensions_schema_json = upd.extensions_schema
            if upd.raw_yaml is not None:
                rec.raw_yaml = upd.raw_yaml
            if upd.notes is not None:
                rec.notes = upd.notes

            db.add(rec)
            db.commit()
            db.refresh(rec)

            result = {
                "id": rec.id,
                "version": rec.version,
                "status": rec.status,
                "doc_type_names": list(rec.doc_type_names or []),
                "message": f"Rule pack {pack_id}@{version} updated successfully"
            }

            log.info(f"MCP update_rulepack_yaml: updated {pack_id}@{version}")
            return result

    except Exception as e:
        log.error(f"MCP update_rulepack_yaml failed for {pack_id}@{version}: {e}")
        db.rollback()
        raise ValueError(f"Failed to update rule pack: {str(e)}")


def publish_rulepack(pack_id: str, version: int) -> Dict[str, Any]:
    """
    Publish a draft rule pack to make it active.
    """
    try:
        with SessionLocal() as db:
            active = publish_pack(db, pack_id=pack_id, version=version)

            result = {
                "id": active.id,
                "version": active.version,
                "status": "active",
                "doc_type_names": list(getattr(active, "doc_type_names", [])),
                "message": f"Rule pack {pack_id}@{version} published successfully"
            }

            log.info(f"MCP publish_rulepack: published {pack_id}@{version}")
            return result

    except Exception as e:
        log.error(f"MCP publish_rulepack failed for {pack_id}@{version}: {e}")
        raise ValueError(f"Failed to publish rule pack: {str(e)}")


def deprecate_rulepack(pack_id: str, version: int) -> Dict[str, Any]:
    """
    Deprecate an active rule pack.
    """
    try:
        with SessionLocal() as db:
            rec = (
                db.query(RulePackRecord)
                .filter(RulePackRecord.id == pack_id, RulePackRecord.version == version)
                .one_or_none()
            )

            if rec is None:
                raise ValueError(f"Rule pack {pack_id}@{version} not found")

            if rec.status == "deprecated":
                result = {
                    "id": rec.id,
                    "version": rec.version,
                    "status": "deprecated",
                    "message": f"Rule pack {pack_id}@{version} was already deprecated"
                }
                return result

            if rec.status not in ("active", "draft"):
                raise ValueError(f"Cannot deprecate rule pack with status '{rec.status}'")

            rec.status = "deprecated"
            db.add(rec)
            db.commit()

            result = {
                "id": rec.id,
                "version": rec.version,
                "status": "deprecated",
                "message": f"Rule pack {pack_id}@{version} deprecated successfully"
            }

            log.info(f"MCP deprecate_rulepack: deprecated {pack_id}@{version}")
            return result

    except Exception as e:
        log.error(f"MCP deprecate_rulepack failed for {pack_id}@{version}: {e}")
        raise ValueError(f"Failed to deprecate rule pack: {str(e)}")


def delete_rulepack(pack_id: str, version: int, force: bool = False) -> Dict[str, Any]:
    """
    Delete a rule pack version.
    By default, only draft packs can be deleted. Set force=True to delete any status.
    """
    try:
        with SessionLocal() as db:
            rec = (
                db.query(RulePackRecord)
                .filter(RulePackRecord.id == pack_id, RulePackRecord.version == version)
                .one_or_none()
            )

            if rec is None:
                raise ValueError(f"Rule pack {pack_id}@{version} not found")

            if rec.status != "draft" and not force:
                raise ValueError(
                    f"Cannot delete {rec.status} pack without force=True. "
                    f"Consider deprecating it instead, or use force=True if deletion is really needed."
                )

            db.delete(rec)
            db.commit()

            result = {
                "id": pack_id,
                "version": version,
                "status": "deleted",
                "message": f"Rule pack {pack_id}@{version} deleted successfully"
            }

            log.info(f"MCP delete_rulepack: deleted {pack_id}@{version}")
            return result

    except Exception as e:
        log.error(f"MCP delete_rulepack failed for {pack_id}@{version}: {e}")
        db.rollback()
        raise ValueError(f"Failed to delete rule pack: {str(e)}")


# ========================================
# DOCUMENT ANALYSIS TOOLS
# ========================================

def analyze_document(req: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze a contract document using rule packs.
    Enhanced version with comprehensive output and optional v1 bridge.
    """
    try:
        document_path = req.get("document_path")
        document_text = req.get("document_text")
        doc_type_hint = req.get("doc_type_hint")
        pack_id_hint = req.get("pack_id")  # New: allow specifying exact pack

        # Derive text from input
        text = None
        document_name = "mcp_document"

        if document_path:
            path_obj = Path(document_path)
            if not path_obj.exists():
                raise ValueError(f"Document path does not exist: {document_path}")

            with open(path_obj, 'rb') as f:
                raw_bytes = f.read()
            text = ingest_bytes_to_text(raw_bytes, filename=path_obj.name)
            document_name = path_obj.stem

        elif document_text:
            text = document_text
            document_name = "text_input"

        else:
            raise ValueError("Either document_path or document_text must be provided")

        # Initialize DB and load packs
        init_db()
        with SessionLocal() as db:
            packs_dict = load_packs_for_runtime(db)

            if not packs_dict:
                raise ValueError("No active rule packs available")

            # Choose pack (enhanced selection logic)
            selected_pack = None
            selected_pack_id = None

            if pack_id_hint and pack_id_hint in packs_dict:
                # Use explicitly specified pack
                selected_pack = packs_dict[pack_id_hint]
                selected_pack_id = pack_id_hint
            elif doc_type_hint and doc_type_hint in packs_dict:
                # Use doc type hint
                selected_pack = packs_dict[doc_type_hint]
                selected_pack_id = doc_type_hint
            else:
                # Use guess or fallback to first pack
                guessed_id = guess_doc_type_id(text, packs_dict)
                if guessed_id:
                    selected_pack = packs_dict[guessed_id]
                    selected_pack_id = guessed_id
                else:
                    # Fallback to first available pack
                    selected_pack_id = next(iter(packs_dict.keys()))
                    selected_pack = packs_dict[selected_pack_id]

            # Create safe output directory
            doc_hash = hashlib.md5(document_name.encode()).hexdigest()[:8]
            out_dir = Path("outputs") / "mcp_demo" / f"{document_name}_{doc_hash}"
            out_dir.mkdir(parents=True, exist_ok=True)

            # Check if v1 bridge should be used
            use_v1_bridge = os.getenv("USE_V1_BRIDGE", "0").lower() in ("1", "true", "yes")
            v1_result = None

            if use_v1_bridge:
                try:
                    log.info("Using v1 LangExtract bridge for additional processing")
                    pack_prompt = getattr(selected_pack, 'llm_prompt', '') or ''
                    pack_examples = getattr(selected_pack, 'llm_examples', []) or []

                    v1_result = remote_extract(
                        text=text,
                        prompt=pack_prompt,
                        examples=pack_examples
                    )

                    # Save v1 results
                    v1_output_file = out_dir / "v1_extract_result.json"
                    with open(v1_output_file, 'w', encoding='utf-8') as f:
                        json.dump(v1_result, f, indent=2, ensure_ascii=False)
                    log.info(f"V1 extraction result saved to: {v1_output_file}")

                except Exception as e:
                    log.warning(f"V1 bridge failed, continuing with standard analysis: {e}")

            # Run standard analysis (always performed)
            report = make_report(
                document_name=document_name,
                text=text,
                rules=selected_pack.rules
            )

            # Save artifacts
            save_markdown(report, out_dir)
            save_txt(report, out_dir)

            # Build comprehensive results
            violations = []
            findings_summary = []

            for finding in report.findings:
                finding_summary = {
                    "rule_id": finding.rule_id,
                    "passed": finding.passed,
                    "details": finding.details
                }
                findings_summary.append(finding_summary)

                if not finding.passed:
                    excerpt = ""
                    citations = []

                    if hasattr(finding, 'citations') and finding.citations:
                        for citation in finding.citations:
                            quote = (citation.quote or "").strip()
                            if len(quote) > 200:
                                quote = quote[:200] + "..."
                            citations.append({
                                "quote": quote,
                                "char_start": getattr(citation, 'char_start', None),
                                "char_end": getattr(citation, 'char_end', None)
                            })

                        if citations:
                            excerpt = citations[0]["quote"]

                    violations.append({
                        "rule_id": finding.rule_id,
                        "excerpt": excerpt,
                        "citations": citations,
                        "details": finding.details
                    })

            result = {
                "document_name": document_name,
                "doc_type": selected_pack_id,
                "pack_version": getattr(selected_pack, 'version', 1),
                "overall_result": "PASS" if report.passed_all else "FAIL",
                "violations": violations,
                "findings_summary": findings_summary,
                "violation_count": len(violations),
                "total_findings": len(findings_summary),
                "output_files": {
                    "markdown_report": str(out_dir / "report.md"),
                    "text_report": str(out_dir / "report.txt"),
                    "v1_extract_result": str(out_dir / "v1_extract_result.json") if v1_result else None
                },
                "v1_bridge_used": use_v1_bridge and v1_result is not None
            }

            log.info(f"MCP analyze_document: processed {document_name}, result: {result['overall_result']}, violations: {len(violations)}")
            return result

    except Exception as e:
        log.error(f"MCP analyze_document failed: {e}")
        raise ValueError(f"Document analysis failed: {str(e)}")


def preview_document_analysis(document_text: str, pack_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Quick preview analysis without saving files.
    Useful for iterative rule pack development.
    """
    try:
        # Initialize DB and load packs
        init_db()
        with SessionLocal() as db:
            packs_dict = load_packs_for_runtime(db)

            if not packs_dict:
                raise ValueError("No active rule packs available")

            # Choose pack
            selected_pack_id = pack_id
            if not selected_pack_id or selected_pack_id not in packs_dict:
                guessed_id = guess_doc_type_id(document_text, packs_dict)
                selected_pack_id = guessed_id or next(iter(packs_dict.keys()))

            selected_pack = packs_dict[selected_pack_id]

            # Run analysis
            report = make_report(
                document_name="preview",
                text=document_text,
                rules=selected_pack.rules
            )

            # Build summary results
            violations = []
            for finding in report.findings:
                if not finding.passed:
                    excerpt = ""
                    if hasattr(finding, 'citations') and finding.citations:
                        first_citation = finding.citations[0]
                        excerpt = (first_citation.quote or "").strip()
                        if len(excerpt) > 100:
                            excerpt = excerpt[:100] + "..."

                    violations.append({
                        "rule_id": finding.rule_id,
                        "excerpt": excerpt,
                        "details": finding.details
                    })

            result = {
                "pack_used": selected_pack_id,
                "overall_result": "PASS" if report.passed_all else "FAIL",
                "violation_count": len(violations),
                "violations": violations,
                "total_findings_checked": len(report.findings)
            }

            log.info(f"MCP preview_document_analysis: {result['overall_result']}, {len(violations)} violations")
            return result

    except Exception as e:
        log.error(f"MCP preview_document_analysis failed: {e}")
        raise ValueError(f"Preview analysis failed: {str(e)}")


# ========================================
# UTILITY AND HELPER TOOLS
# ========================================

def generate_rulepack_template(pack_id: str, doc_type_names: List[str]) -> str:
    """
    Generate a YAML template for creating new rule packs.
    Useful for LLM to understand the expected structure.
    """
    template = f"""# Rule Pack Template
id: {pack_id}
schema_version: "1.0"
doc_type_names:
{chr(10).join(f"  - {name}" for name in doc_type_names)}

# Jurisdiction rules - specify allowed countries
jurisdiction_allowlist:
  - "United States"
  - "Canada"
  - "European Union"

# Liability cap rules
liability_cap:
  enabled: true
  min_amount: 1000000
  max_amount: 50000000
  required_currency: ["USD", "EUR", "CAD"]

# Contract value rules
contract:
  min_value: 100000
  max_value: 10000000
  value_required: true

# Fraud detection rules
fraud:
  enabled: true
  check_patterns: true

# LLM prompt for additional analysis
prompt: |
  Review this contract for compliance with the specified rules.
  Pay special attention to liability caps, jurisdiction clauses, and contract values.
  Identify any potential compliance issues or missing required clauses.

# Examples for LLM training (optional)
examples: []

# Additional notes
notes: "Template rule pack for {pack_id}"
"""

    log.info(f"MCP generate_rulepack_template: generated template for {pack_id}")
    return template


def validate_rulepack_yaml(yaml_content: str) -> Dict[str, Any]:
    """
    Validate YAML content before creating/updating rule packs.
    Returns validation results and any errors found.
    """
    try:
        import yaml

        # Parse YAML
        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            return {
                "valid": False,
                "error": f"Invalid YAML syntax: {str(e)}",
                "error_type": "yaml_syntax"
            }

        if not data:
            return {
                "valid": False,
                "error": "Empty YAML content",
                "error_type": "empty_content"
            }

        # Check required fields
        required_fields = ["id", "doc_type_names"]
        missing_fields = []

        for field in required_fields:
            if field not in data:
                missing_fields.append(field)

        if missing_fields:
            return {
                "valid": False,
                "error": f"Missing required fields: {', '.join(missing_fields)}",
                "error_type": "missing_fields",
                "missing_fields": missing_fields
            }

        # Validate field types
        validation_errors = []

        if not isinstance(data["id"], str) or not data["id"].strip():
            validation_errors.append("'id' must be a non-empty string")

        if not isinstance(data["doc_type_names"], list) or not data["doc_type_names"]:
            validation_errors.append("'doc_type_names' must be a non-empty list")

        if validation_errors:
            return {
                "valid": False,
                "error": "Field validation errors: " + "; ".join(validation_errors),
                "error_type": "field_validation",
                "validation_errors": validation_errors
            }

        # Success
        result = {
            "valid": True,
            "pack_id": data["id"],
            "doc_type_names": data["doc_type_names"],
            "has_jurisdiction": "jurisdiction_allowlist" in data,
            "has_liability_cap": "liability_cap" in data,
            "has_contract_rules": "contract" in data,
            "has_fraud_rules": "fraud" in data,
            "has_prompt": "prompt" in data,
            "has_examples": "examples" in data
        }

        log.info(f"MCP validate_rulepack_yaml: validation successful for {data['id']}")
        return result

    except Exception as e:
        log.error(f"MCP validate_rulepack_yaml failed: {e}")
        return {
            "valid": False,
            "error": f"Validation failed: {str(e)}",
            "error_type": "internal_error"
        }


def get_system_info() -> Dict[str, Any]:
    """
    Get system information for debugging and monitoring.
    """
    try:
        with SessionLocal() as db:
            total_packs = db.query(RulePackRecord).count()
            active_packs = db.query(RulePackRecord).filter(RulePackRecord.status == "active").count()
            draft_packs = db.query(RulePackRecord).filter(RulePackRecord.status == "draft").count()
            deprecated_packs = db.query(RulePackRecord).filter(RulePackRecord.status == "deprecated").count()

        outputs_dir = Path("outputs")
        outputs_size = sum(f.stat().st_size for f in outputs_dir.rglob('*') if f.is_file()) if outputs_dir.exists() else 0

        result = {
            "database": {
                "total_rule_packs": total_packs,
                "active_packs": active_packs,
                "draft_packs": draft_packs,
                "deprecated_packs": deprecated_packs
            },
            "environment": {
                "v1_bridge_enabled": os.getenv("USE_V1_BRIDGE", "0").lower() in ("1", "true", "yes"),
                "outputs_directory_size_bytes": outputs_size,
                "outputs_directory_exists": outputs_dir.exists()
            },
            "mcp_tools": {
                "total_tools": 16,  # Update this count as tools are added
                "categories": ["rule_pack_management", "document_analysis", "utilities"]
            }
        }

        log.info("MCP get_system_info: retrieved system information")
        return result

    except Exception as e:
        log.error(f"MCP get_system_info failed: {e}")
        raise ValueError(f"Failed to get system information: {str(e)}")


# Legacy compatibility functions (keep existing names)
def list_rulepacks() -> List[Dict[str, Any]]:
    """Legacy compatibility - use list_active_rulepacks instead."""
    return list_active_rulepacks()


def get_rulepack(name: str, version: Optional[str] = None) -> Dict[str, Any]:
    """Legacy compatibility - use get_rulepack_details instead."""
    version_int = int(version) if version else None
    return get_rulepack_details(name, version_int)


def analyze(req: Dict[str, Any]) -> Dict[str, Any]:
    """Legacy compatibility - use analyze_document instead."""
    return analyze_document(req)


# V1 Bridge Usage Instructions:
#
# To enable the v1 LangExtract bridge, set the environment variable:
#   USE_V1_BRIDGE=1
#
# This will make analyze_document() call the v1 service at http://127.0.0.1:8091/extract
# in addition to the standard v2 analysis pipeline.
#
# To disable (default behavior):
#   USE_V1_BRIDGE=0  (or unset the variable)
#
# Example usage:
#   PowerShell: $env:USE_V1_BRIDGE="1"; uvicorn app:app --host 127.0.0.1 --port 8000 --reload
#   Windows CMD: set USE_V1_BRIDGE=1 && uvicorn app:app --host 127.0.0.1 --port 8000 --reload
#
# The v1 service must be running separately on port 8091 for the bridge to work.