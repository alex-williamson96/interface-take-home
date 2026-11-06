from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from rate_facts import page_path
from site_profile import SITE
from text_basics import Found, search_terms, words_in

if TYPE_CHECKING:
    from passages import PassageIndex

FEE_SCHEDULE_PATH = re.compile(SITE.fee_schedule_path_pattern)
FEE_AMOUNT = re.compile(r"\$\d|\d%|\bfree\b", re.I)
FEE_ROW_WRITTEN_AS_A_LINE = re.compile(r"^(?P<label>[A-Z][^$|]*?):?\s+(?P<amount>(?:\$\d|Free\b|\d+% of)[^|]*)$")
A_SENTENCE_NOT_AN_AMOUNT = re.compile(r"\.(?:\s|$)")
FEE_WORD = re.compile(r"\bfees?\b", re.I)
FEE_SECTION_HEADING = re.compile(r"(?:Services|Charges|Fees)(?: Consumer| Business)?$")
FOOTNOTE_AFTER_THE_AMOUNT = re.compile(r"\s+\*.*$")
DATE_WORDS_IN_A_FEE_QUESTION = re.compile(r"\b(?:in|on|as of)?\s*[A-Z][a-z]+\.? (?:\d{1,2},? )?20\d\d\b")
FEE_ROWS_IN_AN_ANSWER = 4
WORDS_THAT_ASK_FOR_A_FEE = frozenset(words_in("fee cost charge charged price penalty amount"))
WORDS_NAMING_A_CARD = frozenset(words_in("platinum rewards visa credit card business"))
BUSINESS = next(iter(words_in("business")))


@dataclass(frozen=True)
class FeeRow:
    label: str
    amount: str
    words: frozenset[str]
    url: str


def _fee_label_and_amount(line: str) -> Optional[tuple[str, str]]:
    if line.startswith("|"):
        cells = [html.unescape(html.unescape(cell)).strip() for cell in line.strip().strip("|").split("|")]
        return (cells[0], cells[1]) if len(cells) >= 2 and FEE_AMOUNT.search(cells[1]) else None
    written_out = FEE_ROW_WRITTEN_AS_A_LINE.match(line.replace("\\", "").replace("_", "").strip())
    if not written_out or A_SENTENCE_NOT_AN_AMOUNT.search(written_out.group("amount")):
        return None
    return written_out.group("label"), written_out.group("amount")


def _fee_section_heading(line: str) -> Optional[str]:
    heading = line.strip().strip("|").split("|")[0].replace("*", "").strip()
    return heading if FEE_SECTION_HEADING.search(heading) else None


def fee_rows_in(markdown: str, url: str) -> list[FeeRow]:
    rows = []
    in_a_business_section = False
    for line in markdown.splitlines():
        found = _fee_label_and_amount(line)
        heading = None if found else _fee_section_heading(line)
        if heading:
            in_a_business_section = heading.endswith("Business")
        if found:
            label, amount = found
            if in_a_business_section and BUSINESS not in words_in(label):
                label = f"Business: {label}"
            rows.append(FeeRow(label, FOOTNOTE_AFTER_THE_AMOUNT.sub("", amount), frozenset(words_in(label)), url))
    return rows


def keep_the_cleanest_label(rows: dict[str, FeeRow], row: FeeRow) -> None:
    same_letters = "".join(sorted(re.sub(r"\W", "", row.label.lower())))
    kept = rows.get(same_letters)
    if kept is None or len(row.label) < len(kept.label):
        rows[same_letters] = row


def _fee_terms(question: str) -> set[str]:
    return search_terms(DATE_WORDS_IN_A_FEE_QUESTION.sub(" ", question)) - WORDS_THAT_ASK_FOR_A_FEE


def fee_for(index: PassageIndex, question: str) -> Optional[Found]:
    return fee_on_the_schedule(index, question) or _card_fee_in_page_text(index, _fee_terms(question))


def fee_on_the_schedule(index: PassageIndex, question: str) -> Optional[Found]:
    terms = _fee_terms(question)
    stating = [row for row in index.fee_rows.values() if terms and terms <= row.words]
    if BUSINESS not in terms and any(BUSINESS not in row.words for row in stating):
        stating = [row for row in stating if BUSINESS not in row.words]
    if not stating:
        return None
    chosen = stating[:FEE_ROWS_IN_AN_ANSWER]
    listed = "; ".join(f"{row.label}: {row.amount}" for row in chosen)
    return Found(f"{listed}.", (chosen[0].url,), listed)


def _card_fee_in_page_text(index: PassageIndex, terms: set[str]) -> Optional[Found]:
    asked = terms - WORDS_NAMING_A_CARD
    if not asked:
        return None
    for passage in index.passages:
        if SITE.card_page_path_part not in page_path(passage.url) or not asked <= passage.words:
            continue
        for clause in re.split(r"(?<=[.;])\s+", passage.text):
            if FEE_WORD.search(clause) and asked <= set(words_in(clause)):
                return Found(clause.rstrip(";") + ("" if clause.endswith(".") else "."), (passage.url,), passage.text)
    return None
