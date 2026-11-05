from __future__ import annotations

import re
from collections import defaultdict
from typing import Optional

from contract import Conflict, Source
from prose import PassageIndex
from rate_facts import RateFact, is_rate_page, page_path, stem, words_of

NUMBER = re.compile(r"\d+(?:\.\d+)?")
VALUE_NAMES = {"apy": "APY", "apr": "APR", "rate": "rate", "dividend": "dividend", "promo_apy": "promotional APY"}
WORDS_EVERY_PRODUCT_IN_A_FAMILY_SHARES = frozenset(stem(word) for word in "money market checking savings account".split())


def rate_conflicts(facts: tuple[RateFact, ...], snapshot_id: str) -> list[Conflict]:
    rate_page_rows = [fact for fact in facts if is_rate_page(page_path(fact.url))]
    disagreeing_on_page: dict[tuple[str, str], list[tuple[RateFact, RateFact]]] = defaultdict(list)
    for fact in facts:
        current = _row_restated(fact, rate_page_rows)
        if current is not None and _differs(fact, current):
            disagreeing_on_page[page_path(fact.url), fact.family].append((fact, current))
    pages_repeating_it: dict[tuple, list[str]] = defaultdict(list)
    for (path, family), pairs in disagreeing_on_page.items():
        pages_repeating_it[family, _stale_values(pairs)].append(path)
    return [
        _rate_conflict(paths, family, disagreeing_on_page[paths[0], family], snapshot_id)
        for (family, _), paths in pages_repeating_it.items()
    ]


def branch_count_conflict(passages: PassageIndex, snapshot_id: str) -> Optional[Conflict]:
    newest, undated = passages.branch_count_statements()
    if newest is None or not undated or all(count == newest[0] for count, _ in undated):
        return None
    statements = [newest, *undated]
    return Conflict(
        topic="number of branches",
        values=list(dict.fromkeys(count for count, _ in statements)),
        sources=[Source(url=p.url, snapshot_id=snapshot_id, quote=p.text) for _, p in statements],
        resolution=newest[0],
        reason=f"The newest dated statement ({newest[1].published}) wins over an undated page.",
    )


def _row_restated(fact: RateFact, rate_page_rows: list[RateFact]) -> Optional[RateFact]:
    same_product = [row for row in rate_page_rows if _same_tier(fact, row)]
    if not same_product:
        return None

    def closeness(row: RateFact) -> tuple[int, int, bool, str]:
        return _shared_model_years(fact, row), len(fact.words & row.words), row.from_rate_sheet, row.effective or ""

    return max(same_product, key=closeness)


def _same_tier(fact: RateFact, row: RateFact) -> bool:
    same_tier = (
        page_path(fact.url) != page_path(row.url)
        and _names_the_same_product(fact, row)
        and fact.family == row.family
        and fact.business == row.business
        and fact.term_months == row.term_months
        and fact.amount_range == row.amount_range
    )
    both_dated_by_model_year = fact.model_years is not None and row.model_years is not None
    return same_tier and (not both_dated_by_model_year or _shared_model_years(fact, row) > 0)


def _names_the_same_product(fact: RateFact, row: RateFact) -> bool:
    naming_words = {word for word in words_of(row.name) if not any(character.isdigit() for character in word)}
    return bool((naming_words - WORDS_EVERY_PRODUCT_IN_A_FAMILY_SHARES) & fact.words)


def _stale_values(pairs: list[tuple[RateFact, RateFact]]) -> tuple[str, ...]:
    return tuple(sorted({value for stale, _ in pairs for value in stale.values.values()}))


def _shared_model_years(fact: RateFact, row: RateFact) -> int:
    if fact.model_years is None or row.model_years is None:
        return 0
    return max(0, min(fact.model_years[1], row.model_years[1]) - max(fact.model_years[0], row.model_years[0]) + 1)


def _differs(fact: RateFact, current: RateFact) -> bool:
    kinds_both_state = fact.values.keys() & current.values.keys()
    return any(_numbers(fact.values[kind]) != _numbers(current.values[kind]) for kind in kinds_both_state)


def _numbers(value: str) -> tuple[float, ...]:
    return tuple(float(number) for number in NUMBER.findall(value))


def _rate_conflict(paths: list[str], family: str, pairs: list[tuple[RateFact, RateFact]], snapshot_id: str) -> Conflict:
    showing = ", ".join(paths)
    names = list(dict.fromkeys(current.name for _, current in pairs))
    stale_values = [value for stale, _ in pairs for value in stale.values.values()]
    current_values = [value for _, current in pairs for value in current.values.values()]
    stale_row, current_row = pairs[0]
    return Conflict(
        topic=f"{family.replace('_', ' ')} rates on {showing}: {'; '.join(names)}",
        values=list(dict.fromkeys(stale_values + current_values)),
        sources=[
            Source(url=stale_row.url, snapshot_id=snapshot_id, quote=stale_row.row),
            Source(url=current_row.url, snapshot_id=snapshot_id, quote=current_row.row),
        ],
        resolution="; ".join(dict.fromkeys(_described(current) for _, current in pairs)),
        reason=(
            f"{page_path(current_row.url)} is the page rates are kept on ({_when(current_row)}); "
            f"older rates ({_when(stale_row)}) remain on {showing}."
        ),
    )


def _when(fact: RateFact) -> str:
    return f"effective {fact.effective}" if fact.effective else "undated"


def _described(fact: RateFact) -> str:
    values = ", ".join(f"{value} {VALUE_NAMES.get(kind, kind)}" for kind, value in fact.values.items())
    return f"{fact.name}: {values}"
