from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional

from passages import PUBLISHED, PassageIndex
from rate_facts import stem
from site_profile import SITE, SITE_NAME_IN_LOWERCASE
from text_basics import Found, Passage, names_in, search_terms, words_in

ROUTING_ASKED = re.compile(r"\brouting\b|\baba\b", re.I)
ADDRESS_ASKED = re.compile(r"\baddress\b", re.I)
ATM_ASKED = re.compile(r"\batms?\b", re.I)
HOW_TO_REACH_ASKED = re.compile(
    rf"\bphone (?:numbers?|for)\b|\b(?:your|{SITE_NAME_IN_LOWERCASE}'s) phone\b|\bcontact information\b"
    rf"|\b(?:who|number)\b.*\b(?:call|talk|speak)\b|\bcall (?:you|{SITE_NAME_IN_LOWERCASE}|someone)\b",
    re.I,
)
DATE_ASKED = re.compile(r"\bwhen\b|\b(?:what|which) (?:date|year)s?\b|\bdeadline\b|\bstill open\b", re.I)
COUNTED_THING = re.compile(r"\b(?i:how many|the number of)\s+(?:[A-Z][a-z]+\s+)*([A-Za-z]+)")
MEMBERSHIP_TOTAL = r"membership (?:totals|has grown to) (?:more than )?\d+(?:,\d{3})*"

DATE_OR_YEAR = re.compile(PUBLISHED.pattern + r"|\b(?:19|20)\d\d\b")
ADDRESS = re.compile(r"\d+ [^,\n]+, [A-Z][A-Za-z ]+, [A-Z]{2},? \d{5}")
ROUTING_NUMBER = re.compile(r"\b\d{9}\b")
PHONE = re.compile(r"\b\d{3}-\d{3}-\d{4}\b")
BRANCH_LISTING = re.compile(rf"\b{re.escape(SITE.name)} Branch\b")

MEMBER = stem("member")
COUNTED_AS_BRANCHES = frozenset(stem(word) for word in ("location", "office"))
WORDS_A_SHAPE_ALREADY_SATISFIES = frozenset(words_in("address phone number year date"))
WORDS_ROUTING_IS_FOUND_BY = frozenset(words_in("routing"))
WORDS_THAT_ONLY_ASK_WHEN = frozenset(words_in("next hold held pass passed happen happened"))
SHARE_OF_TOP_SCORE_CONSIDERED_TIED = 0.9


@dataclass(frozen=True)
class QuestionKind:
    name: str
    asks: Callable[[str], bool]
    answer: Callable[[str, PassageIndex], Optional[Found]]


@dataclass(frozen=True)
class Asked:
    names: set[str]
    shape: Optional[re.Pattern]
    terms: set[str]
    ranked: list[tuple[float, Passage]]


def shape_asked_for(question: str) -> Optional[re.Pattern]:
    if ROUTING_ASKED.search(question):
        return ROUTING_NUMBER
    if ADDRESS_ASKED.search(question):
        return ADDRESS
    if HOW_TO_REACH_ASKED.search(question):
        return PHONE
    if DATE_ASKED.search(question):
        return DATE_OR_YEAR
    counted = COUNTED_THING.search(question)
    if counted:
        counted_word = stem(counted.group(1).lower())
        singular = "branch" if counted_word in COUNTED_AS_BRANCHES else counted_word.removesuffix("e")
        stated_count = rf"\b(?!(?:19|20)\d\d\b)\d+(?:,\d{{3}})*\s+(?:\w+\s+)?{re.escape(singular)}"
        return re.compile(f"{MEMBERSHIP_TOTAL}|{stated_count}" if counted_word == MEMBER else stated_count, re.I)
    return None


def what_is_asked(question: str, index: PassageIndex) -> Asked:
    names = names_in(question)
    shape = shape_asked_for(question)
    terms = search_terms(question) - (WORDS_A_SHAPE_ALREADY_SATISFIES if shape else frozenset())
    if shape is ROUTING_NUMBER:
        terms = WORDS_ROUTING_IS_FOUND_BY
    if shape is DATE_OR_YEAR:
        terms = terms - WORDS_THAT_ONLY_ASK_WHEN
    ranked = index.ranked(terms, names, shape, 1) if shape else index.ranked(terms, names, shape)
    if shape is ADDRESS and not ATM_ASKED.search(question):
        ranked = [scored for scored in ranked if BRANCH_LISTING.search(scored[1].text)]
    return Asked(names, shape, terms, ranked)


def tied_for_the_top(ranked: list[tuple[float, Passage]]) -> list[Passage]:
    top_score = ranked[0][0]
    return [passage for score, passage in ranked if score >= top_score * SHARE_OF_TOP_SCORE_CONSIDERED_TIED]


def newest_among_the_tied(ranked: list[tuple[float, Passage]]) -> Passage:
    return max(tied_for_the_top(ranked), key=lambda passage: passage.published)
