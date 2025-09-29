"""
Citation mapping utilities for converting character positions to page/line numbers.
"""

from typing import List, Tuple, Optional
from schemas import Citation

PAGE_BREAK = "\f"

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