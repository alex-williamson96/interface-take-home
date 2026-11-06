from __future__ import annotations

from typing import Optional

from asked import ADDRESS, PHONE, ROUTING_NUMBER, QuestionKind, newest_among_the_tied, shape_asked_for, what_is_asked
from passages import TRUST_OF_SITE_PAGE, PassageIndex
from rate_facts import page_path
from site_profile import SITE
from text_basics import Found, words_in

WORDS_ABOUT_REACHING_THE_SITE = frozenset(
    words_in(
        "call contact information update change customer member service support main general credit union talk speak "
        "reach someone charge credit card debit visa mortgage loan rate question"
    )
)


def _phone(question: str, index: PassageIndex) -> Optional[Found]:
    asked = what_is_asked(question, index)
    stating = [passage for _, passage in asked.ranked if passage.trust == TRUST_OF_SITE_PAGE]
    if asked.terms <= WORDS_ABOUT_REACHING_THE_SITE:
        stating += [p for p in index.passages if page_path(p.url) == SITE.locator_path and PHONE.search(p.text)]
    best = next(iter(stating), None)
    return Found(f"Call {PHONE.search(best.text).group(0)}.", (best.url,), best.text) if best else None


def _value_stated(question: str, index: PassageIndex) -> Optional[Found]:
    asked = what_is_asked(question, index)
    if not asked.ranked:
        return None
    best = newest_among_the_tied(asked.ranked)
    value = asked.shape.search(best.text).group(0)
    return Found(value + ".", index.pages_stating(value, best), best.text)


PHONE_NUMBER = QuestionKind("phone number", lambda question: shape_asked_for(question) is PHONE, _phone)
ROUTING = QuestionKind("routing number", lambda question: shape_asked_for(question) is ROUTING_NUMBER, _value_stated)
STREET_ADDRESS = QuestionKind("address", lambda question: shape_asked_for(question) is ADDRESS, _value_stated)
