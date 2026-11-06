from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SiteProfile:
    name: str
    words_after_the_name: str
    foundation_word: str
    foundation_name: str
    founding_statement: str
    states_served: tuple[str, ...]
    outlet_that_ranks_it: str
    reviewed_conflicts_file: str

    rate_sheet_paths: frozenset[str]
    product_page_prefixes: tuple[str, ...]
    prefixes_that_are_not_rate_pages: tuple[str, ...]
    prefixes_not_searched: tuple[str, ...]
    listing_paths: tuple[str, ...]
    least_trusted_prefixes: tuple[str, ...]
    less_trusted_prefixes: tuple[str, ...]
    news_prefix: str
    landing_page_suffix: str
    locator_path: str
    card_page_path_part: str
    fee_schedule_path_pattern: str

    heading_after_the_hours: str
    heading_after_an_article: str

    money_market_names_pattern: str
    savings_names_in_questions_pattern: str
    savings_names_in_tables_pattern: str


DUPACO = SiteProfile(
    name="Dupaco",
    words_after_the_name="community credit union",
    foundation_word="foundation",
    foundation_name="the Dupaco Foundation",
    founding_statement="founded in 1948",
    states_served=("Iowa", "Illinois", "Wisconsin"),
    outlet_that_ranks_it="forbes",
    reviewed_conflicts_file="reviewed_conflicts.json",
    rate_sheet_paths=frozenset({"/rates", "/business-rates"}),
    product_page_prefixes=("/personal/", "/business/"),
    prefixes_that_are_not_rate_pages=("/business/resources",),
    prefixes_not_searched=("/calculators", "/business-calculators", "/privacy-policy", "/digital-privacy-policy"),
    listing_paths=("/newsroom", "/learn/blog", "/learn", "/business/resources"),
    least_trusted_prefixes=("/hubfs",),
    less_trusted_prefixes=("/learn", "/business/resources", "/20"),
    news_prefix="/newsroom",
    landing_page_suffix="-lp",
    locator_path="/contact",
    card_page_path_part="credit-cards",
    fee_schedule_path_pattern=r"fee-schedule|^/fees?$",
    heading_after_the_hours="ABOUT DUPACO",
    heading_after_an_article="Handpicked for You",
    money_market_names_pattern=r"investor[’']?s choice|\bachieve\b",
    savings_names_in_questions_pattern=r"holiday club|launchpad|you[- ]name[- ]it|high[- ]yield|\bbright\b|\bhsas?\b",
    savings_names_in_tables_pattern=r"holiday club",
)

SITE = DUPACO
SITE_NAME_IN_LOWERCASE = SITE.name.lower()
