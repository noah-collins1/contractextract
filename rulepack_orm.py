
from __future__ import annotations
from sqlalchemy import String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from db import Base

class RulePackORM(Base):
    __tablename__ = "rule_packs"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    doc_type_names: Mapped[list] = mapped_column(JSON, default=list)
    rules: Mapped[dict] = mapped_column(JSON, default=dict)
    prompt: Mapped[str] = mapped_column(Text, default="")
    examples: Mapped[list] = mapped_column(JSON, default=list)
