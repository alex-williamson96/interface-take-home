from __future__ import annotations

import re
from typing import Optional

from asked import QuestionKind
from passages import PassageIndex
from rate_facts import stem
from site_profile import SITE
from text_basics import Found, Passage, names_in, words_in

HOURS_ASKED = re.compile(r"\bhours?\b", re.I)
OPENING_TIME_ASKED = re.compile(r"\bwhen (?:does|do|is|are)\b.*\b(?:branch(?:es)?|lobby|lobbies|drive-up)\b.*\bopen\b", re.I)
TIME_OF_DAY_ASKED = re.compile(r"\bwhat time\b.*\b(?:open|close)\b", re.I)
CLOSING_TIME_ASKED = re.compile(r"\bwhen (?:does|do|is)\b.*\b(?:branch(?:es)?|lobby|drive-up)\b.*\bclose\b", re.I)
TIME_OF_DAY = re.compile(r"\d(?::\d\d)?\s*[ap]\.?m\b", re.I)
HOURS_BLOCK = re.compile(r"\b(?:lobby|drive-up)\b.*" + TIME_OF_DAY.pattern, re.I | re.S)
SCHEDULE_START = re.compile(r"\b(?:lobby|drive-up)\b", re.I)
SCHEDULE_END = re.compile(rf"\s*\b{re.escape(SITE.heading_after_the_hours)}\b.*$", re.S)
TITLE_SITE_SUFFIX = re.compile(r"\s*\|.*$")
SCHEDULES_IN_AN_ANSWER = 4
WORDS_NAMING_A_KIND_OF_HOURS = frozenset(words_in("lobby drive"))


def title_of(passage: Passage) -> str:
    return TITLE_SITE_SUFFIX.sub("", passage.title)


def _schedule_of(passage: Passage) -> str:
    start = SCHEDULE_START.search(passage.text)
    return SCHEDULE_END.sub("", passage.text[start.start():]).strip()


def _schedule_key(passage: Passage) -> str:
    return re.sub(r"[^a-z0-9:]", "", _schedule_of(passage).lower())


def _asks_when_a_branch_is_open(question: str) -> bool:
    closing_time = not names_in(question) and CLOSING_TIME_ASKED.search(question)
    return bool(
        HOURS_ASKED.search(question)
        or OPENING_TIME_ASKED.search(question)
        or TIME_OF_DAY_ASKED.search(question)
        or closing_time
    )


def _hours(question: str, index: PassageIndex) -> Optional[Found]:
    kinds = {word for word in words_in(question) if word in WORDS_NAMING_A_KIND_OF_HOURS}
    names = names_in(question)
    ranked = index.ranked(kinds | names or {stem("branch")}, names, HOURS_BLOCK, fewest_body_matches=1)
    if not ranked:
        return None
    schedules: dict[str, Passage] = {}
    for _, passage in sorted(ranked, key=lambda scored: scored[1].published, reverse=True):
        schedules.setdefault(_schedule_key(passage), passage)
    chosen = list(schedules.values())
    if names or len(chosen) == 1:
        return Found(_schedule_of(chosen[0]), (chosen[0].url,), chosen[0].text)
    chosen = chosen[:SCHEDULES_IN_AN_ANSWER]
    listed = " | ".join(f"{title_of(p)}: {_schedule_of(p)}" for p in chosen)
    cited = tuple(dict.fromkeys((index.locator_url(), chosen[0].url)))
    return Found(f"Hours vary by branch; which branch do you need? {listed}", tuple(u for u in cited if u), chosen[0].text)


HOURS = QuestionKind("hours", _asks_when_a_branch_is_open, _hours)
