from __future__ import annotations

import re
from collections import Counter
from typing import Optional

from asked import COUNTED_THING, QuestionKind, what_is_asked
from page_answers import SENTENCE_END, mentions
from passages import TRUST_OF_SITE_PAGE, PassageIndex
from site_profile import SITE, SITE_NAME_IN_LOWERCASE
from text_basics import Found, Passage, names_in, search_terms, words_in

BRANCH_COUNT = re.compile(r"(?<![\d,])\b(\d{1,3}) (?:\w+ )?branch(?:es)?\b", re.I)
STATED_ABOUT_THE_SITE = re.compile(rf"\b{SITE_NAME_IN_LOWERCASE}\b|\bit has\b|\bour\b|\b{SITE.founding_statement}\b", re.I)
FEWEST_PAGES_FOR_A_REPEATED_COUNT = 2
FEWEST_WORDS_THAT_NARROW_A_COUNT = 2


def _most_stated_count(question: str, index: PassageIndex) -> Optional[Found]:
    asked = what_is_asked(question, index)
    if not asked.ranked:
        return None
    terms = search_terms(question) - set(words_in(COUNTED_THING.search(question).group(1)))
    names = names_in(question)
    statements = [
        (sentence, asked.shape.search(sentence).group(0).lower(), passage)
        for _, passage in asked.ranked
        for sentence in SENTENCE_END.split(passage.text)
        if asked.shape.search(sentence)
        and STATED_ABOUT_THE_SITE.search(sentence)
        and names <= set(words_in(sentence))
        and (len(terms) < FEWEST_WORDS_THAT_NARROW_A_COUNT or mentions(sentence, terms))
    ]
    if not statements:
        return None
    pages_stating: Counter = Counter()
    for _, count, passage in statements:
        pages_stating[count] += index.pages_repeating[passage.text]

    def strength(statement: tuple[str, str, Passage]) -> tuple[int, bool, str]:
        sentence, count, passage = statement
        repeated = pages_stating[count] >= FEWEST_PAGES_FOR_A_REPEATED_COUNT
        return len(terms & set(words_in(sentence))), repeated, passage.published if passage.has_its_own_date else ""

    sentence, _, passage = max(statements, key=strength)
    return Found(sentence, (passage.url,), passage.text)


def branch_count_statements(index: PassageIndex) -> tuple[Optional[tuple[str, Passage]], list[tuple[str, Passage]]]:
    statements = [(found.group(1), p) for p in index.passages if (found := BRANCH_COUNT.search(p.text))]
    dated = [statement for statement in statements if statement[1].has_its_own_date]
    newest = max(dated, key=lambda statement: statement[1].published, default=None)
    undated_site_pages = [
        statement for statement in statements if not statement[1].has_its_own_date and statement[1].trust == TRUST_OF_SITE_PAGE
    ]
    newest_first = sorted(dated, key=lambda statement: statement[1].published, reverse=True)
    return newest, undated_site_pages + newest_first


COUNT = QuestionKind("count", lambda question: bool(COUNTED_THING.search(question)), _most_stated_count)
