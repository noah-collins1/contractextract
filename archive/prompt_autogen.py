# prompt_autogen.py
from llm_provider import OllamaProvider
AUTO = OllamaProvider(model_id="llama3:8b-instruct-q4_K_M")

def draft_prompt(doc_type_name: str, rule_set_dict: dict, sample_text: str) -> str:
    sys = (
      "You are writing an extraction prompt for LangExtract. "
      "Given the doc type and rules, produce a concise prompt that requests exact spans and the needed attributes."
    )
    user = f"Doc type: {doc_type_name}\nRules: {rule_set_dict}\n\nSample:\n{sample_text[:4000]}"
    res = AUTO.extract(text_or_documents=user, prompt=sys, examples=[], extraction_passes=1)
    doc = (getattr(res, "documents", []) or [None])[0]
    return (getattr(doc, "text", "") or "").strip()
