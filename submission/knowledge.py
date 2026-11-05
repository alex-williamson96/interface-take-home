from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Optional

from conflicts import branch_count_conflict, foundation_founding_conflict, rate_conflicts
from contract import Answer, Conflict, Snapshot, Source
from prose import EXCLUDED_PAGE_PREFIXES, Found, PassageIndex
from question import (
    BUSINESS_ASKED,
    RateQuestion,
    asks_about_a_fee,
    asks_for_a_link,
    family_of_rates_asked_about,
    parse_rate_question,
    search_may_answer,
)
from rate_facts import RateFact, classify_family, extract_rate_facts, extract_table_facts, page_path, stem

REFUSAL_TEXT = "I can't confirm that from the website. Please contact Dupaco."
JUMBO = stem("jumbo")
CASH = stem("cash")
FAMILY_OF_CASH_OUT_ROWS = "home_equity"
EXCLUDED_UNLESS_ASKED = frozenset(stem(word) for word in ("jumbo", "refinance", "relief", "introductory", "transfer", "cash"))
FAMILY_SPANNING_PERSONAL_AND_BUSINESS = "card"
MAX_CITED_PAGES = 4


@dataclass(frozen=True)
class IndexedSnapshot:
    snapshot_id: str
    taken_on: str
    facts: tuple[RateFact, ...]
    facts_on_every_page: tuple[RateFact, ...]
    passages: PassageIndex


class KnowledgeSystem:
    def __init__(self) -> None:
        self._snapshots: list[IndexedSnapshot] = []

    def ingest(self, snapshot: Snapshot) -> None:
        facts: list[RateFact] = []
        facts_on_every_page: list[RateFact] = []
        for page in snapshot.pages:
            facts.extend(extract_rate_facts(page.url, page.markdown))
            if not page_path(page.url).startswith(EXCLUDED_PAGE_PREFIXES):
                facts_on_every_page.extend(extract_table_facts(page.url, page.markdown))
        passages = PassageIndex(snapshot.pages, snapshot.taken_on)
        self._snapshots.append(
            IndexedSnapshot(snapshot.snapshot_id, snapshot.taken_on, tuple(facts), tuple(facts_on_every_page), passages)
        )

    def answer(self, question: str, as_of: Optional[str] = None) -> Answer:
        snapshot = self._snapshot_for(as_of)
        if snapshot is None:
            return refusal()
        parsed = parse_rate_question(question)
        if parsed is None:
            return _answer_from_search(question, snapshot)
        selected = select_facts(parsed, snapshot.facts)
        if not selected:
            return refusal()
        return Answer(
            text=render_answer(parsed, selected),
            sources=cite(selected, snapshot),
        )

    def conflicts(self) -> list[Conflict]:
        if not self._snapshots:
            return []
        latest = self._snapshots[-1]
        found = rate_conflicts(latest.facts_on_every_page, latest.snapshot_id)
        statements_that_disagree = (
            branch_count_conflict(latest.passages, latest.snapshot_id),
            foundation_founding_conflict(latest.passages, latest.snapshot_id),
        )
        return found + [conflict for conflict in statements_that_disagree if conflict]

    def _snapshot_for(self, as_of: Optional[str]) -> Optional[IndexedSnapshot]:
        eligible = [s for s in self._snapshots if as_of is None or s.taken_on <= as_of]
        return eligible[-1] if eligible else None


def refusal() -> Answer:
    return Answer(text=REFUSAL_TEXT, confident=False)


def _answer_from_search(question: str, snapshot: IndexedSnapshot) -> Answer:
    if asks_about_a_fee(question):
        found = snapshot.passages.fee_for(question)
    elif not search_may_answer(question):
        return refusal()
    elif asks_for_a_link(question):
        found = _link_answer(question, snapshot)
    else:
        found = snapshot.passages.search(question)
    if found is None:
        return refusal()
    sources = [Source(url=url, snapshot_id=snapshot.snapshot_id, quote=found.quote) for url in found.urls]
    return Answer(text=found.text, sources=sources, conflict_note=found.conflict_note)


def _link_answer(question: str, snapshot: IndexedSnapshot) -> Optional[Found]:
    family = family_of_rates_asked_about(question)
    business = bool(BUSINESS_ASKED.search(question))
    product_pages = Counter(
        f.url.split("#")[0]
        for f in snapshot.facts
        if f.family == family and not f.from_rate_sheet and f.business == business
    )
    if not product_pages:
        return snapshot.passages.link_for(question)
    def named_for_the_family(url: str) -> bool:
        return classify_family(page_path(url).replace("-", " ").replace("/", " ")) == family

    page = max(product_pages, key=lambda url: (product_pages[url], named_for_the_family(url)))
    return Found(page, (page,), page)


def select_facts(question: RateQuestion, facts: tuple[RateFact, ...]) -> list[RateFact]:
    candidates = _authoritative_for_family(question, facts)
    candidates = [f for f in candidates if _qualifiers_fit(question, f)]
    naming_a_product = any(question.words & f.words for f in candidates)
    if question.family != FAMILY_SPANNING_PERSONAL_AND_BUSINESS or naming_a_product or question.business:
        candidates = [f for f in candidates if f.business == question.business]
    candidates = _best_word_matches(question, candidates)
    candidates = _having_every_asked_variant(question, candidates)
    candidates = _narrowest_amount_tier(question, candidates)
    candidates = _without_unasked_variants(question, candidates)
    candidates = _extreme_only(question, candidates)
    return sorted(_unique_by_name_and_values(candidates), key=lambda fact: fact.business)


def _authoritative_for_family(question: RateQuestion, facts: tuple[RateFact, ...]) -> list[RateFact]:
    family_facts = [f for f in facts if f.family == question.family]
    sheet_scopes = {f.business for f in family_facts if f.from_rate_sheet}
    newest_product_rows = _newest_dated_product_rows(family_facts)
    authoritative = []
    for fact in family_facts:
        if fact.from_rate_sheet:
            authoritative.append(_newer_row_if_it_disagrees(fact, newest_product_rows))
        elif fact.business not in sheet_scopes:
            authoritative.append(fact)
    return authoritative


def _same_row_key(fact: RateFact) -> tuple[bool, str]:
    return fact.business, fact.label.replace(",", "")


def _newest_dated_product_rows(facts: list[RateFact]) -> dict[tuple[bool, str], RateFact]:
    newest: dict[tuple[bool, str], RateFact] = {}
    for fact in facts:
        if fact.from_rate_sheet or fact.effective is None:
            continue
        current = newest.get(_same_row_key(fact))
        if current is None or fact.effective > current.effective:
            newest[_same_row_key(fact)] = fact
    return newest


def _newer_row_if_it_disagrees(sheet_row: RateFact, newest_product_rows: dict[tuple[bool, str], RateFact]) -> RateFact:
    product_row = newest_product_rows.get(_same_row_key(sheet_row))
    if product_row is None or sheet_row.effective is None:
        return sheet_row
    if product_row.effective > sheet_row.effective and product_row.values != sheet_row.values:
        return product_row
    return sheet_row


def _qualifiers_fit(question: RateQuestion, fact: RateFact) -> bool:
    if question.term_months is not None and fact.term_months != question.term_months:
        return False
    if question.model_year is not None and fact.model_years is not None:
        first, last = fact.model_years
        if not first <= question.model_year <= last:
            return False
    if question.amount is not None and fact.amount_range is not None:
        low, high = fact.amount_range
        if not low <= question.amount <= high:
            return False
    return True


def _best_word_matches(question: RateQuestion, facts: list[RateFact]) -> list[RateFact]:
    if not facts:
        return facts
    words_on_any_row = frozenset().union(*(f.words for f in facts))
    if not question.product_words <= words_on_any_row:
        return []
    best = max(len(question.words & f.words) for f in facts)
    return [f for f in facts if len(question.words & f.words) == best]


def _having_every_asked_variant(question: RateQuestion, facts: list[RateFact]) -> list[RateFact]:
    asked = EXCLUDED_UNLESS_ASKED & question.words
    return [f for f in facts if asked <= f.words]


def _narrowest_amount_tier(question: RateQuestion, facts: list[RateFact]) -> list[RateFact]:
    if question.amount is None:
        return facts
    narrowest: dict[tuple, tuple[float, float]] = {}
    for fact in facts:
        if fact.amount_range is not None:
            tier_group = (fact.heading, fact.term_months)
            narrowest[tier_group] = min(narrowest.get(tier_group, _tier_width(fact)), _tier_width(fact))
    return [f for f in facts if f.amount_range is None or _tier_width(f) == narrowest[(f.heading, f.term_months)]]


def _tier_width(fact: RateFact) -> tuple[float, float]:
    low, high = fact.amount_range
    return high, -low


def _without_unasked_variants(question: RateQuestion, facts: list[RateFact]) -> list[RateFact]:
    unasked = EXCLUDED_UNLESS_ASKED - question.words
    jumbo_can_apply = question.amount is not None or question.wants_highest or question.wants_lowest
    if jumbo_can_apply:
        unasked -= {JUMBO}
    if question.family == FAMILY_OF_CASH_OUT_ROWS:
        unasked -= {CASH}
    remaining =[f for f in facts if not (unasked & f.words)]
    return remaining or facts


def _extreme_only(question: RateQuestion, facts: list[RateFact]) -> list[RateFact]:
    if not facts or not (question.wants_highest or question.wants_lowest):
        return facts
    chooser = max if question.wants_highest else min
    target = chooser(_headline_number(f) for f in facts)
    return [f for f in facts if _headline_number(f) == target]


def _headline_number(fact: RateFact) -> float:
    value = fact.values.get("apy") or fact.values.get("apr") or fact.values.get("rate") or fact.values.get("dividend")
    return float(value.split("%")[0])


def _unique_by_name_and_values(facts: list[RateFact]) -> list[RateFact]:
    seen: dict[tuple[str, tuple], RateFact] = {}
    for fact in facts:
        seen.setdefault((fact.name, tuple(sorted(fact.values.items()))), fact)
    return list(seen.values())


def render_answer(question: RateQuestion, facts: list[RateFact]) -> str:
    return _yes_or_no_lead(question, facts) + _render_list(question, facts)


def _render_list(question: RateQuestion, facts: list[RateFact]) -> str:
    return "; ".join(f"{fact.name}: {_render_values(question, fact)}" for fact in facts) + "."


def _yes_or_no_lead(question: RateQuestion, facts: list[RateFact]) -> str:
    if question.percent_asked_about is None:
        return ""
    paying_it = [f for f in facts if _pays_exactly(f, question.percent_asked_about)]
    if not paying_it:
        return "No. Listed rates: "
    return f"Yes: {_render_list(question, paying_it)} All listed rates: "


def _pays_exactly(fact: RateFact, percent: float) -> bool:
    return any(value.endswith("%") and "–" not in value and float(value[:-1]) == percent for value in fact.values.values())


def _render_values(question: RateQuestion, fact: RateFact) -> str:
    values = fact.values
    if "promo_apy" in values and "apy" in values:
        return f"{values['promo_apy']} APY for the promotional period, then {values['apy']} APY"
    if "rate" in values and "apr" in values:
        return f"{values['rate']} rate, {values['apr']} APR"
    if question.wants_dividend and "dividend" in values and "apy" in values:
        return f"{values['dividend']} dividend rate, {values['apy']} APY"
    if "apy" in values:
        return f"{values['apy']} APY"
    if "apr" in values:
        return f"{values['apr']} APR"
    return next(iter(values.values()))


def cite(selected: list[RateFact], snapshot: IndexedSnapshot) -> list[Source]:
    cited: dict[str, Source] = {}
    for fact in selected:
        cited.setdefault(fact.url, Source(url=fact.url, snapshot_id=snapshot.snapshot_id, quote=fact.row))
    selected_values = {(f.family, tuple(sorted(f.values.items()))) for f in selected}
    for other in snapshot.facts:
        if len(cited) >= MAX_CITED_PAGES:
            break
        if other.business and not any(f.business for f in selected):
            continue
        if (other.family, tuple(sorted(other.values.items()))) in selected_values:
            cited.setdefault(other.url, Source(url=other.url, snapshot_id=snapshot.snapshot_id, quote=other.row))
    return list(cited.values())
