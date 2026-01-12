"""
Section taxonomy for CMO prospectus classification.

This module defines the standardized section categories used to classify
and organize CMO prospectus documents for efficient retrieval and script generation.
"""

from enum import Enum
from typing import Dict, List, Optional
from dataclasses import dataclass


class SectionCategory(str, Enum):
    """
    Section categories for CMO prospectus documents.

    Each category represents a type of section that can appear at any level
    in the document hierarchy. The hierarchy is maintained by the parsed_file
    structure itself (via subsections), not by subcategory enums.
    """

    # Top-level categories
    DEAL_SUMMARY = "deal_summary"
    RISK_DESCRIPTION = "risk_factors"
    CERTIFICATE_DESCRIPTION = "certificate_structure"
    COLLATERAL_DESCRIPTION = "collateral_description"

    # Common sections under DEAL_SUMMARY
    OFFERED_CERTIFICATES = "offered_certificates"
    COUNTERPARTIES = "counterparties"
    KEY_DATES = "key_dates"
    PAYMENT_PRIORITY = "payment_priority"
    INTEREST_DISTRIBUTION = "interest_distribution"
    PRINCIPAL_DISTRIBUTION = "principal_distribution"
    CROSS_COLLATERALIZATION = "cross_collateralization"
    CLEAN_UP_CALL = "clean_up_call"
    CREDIT_ENHANCEMENT = "credit_enhancement"
    MORTGAGE_SUMMARY = "mortgage_summary"
    TAX_INFORMATION = "tax_information"
    CERTIFICATE_RATINGS = "certificate_ratings"

    # Risk description sections
    PREPAYMENT_RISK = "prepayment_risk"
    INTEREST_RATE_RISK = "interest_rate_risk"
    CREDIT_ENHANCEMENT_RISK = "credit_enhancement_risk"

    # Collateral description sections
    MORTGAGE_CHARACTERISTICS = "loan_characteristics"
    MORTGAGE_STATISTICS = "loan_statistics"
    MORTGAGE_ASSIGNMENT = "loan_assignment"

    # Certificate description sections
    CERTIFICATE_CHARACTERISTICS = "certificate_characteristics"
    LOSS_ALLOCATION = "loss_allocation"
    SUBORDINATE_CERTIFICATES_PAYMENTS = "subordinate_certificates_payments"


@dataclass
class SectionMapping:
    """Common prospectus section titles mapped to taxonomy categories."""

    category: SectionCategory
    common_titles: List[str]
    keywords: List[str]


# Mapping of common prospectus section titles to taxonomy
SECTION_MAPPINGS: List[SectionMapping] = [
    # Top-level categories
    SectionMapping(
        category=SectionCategory.DEAL_SUMMARY,
        common_titles=["SUMMARY", "DEAL SUMMARY", "TRANSACTION SUMMARY"],
        keywords=["summary", "deal", "transaction", "overview"],
    ),
    SectionMapping(
        category=SectionCategory.RISK_DESCRIPTION,
        common_titles=["RISK FACTORS", "RISKS"],
        keywords=["risk", "potential", "may", "could"],
    ),
    SectionMapping(
        category=SectionCategory.CERTIFICATE_DESCRIPTION,
        common_titles=["THE CERTIFICATES", "DESCRIPTION OF CERTIFICATES"],
        keywords=["certificate", "description", "overview"],
    ),
    SectionMapping(
        category=SectionCategory.COLLATERAL_DESCRIPTION,
        common_titles=["THE MORTGAGE LOANS", "DESCRIPTION OF THE MORTGAGE LOANS", "COLLATERAL"],
        keywords=["mortgage", "collateral", "loan", "pool"],
    ),

    # DEAL_SUMMARY subsections
    SectionMapping(
        category=SectionCategory.OFFERED_CERTIFICATES,
        common_titles=["OFFERED CERTIFICATES", "THE CERTIFICATES", "CERTIFICATE TABLE"],
        keywords=["certificate", "class", "cusip", "principal amount", "interest rate", "designation"],
    ),
    SectionMapping(
        category=SectionCategory.COUNTERPARTIES,
        common_titles=["THE TRUST", "THE TRUSTEE", "THE SERVICER", "THE DEPOSITOR", "THE CUSTODIAN", "THE SELLER", "THE MASTER SERVICER", "THE SECURITY ADMINISTRATOR"],
        keywords=["trust", "depositor", "servicer", "trustee", "custodian", "seller", "master servicer", "administrator"],
    ),
    SectionMapping(
        category=SectionCategory.KEY_DATES,
        common_titles=["KEY DATES", "IMPORTANT DATES", "CUT-OFF DATE", "DISTRIBUTION DATE", "RECORD DATE"],
        keywords=["dated date", "first payment date", "settlement date", "closing date", "cut-off date", "distribution date", "record date"],
    ),
    SectionMapping(
        category=SectionCategory.PAYMENT_PRIORITY,
        common_titles=["PRIORITY OF DISTRIBUTIONS", "PAYMENT PRIORITY", "DISTRIBUTION PRIORITY"],
        keywords=["priority", "waterfall", "cash flow"],
    ),
    SectionMapping(
        category=SectionCategory.INTEREST_DISTRIBUTION,
        common_titles=["DISTRIBUTIONS OF INTEREST", "INTEREST PAYMENTS"],
        keywords=["interest", "distribution", "allocation"],
    ),
    SectionMapping(
        category=SectionCategory.PRINCIPAL_DISTRIBUTION,
        common_titles=["DISTRIBUTIONS OF PRINCIPAL", "PRINCIPAL PAYMENTS"],
        keywords=["principal", "distribution", "allocation"],
    ),
    SectionMapping(
        category=SectionCategory.CROSS_COLLATERALIZATION,
        common_titles=["LIMITED CROSS-COLLATERALIZATION", "CROSS-COLLATERALIZATION"],
        keywords=["cross-collateralization"],
    ),
    SectionMapping(
        category=SectionCategory.CLEAN_UP_CALL,
        common_titles=["OPTIONAL CLEAN-UP REDEMPTION", "CLEAN-UP CALL", "OPTIONAL CLEAN-UP REDEMPTION OF THE CERTIFICATES"],
        keywords=["redemption", "clean-up", "optional"],
    ),
    SectionMapping(
        category=SectionCategory.CREDIT_ENHANCEMENT,
        common_titles=["SUBORDINATION", "CREDIT ENHANCEMENT"],
        keywords=["subordination", "subordinate", "senior", "credit enhancement", "overcollateralization"],
    ),
    SectionMapping(
        category=SectionCategory.MORTGAGE_SUMMARY,
        common_titles=["DESCRIPTION OF THE MORTGAGE POOLS", "POOL SUMMARY"],
        keywords=["mortgage loans", "pool", "characteristics", "aggregate"],
    ),
    SectionMapping(
        category=SectionCategory.TAX_INFORMATION,
        common_titles=["MATERIAL FEDERAL INCOME TAX CONSEQUENCES", "TAX MATTERS"],
        keywords=["tax", "irs", "income"],
    ),
    SectionMapping(
        category=SectionCategory.CERTIFICATE_RATINGS,
        common_titles=["RATINGS", "CERTIFICATE RATINGS"],
        keywords=["rating", "moody", "s&p", "fitch", "credit rating"],
    ),

    # RISK_DESCRIPTION subsections
    SectionMapping(
        category=SectionCategory.PREPAYMENT_RISK,
        common_titles=["PREPAYMENT RISK", "PREPAYMENT CONSIDERATIONS"],
        keywords=["prepayment", "psa", "cpr", "speed", "refinance"],
    ),
    SectionMapping(
        category=SectionCategory.INTEREST_RATE_RISK,
        common_titles=["INTEREST RATE RISK", "RATE CONSIDERATIONS"],
        keywords=["interest rate", "yield", "rate change", "rate sensitivity"],
    ),
    SectionMapping(
        category=SectionCategory.CREDIT_ENHANCEMENT_RISK,
        common_titles=["CREDIT RISK", "LOSS RISK", "DEFAULT RISK"],
        keywords=["credit", "default", "loss", "delinquency", "credit enhancement"],
    ),

    # CERTIFICATE_DESCRIPTION subsections
    SectionMapping(
        category=SectionCategory.CERTIFICATE_CHARACTERISTICS,
        common_titles=["DESCRIPTION OF THE CERTIFICATES", "CERTIFICATE CHARACTERISTICS"],
        keywords=["certificate", "class", "tranche", "principal", "interest"],
    ),
    SectionMapping(
        category=SectionCategory.LOSS_ALLOCATION,
        common_titles=["ALLOCATION OF LOSSES", "LOSS ALLOCATION"],
        keywords=["losses", "realized loss", "allocation", "bankruptcy", "fraud", "special hazard"],
    ),
    SectionMapping(
        category=SectionCategory.SUBORDINATE_CERTIFICATES_PAYMENTS,
        common_titles=["SUBORDINATE CERTIFICATES", "SUBORDINATION PAYMENTS", "PAYMENTS OF SUBORDINATE CERTIFICATES"],
        keywords=["subordinate", "subordination", "junior", "mezzanine"],
    ),

    # COLLATERAL_DESCRIPTION subsections
    SectionMapping(
        category=SectionCategory.MORTGAGE_CHARACTERISTICS,
        common_titles=["THE MORTGAGE LOANS", "LOAN CHARACTERISTICS"],
        keywords=["adjustable rate", "fixed rate", "amortization", "term", "maturity"],
    ),
    SectionMapping(
        category=SectionCategory.MORTGAGE_STATISTICS,
        common_titles=["TABULAR CHARACTERISTICS", "POOL CHARACTERISTICS", "STATISTICAL INFORMATION"],
        keywords=["weighted average", "wac", "wam", "wala", "ltv", "fico", "balance"],
    ),
    SectionMapping(
        category=SectionCategory.MORTGAGE_ASSIGNMENT,
        common_titles=["ASSIGNMENT OF MORTGAGE LOANS", "LOAN ASSIGNMENT"],
        keywords=["assignment", "transfer", "conveyance"],
    ),
]


def get_category_mappings(category: SectionCategory) -> List[SectionMapping]:
    """
    Get all section mappings for a specific category.

    Args:
        category: The section category to filter by

    Returns:
        List of SectionMapping objects for the category
    """
    # TODO: Implement filtering logic
    pass


def get_mapping_by_title(title: str) -> Optional[SectionMapping]:
    """
    Find the best matching section mapping for a given title.

    Args:
        title: The section title from the prospectus

    Returns:
        SectionMapping if found, None otherwise
    """
    # TODO: Implement fuzzy matching logic
    pass
