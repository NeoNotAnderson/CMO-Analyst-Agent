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
        Parsed files only have 2 levels: level 1 (top-level) and level 2 (subsections).
        Subsections do not have further subsections.

        Example:
            Section (level=1, title="SUMMARY") -> category="deal_summary"
            Section (level=2, title="Offered Certificates", parent="SUMMARY") -> category="offered_certificates"

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

        # Classify each level 1 section
        for section in sections:
            # Classify the level 1 section
            self._classify_and_enrich_section(section, parent_category=None, is_subsection=False)

            # Count results
            if section.get('category'):
                classified_count += 1
            else:
                unclassified_count += 1

            # Classify level 2 subsections if they exist
            if 'sections' in section and section['sections']:
                # Pass parent's category to constrain subcategory choices
                parent_cat = SectionCategory(section['category']) if section.get('category') else None

                for subsection in section['sections']:
                    self._classify_and_enrich_section(subsection, parent_category=parent_cat, is_subsection=True)

                    # Count results
                    if subsection.get('category'):
                        classified_count += 1
                    else:
                        unclassified_count += 1

        # Save the enriched parsed_file back to the prospectus
        prospectus.parsed_file = parsed_file
        prospectus.parse_status = 'completed'
        prospectus.save(update_fields=['parsed_file'])

        # Return metadata
        return {
            'success': True,
            'total_sections': classified_count + unclassified_count,
            'classified_count': classified_count,
            'unclassified_count': unclassified_count,
            'prospectus_id': str(prospectus.prospectus_id)
        }

    def _classify_and_enrich_section(self, section: Dict, parent_category: Optional[SectionCategory] = None, is_subsection: bool = False) -> None:
        """
        Classify a single section and add category/confidence fields to it in-place.

        Args:
            section: Section dict from parsed_file (modified in-place)
            parent_category: Parent section's category for hierarchy constraint
        """
        title = section.get('title', '')
        # in case some sections don't have 'level'
        level = 2 if is_subsection else 1
        section['level'] = level
        page_start = section.get('page_num', 0)

        # Get content sample from section text (first 400 chars)
        section_text = section.get('text', '')
        content_sample = section_text[:400] if section_text else ''

        # Classify the section with hierarchy constraint
        category, confidence = self._classify_single_section(
            title=title,
            level=level,
            page_num=page_start,
            content_sample=content_sample,
            parent_category=parent_category
        )

        # Add classification fields to the section dict (only category and confidence)
        section['category'] = category.value if category else None
        section['confidence'] = float(confidence) if confidence > 0 else 0.0


    def _classify_single_section(
        self,
        title: str,
        level: int,
        page_num: int,
        content_sample: Optional[str] = None,
        parent_category: Optional[SectionCategory] = None
    ) -> Tuple[Optional[SectionCategory], float]:
        """
        Classify a single section using rule-based and LLM methods with hierarchy constraint.

        Args:
            title: Section title
            level: Hierarchy level
            page_num: Starting page number
            content_sample: Sample content from the section (optional)
            parent_category: Parent section's category for hierarchy constraint

        Returns:
            Tuple of (category, confidence_score)
        """
        # Get allowed categories based on hierarchy
        from .section_taxonomy import get_allowed_categories
        allowed_categories = get_allowed_categories(level, parent_category)

        # Step 1: Try rule-based matching (exact then fuzzy) with hierarchy filter
        mapping, confidence = self._rule_based_match(title, allowed_categories)

        # Step 2: If confidence < 0.85, use LLM classification
        if confidence < 0.85 and self.llm_client and content_sample:
            llm_category, llm_confidence = self._llm_classify(
                title=title,
                content_sample=content_sample,
                context={'level': level, 'page_num': page_num, 'parent_category': parent_category},
                allowed_categories=allowed_categories
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
        title: str,
        allowed_categories: set
    ) -> Tuple[Optional[SectionMapping], float]:
        """
        Attempt to match section using rule-based methods with hierarchy constraint.
        Only uses exact and fuzzy matching.

        Args:
            title: Section title to match
            allowed_categories: Set of allowed SectionCategory values based on hierarchy

        Returns:
            Tuple of (SectionMapping, confidence_score)
        """
        if not title:
            return (None, 0.0)

        title_normalized = title.strip().upper()
        best_match = None
        best_confidence = 0.0

        for mapping in self.section_mappings:
            # Skip if this category is not allowed by hierarchy
            if mapping.category not in allowed_categories:
                continue

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
        context: Optional[Dict] = None,
        allowed_categories: Optional[set] = None
    ) -> Tuple[Optional[SectionCategory], float]:
        """
        Use LLM to classify section when rule-based methods fail.

        Args:
            title: Section title
            content_sample: Sample content from section
            context: Additional context (parent section, etc.)
            allowed_categories: Set of allowed categories based on hierarchy

        Returns:
            Tuple of (category, confidence_score)
        """
        if not self.llm_client:
            return (None, 0.0)

        # Build classification prompt with hierarchy constraint
        prompt = self._build_classification_prompt(title, content_sample, context, allowed_categories)

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

            # Require confidence >= 0.8, otherwise treat as None
            # Less information is better than wrong information
            if not category_str or confidence < 0.8:
                return (None, 0.0)

            # Convert string to enum
            try:
                category = SectionCategory(category_str)
                return (category, confidence)
            except ValueError:
                print(f"LLM classification error: '{category_str}' is not a valid SectionCategory")
                return (None, 0.0)

        except Exception as e:
            print(f"LLM classification error: {e}")
            return (None, 0.0)

    def _build_classification_prompt(
        self,
        title: str,
        content_sample: str,
        context: Optional[Dict] = None,
        allowed_categories: Optional[set] = None
    ) -> str:
        """
        Build prompt for LLM classification with hierarchy constraint.

        Args:
            title: Section title
            content_sample: Sample content
            context: Additional context
            allowed_categories: Set of allowed categories based on hierarchy

        Returns:
            Formatted prompt string
        """
        # Build taxonomy description - only allowed categories
        # Format: "- category_value" (LLM should return the value, not the name)
        if allowed_categories:
            categories_desc = "\n".join([
                f"- {cat.value}" for cat in allowed_categories
            ])
        else:
            categories_desc = "\n".join([
                f"- {cat.value}" for cat in SectionCategory
            ])

        # Add parent context if available
        parent_info = ""
        if context and context.get('parent_category'):
            parent_cat = context['parent_category']
            parent_info = f"\nParent Section Category: {parent_cat.value if isinstance(parent_cat, SectionCategory) else parent_cat}"

        prompt = f"""You are classifying sections from a CMO prospectus document.

ALLOWED CATEGORIES FOR THIS SECTION:{parent_info}
{categories_desc}

SECTION TO CLASSIFY:
Title: {title}
Level: {context.get('level') if context else 'unknown'}
Content Sample: {content_sample[:500]}

IMPORTANT: You MUST select a category from the allowed list above based on the section's hierarchy level.
- Level 1 sections can only be top-level categories (deal_summary, risk_factors, etc.)
- Level 2+ sections can only be subcategories under their parent category

Classify this section into the most appropriate category from the ALLOWED list.
Return your response as JSON with the following format:
{{
    "category": "category_value",
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}

Use the exact enum values from the ALLOWED CATEGORIES list above.
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
        Collect statistics from sections (2-level structure only).

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

            # Process level 2 subsections (only one level deep)
            if 'sections' in section and section['sections']:
                for subsection in section['sections']:
                    stats['total_sections'] += 1
                    sub_category = subsection.get('category')
                    sub_confidence = subsection.get('confidence', 0.0)

                    if sub_category:
                        stats['classified_count'] += 1
                        stats['by_category'][sub_category] = stats['by_category'].get(sub_category, 0) + 1
                        confidences.append(sub_confidence)

                        # Determine classification method by confidence
                        if sub_confidence >= 0.95:
                            stats['by_method']['exact'] += 1
                        elif sub_confidence >= 0.75:
                            stats['by_method']['fuzzy'] += 1
                        else:
                            stats['by_method']['llm'] += 1
                    else:
                        stats['unclassified_count'] += 1

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
