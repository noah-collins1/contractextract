import os, yaml
from llm_provider import LLMProvider, OllamaProvider

def load_provider(config_path: str = "llm.yaml") -> LLMProvider:
    cfg = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}

    kind = os.getenv("LLM_PROVIDER", cfg.get("provider", "ollama")).lower()
    if kind == "ollama":
        return OllamaProvider(
            model_id=cfg.get("model_id", "llama3:8b-instruct-q4_K_M"),
            url=cfg.get("model_url", "http://localhost:11434"),
        )
    raise ValueError(f"Unknown provider: {kind}")
