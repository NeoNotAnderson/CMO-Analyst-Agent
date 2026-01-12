"""
Section classifier for CMO prospectus documents.

This module uses LLM to classify prospectus sections into standardized categories
based on the section taxonomy.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import json
from difflib import SequenceMatcher

from .section_taxonomy import (
    SectionCategory,
    SectionMapping,
    SECTION_MAPPINGS
)
from core.models import Prospectus


# Classification now enriches parsed_file directly instead of creating separate objects


class SectionClassifier:
    """
    Classifies prospectus sections using LLM and rule-based matching.
    """

    def __init__(self, llm_client=None):
        """
        Initialize the section classifier.

        Args:
            llm_client: LLM client for GPT-5-NANO (to be injected)
        """
        self.llm_client = llm_client
        self.section_mappings = SECTION_MAPPINGS

    def classify_from_prospectus(
        self,
        prospectus: Prospectus
    ) -> Dict:
        """
        Classify all sections and enrich parsed_file with category/confidence in-place.

        This method adds 'category' and 'confidence' fields to each section in parsed_file.
        The hierarchy is already handled by the 'subsections' structure, so we don't need
        subcategory fields.

        Example:
            Section (level=1, title="SUMMARY") -> category="deal_summary"
                Subsection (level=2, title="OFFERED CERTIFICATES") -> category="offered_certificates"

        Args:
            prospectus: Prospectus object with parsed_file containing all sections

        Returns:
            Dict with metadata about classification results
        """
        # Extract sections from parsed_file
        parsed_file = prospectus.parsed_file
        if not parsed_file or 'sections' not in parsed_file:
            return {
                'success': False,
                'error': 'No sections found in parsed_file'
            }

        sections = parsed_file['sections']
        classified_count = 0
        unclassified_count = 0

        # Classify each section and add fields in-place
        for section in sections:
            self._classify_and_enrich_section(section)

            # Count results
            if section.get('category'):
                classified_count += 1
            else:
                unclassified_count += 1

            # Recursively classify subsections if they exist
            if 'subsections' in section and section['subsections']:
                sub_classified, sub_unclassified = self._classify_subsections(section['subsections'])
                classified_count += sub_classified
                unclassified_count += sub_unclassified

        # Save the enriched parsed_file back to the prospectus
        prospectus.parsed_file = parsed_file
        prospectus.save(update_fields=['parsed_file'])

        # Return metadata
        return {
            'success': True,
            'total_sections': classified_count + unclassified_count,
            'classified_count': classified_count,
            'unclassified_count': unclassified_count,
            'prospectus_id': str(prospectus.prospectus_id)
        }

    def _classify_and_enrich_section(self, section: Dict) -> None:
        """
        Classify a single section and add category/confidence fields to it in-place.

        Args:
            section: Section dict from parsed_file (modified in-place)
        """
        title = section.get('title', '')
        level = section.get('level', 1)
        page_start = section.get('page_num', 0)

        # Get content sample from section text (first 400 chars)
        section_text = section.get('text', '')
        content_sample = section_text[:400] if section_text else ''

        # Classify the section
        category, confidence = self._classify_single_section(
            title=title,
            level=level,
            page_num=page_start,
            content_sample=content_sample
        )

        # Add classification fields to the section dict (only category and confidence)
        section['category'] = category.value if category else None
        section['confidence'] = float(confidence) if confidence > 0 else 0.0

    def _classify_subsections(self, subsections: List[Dict]) -> Tuple[int, int]:
        """
        Recursively classify subsections.

        Args:
            subsections: List of subsection dicts (modified in-place)

        Returns:
            Tuple of (classified_count, unclassified_count)
        """
        classified = 0
        unclassified = 0

        for subsection in subsections:
            self._classify_and_enrich_section(subsection)

            # Count
            if subsection.get('category'):
                classified += 1
            else:
                unclassified += 1

            # Recurse deeper if needed
            if 'subsections' in subsection and subsection['subsections']:
                sub_classified, sub_unclassified = self._classify_subsections(subsection['subsections'])
                classified += sub_classified
                unclassified += sub_unclassified

        return (classified, unclassified)

    def _classify_single_section(
        self,
        title: str,
        level: int,
        page_num: int,
        content_sample: Optional[str] = None
    ) -> Tuple[Optional[SectionCategory], float]:
        """
        Classify a single section using rule-based and LLM methods.

        Args:
            title: Section title
            level: Hierarchy level
            page_num: Starting page number
            content_sample: Sample content from the section (optional)

        Returns:
            Tuple of (category, confidence_score)
        """
        # Step 1: Try rule-based matching (exact then fuzzy)
        mapping, confidence = self._rule_based_match(title)

        # Step 2: If confidence < 0.85, use LLM classification
        if confidence < 0.85 and self.llm_client and content_sample:
            llm_category, llm_confidence = self._llm_classify(
                title=title,
                content_sample=content_sample,
                context={'level': level, 'page_num': page_num}
            )
            # Use LLM result if it has higher confidence
            if llm_confidence > confidence:
                return (llm_category, llm_confidence)

        # Return rule-based result
        if mapping:
            return (mapping.category, confidence)

        return (None, 0.0)

    def _rule_based_match(
        self,
        title: str
    ) -> Tuple[Optional[SectionMapping], float]:
        """
        Attempt to match section using rule-based methods.
        Only uses exact and fuzzy matching.

        Args:
            title: Section title to match

        Returns:
            Tuple of (SectionMapping, confidence_score)
        """
        if not title:
            return (None, 0.0)

        title_normalized = title.strip().upper()
        best_match = None
        best_confidence = 0.0

        for mapping in self.section_mappings:
            # 1. Exact title match (confidence: 0.95-1.0)
            for common_title in mapping.common_titles:
                if title_normalized == common_title.upper():
                    return (mapping, 0.98)

            # 2. Fuzzy string matching (confidence: 0.70-0.90)
            for common_title in mapping.common_titles:
                similarity = SequenceMatcher(
                    None,
                    title_normalized,
                    common_title.upper()
                ).ratio()

                # If similarity > 0.85, consider it a good fuzzy match
                if similarity > 0.85:
                    confidence = similarity * 0.9  # Scale down slightly
                    if confidence > best_confidence:
                        best_match = mapping
                        best_confidence = confidence

        return (best_match, best_confidence)

    def _llm_classify(
        self,
        title: str,
        content_sample: str,
        context: Optional[Dict] = None
    ) -> Tuple[Optional[SectionCategory], float]:
        """
        Use LLM to classify section when rule-based methods fail.

        Args:
            title: Section title
            content_sample: Sample content from section
            context: Additional context (parent section, etc.)

        Returns:
            Tuple of (category, confidence_score)
        """
        if not self.llm_client:
            return (None, 0.0)

        # Build classification prompt
        prompt = self._build_classification_prompt(title, content_sample, context)

        try:
            # Call GPT-5-NANO with structured output
            response = self.llm_client.chat.completions.create(
                model="gpt-5-nano",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )

            # Parse response
            result = json.loads(response.choices[0].message.content)

            category_str = result.get('category')
            confidence = float(result.get('confidence', 0.0))

            # Convert string to enum
            category = SectionCategory(category_str) if category_str else None

            return (category, confidence)

        except Exception as e:
            print(f"LLM classification error: {e}")
            return (None, 0.0)

    def _build_classification_prompt(
        self,
        title: str,
        content_sample: str,
        context: Optional[Dict] = None
    ) -> str:
        """
        Build prompt for LLM classification.

        Args:
            title: Section title
            content_sample: Sample content
            context: Additional context

        Returns:
            Formatted prompt string
        """
        # Build taxonomy description
        categories_desc = "\n".join([
            f"- {cat.value}: {cat.name}" for cat in SectionCategory
        ])

        prompt = f"""You are classifying sections from a CMO prospectus document.

AVAILABLE CATEGORIES:
{categories_desc}

SECTION TO CLASSIFY:
Title: {title}
Content Sample: {content_sample[:500]}

{"Context: " + json.dumps(context) if context else ""}

Classify this section into the most appropriate category.
Return your response as JSON with the following format:
{{
    "category": "category_value",
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}

Use the exact enum values (e.g., "deal_summary", "offered_certificates", "payment_priority").
The hierarchy is maintained by the document structure, so assign the most specific category that matches.
"""
        return prompt

    def get_classification_stats(
        self,
        parsed_file: Dict
    ) -> Dict:
        """
        Get statistics about classification results from enriched parsed_file.

        Args:
            parsed_file: The enriched parsed_file with category/confidence fields

        Returns:
            Dictionary with statistics
        """
        stats = {
            'total_sections': 0,
            'classified_count': 0,
            'unclassified_count': 0,
            'coverage_percentage': 0.0,
            'average_confidence': 0.0,
            'by_category': {},
            'by_method': {'exact': 0, 'fuzzy': 0, 'llm': 0}
        }

        if not parsed_file or 'sections' not in parsed_file:
            return stats

        # Recursively collect stats
        confidences = []
        self._collect_stats_recursive(parsed_file['sections'], stats, confidences)

        # Calculate averages
        if stats['total_sections'] > 0:
            stats['coverage_percentage'] = (stats['classified_count'] / stats['total_sections']) * 100

        if confidences:
            stats['average_confidence'] = sum(confidences) / len(confidences)

        return stats

    def _collect_stats_recursive(self, sections: List[Dict], stats: Dict, confidences: List[float]) -> None:
        """
        Recursively collect statistics from sections and subsections.

        Args:
            sections: List of section dicts
            stats: Stats dict to update
            confidences: List to collect confidence scores
        """
        for section in sections:
            stats['total_sections'] += 1

            category = section.get('category')
            confidence = section.get('confidence', 0.0)

            if category:
                stats['classified_count'] += 1
                stats['by_category'][category] = stats['by_category'].get(category, 0) + 1
                confidences.append(confidence)

                # Determine classification method by confidence
                if confidence >= 0.95:
                    stats['by_method']['exact'] += 1
                elif confidence >= 0.75:
                    stats['by_method']['fuzzy'] += 1
                else:
                    stats['by_method']['llm'] += 1
            else:
                stats['unclassified_count'] += 1

            # Recurse into subsections
            if 'subsections' in section and section['subsections']:
                self._collect_stats_recursive(section['subsections'], stats, confidences)

    def export_section_map(
        self,
        parsed_file: Dict,
        format: str = "json"
    ) -> str:
        """
        Export enriched parsed_file in specified format.

        Args:
            parsed_file: The enriched parsed_file with category/confidence fields
            format: Output format (json, yaml, etc.)

        Returns:
            Serialized section map
        """
        export_data = {
            'sections': parsed_file.get('sections', []),
            'statistics': self.get_classification_stats(parsed_file)
        }

        if format == "json":
            return json.dumps(export_data, indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")


def create_section_classifier(llm_client=None) -> SectionClassifier:
    """
    Factory function to create a section classifier.

    Args:
        llm_client: LLM client instance

    Returns:
        Initialized SectionClassifier
    """
    return SectionClassifier(llm_client=llm_client)
