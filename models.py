#Will contain pydantic models
from pydantic import BaseModel
from typing import Optional, List, Tuple

class LiabilityCap(BaseModel):
    cap_text: Optional[str] = None
    cap_money_amount: Optional[float] = None
    cap_money_currency: Optional[str] = None
    cap_multiplier: Optional[float] = None
    carveouts: List[str] = []
    span: Optional[Tuple[int,int]] = None

class ContractValue(BaseModel):
    amount: Optional[float] = None
    currency: Optional[str] = None
    span: Optional[Tuple[int,int]] = None

class FraudClause(BaseModel):
    present: bool = False
    liable_party: Optional[str] = None  # self|other|mutual
    span: Optional[Tuple[int,int]] = None

class Jurisdiction(BaseModel):
    country: Optional[str] = None
    region: Optional[str] = None
    span: Optional[Tuple[int,int]] = None
