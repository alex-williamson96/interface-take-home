from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from rate_facts import stem
from site_profile import SITE, SITE_NAME_IN_LOWERCASE

QUESTION_WORD = re.compile(r"[a-z0-9$]+(?:'[a-z]+)?")
WORD_ENDING = re.compile(r"(?:ibility|ible|ation|ition|tion|(?<=\w{4})(?:ated|ates|ate)|ized|izes|ize|ing|ed|es|e)$")
SHORTEST_WORD_WITH_ITS_ENDING_REMOVED = 5
WORDS_THAT_MEAN_SOMETHING_ELSE_WITHOUT_THEIR_ENDING = frozenset({SITE.foundation_word, "founded"})
ROOTS_OF_IRREGULAR_WORDS = {
    "closure": "clos",
    "lobbie": "lobby",
    "acquisition": "acquir",
    "completion": "complet",
    "finish": "complet",
    "finished": "complet",
}
CAPITALIZED_AFTER_FIRST_WORD = re.compile(r"(?<=\s)[A-Z][A-Za-z$'-]*")
BECOMING_A_MEMBER = re.compile(rf"\bbecome a(?: {SITE_NAME_IN_LOWERCASE})? member\b|\bmembership\b", re.I)
WORDS_THAT_DO_NOT_SEARCH_TEXT = f"""
    a about all also am an and any are as at be been can could did do does {SITE_NAME_IN_LOWERCASE} {SITE_NAME_IN_LOWERCASE}'s for from get give go going
    had has have how i i'd i'm if in is it its just know like many may me much my need of on or our please provide
    repeat should so some still tell that the their them there these they this to today total us was we were what what's
    when where which who why will with would you your link url website webpage page use see
"""


def _without_ending(word: str) -> str:
    if word in ROOTS_OF_IRREGULAR_WORDS:
        return ROOTS_OF_IRREGULAR_WORDS[word]
    if len(word) < SHORTEST_WORD_WITH_ITS_ENDING_REMOVED or word in WORDS_THAT_MEAN_SOMETHING_ELSE_WITHOUT_THEIR_ENDING:
        return word
    return WORD_ENDING.sub("", word)


def words_in(text: str) -> list[str]:
    return [_without_ending(stem(word)) for word in QUESTION_WORD.findall(text.lower().replace("’", "'"))]


WORDS_THAT_DO_NOT_SEARCH = frozenset(words_in(WORDS_THAT_DO_NOT_SEARCH_TEXT))
WORDS_ANY_BRANCH_SHARES = frozenset(words_in("branch location drive up lobby"))
WORDS_IN_THE_SITES_OWN_NAME = frozenset(words_in(SITE.words_after_the_name))
WORDS_THAT_NAME_NOTHING_ALONE = WORDS_ANY_BRANCH_SHARES | WORDS_IN_THE_SITES_OWN_NAME


def search_terms(question: str) -> set[str]:
    expanded = BECOMING_A_MEMBER.sub(lambda found: found.group(0) + " join", question)
    return {word for word in words_in(expanded) if word not in WORDS_THAT_DO_NOT_SEARCH}


def names_in(question: str) -> set[str]:
    names = set()
    for capitalized in CAPITALIZED_AFTER_FIRST_WORD.findall(question):
        for word in words_in(capitalized):
            if word not in WORDS_THAT_DO_NOT_SEARCH and word not in WORDS_THAT_NAME_NOTHING_ALONE:
                names.add(word)
    return names


@dataclass(frozen=True)
class Passage:
    text: str
    display: str
    url: str
    title: str
    words: frozenset[str]
    title_words: frozenset[str]
    searchable_words: frozenset[str]
    published: str
    has_its_own_date: bool
    trust: float

    @property
    def described(self) -> str:
        return f"{self.title} ({self.published or 'undated'}, {self.url})\n{self.display}"


@dataclass(frozen=True)
class Found:
    text: str
    urls: tuple[str, ...]
    quote: str
    conflict_note: Optional[str] = None
