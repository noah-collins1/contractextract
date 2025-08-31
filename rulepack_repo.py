# rulepack_repo.py
from typing import List, Optional
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from models_rulepack import RulePackRecord
from rulepack_dtos import RulePackCreate, RulePackUpdate, RulePackRead
from schemas import RuleSet, ExampleItem, RulePack as RuntimeRulePack

def _to_read(r: RulePackRecord) -> RulePackRead:
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
    return RuntimeRulePack(
        id=r.id,
        doc_type_names=list(r.doc_type_names or []),
        rules=RuleSet.parse_obj(r.ruleset_json or {}),
        prompt=r.llm_prompt or "",
        examples=[ExampleItem.parse_obj(x) for x in (r.llm_examples_json or [])],
    )

def _next_version_for_id(db: Session, pack_id: str) -> int:
    q = select(RulePackRecord.version).where(RulePackRecord.id == pack_id)
    versions = [row[0] for row in db.execute(q).all()]
    return (max(versions) + 1) if versions else 1

def create_draft(db: Session, payload: RulePackCreate) -> RulePackRead:
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
    rec = db.get(RulePackRecord, {"id": pack_id, "version": version})
    if not rec:
        raise ValueError(f"Rule pack {pack_id}@{version} not found")
    rec.status = "deprecated"
    db.commit()
    db.refresh(rec)
    return _to_read(rec)

def get_pack(db: Session, pack_id: str, version: Optional[int] = None, status: Optional[str] = None) -> RulePackRead:
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
    q = select(RulePackRecord)
    if status:
        q = q.where(RulePackRecord.status == status)
    rows = db.execute(q.order_by(RulePackRecord.id, RulePackRecord.version)).scalars().all()
    return [_to_read(r) for r in rows]

def load_active_rulepacks(db: Session) -> List[RuntimeRulePack]:
    q = select(RulePackRecord).where(RulePackRecord.status == "active")
    rows = db.execute(q).scalars().all()
    return [_to_runtime(r) for r in rows]
