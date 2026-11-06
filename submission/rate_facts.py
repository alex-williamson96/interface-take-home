from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterator, Optional
from urllib.parse import urlparse

from site_profile import SITE

RATE_SHEET_PATHS = SITE.rate_sheet_paths
PRODUCT_PAGE_PREFIXES = SITE.product_page_prefixes
NOT_RATE_PAGE_PREFIXES = SITE.prefixes_that_are_not_rate_pages

LONGEST_HEADING_CHARS = 70
HEADING_LINES_KEPT = 2
LINES_SEARCHED_FOR_EFFECTIVE_DATE = 30
MONTHS_PER_YEAR = 12

VALUE_COLUMNS = (
    ("promo_apy", re.compile(r"(?:yield|\bapy\b).*1st \d+ months", re.I)),
    ("promo_dividend", re.compile(r"dividend.*1st \d+ months", re.I)),
    ("apy", re.compile(r"yield|\bapy\b", re.I)),
    ("dividend", re.compile(r"dividend", re.I)),
    ("apr", re.compile(r"annual percentage rate|\bapr\b", re.I)),
    ("rate", re.compile(r"^rate$", re.I)),
)
IGNORED_COLUMN = re.compile(r"points|payment|min\.", re.I)
MINIMUM_TO_EARN_COLUMN = re.compile(r"min\. to earn", re.I)
PRODUCT_NAME_IN_HEADER = re.compile(r"\bvisa\b", re.I)

SEPARATOR_ROW = re.compile(r"^\|\s*:?-{3}")
EFFECTIVE_DATE = re.compile(r"effective as of (\d{1,2})/(\d{1,2})/(\d{4})", re.I)
PERCENT_RANGE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*%?\s*[-–—]\s*(\d+(?:\.\d+)?)\s*%?")
PERCENT = re.compile(r"^\s*(\d+(?:\.\d+)?)")
DOLLAR_VALUE = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)")
DOLLAR_RANGE = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)\s*[-–—]\s*\$?\s*([\d,]+(?:\.\d+)?)")
DOLLAR_FLOOR = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)\s*\+")
DOLLAR_CEILING = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)\s+or less", re.I)
TERM = re.compile(r"(\d+)[\s-]*(months?|mos?\b|years?|yrs?\b)", re.I)
MODEL_YEARS = re.compile(r"(20\d\d)\s*[-–—]\s*(\d{2,4})")
SINGLE_MODEL_YEAR = re.compile(r"\b(20\d\d)\b")
EARLIEST_MODEL_YEAR = 1900
WORD = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
CANONICAL_WORDS = {"intro": "introductory", "hsa": "health", "cds": "cd"}

FAMILY_PATTERNS = (
    ("money_market", re.compile(rf"money market|{SITE.money_market_names_pattern}", re.I)),
    ("ira", re.compile(r"\bira\b|\biras\b|\broth\b|traditional:", re.I)),
    ("home_improvement", re.compile(r"home improvement", re.I)),
    ("home_equity", re.compile(r"home equity|heloc", re.I)),
    ("mortgage", re.compile(r"home loan|fixed conventional|mortgage", re.I)),
    ("auto", re.compile(r"\bauto\b|motorcycle", re.I)),
    ("recreation", re.compile(r"boat|\brv\b|atv|snowmobile|jet ski", re.I)),
    ("personal_loan", re.compile(r"personal loan", re.I)),
    ("card", re.compile(r"\bvisa\b|credit card", re.I)),
    ("certificate", re.compile(r"certificate|month fixed|\bterm \d+ month", re.I)),
    ("checking", re.compile(r"checking", re.I)),
    ("savings", re.compile(rf"saving|{SITE.savings_names_in_tables_pattern}", re.I)),
)


@dataclass(frozen=True)
class RateFact:
    family: str
    heading: str
    label: str
    values: dict[str, str]
    words: frozenset[str]
    term_months: Optional[int]
    amount_range: Optional[tuple[float, float]]
    model_years: Optional[tuple[int, int]]
    business: bool
    url: str
    from_rate_sheet: bool
    effective: Optional[str]
    row: str

    @property
    def name(self) -> str:
        if not self.label:
            return self.heading
        label_repeats_heading = words_of(self.heading) & words_of(self.label)
        label_names_a_product = classify_family(self.label) is not None
        if self.heading and not label_repeats_heading and not label_names_a_product:
            return f"{self.heading} {self.label}"
        return self.label


def words_of(text: str) -> frozenset[str]:
    return frozenset(stem(w) for w in WORD.findall(text.lower()))


def stem(word: str) -> str:
    word = word.removesuffix("'s")
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        word = word[:-1]
    return CANONICAL_WORDS.get(word, word)


def page_path(url: str) -> str:
    return urlparse(url).path.rstrip("/").lower() or "/"


def is_rate_page(path: str) -> bool:
    if path in RATE_SHEET_PATHS:
        return True
    return path.startswith(PRODUCT_PAGE_PREFIXES) and not path.startswith(NOT_RATE_PAGE_PREFIXES)


def split_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def clean_label(cell: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\\?\*+|—", "", cell)).strip()


def format_percent(cell: str) -> Optional[str]:
    span = PERCENT_RANGE.match(cell)
    if span:
        return f"{span.group(1)}%–{span.group(2)}%"
    single = PERCENT.match(cell)
    return f"{single.group(1)}%" if single else None


def dollars(text: str) -> float:
    return float(text.replace(",", ""))


def parse_amount_range(label: str) -> Optional[tuple[float, float]]:
    span = DOLLAR_RANGE.search(label)
    if span:
        return dollars(span.group(1)), dollars(span.group(2))
    floor = DOLLAR_FLOOR.search(label)
    if floor:
        return dollars(floor.group(1)), math.inf
    ceiling = DOLLAR_CEILING.search(label)
    if ceiling:
        return 0.0, dollars(ceiling.group(1))
    return None


def _range_from_minimum(cells: list[str], minimum_column: Optional[int]) -> Optional[tuple[float, float]]:
    minimum = DOLLAR_VALUE.search(cells[minimum_column]) if minimum_column is not None else None
    return (dollars(minimum.group(1)), math.inf) if minimum else None


def parse_term_months(text: str) -> Optional[int]:
    term = TERM.search(text)
    if not term:
        return None
    count = int(term.group(1))
    return count * MONTHS_PER_YEAR if term.group(2).lower().startswith("y") else count


def parse_model_years(label: str) -> Optional[tuple[int, int]]:
    if "model year" not in label.lower():
        return None
    span = MODEL_YEARS.search(label)
    if not span:
        single = SINGLE_MODEL_YEAR.search(label)
        if not single:
            return None
        year = int(single.group(1))
        return (EARLIEST_MODEL_YEAR, year) if "older" in label.lower() else (year, year)
    first, second = span.group(1), span.group(2)
    other = int(second) if len(second) == 4 else int(first[:2] + second)
    return min(int(first), other), max(int(first), other)


def classify_family(text: str) -> Optional[str]:
    for family, pattern in FAMILY_PATTERNS:
        if pattern.search(text):
            return family
    return None


def heading_text(line: str) -> str:
    return line.strip().lstrip("#").strip()


def cannot_be_a_heading(line: str) -> bool:
    text = heading_text(line)
    return line.startswith("|") or len(text) > LONGEST_HEADING_CHARS or text.startswith(("[", "!"))


def headings_above(lines: list[str], table_start: int) -> list[str]:
    kept: list[str] = []
    for line in reversed(lines[:table_start]):
        text = heading_text(line)
        if not text:
            continue
        if cannot_be_a_heading(line):
            break
        kept.append(text)
        if len(kept) == HEADING_LINES_KEPT:
            break
    return kept


def nearest_family_heading(lines: list[str], table_start: int) -> Optional[str]:
    for line in reversed(lines[:table_start]):
        text = heading_text(line)
        if text and not cannot_be_a_heading(line) and classify_family(text):
            return text
    return None


def effective_date_after(lines: list[str], table_end: int) -> Optional[str]:
    for line in lines[table_end : table_end + LINES_SEARCHED_FOR_EFFECTIVE_DATE]:
        if line.startswith("|"):
            return None
        found = EFFECTIVE_DATE.search(line)
        if found:
            month, day, year = found.groups()
            return f"{year}-{int(month):02d}-{int(day):02d}"
    return None


def read_table_ends(lines: list[str]) -> Iterator[tuple[int, int]]:
    index = 0
    while index + 1 < len(lines):
        if lines[index].startswith("|") and SEPARATOR_ROW.match(lines[index + 1]):
            end = index + 2
            while end < len(lines) and lines[end].startswith("|"):
                end += 1
            yield index, end
            index = end
        else:
            index += 1


def extract_rate_facts(url: str, markdown: str) -> list[RateFact]:
    return extract_table_facts(url, markdown) if is_rate_page(page_path(url)) else []


def extract_table_facts(url: str, markdown: str) -> list[RateFact]:
    path = page_path(url)
    lines = markdown.splitlines()
    facts: list[RateFact] = []
    for start, end in read_table_ends(lines):
        facts.extend(_facts_from_table(url, path, lines, start, end))
    return facts


def _facts_from_table(url: str, path: str, lines: list[str], start: int, end: int) -> list[RateFact]:
    headers = split_cells(lines[start])
    value_columns: dict[int, str] = {}
    label_columns: list[int] = []
    for position, header in enumerate(headers):
        kind = next((name for name, pattern in VALUE_COLUMNS if pattern.search(header)), None)
        if kind:
            value_columns[position] = kind
        elif not IGNORED_COLUMN.search(header):
            label_columns.append(position)
    if not value_columns:
        return []

    minimum_column = next((p for p, header in enumerate(headers) if MINIMUM_TO_EARN_COLUMN.search(header)), None)
    headings = headings_above(lines, start)
    label_headers = " ".join(headers[p] for p in label_columns)
    named_in_header = next((clean_label(headers[p]) for p in label_columns if PRODUCT_NAME_IN_HEADER.search(headers[p])), "")
    section = None if classify_family(" ".join(headings)) else nearest_family_heading(lines, start)
    heading = named_in_header or (headings[0] if headings else section or "")
    context = " ".join(headings + ([section] if section else []))
    effective = effective_date_after(lines, end)
    from_rate_sheet = path in RATE_SHEET_PATHS

    facts = []
    for line in lines[start + 2 : end]:
        cells = split_cells(line)
        if len(cells) != len(headers):
            continue
        values = {
            kind: formatted
            for position, kind in value_columns.items()
            if (formatted := format_percent(cells[position]))
        }
        if not values:
            continue
        label = clean_label(" ".join(cells[p] for p in label_columns))
        described = f"{context} {label_headers} {label}"
        family = classify_family(described)
        if family is None:
            continue
        facts.append(
            RateFact(
                family=family,
                heading=clean_label(heading),
                label=label,
                values=values,
                words=words_of(described),
                term_months=parse_term_months(label),
                amount_range=parse_amount_range(label) or _range_from_minimum(cells, minimum_column),
                model_years=parse_model_years(label),
                business=path.startswith("/business") or "business" in described.lower(),
                url=url,
                from_rate_sheet=from_rate_sheet,
                effective=effective,
                row=line.strip(),
            )
        )
    return facts
