#!/usr/bin/env python3
"""
Pure stdio MCP Server for ContractExtract
Direct LibreChat integration via stdio protocol (no HTTP overhead)
Replaces mcp_server.py FastMCP implementation for Phase 3
"""

import asyncio
import json
import logging
import os
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

# MCP stdio server imports
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource

# Import business logic
from infrastructure import SessionLocal, init_db, RulePack as RuntimeRulePack, RuleSet, ExampleItem
from rulepack_manager import load_packs_for_runtime, RulePackRecord, import_rulepack_yaml, publish_pack, RulePackRead, RulePackUpdate
from document_analysis import ingest_bytes_to_text, guess_doc_type_id
from contract_analyzer import make_report, save_markdown, save_txt

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
log = logging.getLogger("contractextract.mcp.stdio")

# Initialize the MCP server
server = Server("ContractExtract")

# ========================================
# TOOL DEFINITIONS (Pure stdio MCP)
# ========================================

@server.list_tools()
async def list_tools() -> List[Tool]:
    """List all available MCP tools for LibreChat."""
    return [
        # Rule Pack Management Tools
        Tool(
            name="list_all_rulepacks",
            description="List ALL rule packs in the database (any status/version) with detailed information",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="list_active_rulepacks",
            description="List only active rule packs available for document analysis",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_rulepack_details",
            description="Get detailed information for a specific rule pack version",
            inputSchema={
                "type": "object",
                "properties": {
                    "pack_id": {"type": "string", "description": "Rule pack identifier"},
                    "version": {"type": "integer", "description": "Version number (optional, defaults to latest)"}
                },
                "required": ["pack_id"]
            }
        ),
        Tool(
            name="get_rulepack_yaml",
            description="Get the raw YAML content for a rule pack",
            inputSchema={
                "type": "object",
                "properties": {
                    "pack_id": {"type": "string", "description": "Rule pack identifier"},
                    "version": {"type": "integer", "description": "Version number (optional, defaults to latest)"}
                },
                "required": ["pack_id"]
            }
        ),
        Tool(
            name="list_rulepack_versions",
            description="List all versions for a given rule pack id",
            inputSchema={
                "type": "object",
                "properties": {
                    "pack_id": {"type": "string", "description": "Rule pack identifier"}
                },
                "required": ["pack_id"]
            }
        ),

        # Rule Pack Creation/Editing Tools
        Tool(
            name="create_rulepack_from_yaml",
            description="Create a new rule pack from YAML content",
            inputSchema={
                "type": "object",
                "properties": {
                    "yaml_content": {"type": "string", "description": "Complete YAML rule pack definition"},
                    "created_by": {"type": "string", "description": "Creator identifier (optional)", "default": "mcp-llm"}
                },
                "required": ["yaml_content"]
            }
        ),
        Tool(
            name="update_rulepack_yaml",
            description="Update a draft rule pack with new YAML content",
            inputSchema={
                "type": "object",
                "properties": {
                    "pack_id": {"type": "string", "description": "Rule pack identifier"},
                    "version": {"type": "integer", "description": "Version number"},
                    "yaml_content": {"type": "string", "description": "Updated YAML content"}
                },
                "required": ["pack_id", "version", "yaml_content"]
            }
        ),
        Tool(
            name="publish_rulepack",
            description="Publish a draft rule pack to make it active",
            inputSchema={
                "type": "object",
                "properties": {
                    "pack_id": {"type": "string", "description": "Rule pack identifier"},
                    "version": {"type": "integer", "description": "Version number"}
                },
                "required": ["pack_id", "version"]
            }
        ),
        Tool(
            name="deprecate_rulepack",
            description="Deprecate an active rule pack",
            inputSchema={
                "type": "object",
                "properties": {
                    "pack_id": {"type": "string", "description": "Rule pack identifier"},
                    "version": {"type": "integer", "description": "Version number"}
                },
                "required": ["pack_id", "version"]
            }
        ),
        Tool(
            name="delete_rulepack",
            description="Delete a rule pack version (use with caution)",
            inputSchema={
                "type": "object",
                "properties": {
                    "pack_id": {"type": "string", "description": "Rule pack identifier"},
                    "version": {"type": "integer", "description": "Version number"},
                    "force": {"type": "boolean", "description": "Force delete non-draft packs", "default": False}
                },
                "required": ["pack_id", "version"]
            }
        ),

        # Document Analysis Tools
        Tool(
            name="analyze_document",
            description="Analyze a contract document using rule packs",
            inputSchema={
                "type": "object",
                "properties": {
                    "document_path": {"type": "string", "description": "Path to document file (optional)"},
                    "document_text": {"type": "string", "description": "Document text content (optional)"},
                    "doc_type_hint": {"type": "string", "description": "Document type hint (optional)"},
                    "pack_id": {"type": "string", "description": "Specific rule pack to use (optional)"}
                },
                "oneOf": [
                    {"required": ["document_path"]},
                    {"required": ["document_text"]}
                ]
            }
        ),
        Tool(
            name="preview_document_analysis",
            description="Quick preview analysis without saving files",
            inputSchema={
                "type": "object",
                "properties": {
                    "document_text": {"type": "string", "description": "Document text content"},
                    "pack_id": {"type": "string", "description": "Specific rule pack to use (optional)"}
                },
                "required": ["document_text"]
            }
        ),

        # Utility Tools
        Tool(
            name="generate_rulepack_template",
            description="Generate a YAML template for creating new rule packs",
            inputSchema={
                "type": "object",
                "properties": {
                    "pack_id": {"type": "string", "description": "Identifier for the new rule pack"},
                    "doc_type_names": {"type": "array", "items": {"type": "string"}, "description": "Document types this pack handles"}
                },
                "required": ["pack_id", "doc_type_names"]
            }
        ),
        Tool(
            name="validate_rulepack_yaml",
            description="Validate YAML content before creating/updating rule packs",
            inputSchema={
                "type": "object",
                "properties": {
                    "yaml_content": {"type": "string", "description": "YAML content to validate"}
                },
                "required": ["yaml_content"]
            }
        ),
        Tool(
            name="get_system_info",
            description="Get system information for debugging and monitoring",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any] | None = None) -> List[TextContent]:
    """Handle tool calls from LibreChat."""
    try:
        args = arguments or {}
        log.info(f"MCP stdio call_tool: {name} with args: {list(args.keys())}")

        # Route to appropriate handler function
        if name == "list_all_rulepacks":
            result = await handle_list_all_rulepacks()
        elif name == "list_active_rulepacks":
            result = await handle_list_active_rulepacks()
        elif name == "get_rulepack_details":
            result = await handle_get_rulepack_details(args)
        elif name == "get_rulepack_yaml":
            result = await handle_get_rulepack_yaml(args)
        elif name == "list_rulepack_versions":
            result = await handle_list_rulepack_versions(args)
        elif name == "create_rulepack_from_yaml":
            result = await handle_create_rulepack_from_yaml(args)
        elif name == "update_rulepack_yaml":
            result = await handle_update_rulepack_yaml(args)
        elif name == "publish_rulepack":
            result = await handle_publish_rulepack(args)
        elif name == "deprecate_rulepack":
            result = await handle_deprecate_rulepack(args)
        elif name == "delete_rulepack":
            result = await handle_delete_rulepack(args)
        elif name == "analyze_document":
            result = await handle_analyze_document(args)
        elif name == "preview_document_analysis":
            result = await handle_preview_document_analysis(args)
        elif name == "generate_rulepack_template":
            result = await handle_generate_rulepack_template(args)
        elif name == "validate_rulepack_yaml":
            result = await handle_validate_rulepack_yaml(args)
        elif name == "get_system_info":
            result = await handle_get_system_info()
        else:
            raise ValueError(f"Unknown tool: {name}")

        # Format result as TextContent
        result_text = json.dumps(result, indent=2, default=str)
        log.info(f"MCP stdio call_tool: {name} completed successfully")
        return [TextContent(type="text", text=result_text)]

    except Exception as e:
        error_msg = f"Tool '{name}' failed: {str(e)}"
        log.error(error_msg)
        return [TextContent(type="text", text=json.dumps({"error": error_msg}))]

# ========================================
# TOOL HANDLER FUNCTIONS
# ========================================

async def handle_list_all_rulepacks() -> List[Dict[str, Any]]:
    """List ALL rule packs in the database (any status/version)."""
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

async def handle_list_active_rulepacks() -> List[Dict[str, Any]]:
    """List only active rule packs (for runtime evaluation)."""
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

async def handle_get_rulepack_details(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get detailed information for a specific rule pack version."""
    pack_id = args["pack_id"]
    version = args.get("version")

    with SessionLocal() as db:
        query = db.query(RulePackRecord).filter(RulePackRecord.id == pack_id)

        if version is not None:
            query = query.filter(RulePackRecord.version == version)
        else:
            query = query.order_by(RulePackRecord.version.desc())

        rec = query.first()

        if rec is None:
            raise ValueError(f"Rule pack '{pack_id}' not found")

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

async def handle_get_rulepack_yaml(args: Dict[str, Any]) -> str:
    """Get the raw YAML content for a rule pack."""
    pack_id = args["pack_id"]
    version = args.get("version")

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

async def handle_list_rulepack_versions(args: Dict[str, Any]) -> List[Dict[str, Any]]:
    """List all versions for a given rule pack id."""
    pack_id = args["pack_id"]

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

async def handle_create_rulepack_from_yaml(args: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new rule pack from YAML content."""
    yaml_content = args["yaml_content"]
    created_by = args.get("created_by", "mcp-llm")

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

async def handle_update_rulepack_yaml(args: Dict[str, Any]) -> Dict[str, Any]:
    """Update a draft rule pack with new YAML content."""
    pack_id = args["pack_id"]
    version = args["version"]
    yaml_content = args["yaml_content"]

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
        import yaml

        raw = yaml.safe_load(yaml_content) or {}

        rules = RuleSet(
            jurisdiction={"allowed_countries": raw.get("jurisdiction_allowlist", [])},
            liability_cap=raw.get("liability_cap", {}) or {},
            contract=raw.get("contract", {}) or {},
            fraud=raw.get("fraud", {}) or {},
        )
        examples_yaml = raw.get("examples", []) or []
        examples = [ExampleItem.model_validate(e) for e in examples_yaml]

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
            rec.ruleset_json = upd.rules.model_dump()
        if upd.rules_json is not None:
            rec.rules_json = list(upd.rules_json)
        if upd.llm_prompt is not None:
            rec.llm_prompt = upd.llm_prompt
        if upd.examples is not None:
            rec.llm_examples_json = [e.model_dump() for e in upd.examples]
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

async def handle_publish_rulepack(args: Dict[str, Any]) -> Dict[str, Any]:
    """Publish a draft rule pack to make it active."""
    pack_id = args["pack_id"]
    version = args["version"]

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

async def handle_deprecate_rulepack(args: Dict[str, Any]) -> Dict[str, Any]:
    """Deprecate an active rule pack."""
    pack_id = args["pack_id"]
    version = args["version"]

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

async def handle_delete_rulepack(args: Dict[str, Any]) -> Dict[str, Any]:
    """Delete a rule pack version."""
    pack_id = args["pack_id"]
    version = args["version"]
    force = args.get("force", False)

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

async def handle_analyze_document(args: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze a contract document using rule packs."""
    document_path = args.get("document_path")
    document_text = args.get("document_text")
    doc_type_hint = args.get("doc_type_hint")
    pack_id_hint = args.get("pack_id")

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
        out_dir = Path("outputs") / "mcp_stdio" / f"{document_name}_{doc_hash}"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Run standard analysis
        report = make_report(
            document_name=document_name,
            text=text,
            rules=selected_pack.rules
        )

        # Save artifacts
        save_markdown(report, out_dir)
        save_txt(report, out_dir)

        # Read markdown content for LibreChat display
        markdown_path = out_dir / "report.md"
        markdown_content = markdown_path.read_text(encoding='utf-8') if markdown_path.exists() else ""

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
            "markdown_report": markdown_content,
            "output_files": {
                "markdown_report": str(out_dir / "report.md"),
                "text_report": str(out_dir / "report.txt")
            }
        }

        log.info(f"MCP analyze_document: processed {document_name}, result: {result['overall_result']}, violations: {len(violations)}")
        return result

async def handle_preview_document_analysis(args: Dict[str, Any]) -> Dict[str, Any]:
    """Quick preview analysis without saving files."""
    document_text = args["document_text"]
    pack_id = args.get("pack_id")

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

async def handle_generate_rulepack_template(args: Dict[str, Any]) -> str:
    """Generate a YAML template for creating new rule packs."""
    pack_id = args["pack_id"]
    doc_type_names = args["doc_type_names"]

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

async def handle_validate_rulepack_yaml(args: Dict[str, Any]) -> Dict[str, Any]:
    """Validate YAML content before creating/updating rule packs."""
    yaml_content = args["yaml_content"]

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

async def handle_get_system_info() -> Dict[str, Any]:
    """Get system information for debugging and monitoring."""
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
            "stdio_protocol": True,
            "pydantic_version": "v2",
            "langextract_version": "1.0.9",
            "outputs_directory_size_bytes": outputs_size,
            "outputs_directory_exists": outputs_dir.exists()
        },
        "mcp_tools": {
            "total_tools": 16,
            "protocol": "stdio",
            "categories": ["rule_pack_management", "document_analysis", "utilities"]
        }
    }

    log.info("MCP get_system_info: retrieved system information")
    return result

# ========================================
# MAIN ASYNC ENTRY POINT
# ========================================

async def main():
    """Main entry point for the stdio MCP server."""
    log.info("Starting ContractExtract MCP stdio server...")
    log.info("Server supports 16 tools for comprehensive rule pack and document analysis")

    # Initialize database on startup
    try:
        init_db()
        log.info("Database initialized successfully")
    except Exception as e:
        log.error(f"Database initialization failed: {e}")
        # Continue anyway - some operations may still work

    # Run the stdio server
    async with stdio_server() as (read_stream, write_stream):
        log.info("MCP stdio server running - ready for LibreChat connection")
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())