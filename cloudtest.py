# cloudtest.py
import textwrap
import langextract as lx
from llm_factory import load_provider  # same factory, but now cloud
import os

# A tiny, provider-agnostic prompt + few-shots
PROMPT = textwrap.dedent("""
Extract grounded facts from the text. Use exact spans (no paraphrase).

Classes:
- liability_cap(cap_text, cap_multiplier, cap_money.amount, cap_money.currency, carveouts[])

Guidelines:
- If the cap references "12 months of fees", set cap_multiplier=1.0.
- Include "fraud" in carveouts if the clause carves it out.

Return ONLY a single JSON object with this shape (no extra text):

{
  "extractions": [
    {
      "liability_cap": "<exact span>",
      "liability_cap_attributes": {
        "cap_multiplier": <number or null>,
        "cap_money.amount": <number or null>,
        "cap_money.currency": "<ISO or null>",
        "carveouts": ["<string>", "..."]
      }
    }
  ]
}
""")


EXAMPLES = [
    lx.data.ExampleData(
        text="Limitation of Liability: except for fraud, liability is capped at the fees paid in the twelve (12) months prior.",
        extractions=[
            lx.data.Extraction(
                "liability_cap",
                "liability is capped at the fees paid in the twelve (12) months prior",
                attributes={"cap_multiplier": 1.0, "carveouts": ["fraud"]}
            )
        ]
    )
]

def main():
    # Force cloud provider by reading from llm.yaml that specifies a cloud backend
    provider = load_provider("llm_cloud.yaml")  # <- point to a config that requires API key

    # sanity check: API key should be set
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing cloud API key in environment!")

    snippet = (
        "Limitation of Liability. Except for fraud and gross negligence, "
        "each party's liability is capped at an amount equal to the fees paid "
        "in the 12 months preceding the claim."
    )

    result = provider.extract(
        text_or_documents=snippet,
        prompt=PROMPT,
        examples=EXAMPLES,
        extraction_passes=1,
        max_workers=2,
        max_char_buffer=800
    )

    lx.io.save_annotated_documents([result], "outputs/extractions")
    vis = lx.visualize("outputs/extractions")
    with open("outputs/review.html", "w", encoding="utf-8") as f:
        f.write(vis if isinstance(vis, str) else vis.data)

    print("=== Raw extractions ===")
    print(result.get("_extractions") if isinstance(result, dict) else result)

if __name__ == "__main__":
    main()
