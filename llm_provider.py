from abc import ABC, abstractmethod
from typing import Any, Sequence
import langextract as lx

class LLMProvider(ABC):
    @abstractmethod
    def extract(
        self,
        *,
        text_or_documents: Sequence[str] | str,
        prompt: str,
        examples: list[Any],
        extraction_passes: int = 1,
        max_workers: int = 4,
        max_char_buffer: int = 1000,
    ) -> Any: ...

class GeminiProvider(LLMProvider):
    def __init__(self, model_id: str = "gemini-2.5-flash"):
        self.model_id = model_id

    def extract(self, *, text_or_documents, prompt, examples,
                extraction_passes=1, max_workers=4, max_char_buffer=1000):
        return lx.extract(
            text_or_documents=text_or_documents,
            prompt_description=prompt,
            examples=examples,
            model_id=self.model_id,
            extraction_passes=extraction_passes,
            max_workers=max_workers,
            max_char_buffer=max_char_buffer,
            fence_output=True,
            use_schema_constraints=True,
        )

class OllamaProvider(LLMProvider):
    def __init__(self, model_id="llama3:8b-instruct-q4_K_M", url="http://localhost:11434"):
        self.model_id, self.url = model_id, url

    def extract(self, *, text_or_documents, prompt, examples,
                extraction_passes=1, max_workers=2, max_char_buffer=800):
        return lx.extract(
            text_or_documents=text_or_documents,
            prompt_description=prompt,
            examples=examples,
            model_id=self.model_id,
            model_url=self.url,
            extraction_passes=extraction_passes,
            max_workers=max_workers,
            max_char_buffer=max_char_buffer,
            fence_output=False,
            use_schema_constraints=False,
        )

