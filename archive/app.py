# app.py
from __future__ import annotations
from typing import Optional, List, Dict, Any, Union
import yaml
import hashlib
import logging
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

# --- DB session dependency ---
from db import SessionLocal, init_db

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Domain imports wired to your repo layout ---
from yaml_importer import import_rulepack_yaml
from rulepack_repo import publish_pack, load_active_rulepacks  # repo layer (DB CRUD)
from rulepack_loader import load_packs_for_runtime            # runtime helper (active -> Pydantic RulePack)
from doc_type import guess_doc_type_id                        # needs (text, packs_by_id)
from ingest import ingest_bytes_to_text                       # helper you added
from evaluator import make_report                             # returns DocumentReport
from schemas import RuleSet, ExampleItem
from rulepack_dtos import RulePackRead, RulePackUpdate
from models_rulepack import RulePackRecord

app = FastAPI(title="ContractExtract PoC API")

# CORS for local Vite (http://localhost:5173 by default)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------- Schemas (Pydantic) ---------
class RulePackOut(BaseModel):
    id: str
    version: int
    status: str
    doc_type_names: List[str] = []

class ImportYamlIn(BaseModel):
    id: Optional[str] = None  # kept for shape compatibility; importer reads id from YAML
    yaml_text: str

class PreviewRunOut(BaseModel):
    document_name: str
    pack_id: str
    report_markdown: str
    meta: dict

class DeleteResult(BaseModel):
    id: str
    version: int
    status: str  # "deleted"


class UpdateDraftInPatch(BaseModel):
    patch: RulePackUpdate

class UpdateDraftInYaml(BaseModel):
    yaml_text: str

# --------- Helpers ---------
# Unified rendering now handled by evaluator.py

def _to_read_dto(r: RulePackRecord) -> RulePackRead:
    return RulePackRead(
        id=r.id,
        version=r.version,
        status=r.status,
        schema_version=r.schema_version,
        doc_type_names=list(r.doc_type_names or []),
        rules=RuleSet.parse_obj(r.ruleset_json or {}),
        rules_json=list(r.rules_json or []),
        llm_prompt=r.llm_prompt,
        examples=[ExampleItem.parse_obj(e) for e in (r.llm_examples_json or [])],
        extensions=r.extensions_json,
        extensions_schema=r.extensions_schema_json,
        raw_yaml=r.raw_yaml,
        notes=r.notes,
        created_by=r.created_by,
    )

def _apply_update_to_record(rec: RulePackRecord, upd: RulePackUpdate):
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

def _parse_yaml_to_update(yaml_text: str) -> RulePackUpdate:
    """
    Parse YAML into a RulePackUpdate (so a frontend can submit YAML OR structured JSON).
    Mirrors yaml_importer expectations but does not create a new record.
    """
    raw = yaml.safe_load(yaml_text) or {}
    rules = RuleSet(
        jurisdiction={"allowed_countries": raw.get("jurisdiction_allowlist", [])},
        liability_cap=raw.get("liability_cap", {}) or {},
        contract=raw.get("contract", {}) or {},
        fraud=raw.get("fraud", {}) or {},
    )
    examples_yaml = raw.get("examples", []) or []
    examples = [ExampleItem.parse_obj(e) for e in examples_yaml]
    return RulePackUpdate(
        schema_version=raw.get("schema_version"),
        doc_type_names=raw.get("doc_type_names") or None,
        rules=rules,
        rules_json=(raw.get("rules") or []),
        llm_prompt=raw.get("prompt") or None,
        examples=examples,
        extensions=raw.get("extensions"),
        extensions_schema=raw.get("extensions_schema"),
        raw_yaml=yaml_text,
        notes=raw.get("notes"),
    )




# --------- Endpoints ---------

@app.on_event("startup")
def _startup():
    # Make sure tables exist
    init_db()
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@app.get("/rule-packs", response_model=List[RulePackOut])
def get_rule_packs(status: Optional[str] = None, db: Session = Depends(get_db)):
    """
    For PoC, support active packs (default). Draft listing can be added later.
    """
    s = (status or "active").strip().lower()
    if s != "active":
        raise HTTPException(400, "For now this endpoint only supports status=active.")
    # Repo returns DB-backed rows; we only need id/version/doc_type_names
    rows = load_active_rulepacks(db)  # returns list of RuntimeRulePack or DTO-like objects
    out = []
    for p in rows:
        # tolerate different shapes (Pydantic RuntimeRulePack vs repo DTO)
        pid = getattr(p, "id", None)
        ver = getattr(p, "version", 1)
        names = list(getattr(p, "doc_type_names", []))
        out.append(RulePackOut(id=pid, version=ver, status="active", doc_type_names=names))
    return out


@app.get("/rule-packs/{pack_id}/{version}", response_model=RulePackRead)
def read_rule_pack(pack_id: str, version: int, db: Session = Depends(get_db)):
    rec = (
        db.query(RulePackRecord)
        .filter(RulePackRecord.id == pack_id, RulePackRecord.version == version)
        .one_or_none()
    )
    if rec is None:
        raise HTTPException(404, f"{pack_id}@{version} not found")
    return _to_read_dto(rec)

@app.get("/rule-packs/{pack_id}/{version}/yaml", response_model=str)
def read_rule_pack_yaml(pack_id: str, version: int, db: Session = Depends(get_db)):
    rec = (
        db.query(RulePackRecord)
        .filter(RulePackRecord.id == pack_id, RulePackRecord.version == version)
        .one_or_none()
    )
    if rec is None:
        raise HTTPException(404, f"{pack_id}@{version} not found")
    return rec.raw_yaml or ""


@app.post("/rule-packs/import-yaml", response_model=RulePackOut)
def import_yaml(
    body: ImportYamlIn = Body(
        ...,
        examples={
            "strategic_alliance": {
                "summary": "Strategic Alliance Rule Pack",
                "description": "Complete strategic alliance rule pack with all required fields",
                "value": {
                    "yaml_text": '''id: strategic_alliance_v1
schema_version: "1.0"
doc_type_names:
  - "Strategic Alliance Agreement"
  - "Alliance Agreement"
  - "Strategic Partnership Agreement"
jurisdiction_allowlist:
  - "United States"
  - "US"
  - "Canada"
  - "European Union"
  - "EU"
liability_cap:
  max_cap_amount: 1000000.0
  max_cap_multiplier: 1.0
contract:
  max_contract_value: 5000000.0
fraud:
  require_fraud_clause: true
  require_liability_on_other_party: true
prompt: |
  Extract grounded facts from the contract text. Use exact spans (no paraphrasing).
  Return ONLY a single JSON object with liability_cap, contract_value, fraud_clause, governing_law.
examples:
  - text: "Limitation of Liability: except for fraud, liability is capped at the fees paid in the twelve (12) months prior."
    extractions:
      - label: "liability_cap"
        span: "liability is capped at the fees paid in the twelve (12) months prior"
        attributes:
          cap_multiplier: 1.0
          carveouts: ["fraud"]
notes: "Strategic alliance agreements focusing on partnership terms, liability limits, and fraud protection"'''
                }
            },
            "employment": {
                "summary": "Employment Agreement Rule Pack",
                "description": "Employment contract rule pack template",
                "value": {
                    "yaml_text": '''id: employment_v1
schema_version: "1.0"
doc_type_names:
  - "Employment Agreement"
  - "Offer Letter"
  - "Employment Contract"
jurisdiction_allowlist:
  - "United States"
  - "Canada"
liability_cap:
  max_cap_amount: null
  max_cap_multiplier: null
contract:
  max_contract_value: null
fraud:
  require_fraud_clause: false
  require_liability_on_other_party: false
prompt: |
  Extract employment terms and conditions from the contract text.
examples: []
notes: "Employment agreements and offer letters"'''
                }
            }
        }
    ),
    db: Session = Depends(get_db)
):
    """
    Import YAML as a DRAFT rule pack. The YAML itself must contain 'id' and doc_type_names, etc.
    """
    try:
        draft = import_rulepack_yaml(db, yaml_text=body.yaml_text, created_by="api")
        return RulePackOut(
            id=draft.id,
            version=draft.version,
            status="draft",
            doc_type_names=list(getattr(draft, "doc_type_names", [])),
        )
    except Exception as e:
        raise HTTPException(400, f"YAML import failed: {e}")

@app.post("/rule-packs/{pack_id}/{version}:publish", response_model=RulePackOut)
def publish_pack_route(pack_id: str, version: int, db: Session = Depends(get_db)):
    try:
        active = publish_pack(db, pack_id=pack_id, version=version)
        return RulePackOut(
            id=active.id,
            version=active.version,
            status="active",
            doc_type_names=list(getattr(active, "doc_type_names", [])),
        )
    except Exception as e:
        raise HTTPException(400, f"Publish failed: {e}")

# =========================
#  Upload YAML (file)
# =========================
@app.post("/rule-packs/upload-yaml", response_model=RulePackOut)
async def upload_yaml(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Upload a .yml/.yaml file. We read it as UTF-8 text, import as a DRAFT,
    and return the created draft pack metadata.
    """
    try:
        data = await file.read()
        yaml_text = data.decode("utf-8", errors="replace")
        draft = import_rulepack_yaml(db, yaml_text=yaml_text, created_by="api-upload")
        return RulePackOut(
            id=draft.id,
            version=draft.version,
            status="draft",
            doc_type_names=list(getattr(draft, "doc_type_names", [])),
        )
    except Exception as e:
        raise HTTPException(400, f"YAML upload failed: {e}")

# =========================
#  List ALL packs
# =========================
@app.get("/rule-packs/all", response_model=List[RulePackOut])
def list_all_packs(db: Session = Depends(get_db)):
    """
    Return every pack in the database (any status/version).
    """
    try:
        rows = db.query(RulePackRecord).order_by(
            RulePackRecord.id.asc(), RulePackRecord.version.asc()
        ).all()
        out: List[RulePackOut] = []
        for r in rows:
            out.append(
                RulePackOut(
                    id=r.id,
                    version=r.version,
                    status=r.status,
                    doc_type_names=list(r.doc_type_names or []),
                )
            )
        return out
    except Exception as e:
        raise HTTPException(500, f"Failed to list packs: {e}")

@app.post("/preview-run", response_model=PreviewRunOut)
async def preview_run(
    file: UploadFile = File(...),
    pack_id: Optional[str] = Form(None),  # if omitted, auto-detect by doc type
    db: Session = Depends(get_db),
):
    try:
        raw_bytes = await file.read()

        # Calculate SHA1 for logging and metadata
        sha1_hash = hashlib.sha1(raw_bytes).hexdigest()

        text = ingest_bytes_to_text(raw_bytes, filename=file.filename)

        # Load active packs once
        active_packs = load_active_rulepacks(db)
        if not active_packs:
            raise HTTPException(404, "No active rule packs available.")

        by_id = {p.id: p for p in active_packs}

        selected_pack_id = pack_id
        doc_type_meta = {}

        if not selected_pack_id:
            # Auto-detect: use enhanced detection with detailed metadata
            from document_classifier import guess_doc_type_id_enhanced
            detected_pack_id, candidates, selection_reason = guess_doc_type_id_enhanced(text, by_id)
            selected_pack_id = detected_pack_id or next(iter(by_id.keys()))

            # Build document type detection metadata
            doc_type_meta = {
                "auto_detected": True,
                "selection_reason": selection_reason,
                "candidates": [
                    {
                        "pack_id": c.pack_id,
                        "doc_type": c.doc_type,
                        "score": round(c.score, 2),
                        "confidence": round(c.score / 10.0, 3),  # Normalize to 0-1
                        "reason": c.reason
                    }
                    for c in candidates[:3]  # Top 3 candidates
                ]
            }
        else:
            doc_type_meta = {
                "auto_detected": False,
                "forced_pack_id": pack_id
            }

        pack = by_id.get(selected_pack_id)
        if not pack:
            raise HTTPException(404, f"Rule pack '{selected_pack_id}' not found or not active.")

        # Evaluate using the rules inside the selected pack (unified path)
        from evaluator import make_report, render_markdown
        report = make_report(document_name=file.filename, text=text, rules=pack.rules)
        report_md = render_markdown(report)

        # Create metadata for logging and response
        meta = {
            "filename": file.filename or "unknown",
            "sha1": sha1_hash,
            "selected_pack_id": selected_pack_id,
            "pass_fail": "PASS" if report.passed_all else "FAIL",
            "document_type_detection": doc_type_meta
        }

        # Log the processing details
        logging.info(f"Preview run: filename={meta['filename']}, sha1={meta['sha1']}, pack_id={meta['selected_pack_id']}, result={meta['pass_fail']}")

        return PreviewRunOut(
            document_name=file.filename,
            pack_id=selected_pack_id,
            report_markdown=report_md,
            meta=meta
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Preview run failed: {e}")

@app.post("/preview-run.md", response_class=PlainTextResponse)
async def preview_run_markdown(
    file: UploadFile = File(...),
    pack_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Same as /preview-run but returns only the markdown report as text/markdown.
    Perfect for direct download or preview in browsers.
    """
    try:
        raw_bytes = await file.read()
        sha1_hash = hashlib.sha1(raw_bytes).hexdigest()
        text = ingest_bytes_to_text(raw_bytes, filename=file.filename)

        # Load active packs
        active_packs = load_active_rulepacks(db)
        if not active_packs:
            raise HTTPException(404, "No active rule packs available.")

        by_id = {p.id: p for p in active_packs}

        # Document type detection (same logic as JSON endpoint)
        selected_pack_id = pack_id
        if not selected_pack_id:
            from document_classifier import guess_doc_type_id_enhanced
            detected_pack_id, candidates, selection_reason = guess_doc_type_id_enhanced(text, by_id)
            selected_pack_id = detected_pack_id or next(iter(by_id.keys()))

        pack = by_id.get(selected_pack_id)
        if not pack:
            raise HTTPException(404, f"Rule pack '{selected_pack_id}' not found or not active.")

        # Generate report
        from evaluator import make_report, render_markdown
        report = make_report(document_name=file.filename, text=text, rules=pack.rules)
        report_md = render_markdown(report)

        # Log for consistency
        logging.info(f"Preview run (markdown): filename={file.filename}, sha1={sha1_hash}, pack_id={selected_pack_id}, result={'PASS' if report.passed_all else 'FAIL'}")

        return PlainTextResponse(content=report_md, media_type="text/markdown")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Preview run (markdown) failed: {e}")

# =========================
#  Delete a rule pack
# =========================
@app.delete("/rule-packs/{pack_id}/{version}", response_model=DeleteResult)
def delete_rule_pack(
    pack_id: str,
    version: int,
    force: bool = Query(False, description="If true, allow deleting non-draft packs."),
    db: Session = Depends(get_db),
):
    """
    Delete a specific rule pack version.
    - By default, only 'draft' packs can be deleted.
    - Set ?force=true to delete regardless of status (use with caution).
    """
    try:
        rec: RulePackRecord | None = (
            db.query(RulePackRecord)
            .filter(RulePackRecord.id == pack_id, RulePackRecord.version == version)
            .one_or_none()
        )
        if rec is None:
            raise HTTPException(status_code=404, detail=f"Rule pack {pack_id}@{version} not found.")

        if rec.status != "draft" and not force:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot delete {rec.status} pack without force=true. "
                    "Deprecate it or pass ?force=true if you really need to remove it."
                ),
            )

        db.delete(rec)
        db.commit()
        return DeleteResult(id=pack_id, version=version, status="deleted")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Failed to delete rule pack: {e}")



# ======================================================
#  UPDATE and DEPRECATE
# ======================================================

class UpdateDraftIn(BaseModel):
    # Provide one of these:
    yaml_text: Optional[str] = None
    patch: Optional[RulePackUpdate] = None

@app.put("/rule-packs/{pack_id}/{version}", response_model=RulePackRead)
def update_rule_pack_draft(
    pack_id: str,
    version: int,
    body: Union[UpdateDraftInPatch, UpdateDraftInYaml] = Body(
        ...,
        examples={
            "json_patch": {
                "summary": "Edit via JSON patch (frontend forms)",
                "value": {
                    "patch": {
                        "doc_type_names": [
                            "Strategic Alliance Agreement",
                            "Alliance Agreement",
                            "Strategic Partnership Agreement"
                        ],
                        "rules": {
                            "jurisdiction": {
                                "allowed_countries": ["United States", "Canada", "EU"]
                            }
                        },
                        "notes": "Added alias + tightened jurisdiction."
                    }
                },
            },
            "yaml_replace": {
                "summary": "Replace using YAML (power users)",
                "value": {
                    "yaml_text": "id: strategic_alliance_v1\ndoc_type_names:\n  - Strategic Alliance Agreement\n  - Alliance Agreement\n  - Strategic Partnership Agreement\njurisdiction_allowlist: [\"United States\", \"Canada\", \"EU\"]\nliability_cap: {}\ncontract: {}\nfraud: {}\nprompt: \"\"\nexamples: []\nnotes: \"Replaced via YAML\"\n"
                },
            },
        },
    ),
    db: Session = Depends(get_db),
):
    rec = (
        db.query(RulePackRecord)
        .filter(RulePackRecord.id == pack_id, RulePackRecord.version == version)
        .one_or_none()
    )
    if rec is None:
        raise HTTPException(404, f"{pack_id}@{version} not found")
    if rec.status != "draft":
        raise HTTPException(400, f"Only drafts are editable; current status is '{rec.status}'")

    try:
        # body is one of the two models
        if isinstance(body, UpdateDraftInYaml):
            upd = _parse_yaml_to_update(body.yaml_text)
            _apply_update_to_record(rec, upd)
        else:  # UpdateDraftInPatch
            _apply_update_to_record(rec, body.patch)

        db.add(rec)
        db.commit()
        db.refresh(rec)
        return _to_read_dto(rec)
    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"Draft update failed: {e}")



class DeprecateResult(BaseModel):
    id: str
    version: int
    status: str

@app.post("/rule-packs/{pack_id}/{version}:deprecate", response_model=DeprecateResult)
def deprecate_rule_pack(pack_id: str, version: int, db: Session = Depends(get_db)):
    rec = (
        db.query(RulePackRecord)
        .filter(RulePackRecord.id == pack_id, RulePackRecord.version == version)
        .one_or_none()
    )
    if rec is None:
        raise HTTPException(404, f"{pack_id}@{version} not found")
    if rec.status == "deprecated":
        return DeprecateResult(id=rec.id, version=rec.version, status="deprecated")
    if rec.status not in ("active", "draft"):
        raise HTTPException(400, f"Cannot deprecate status '{rec.status}'")

    rec.status = "deprecated"
    db.add(rec)
    db.commit()
    return DeprecateResult(id=rec.id, version=rec.version, status="deprecated")


# =========================
# List all versions for a given pack id
# =========================
@app.get("/rule-packs/{pack_id}", response_model=List[RulePackOut])
def list_pack_versions(pack_id: str, db: Session = Depends(get_db)):
    """
    Return all versions for a given rule pack id (any status), ordered by version asc.
    Useful for a UI 'Versions' drawer.
    """
    rows = (
        db.query(RulePackRecord)
        .filter(RulePackRecord.id == pack_id)
        .order_by(RulePackRecord.version.asc())
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"No rule pack found with id '{pack_id}'")

    return [
        RulePackOut(
            id=r.id,
            version=r.version,
            status=r.status,
            doc_type_names=list(r.doc_type_names or []),
        )
        for r in rows
    ]


# Import direct MCP endpoint
from mcp_server.direct_mcp_endpoint import router as mcp_router

# Include the MCP router
app.include_router(mcp_router, tags=["mcp"])

