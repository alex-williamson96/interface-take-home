from __future__ import annotations

from typing import Optional

from asked import QuestionKind, newest_among_the_tied, tied_for_the_top, what_is_asked
from page_answers import DEFINITION_ASKED, answer_from_page
from passages import PassageIndex
from text_basics import Found, Passage


def _titled_with_the_name(
    question: str, names: set[str], ranked: list[tuple[float, Passage]]
) -> list[tuple[float, Passage]]:
    if not names or DEFINITION_ASKED.search(question):
        return []
    return [scored for scored in ranked if names <= scored[1].title_words]


def _first_on_its_page_among_the_tied(best: Passage, ranked: list[tuple[float, Passage]], page: list[Passage]) -> Passage:
    tied = tied_for_the_top(ranked)
    return next((passage for passage in page if passage in tied), best)


def _best_passage(question: str, index: PassageIndex) -> Optional[Found]:
    asked = what_is_asked(question, index)
    if not asked.ranked:
        return None
    best = newest_among_the_tied(_titled_with_the_name(question, asked.names, asked.ranked) or asked.ranked)
    if DEFINITION_ASKED.search(question):
        best = _first_on_its_page_among_the_tied(best, asked.ranked, index.passages_of[best.url])
    return answer_from_page(question, best, index.passages_of[best.url], asked.names, None)


OPEN_ENDED = QuestionKind("open-ended", lambda question: True, _best_passage)
