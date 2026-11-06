from __future__ import annotations

import re
from typing import Optional

from asked import DATE_OR_YEAR, WORDS_A_SHAPE_ALREADY_SATISFIES, WORDS_THAT_ONLY_ASK_WHEN
from passages import MONTH_NUMBERS
from rate_facts import stem
from site_profile import SITE, SITE_NAME_IN_LOWERCASE
from text_basics import (
    WORDS_ANY_BRANCH_SHARES,
    WORDS_IN_THE_SITES_OWN_NAME,
    Found,
    Passage,
    search_terms,
    words_in,
)

SENTENCE_END = re.compile(r"(?<=[.!?])(?<![\s.][A-Z]\.)\s+(?=[A-Z\"“])")
SENTENCES_IN_AN_ANSWER = 3
FEWEST_SENTENCES_THAT_DEFINE_SOMETHING = 2
LOWEST_SHARE_OF_BEST_SENTENCE_KEPT = 0.5
DEFINITION_ASKED = re.compile(r"^\s*what(?:'s| is| are)\b", re.I)
CHARTER_AREA = re.compile(r"\bcharter area\b", re.I)
STATES_SERVED = re.compile(r".*".join(rf"\b{state}\b" for state in SITE.states_served))
CLAUSE_BREAK = re.compile(r",\s+(?!\d)")
FULL_DATE = re.compile(rf"\b({'|'.join(MONTH_NUMBERS)})[a-z]*\.? (\d{{1,2}}), (20\d\d)\b")
MONTH_AND_YEAR = re.compile(rf"\b({'|'.join(MONTH_NUMBERS)})[a-z]*\.? (20\d\d)\b")
EARLY_IN_A_YEAR = re.compile(r"\bearly (20\d\d)\b")
LAST_DAY_OF_ANY_MONTH = 31
END_OF_EARLY_IN_A_YEAR = "03-31"
BARE_YEAR = re.compile(r"\b(?:19|20)\d\d\b")
LOWERCASE_WORD = re.compile(r"\b[a-z]{2,}")
RATE_SHEET_FOOTER = re.compile(r"\brates are effective as of\b", re.I)
REFERS_BACK_TO_THE_SUBJECT = re.compile(
    r"^\W*(?:this|it|its|founded|established|the (?:branch|location|acquisition|credit union|office|building)\b)\b", re.I
)
CLOSING_STATED = re.compile(r"\bclos(?:e|es|ed|ing|ure)\b|\blast day\b", re.I)
CLOSE = words_in("close")[0]


def latest_date_in(sentence: str) -> tuple[str, str]:
    full_dates = [
        (f"{found.group(3)}-{MONTH_NUMBERS[found.group(1)]:02d}-{int(found.group(2)):02d}", found.group(0))
        for found in FULL_DATE.finditer(sentence)
    ]
    if full_dates:
        return max(full_dates)
    months = [
        (f"{found.group(2)}-{MONTH_NUMBERS[found.group(1)]:02d}-{LAST_DAY_OF_ANY_MONTH}", found.group(0))
        for found in MONTH_AND_YEAR.finditer(sentence)
    ]
    if months:
        return max(months)
    early = [(f"{found.group(1)}-{END_OF_EARLY_IN_A_YEAR}", found.group(0)) for found in EARLY_IN_A_YEAR.finditer(sentence)]
    if early:
        return max(early)
    year = max(BARE_YEAR.findall(sentence))
    return f"{year}-12-31", year


def asked_beyond_the_name(question: str, names: set[str]) -> set[str]:
    return (
        search_terms(question)
        - names
        - WORDS_A_SHAPE_ALREADY_SATISFIES
        - WORDS_ANY_BRANCH_SHARES
        - WORDS_IN_THE_SITES_OWN_NAME
        - WORDS_THAT_ONLY_ASK_WHEN
    )


def mentions(sentence: str, asked: set[str]) -> bool:
    if not asked:
        return True
    matched = asked & set(words_in(sentence))
    if CLOSE in asked and CLOSING_STATED.search(sentence):
        matched = matched | {CLOSE}
    return 2 * len(matched) >= len(asked)


def through_the_date(sentence: str) -> str:
    end_of_date = [found.end() for found in DATE_OR_YEAR.finditer(sentence)][-1]
    clause_break = CLAUSE_BREAK.search(sentence, end_of_date)
    return sentence[: clause_break.start()] + "." if clause_break else sentence


def can_state_a_date(sentence: str) -> bool:
    return (
        bool(DATE_OR_YEAR.search(sentence))
        and bool(LOWERCASE_WORD.search(sentence))
        and not RATE_SHEET_FOOTER.search(sentence)
        and not sentence.endswith(("?", ":"))
    )


def _states_it_about_the_name(sentence: str, asked: set[str], names: set[str]) -> bool:
    about_the_name = names <= set(words_in(sentence)) or bool(REFERS_BACK_TO_THE_SUBJECT.search(sentence))
    return about_the_name and mentions(through_the_date(sentence), asked)


def _belongs_beside_the_best_passage(sentence: str, names: set[str], shape: Optional[re.Pattern]) -> bool:
    if names:
        return names <= set(words_in(sentence))
    return shape is None


def _sentence_stating_the_date(question: str, sentences: list[str], names: set[str]) -> str:
    terms = search_terms(question)
    asked = asked_beyond_the_name(question, names)

    def strength(sentence: str) -> tuple[bool, int, int, bool]:
        words = set(words_in(through_the_date(sentence)))
        mentions_it = _states_it_about_the_name(sentence, asked, names)
        return mentions_it, len(asked & words), len(terms & words), bool(FULL_DATE.search(sentence))

    return max(sentences, key=strength)


def answer_from_page(
    question: str, best: Passage, page: list[Passage], names: set[str], shape: Optional[re.Pattern]
) -> Optional[Found]:
    terms = search_terms(question) | {stem(SITE_NAME_IN_LOWERCASE)}
    passage_of: dict[str, Passage] = {}
    for passage in page:
        for sentence in SENTENCE_END.split(passage.display):
            shape_fits = can_state_a_date(sentence) if shape is DATE_OR_YEAR else shape is None or shape.search(sentence)
            belongs = passage is best or _belongs_beside_the_best_passage(sentence, names, shape)
            if shape_fits and belongs and not sentence.endswith("?"):
                passage_of.setdefault(sentence, passage)
    overlap = {sentence: len(terms & set(words_in(sentence))) for sentence in passage_of}
    best_overlap = max(overlap.values(), default=0)
    if best_overlap == 0:
        return None
    if shape is DATE_OR_YEAR:
        sentence = _sentence_stating_the_date(question, list(passage_of), names)
        if not _states_it_about_the_name(sentence, asked_beyond_the_name(question, names), names):
            return None
        return Found(through_the_date(sentence), (best.url,), passage_of[sentence].text)
    worth_keeping = [s for s in passage_of if overlap[s] >= best_overlap * LOWEST_SHARE_OF_BEST_SENTENCE_KEPT]
    kept = set(sorted(worth_keeping, key=lambda s: overlap[s], reverse=True)[:SENTENCES_IN_AN_ANSWER])
    answer = [s for s in passage_of if s in kept]
    from_best = [s for s in passage_of if passage_of[s] is best][:SENTENCES_IN_AN_ANSWER]
    if shape is None and DEFINITION_ASKED.search(question) and len(from_best) >= FEWEST_SENTENCES_THAT_DEFINE_SOMETHING:
        answer = from_best
    if CHARTER_AREA.search(" ".join(answer)):
        answer += [s for s in passage_of if STATES_SERVED.search(s) and s not in answer][:1]
    quoted = dict.fromkeys(passage_of[s].text for s in answer)
    return Found(" ".join(answer), (best.url,), " ".join(quoted))
