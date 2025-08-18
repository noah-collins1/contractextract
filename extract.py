import langextract as lx
import textwrap

PROMPT = textwrap.dedent("""
Extract grounded facts from the contract text. Use exact spans (no paraphrase).

Classes (one or more may appear):
- liability_cap(cap_text, cap_money.amount, cap_money.currency, cap_multiplier, carveouts[])
- contract_value(tcv.amount, tcv.currency)
- fraud(present, liable_party in {self, other, mutual})
- jurisdiction(country, region)

Guidelines:
- liability_cap:
  - If the cap is a fixed amount (e.g., "USD 1,000,000"), set cap_money.amount + cap_money.currency.
  - If tied to fees/TCV over a window (e.g., "12 months of fees"), set cap_multiplier=1.0 when equal to one full contract value window.
  - Include carveouts named in the clause (e.g., "fraud", "gross negligence", "IP infringement").
- contract_value:
  - Extract the Total Contract Value if stated (e.g., "USD 900,000").
- fraud:
  - present=true if a fraud clause exists.
  - liable_party: "other" if the other/counterparty bears liability, "self" if this party bears its own, "mutual" if both bear their own.
- jurisdiction:
  - country as written (e.g., "United States", "Canada", "Germany", "Australia").
  - region/state if present (e.g., "Delaware").
""")

examples = [
    # --- LIABILITY CAP: fixed money cap with carveouts (fraud, gross negligence) ---
    lx.data.ExampleData(
        text="In no event shall a party's aggregate liability exceed USD 1,000,000, except for fraud or gross negligence.",
        extractions=[
            lx.data.Extraction(
                extraction_class="liability_cap",
                extraction_text="aggregate liability exceed USD 1,000,000",
                attributes={
                    "cap_money.amount": 1_000_000,
                    "cap_money.currency": "USD",
                    "cap_multiplier": None,
                    "carveouts": ["fraud", "gross negligence"]
                }
            ),
        ],
    ),

    # --- LIABILITY CAP: 12 months of fees (multiplier = 1.0) ---
    lx.data.ExampleData(
        text="Limitation of Liability: except for fraud, liability is capped at the fees paid in the twelve (12) months prior.",
        extractions=[
            lx.data.Extraction(
                extraction_class="liability_cap",
                extraction_text="liability is capped at the fees paid in the twelve (12) months prior",
                attributes={
                    "cap_money.amount": None,
                    "cap_money.currency": None,
                    "cap_multiplier": 1.0,
                    "carveouts": ["fraud"]
                }
            ),
        ],
    ),

    # --- LIABILITY CAP: equal to all fees in the previous year (multiplier = 1.0), no carveouts ---
    lx.data.ExampleData(
        text="The cap on damages shall be an amount equal to all fees paid under this Agreement during the previous twelve months.",
        extractions=[
            lx.data.Extraction(
                extraction_class="liability_cap",
                extraction_text="amount equal to all fees paid under this Agreement during the previous twelve months",
                attributes={
                    "cap_money.amount": None,
                    "cap_money.currency": None,
                    "cap_multiplier": 1.0,
                    "carveouts": []
                }
            ),
        ],
    ),

    # --- CONTRACT VALUE: USD ---
    lx.data.ExampleData(
        text="The Total Contract Value (TCV) is USD 900,000 payable over two years.",
        extractions=[
            lx.data.Extraction(
                extraction_class="contract_value",
                extraction_text="USD 900,000",
                attributes={"tcv.amount": 900_000, "tcv.currency": "USD"}
            ),
        ],
    ),

    # --- CONTRACT VALUE: EUR ---
    lx.data.ExampleData(
        text="Order Form Total: EUR 250,000 (one-time).",
        extractions=[
            lx.data.Extraction(
                extraction_class="contract_value",
                extraction_text="EUR 250,000",
                attributes={"tcv.amount": 250_000, "tcv.currency": "EUR"}
            ),
        ],
    ),

    # --- FRAUD: liability on the OTHER party (what your rule requires) ---
    lx.data.ExampleData(
        text="Fraud. Vendor shall be wholly liable for any fraud and resultant damages.",
        extractions=[
            lx.data.Extraction(
                extraction_class="fraud",
                extraction_text="Vendor shall be wholly liable for any fraud",
                attributes={"present": True, "liable_party": "other"}
            ),
        ],
    ),

    # --- FRAUD: self responsibility (contrast/negative for your rule) ---
    lx.data.ExampleData(
        text="Each party shall be responsible for its own fraud and willful misconduct.",
        extractions=[
            lx.data.Extraction(
                extraction_class="fraud",
                extraction_text="Each party shall be responsible for its own fraud",
                attributes={"present": True, "liable_party": "self"}
            ),
        ],
    ),

    # --- JURISDICTION: US + state ---
    lx.data.ExampleData(
        text="This Agreement is governed by the laws of the United States and the State of Delaware.",
        extractions=[
            lx.data.Extraction(
                extraction_class="jurisdiction",
                extraction_text="United States and the State of Delaware",
                attributes={"country": "United States", "region": "Delaware"}
            ),
        ],
    ),

    # --- JURISDICTION: Canada ---
    lx.data.ExampleData(
        text="Governing law shall be the laws of Canada.",
        extractions=[
            lx.data.Extraction(
                extraction_class="jurisdiction",
                extraction_text="laws of Canada",
                attributes={"country": "Canada", "region": None}
            ),
        ],
    ),

    # --- JURISDICTION: EU member state (Germany) ---
    lx.data.ExampleData(
        text="Governing law shall be the laws of Germany.",
        extractions=[
            lx.data.Extraction(
                extraction_class="jurisdiction",
                extraction_text="laws of Germany",
                attributes={"country": "Germany", "region": None}
            ),
        ],
    ),

    # --- JURISDICTION: Australia ---
    lx.data.ExampleData(
        text="This Agreement shall be governed by the laws of Australia.",
        extractions=[
            lx.data.Extraction(
                extraction_class="jurisdiction",
                extraction_text="laws of Australia",
                attributes={"country": "Australia", "region": None}
            ),
        ],
    ),

    # --- JURISDICTION: non-allowed (example still extracted so rules can fail it) ---
    lx.data.ExampleData(
        text="This Agreement shall be governed by the laws of India.",
        extractions=[
            lx.data.Extraction(
                extraction_class="jurisdiction",
                extraction_text="laws of India",
                attributes={"country": "India", "region": None}
            ),
        ],
    ),
]
