from models import LiabilityCap, ContractValue, FraudClause, Jurisdiction

def _first(extractions, cls):
    arr = [e for e in extractions if e.get("class_name")==cls] if isinstance(extractions, list) else []
    return arr[0] if arr else None

def map_langextract(extractions: list, raw_text: str):
    # each item looks like: {"class_name": "liability_cap", "text": "...", "attributes": {...}, "_span": [s,e]}
    liab = _first(extractions, "liability_cap")
    cv   = _first(extractions, "contract_value")
    fr   = _first(extractions, "fraud")
    jur  = _first(extractions, "jurisdiction")

    lc = LiabilityCap(
        cap_text = liab.get("text") if liab else None,
        cap_money_amount = (liab.get("attributes",{}).get("cap_money.amount") if liab else None),
        cap_money_currency = (liab.get("attributes",{}).get("cap_money.currency") if liab else None),
        cap_multiplier = (liab.get("attributes",{}).get("cap_multiplier") if liab else None),
        carveouts = (liab.get("attributes",{}).get("carveouts") if liab else []) or [],
        span = tuple(liab.get("_span")) if liab and liab.get("_span") else None,
    )

    tcv = ContractValue(
        amount = cv.get("attributes",{}).get("tcv.amount") if cv else None,
        currency = cv.get("attributes",{}).get("tcv.currency") if cv else None,
        span = tuple(cv.get("_span")) if cv and cv.get("_span") else None,
    )

    fraud = FraudClause(
        present = fr.get("attributes",{}).get("present", False) if fr else False,
        liable_party = fr.get("attributes",{}).get("liable_party") if fr else None,
        span = tuple(fr.get("_span")) if fr and fr.get("_span") else None,
    )

    juris = Jurisdiction(
        country = jur.get("attributes",{}).get("country") if jur else None,
        region = jur.get("attributes",{}).get("region") if jur else None,
        span = tuple(jur.get("_span")) if jur and jur.get("_span") else None,
    )

    return {"liability_cap": lc, "contract_value": tcv, "fraud": fraud, "jurisdiction": juris}
