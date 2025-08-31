# models_rulepack.py
from sqlalchemy import (
    Column, String, Integer, Text, Enum, TIMESTAMP, text, func,
    PrimaryKeyConstraint
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from db import Base

RulePackStatusEnum = Enum("draft", "active", "deprecated", name="rulepack_status")

class RulePackRecord(Base):
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
