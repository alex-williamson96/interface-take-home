from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import replace
from typing import Optional

from asked import DATE_OR_YEAR, QuestionKind, newest_among_the_tied, shape_asked_for, what_is_asked
from kind_hours import title_of
from page_answers import (
    SENTENCE_END,
    answer_from_page,
    asked_beyond_the_name,
    can_state_a_date,
    latest_date_in,
    mentions,
    through_the_date,
)
from passages import TRUST_OF_LEAST_TRUSTED, PassageIndex
from text_basics import Found, Passage, names_in, words_in

MONTH_NAMES = "January February March April May June July August September October November December".split()
FOUNDING_ASKED = re.compile(r"\b(?:founded|established)\b", re.I)
FOUNDING_YEAR = re.compile(r"\b(?:founded|founding|established)\b\D{0,10}((?:19|20)\d\d)\b", re.I)
A_BRANCH_ASKED_ABOUT = re.compile(r"\b(?:branch(?:es)?|locations?)\b", re.I)
FIRST_OR_LAST_OF_A_KIND = re.compile(r"\b(?:first|last|oldest|newest|original)\s+[a-z]+", re.I)
STILL_AHEAD_ASKED = re.compile(r"\bwill\b|\bgoing to\b|\b(?:does|do|is|are)\b", re.I)
ASKED_IN_THE_PAST = re.compile(r"\b(?:did|was|were)\b", re.I)
AHEAD_NOT_NOW_ASKED = re.compile(r"\bwill\b|\bgoing to\b", re.I)
WRITTEN_AS_STILL_AHEAD = re.compile(r"\b(?:will|plans?|planned|expected|scheduled)\b", re.I)
STILL_OPEN_ASKED = re.compile(
    r"^\s*(?:is|are)\s+(.+?)\s+(?:still open\b|open(?: anymore| any more| yet)?\s*\??\s*$)"
    r"|\bif\s+(.+?)\s+(?:is|are)\s+still open\b",
    re.I,
)
CLOSED_ASKED = re.compile(r"^\s*(?:is|are|has|have|did)\s+(.+?)\s+(?:closed|closing|close)\s*\??\s*$", re.I)
FEWEST_ASKED_WORDS_WITHOUT_A_NAME = 2
SCHEDULES_IN_AN_ANSWER = 4


def has_passed(index: PassageIndex, sentence: str) -> bool:
    return latest_date_in(sentence)[0] < index.taken_on


def _reads_ahead_but_passed(index: PassageIndex, sentence: str) -> bool:
    return bool(WRITTEN_AS_STILL_AHEAD.search(sentence)) and has_passed(index, sentence)


def _written_out(published: str) -> str:
    year, month, day = published.split("-")
    return f"{MONTH_NAMES[int(month) - 1]} {int(day)}, {year}"


def _names_what_it_asks_the_date_of(question: str, names: set[str]) -> bool:
    if names or A_BRANCH_ASKED_ABOUT.search(question) or FOUNDING_ASKED.search(question):
        return True
    return len(asked_beyond_the_name(question, names)) >= FEWEST_ASKED_WORDS_WITHOUT_A_NAME


def _stating_any_first_or_last_asked_about(
    question: str, ranked: list[tuple[float, Passage]]
) -> list[tuple[float, Passage]]:
    asked = [" ".join(words_in(found)) for found in FIRST_OR_LAST_OF_A_KIND.findall(question)]
    return [scored for scored in ranked if all(phrase in " ".join(words_in(scored[1].text)) for phrase in asked)]


def _dated_passages_to_try(best: Passage, terms: set[str], ranked: list[tuple[float, Passage]]) -> list[Passage]:
    on_the_same_page = [passage for _, passage in ranked if passage.url == best.url]
    titled_with_what_was_asked = sorted(
        (passage for _, passage in ranked if terms <= passage.title_words),
        key=lambda passage: passage.published,
        reverse=True,
    )
    return [best, *on_the_same_page, *titled_with_what_was_asked]


def _most_recent_statement(
    question: str, names: set[str], ranked: list[tuple[float, Passage]], index: PassageIndex
) -> Optional[Found]:
    asked = asked_beyond_the_name(question, names)
    statements = [
        (sentence, passage)
        for _, passage in ranked
        for sentence in SENTENCE_END.split(passage.display)
        if can_state_a_date(sentence)
        and mentions(through_the_date(sentence), asked)
        and not _reads_ahead_but_passed(index, sentence)
    ]
    if not statements:
        return None
    sentence, passage = max(statements, key=lambda statement: latest_date_in(statement[0])[0])
    lead = "Most recently: " if has_passed(index, sentence) else ""
    return Found(lead + through_the_date(sentence), (passage.url,), passage.text)


def _date_on_page(question: str, passage: Passage, index: PassageIndex) -> Optional[Found]:
    return answer_from_page(question, passage, index.passages_of[passage.url], set(), DATE_OR_YEAR)


def _date_of_an_unnamed_branch(
    question: str, terms: set[str], ranked: list[tuple[float, Passage]], index: PassageIndex
) -> Optional[Found]:
    stating_it = [
        passage
        for _, passage in ranked
        if terms <= passage.searchable_words and passage.trust > TRUST_OF_LEAST_TRUSTED
    ]
    titled_with_it = [passage for passage in stating_it if terms <= passage.title_words]
    by_page: dict[str, list[Passage]] = defaultdict(list)
    for passage in titled_with_it or stating_it:
        by_page[passage.url].append(passage)
    if not by_page:
        return None
    first_date_on_each_page = (
        next(((page, found) for page in passages if (found := _date_on_page(question, page, index))), None)
        for passages in by_page.values()
    )
    dated = [page_and_date for page_and_date in first_date_on_each_page if page_and_date][:SCHEDULES_IN_AN_ANSWER]
    if not dated:
        return None
    if STILL_AHEAD_ASKED.search(question):
        upcoming = [(page, found) for page, found in dated if not has_passed(index, found.text)]
        if not upcoming:
            earlier = " | ".join(f"{title_of(page)}: {found.text}" for page, found in dated)
            return Found(f"The site shows nothing upcoming. Earlier: {earlier}", tuple(p.url for p, _ in dated), dated[0][0].text)
        dated = upcoming
    if len(dated) > 1:
        titles = " | ".join(title_of(page) for page, _ in dated)
        return Found(f"That depends on the branch; which branch do you need? {titles}", tuple(p.url for p, _ in dated), dated[0][0].text)
    page, found = dated[0]
    return Found(f"{title_of(page)}: {found.text}", found.urls, found.quote)


def _date_stated(question: str, index: PassageIndex) -> Optional[Found]:
    asked = what_is_asked(question, index)
    names, terms, ranked = asked.names, asked.terms, asked.ranked
    if not ranked:
        return None
    if not _names_what_it_asks_the_date_of(question, names):
        return None
    ranked = _stating_any_first_or_last_asked_about(question, ranked)
    if not ranked:
        return None
    if not names and A_BRANCH_ASKED_ABOUT.search(question):
        return _date_of_an_unnamed_branch(question, terms, ranked, index)
    ranked = [scored for scored in ranked if names <= scored[1].words]
    if not ranked:
        return None
    best = newest_among_the_tied(ranked)
    found = next(
        (
            answer
            for passage in _dated_passages_to_try(best, terms, ranked)
            if (answer := answer_from_page(question, passage, index.passages_of[passage.url], names, DATE_OR_YEAR))
        ),
        None,
    )
    if found and ASKED_IN_THE_PAST.search(question):
        if WRITTEN_AS_STILL_AHEAD.search(found.text) and not has_passed(index, found.text):
            return None
    if not found or not STILL_AHEAD_ASKED.search(question):
        return found
    if _reads_ahead_but_passed(index, found.text):
        newer = _most_recent_statement(question, names, ranked, index)
        if newer and latest_date_in(newer.text)[0] > latest_date_in(found.text)[0]:
            return newer
        return replace(found, text=f"{latest_date_in(found.text)[1]} has passed. The site said: {found.text}")
    if has_passed(index, found.text) and not AHEAD_NOT_NOW_ASKED.search(question):
        return _most_recent_statement(question, names, ranked, index) or found
    return found


def date_from_the_article(question: str, index: PassageIndex) -> Optional[Found]:
    names = names_in(question)
    asked = asked_beyond_the_name(question, names)
    whether_it_closed = STILL_OPEN_ASKED.search(question) or CLOSED_ASKED.search(question)
    if not names or not asked or whether_it_closed or shape_asked_for(question) is not DATE_OR_YEAR:
        return None
    if not ASKED_IN_THE_PAST.search(question):
        return None
    statements = [
        (sentence, passage)
        for passage in index.passages
        if passage.has_its_own_date and names <= passage.title_words and asked & passage.title_words
        for sentence in SENTENCE_END.split(passage.text)
        if names <= set(words_in(sentence))
        and asked <= set(words_in(sentence))
        and not WRITTEN_AS_STILL_AHEAD.search(sentence)
        and not sentence.endswith(("?", ":"))
    ]
    if not statements:
        return None
    sentence, passage = max(statements, key=lambda statement: statement[1].published)
    return Found(f"{sentence} (article dated {_written_out(passage.published)})", (passage.url,), passage.text)


def founding_year_statements(index: PassageIndex, names: set[str]) -> list[tuple[str, Passage]]:
    return [
        (year, passage)
        for passage in index.passages
        if names <= passage.words
        for sentence in SENTENCE_END.split(passage.text)
        if names <= set(words_in(sentence))
        for year in FOUNDING_YEAR.findall(sentence)
    ]


DATE = QuestionKind("date", lambda question: shape_asked_for(question) is DATE_OR_YEAR, _date_stated)
