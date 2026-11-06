from __future__ import annotations

import re
from collections import Counter
from dataclasses import replace
from typing import Optional

from asked import COUNTED_THING, DATE_ASKED, DATE_OR_YEAR, QuestionKind
from kind_contact import PHONE_NUMBER, ROUTING, STREET_ADDRESS
from kind_count import COUNT
from kind_date import (
    CLOSED_ASKED,
    DATE,
    FOUNDING_ASKED,
    STILL_OPEN_ASKED,
    date_from_the_article,
    founding_year_statements,
    has_passed,
)
from kind_hours import HOURS
from kind_open import OPEN_ENDED
from page_answers import CLOSING_STATED
from passages import LOWEST_COVERAGE_TO_ANSWER, PassageIndex
from site_profile import SITE, SITE_NAME_IN_LOWERCASE
from text_basics import WORDS_ANY_BRANCH_SHARES, Found, Passage, names_in, search_terms, words_in

ELIGIBILITY_ASKED = re.compile(rf"^\s*who (?:can|may|could) (?:join|become a (?:{SITE_NAME_IN_LOWERCASE} )?member)\b", re.I)
WHO_IS_ELIGIBLE = f"Who is eligible to become a {SITE.name} member?"
ORIGIN_ASKED = re.compile(
    rf"^\s*(?:when|what year)\b.*\b(?:did|was)\s+(?:{SITE_NAME_IN_LOWERCASE}|the credit union)\s+(?:get\s+)?"
    r"(?:start|started|begin|open|opened)\s*\??\s*$"
    rf"|^\s*how (?:old is|long has|many years has)\s+{SITE_NAME_IN_LOWERCASE}\b",
    re.I,
)
WHEN_THE_SITE_WAS_FOUNDED = f"When was {SITE.name} founded?"
WHEN_IT_CLOSES_ASKED = re.compile(r"^\s*when\s+(?:will|does|do|did|is|are)\s+(.+?)\s+clos(?:e|ing)\s*\??\s*$", re.I)
LAST_DAY_ASKED = re.compile(r"\blast day (?:for|of|at)\s+(.+?)\s*\??\s*$", re.I)
A_BRANCH_ASKED_ABOUT = re.compile(r"\b(?:branch(?:es)?|locations?)\b", re.I)
SHUT_DOWN = re.compile(r"\bshut(?:ting|s)?(?: down)?\b", re.I)
FULL_SERVICE = re.compile(r"\bfull[- ]service\b", re.I)
NO_IF_CLOSED = ("No.", "Yes, for now.")
YES_IF_CLOSED = ("Yes.", "Not yet.")
PASSAGES_TO_CHOOSE_FROM = 20
KEEP_LOOKING = Found("", (), "")

KINDS_ANSWERED_AS_WORDED = (HOURS, PHONE_NUMBER, COUNT, ROUTING, STREET_ADDRESS, DATE, OPEN_ENDED)


def _answer_as_worded(question: str, index: PassageIndex) -> Optional[Found]:
    return next(kind.answer(question, index) for kind in KINDS_ANSWERED_AS_WORDED if kind.asks(question))


def _when_will_it_close(place: str) -> str:
    return f"When will {place} close?"


def _origin(question: str, index: PassageIndex) -> Optional[Found]:
    return _answer_as_worded(WHEN_THE_SITE_WAS_FOUNDED, index)


def _eligibility(question: str, index: PassageIndex) -> Optional[Found]:
    return _answer_as_worded(WHO_IS_ELIGIBLE, index) or _answer_as_worded(question, index)


def _closes_with_no_place_named(question: str) -> bool:
    closes = WHEN_IT_CLOSES_ASKED.search(question)
    return bool(closes) and not search_terms(closes.group(1))


def _last_day(question: str, index: PassageIndex) -> Optional[Found]:
    place = LAST_DAY_ASKED.search(question).group(1)
    if names_in(_when_will_it_close(place)):
        return _answer_as_worded(_when_will_it_close(place), index)
    return KEEP_LOOKING


def _has_it_closed(place: str, leads: tuple[str, str], index: PassageIndex) -> Optional[Found]:
    found = _answer_as_worded(_when_will_it_close(place), index)
    if not found or not CLOSING_STATED.search(found.text) or not DATE_OR_YEAR.search(found.text):
        return None
    lead = leads[0] if has_passed(index, found.text) else leads[1]
    return replace(found, text=f"{lead} {found.text}")


def _which_branch(index: PassageIndex) -> Found:
    locator = index.locator_url()
    return Found("That depends on the branch; which branch do you need?", (locator,) if locator else (), "")


def _still_open_or_closed(question: str, index: PassageIndex) -> Optional[Found]:
    still_open = STILL_OPEN_ASKED.search(question)
    closed = CLOSED_ASKED.search(question)
    place = next(group for group in (still_open or closed).groups() if group)
    leads = YES_IF_CLOSED if closed else NO_IF_CLOSED
    if names_in(_when_will_it_close(place)):
        return _has_it_closed(place, leads, index)
    beyond_any_branch = search_terms(place) - WORDS_ANY_BRANCH_SHARES
    if A_BRANCH_ASKED_ABOUT.search(place) and beyond_any_branch:
        return _has_it_closed(place.title(), leads, index)
    if search_terms(place) and not beyond_any_branch:
        return _which_branch(index)
    if not search_terms(place):
        return None
    return KEEP_LOOKING


def _disagreement_about_founding(index: PassageIndex, names: set[str]) -> Optional[str]:
    years = {year for year, _ in founding_year_statements(index, names)}
    if len(years) < 2:
        return None
    return f"The site gives more than one year for this: {', '.join(sorted(years))}. This answer uses the best matching page."


def _founding_date(question: str, index: PassageIndex) -> Optional[Found]:
    names = names_in(question)
    if not names:
        return _answer_as_worded(FOUNDING_ASKED.sub("founded", question), index)
    found = (
        _answer_as_worded(question, index)
        or _answer_as_worded(FOUNDING_ASKED.sub("established", question), index)
        or _answer_as_worded(FOUNDING_ASKED.sub("founded", question), index)
    )
    return found and replace(found, conflict_note=_disagreement_about_founding(index, names))


KINDS_THAT_RESTATE_THE_QUESTION = (
    QuestionKind("when the site began", lambda question: bool(ORIGIN_ASKED.search(question)), _origin),
    QuestionKind("who is eligible", lambda question: bool(ELIGIBILITY_ASKED.search(question)), _eligibility),
    QuestionKind("closing, with no place named", _closes_with_no_place_named, lambda question, index: None),
    QuestionKind("last day of a place", lambda question: bool(LAST_DAY_ASKED.search(question)), _last_day),
    QuestionKind(
        "still open or closed",
        lambda question: bool(STILL_OPEN_ASKED.search(question) or CLOSED_ASKED.search(question)),
        _still_open_or_closed,
    ),
    QuestionKind(
        "founding date",
        lambda question: bool(DATE_ASKED.search(question) and FOUNDING_ASKED.search(question)),
        _founding_date,
    ),
)
KINDS_WITH_THEIR_OWN_RULE = (
    *KINDS_THAT_RESTATE_THE_QUESTION,
    QuestionKind(
        "closing date",
        lambda question: bool(WHEN_IT_CLOSES_ASKED.search(question)),
        lambda question, index: None,
    ),
    *(kind for kind in KINDS_ANSWERED_AS_WORDED if kind is not OPEN_ENDED),
)


def search(index: PassageIndex, question: str) -> Optional[Found]:
    question = SHUT_DOWN.sub("close", question)
    return _by_kind_of_question(question, index) or date_from_the_article(question, index)


def _by_kind_of_question(question: str, index: PassageIndex) -> Optional[Found]:
    if COUNTED_THING.search(question):
        question = FULL_SERVICE.sub(" ", question)
    for kind in KINDS_THAT_RESTATE_THE_QUESTION:
        if kind.asks(question):
            found = kind.answer(question, index)
            if found is not KEEP_LOOKING:
                return found
    return _answer_as_worded(question, index)


def candidates_for_an_open_question(index: PassageIndex, question: str) -> list[Passage]:
    question = SHUT_DOWN.sub("close", question)
    if any(kind.asks(question) for kind in KINDS_WITH_THEIR_OWN_RULE):
        return []
    return index.best_matches_at_any_coverage(search_terms(question), PASSAGES_TO_CHOOSE_FROM)


def link_for(index: PassageIndex, question: str) -> Optional[Found]:
    terms = search_terms(question)
    votes: Counter = Counter()
    labels: dict[str, str] = {}
    for label, target in index.links:
        label_words = set(words_in(label)) | set(words_in(target.replace("-", " ").replace("/", " ")))
        if terms and len(terms & label_words) / len(terms) >= LOWEST_COVERAGE_TO_ANSWER:
            page = target.split("#")[0]
            votes[page] += 1
            labels.setdefault(page, label)
    if not votes:
        return None
    page = votes.most_common(1)[0][0]
    return Found(page, (page,), labels[page])
