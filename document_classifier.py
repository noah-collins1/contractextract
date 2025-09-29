"""
Enhanced document type detection with rules-first scoring and LLM fallback.
"""

import re
import json
from typing import Dict, List, Tuple, Optional, NamedTuple
from schemas import RulePack
from settings import settings

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

def guess_doc_type_id(text: str, packs: Dict[str, RulePack]) -> Optional[str]:
    """
    Legacy interface - returns just the pack ID for backward compatibility.
    """
    pack_id, _, _ = _classifier.classify_document(text, packs)
    return pack_id