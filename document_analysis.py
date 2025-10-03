"""
Consolidated Document Analysis Module
Combines PDF ingestion, document type detection, and citation mapping.

Merged from:
- ingest.py: PDF text extraction
- doc_type.py: Legacy document type detection
- document_classifier.py: Enhanced document type detection with LLM fallback
- citation_mapper.py: Page/line citation mapping
"""

import re
import json
import pdfplumber
import tempfile
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional, NamedTuple, Union
from infrastructure import RulePack, Citation, settings

# Constants
PAGE_BREAK = "\f"  # Keep page boundaries in the text

# ========================================
# PDF TEXT EXTRACTION
# ========================================

def ingest_pdfs_from_directory() -> Dict[str, str]:
    """
    Ingest all PDFs from the data/ directory.
    Returns dict mapping filename (without extension) to extracted text.
    """
    pdf_folder = Path("data")
    text_store = dict()
    for pdf_path in pdf_folder.glob("*.pdf"):
        title = pdf_path.name
        print(f"Reading {title}...")
        pages = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""  # avoid None
                pages.append(text.strip())
        full_text = PAGE_BREAK.join(pages)
        text_store[pdf_path.stem] = full_text
    return text_store


def ingest_bytes_to_text(data: bytes, filename: str | None = None) -> str:
    """
    Accept raw PDF bytes, write to a temp file, extract text with pdfplumber,
    and return the combined string with form-feed page breaks.

    Args:
        data: Raw PDF bytes
        filename: Optional filename for proper extension handling

    Returns:
        Extracted text with \f as page separators
    """
    suffix = ""
    if filename and "." in filename:
        suffix = "." + filename.split(".")[-1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        pages = []
        with pdfplumber.open(tmp_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                pages.append(text.strip())
        return PAGE_BREAK.join(pages)
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


# Alias for backward compatibility
ingest = ingest_pdfs_from_directory

# ========================================
# CITATION MAPPING
# ========================================

class PageLineMapper:
    """Maps character positions to page and line numbers in extracted text."""

    def __init__(self, text: str):
        """
        Initialize mapper for a document text with page breaks.

        Args:
            text: Document text with \f as page separators
        """
        self.text = text
        self.page_boundaries = self._calculate_page_boundaries()
        self.line_boundaries = self._calculate_line_boundaries()

    def _calculate_page_boundaries(self) -> List[Tuple[int, int]]:
        """
        Calculate character start/end positions for each page.

        Returns:
            List of (start_char, end_char) tuples for each page
        """
        boundaries = []
        pages = self.text.split(PAGE_BREAK)
        char_pos = 0

        for i, page_text in enumerate(pages):
            start_char = char_pos
            end_char = char_pos + len(page_text)
            boundaries.append((start_char, end_char))

            # Move past the page content and the page break character (except for last page)
            char_pos = end_char
            if i < len(pages) - 1:  # Not the last page
                char_pos += 1  # Account for the \f character

        return boundaries

    def _calculate_line_boundaries(self) -> List[List[Tuple[int, int]]]:
        """
        Calculate line boundaries for each page.

        Returns:
            List of pages, each containing list of (start_char, end_char) for lines
        """
        page_lines = []
        pages = self.text.split(PAGE_BREAK)
        char_pos = 0

        for i, page_text in enumerate(pages):
            lines = page_text.split('\n')
            line_boundaries = []
            page_char_pos = char_pos

            for j, line_text in enumerate(lines):
                start_char = page_char_pos
                end_char = page_char_pos + len(line_text)
                line_boundaries.append((start_char, end_char))

                # Move past the line content and newline (except for last line)
                page_char_pos = end_char
                if j < len(lines) - 1:  # Not the last line
                    page_char_pos += 1  # Account for the \n character

            page_lines.append(line_boundaries)

            # Move past the page and page break
            char_pos = page_char_pos
            if i < len(pages) - 1:  # Not the last page
                char_pos += 1  # Account for the \f character

        return page_lines

    def char_to_page_line(self, char_start: int, char_end: int) -> Tuple[Optional[int], Optional[int], Optional[int]]:
        """
        Convert character positions to page and line numbers.

        Args:
            char_start: Starting character position
            char_end: Ending character position

        Returns:
            Tuple of (page_number, line_start, line_end) (1-based) or (None, None, None) if not found
        """
        # Find which page contains the start position
        page_num = None
        for i, (page_start, page_end) in enumerate(self.page_boundaries):
            if page_start <= char_start <= page_end:
                page_num = i + 1  # 1-based page numbering
                break

        if page_num is None:
            return None, None, None

        # Find which lines contain the start and end positions
        page_idx = page_num - 1  # Convert back to 0-based for array access
        if page_idx >= len(self.line_boundaries):
            return page_num, None, None

        line_start = None
        line_end = None

        for j, (line_start_char, line_end_char) in enumerate(self.line_boundaries[page_idx]):
            if line_start is None and line_start_char <= char_start <= line_end_char:
                line_start = j + 1  # 1-based line numbering

            if line_start_char <= char_end <= line_end_char:
                line_end = j + 1  # 1-based line numbering

        # If span crosses multiple lines but we found start, estimate end
        if line_start is not None and line_end is None:
            # Find the last line that overlaps with the character range
            for j, (line_start_char, line_end_char) in enumerate(self.line_boundaries[page_idx]):
                if line_start_char <= char_end:
                    line_end = j + 1

        return page_num, line_start, line_end

    def enhance_citation(self, citation: Citation) -> Citation:
        """
        Enhance a citation with page and line information.

        Args:
            citation: Citation object with char_start and char_end

        Returns:
            Enhanced citation with page and line information
        """
        page, line_start, line_end = self.char_to_page_line(citation.char_start, citation.char_end)

        # Determine confidence based on whether we found valid page/line info
        confidence = 1.0
        if page is None or line_start is None:
            confidence = 0.5  # Lower confidence if we couldn't map properly

        return Citation(
            char_start=citation.char_start,
            char_end=citation.char_end,
            quote=citation.quote,
            page=page,
            line_start=line_start,
            line_end=line_end,
            confidence=confidence
        )


def enhance_citations_with_page_line(text: str, citations: List[Citation]) -> List[Citation]:
    """
    Enhance a list of citations with page and line information.

    Args:
        text: Document text with page breaks
        citations: List of citations to enhance

    Returns:
        List of enhanced citations
    """
    if not citations:
        return citations

    mapper = PageLineMapper(text)
    return [mapper.enhance_citation(citation) for citation in citations]


# ========================================
# DOCUMENT TYPE DETECTION
# ========================================

class DocTypeCandidate(NamedTuple):
    """A candidate document type with confidence score."""
    pack_id: str
    doc_type: str
    score: float
    reason: str


class DocumentClassifier:
    """Enhanced document classifier with rules-first + LLM fallback."""

    def __init__(self):
        # Keyword scoring weights
        self.keyword_weights = {
            # High-confidence indicators
            "strategic alliance": 3.0,
            "alliance agreement": 3.0,
            "partnership agreement": 2.5,
            "joint venture": 3.0,
            "employment agreement": 3.0,
            "offer letter": 2.5,
            "employment contract": 3.0,
            "non-compete": 3.0,
            "noncompete": 3.0,
            "covenant not to compete": 3.0,
            "intellectual property": 2.5,
            "ip assignment": 3.0,
            "proprietary rights": 2.0,
            "service agreement": 2.5,
            "master services": 3.0,
            "promotion agreement": 2.5,
            "marketing agreement": 2.0,

            # Medium-confidence indicators
            "liability": 1.5,
            "indemnification": 1.5,
            "termination": 1.0,
            "confidentiality": 1.0,
            "exclusivity": 1.5,
            "governing law": 1.0,
            "jurisdiction": 1.0,
            "damages": 1.0,
            "breach": 1.0,

            # Specific clause indicators
            "force majeure": 1.0,
            "assignment": 1.0,
            "severability": 0.5,
            "entire agreement": 0.5,
        }

        # Section header patterns (higher weight)
        self.section_patterns = {
            r"strategic\s+alliance": 4.0,
            r"employment\s+terms": 3.0,
            r"non[_\s-]?compete": 3.5,
            r"intellectual\s+property": 2.5,
            r"service\s+levels?": 2.0,
            r"promotion\s+terms": 2.5,
            r"joint\s+venture": 3.5,
        }

    def normalize_and_dedupe_titles(self, packs: Dict[str, RulePack]) -> Dict[str, List[str]]:
        """Normalize and deduplicate document type names."""
        normalized = {}
        for pack_id, pack in packs.items():
            titles = []
            seen = set()
            for name in pack.doc_type_names:
                # Normalize: lowercase, remove extra spaces, standardize punctuation
                norm = re.sub(r'\s+', ' ', name.lower().strip())
                norm = re.sub(r'[^\w\s]', '', norm)  # Remove punctuation
                if norm not in seen and norm:
                    titles.append(norm)
                    seen.add(norm)
            normalized[pack_id] = titles
        return normalized

    def score_document_heuristic(self, text: str, packs: Dict[str, RulePack]) -> List[DocTypeCandidate]:
        """Score document using rules-based heuristics."""
        if not text:
            return []

        # Use first 6000 chars for classification (more than current 4000)
        head = text[:6000].lower()

        candidates = []
        normalized_titles = self.normalize_and_dedupe_titles(packs)

        for pack_id, pack in packs.items():
            total_score = 0.0
            reasons = []

            # 1. Direct title matching (highest weight)
            for title in normalized_titles[pack_id]:
                title_pattern = re.compile(rf'\b{re.escape(title)}\b', re.IGNORECASE)
                matches = len(title_pattern.findall(head))
                if matches > 0:
                    title_score = matches * 5.0  # High weight for exact title matches
                    total_score += title_score
                    reasons.append(f"title_match({title}): {title_score:.1f}")

            # 2. Keyword scoring
            for keyword, weight in self.keyword_weights.items():
                keyword_pattern = re.compile(rf'\b{re.escape(keyword)}\b', re.IGNORECASE)
                matches = len(keyword_pattern.findall(head))
                if matches > 0:
                    keyword_score = matches * weight
                    total_score += keyword_score
                    reasons.append(f"keyword({keyword}): {keyword_score:.1f}")

            # 3. Section header patterns (medium-high weight)
            for pattern, weight in self.section_patterns.items():
                section_matches = len(re.findall(pattern, head, re.IGNORECASE))
                if section_matches > 0:
                    section_score = section_matches * weight
                    total_score += section_score
                    reasons.append(f"section({pattern}): {section_score:.1f}")

            # 4. Document length bonus (longer docs more likely to be complex agreements)
            length_bonus = min(len(text) / 10000, 1.0)  # Cap at 1.0
            total_score += length_bonus
            if length_bonus > 0.1:
                reasons.append(f"length_bonus: {length_bonus:.1f}")

            # Normalize score by number of doc types for this pack
            if len(pack.doc_type_names) > 1:
                total_score *= 0.9  # Slight penalty for generic packs

            if total_score > 0:
                primary_doc_type = pack.doc_type_names[0] if pack.doc_type_names else "Unknown"
                reason_str = "; ".join(reasons[:5])  # Limit reason length
                candidates.append(DocTypeCandidate(
                    pack_id=pack_id,
                    doc_type=primary_doc_type,
                    score=total_score,
                    reason=reason_str
                ))

        # Sort by score descending
        candidates.sort(key=lambda x: x.score, reverse=True)
        return candidates

    def classify_with_llm_fallback(self, text: str, packs: Dict[str, RulePack], low_confidence_candidates: List[DocTypeCandidate]) -> Optional[DocTypeCandidate]:
        """Use LLM fallback for low-confidence cases."""
        if not settings.DOC_TYPE_USE_LLM_FALLBACK:
            return None

        try:
            from llm_factory import load_provider
            provider = load_provider()
            if not provider:
                return None

            # Create prompt with available document types
            pack_descriptions = []
            for pack_id, pack in packs.items():
                doc_types = ", ".join(pack.doc_type_names)
                pack_descriptions.append(f"- {pack_id}: {doc_types}")

            prompt = f"""You are a legal document classifier. Analyze the document excerpt and determine the most likely document type.

Available document types:
{chr(10).join(pack_descriptions)}

Document excerpt (first 2000 characters):
-----
{text[:2000]}
-----

Respond with ONLY a JSON object in this format:
{{
    "pack_id": "most_likely_pack_id",
    "confidence": 0.85,
    "reasoning": "Brief explanation of why this classification fits"
}}

Requirements:
- pack_id must be exactly one of the available pack IDs
- confidence should be 0.0-1.0
- reasoning should be 1-2 sentences max"""

            # Try LLM classification
            from evaluator import _call_llm_any
            mode, response = _call_llm_any(provider, doc_text=text, prompt=prompt)

            if response and not response.startswith("[llm error:"):
                try:
                    # Parse JSON response
                    result = json.loads(response.strip())
                    pack_id = result.get("pack_id")
                    confidence = float(result.get("confidence", 0.0))
                    reasoning = result.get("reasoning", "LLM classification")

                    if pack_id in packs and confidence > 0.3:
                        primary_doc_type = packs[pack_id].doc_type_names[0] if packs[pack_id].doc_type_names else "Unknown"
                        return DocTypeCandidate(
                            pack_id=pack_id,
                            doc_type=primary_doc_type,
                            score=confidence * 10.0,  # Convert to comparable score
                            reason=f"llm_fallback({mode}): {reasoning}"
                        )
                except (json.JSONDecodeError, ValueError, KeyError):
                    pass

        except Exception:
            pass

        return None

    def classify_document(self, text: str, packs: Dict[str, RulePack]) -> Tuple[Optional[str], List[DocTypeCandidate], str]:
        """
        Classify document with rules-first + optional LLM fallback.

        Returns:
            (selected_pack_id, all_candidates, selection_reason)
        """
        if not packs:
            return None, [], "no_packs_available"

        # Stage A: Rules-first heuristic
        candidates = self.score_document_heuristic(text, packs)

        if not candidates:
            # No candidates from heuristics - use default
            default_pack_id = next(iter(packs.keys()))
            return default_pack_id, [], "no_heuristic_matches_fallback_to_default"

        top_candidate = candidates[0]

        # Check if we need LLM fallback
        if settings.should_use_llm_fallback(top_candidate.score / 10.0):  # Convert score back to 0-1 scale
            # Stage B: LLM fallback
            llm_candidate = self.classify_with_llm_fallback(text, packs, candidates)
            if llm_candidate:
                # Insert LLM result and re-sort
                all_candidates = candidates + [llm_candidate]
                all_candidates.sort(key=lambda x: x.score, reverse=True)
                selected = all_candidates[0]
                reason = f"llm_fallback_triggered (heuristic_confidence={top_candidate.score/10.0:.2f} < threshold={settings.DOC_TYPE_CONFIDENCE_THRESHOLD})"
                return selected.pack_id, all_candidates, reason

        # Use top heuristic result
        reason = f"heuristic_confident (score={top_candidate.score:.1f}, confidence={top_candidate.score/10.0:.2f})"
        return top_candidate.pack_id, candidates, reason


# Global classifier instance
_classifier = DocumentClassifier()

def guess_doc_type_id_enhanced(text: str, packs: Dict[str, RulePack]) -> Tuple[Optional[str], List[DocTypeCandidate], str]:
    """
    Enhanced document type detection with detailed candidate information.

    Returns:
        (selected_pack_id, candidates, selection_reason)
    """
    return _classifier.classify_document(text, packs)


# ========================================
# LEGACY COMPATIBILITY
# ========================================

def compile_title_hints(packs: Dict[str, RulePack]) -> List[Tuple[re.Pattern, str]]:
    """Legacy function for simple regex-based document type hints."""
    hints: List[Tuple[re.Pattern, str]] = []
    for pack in packs.values():
        for name in pack.doc_type_names:
            hints.append((re.compile(rf"\b{name}\b", re.IGNORECASE), pack.id))
    return hints


def guess_doc_type_id(text: str, packs: Dict[str, RulePack]) -> Optional[str]:
    """
    Legacy document type detection - simple regex matching.
    Maintained for backward compatibility.
    """
    head = (text or "")[:4000]
    for rx, pack_id in compile_title_hints(packs):
        if rx.search(head):
            return pack_id
    return None  # runner will fall back to default pack


# ========================================
# PUBLIC API
# ========================================

__all__ = [
    # PDF Ingestion
    'ingest_pdfs_from_directory',
    'ingest_bytes_to_text',
    'ingest',  # alias

    # Citation Mapping
    'PageLineMapper',
    'enhance_citations_with_page_line',

    # Document Classification
    'DocumentClassifier',
    'DocTypeCandidate',
    'guess_doc_type_id_enhanced',
    'guess_doc_type_id',  # legacy

    # Constants
    'PAGE_BREAK'
]