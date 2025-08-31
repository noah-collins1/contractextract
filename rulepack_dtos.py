# rulepack_dtos.py
from typing import List, Optional, Any, Dict, Literal
from pydantic import BaseModel, Field, validator
from schemas import RuleSet, ExampleItem, RulePack as RuntimeRulePack

Status = Literal["draft", "active", "deprecated"]

class RulePackCreate(BaseModel):
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
