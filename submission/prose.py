from __future__ import annotations

import html
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from typing import Optional

from rate_facts import page_path, stem

IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]*)[^)]*\)")
MARKUP = re.compile(r"\\?\*+|\\|^#+\s*|^>\s*|^[-•]\s+", re.M)
QUESTION_WORD = re.compile(r"[a-z0-9$]+(?:'[a-z]+)?")
WORD_ENDING = re.compile(r"(?:ibility|ible|ation|ition|tion|(?<=\w{4})(?:ated|ates|ate)|ized|izes|ize|ing|ed|es|e)$")
SHORTEST_WORD_WITH_ITS_ENDING_REMOVED = 5
WORDS_THAT_MEAN_SOMETHING_ELSE_WITHOUT_THEIR_ENDING = frozenset({"foundation", "founded"})
ROOTS_OF_IRREGULAR_WORDS = {
    "closure": "clos",
    "acquisition": "acquir",
    "completion": "complet",
    "finish": "complet",
    "finished": "complet",
}
SENTENCE_END = re.compile(r"(?<=[.!?])(?<![\s.][A-Z]\.)\s+(?=[A-Z\"“])")
PUBLISHED = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December) (\d{1,2}), (20\d\d)\b"
)
LETTERS_IN_A_SHORT_MONTH = 3
MONTH_NUMBERS = {
    month[:LETTERS_IN_A_SHORT_MONTH]: number
    for number, month in enumerate(
        "January February March April May June July August September October November December".split(), start=1
    )
}
CAPITALIZED_AFTER_FIRST_WORD = re.compile(r"(?<=\s)[A-Z][A-Za-z$'-]*")
MONTH_NAMES = "January February March April May June July August September October November December".split()

CHARS_SEARCHED_FOR_PUBLISHED_DATE = 400
LONGEST_LINE_MERGED_INTO_A_BLOCK = 80
LONGEST_PASSAGE_CHARS = 1500
SENTENCES_IN_AN_ANSWER = 3
FEWEST_SENTENCES_THAT_DEFINE_SOMETHING = 2
FEWEST_LINKS_IN_A_LINK_LIST = 3
FEWEST_PAGES_FOR_A_REPEATED_COUNT = 2
FEWEST_MATCHED_TERMS_WITHOUT_A_TITLE_MATCH = 2
LISTING_PATH_PARTS = ("/tag/", "/author/", "/page/")
LISTING_PATHS = ("/newsroom", "/learn/blog", "/learn", "/business/resources")
SCHEDULES_IN_AN_ANSWER = 4
PAGES_CITED = 4
LOWEST_COVERAGE_TO_ANSWER = 0.6
SHARE_OF_TOP_SCORE_CONSIDERED_TIED = 0.9
TITLE_MATCH_BONUS = 0.25
LOWEST_SHARE_OF_BEST_SENTENCE_KEPT = 0.5
LANDING_PAGE_SUFFIX = "-lp"

EXCLUDED_PAGE_PREFIXES = ("/calculators", "/business-calculators", "/privacy-policy", "/digital-privacy-policy")
LEAST_TRUSTED_PREFIXES = ("/hubfs",)
LESS_TRUSTED_PREFIXES = ("/learn", "/business/resources", "/20")
NEWS_PREFIX = "/newsroom"
TRUST_OF_LEAST_TRUSTED = 0.5
TRUST_OF_LESS_TRUSTED = 0.6
TRUST_OF_NEWS = 0.9
TRUST_OF_SITE_PAGE = 1.0

WORDS_THAT_DO_NOT_SEARCH_TEXT = """
    a about all also am an and any are as at be been can could did do does dupaco dupaco's for from get give go going
    had has have how i i'd i'm if in is it its just know like many may me much my need of on or our please provide
    repeat should so some still tell that the their them there these they this to today total us was we were what what's
    when where which who why will with would you your link url website webpage page use see
"""

LOCATOR_PATH = "/contact"
FEE_SCHEDULE_PATH_PART = "fee-schedule"
FEE_AMOUNT = re.compile(r"\$\d|\d%|\bfree\b", re.I)
FOOTNOTE_AFTER_THE_AMOUNT = re.compile(r"\s+\*.*$")
FEE_ROWS_IN_AN_ANSWER = 4
HOURS_ASKED = re.compile(r"\bhours?\b", re.I)
OPENING_TIME_ASKED = re.compile(r"\bwhen (?:does|do|is)\b.*\b(?:branch(?:es)?|lobby|drive-up)\b.*\bopen\b", re.I)
TIME_OF_DAY_ASKED = re.compile(r"\bwhat time\b.*\b(?:open|close)\b", re.I)
CLOSING_TIME_ASKED = re.compile(r"\bwhen (?:does|do|is)\b.*\b(?:branch(?:es)?|lobby|drive-up)\b.*\bclose\b", re.I)
A_BRANCH_ASKED_ABOUT = re.compile(r"\b(?:branch(?:es)?|locations?)\b", re.I)
FIRST_OR_LAST_OF_A_KIND = re.compile(r"\b(?:first|last|oldest|newest|original)\s+[a-z]+", re.I)
BYLINE = re.compile(r"Written by .*?\|\s*([A-Z][a-z]{2}) (\d{1,2}), (\d{4}) [\d:]+ [AP]M")
DATE_ASKED = re.compile(r"\bwhen\b|\b(?:what|which) (?:date|year)s?\b|\bdeadline\b|\bstill open\b", re.I)
ADDRESS_ASKED = re.compile(r"\baddress\b", re.I)
ATM_ASKED = re.compile(r"\batms?\b", re.I)
DUPACO_BRANCH_LISTING = re.compile(r"\bDupaco Branch\b")
DUPACO_ORIGIN_ASKED = re.compile(
    r"^\s*(?:when|what year)\b.*\b(?:did|was)\s+(?:dupaco|the credit union)\s+(?:get\s+)?"
    r"(?:start|started|begin|open|opened)\s*\??\s*$"
    r"|^\s*how (?:old is|long has|many years has)\s+dupaco\b",
    re.I,
)
WHEN_DUPACO_WAS_FOUNDED = "When was Dupaco founded?"
ROUTING_ASKED = re.compile(r"\brouting\b|\baba\b", re.I)
HOW_TO_REACH_ASKED = re.compile(
    r"\bphone (?:numbers?|for)\b|\b(?:your|dupaco's) phone\b|\bcontact information\b"
    r"|\b(?:who|number)\b.*\b(?:call|talk|speak)\b|\bcall (?:you|dupaco|someone)\b",
    re.I,
)

DATE_OR_YEAR = re.compile(PUBLISHED.pattern + r"|\b(?:19|20)\d\d\b")
FOUNDING_ASKED = re.compile(r"\b(?:founded|established)\b", re.I)
FOUNDING_YEAR = re.compile(r"\b(?:founded|founding|established)\b\D{0,10}((?:19|20)\d\d)\b", re.I)
CLAUSE_BREAK = re.compile(r",\s+(?!\d)")
DEFINITION_ASKED = re.compile(r"^\s*what(?:'s| is| are)\b", re.I)
CHARTER_AREA = re.compile(r"\bcharter area\b", re.I)
STATES_SERVED = re.compile(r"\bIowa\b.*\bIllinois\b.*\bWisconsin\b")
BRANCH_COUNT = re.compile(r"(?<![\d,])\b(\d{1,3}) (?:\w+ )?branch(?:es)?\b", re.I)
FULL_DATE = re.compile(rf"\b({'|'.join(MONTH_NUMBERS)})[a-z]*\.? (\d{{1,2}}), (20\d\d)\b")
MONTH_AND_YEAR = re.compile(rf"\b({'|'.join(MONTH_NUMBERS)})[a-z]*\.? (20\d\d)\b")
EARLY_IN_A_YEAR = re.compile(r"\bearly (20\d\d)\b")
LAST_DAY_OF_ANY_MONTH = 31
END_OF_EARLY_IN_A_YEAR = "03-31"
BARE_YEAR = re.compile(r"\b(?:19|20)\d\d\b")
STILL_AHEAD_ASKED = re.compile(r"\bwill\b|\bgoing to\b|\b(?:does|do|is|are)\b", re.I)
STILL_OPEN_ASKED = re.compile(
    r"^\s*(?:is|are)\s+(.+?)\s+(?:still open\b|open(?: anymore| any more| yet)?\s*\??\s*$)"
    r"|\bif\s+(.+?)\s+(?:is|are)\s+still open\b",
    re.I,
)
CLOSED_ASKED = re.compile(r"^\s*(?:is|are|has|have|did)\s+(.+?)\s+(?:closed|closing|close)\s*\??\s*$", re.I)
WHEN_IT_CLOSES_ASKED = re.compile(r"^\s*when\s+(?:will|does|do|did|is|are)\s+(.+?)\s+clos(?:e|ing)\s*\??\s*$", re.I)
LOWERCASE_WORD = re.compile(r"\b[a-z]{2,}")
FEWEST_ASKED_WORDS_WITHOUT_A_NAME = 2
FEWEST_WORDS_THAT_NARROW_A_COUNT = 2
REFERS_BACK_TO_THE_SUBJECT = re.compile(
    r"^\W*(?:this|it|its|founded|established|the (?:branch|location|acquisition|credit union|office|building)\b)\b", re.I
)
ASKED_IN_THE_PAST = re.compile(r"\b(?:did|was|were)\b", re.I)
SHUT_DOWN = re.compile(r"\bshut(?:ting|s)?(?: down)?\b", re.I)
RATE_SHEET_FOOTER = re.compile(r"\brates are effective as of\b", re.I)
LAST_DAY_ASKED = re.compile(r"\blast day (?:for|of|at)\s+(.+?)\s*\??\s*$", re.I)
AHEAD_NOT_NOW_ASKED = re.compile(r"\bwill\b|\bgoing to\b", re.I)
WRITTEN_AS_STILL_AHEAD = re.compile(r"\b(?:will|plans?|planned|expected|scheduled)\b", re.I)
CLOSING_STATED = re.compile(r"\bclos(?:e|es|ed|ing|ure)\b|\blast day\b", re.I)
TIME_OF_DAY = re.compile(r"\d(?::\d\d)?\s*[ap]\.?m\b", re.I)
HOURS_BLOCK = re.compile(r"\b(?:lobby|drive-up)\b.*" + TIME_OF_DAY.pattern, re.I | re.S)
SCHEDULE_START = re.compile(r"\b(?:lobby|drive-up)\b", re.I)
SCHEDULE_END = re.compile(r"\s*\bABOUT DUPACO\b.*$", re.S)
TITLE_SITE_SUFFIX = re.compile(r"\s*\|.*$")
BECOMING_A_MEMBER = re.compile(r"\bbecome a(?: dupaco)? member\b|\bmembership\b", re.I)
END_OF_ARTICLE = re.compile(r"^#+\s*Handpicked for You.*", re.M | re.S)
TEASER = re.compile(r"\b(?:min read|keep reading|read more)\b", re.I)
COUNTED_THING = re.compile(r"\b(?i:how many|the number of)\s+(?:[A-Z][a-z]+\s+)*([A-Za-z]+)")
FULL_SERVICE = re.compile(r"\bfull[- ]service\b", re.I)
STATED_ABOUT_DUPACO = re.compile(r"\bdupaco\b|\bit has\b|\bour\b|\bfounded in 1948\b", re.I)
MEMBERSHIP_TOTAL = r"membership (?:totals|has grown to) (?:more than )?\d+(?:,\d{3})*"
ADDRESS = re.compile(r"\d+ [^,\n]+, [A-Z][A-Za-z ]+, [A-Z]{2},? \d{5}")
ROUTING_NUMBER = re.compile(r"\b\d{9}\b")
PHONE = re.compile(r"\b\d{3}-\d{3}-\d{4}\b")


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


@dataclass(frozen=True)
class FeeRow:
    label: str
    amount: str
    words: frozenset[str]
    url: str


@dataclass(frozen=True)
class Found:
    text: str
    urls: tuple[str, ...]
    quote: str
    conflict_note: Optional[str] = None


def _without_ending(word: str) -> str:
    if word in ROOTS_OF_IRREGULAR_WORDS:
        return ROOTS_OF_IRREGULAR_WORDS[word]
    if len(word) < SHORTEST_WORD_WITH_ITS_ENDING_REMOVED or word in WORDS_THAT_MEAN_SOMETHING_ELSE_WITHOUT_THEIR_ENDING:
        return word
    return WORD_ENDING.sub("", word)


def words_in(text: str) -> list[str]:
    return [_without_ending(stem(word)) for word in QUESTION_WORD.findall(text.lower().replace("’", "'"))]


WORDS_THAT_DO_NOT_SEARCH = frozenset(words_in(WORDS_THAT_DO_NOT_SEARCH_TEXT))
WORDS_A_SHAPE_ALREADY_SATISFIES = frozenset(words_in("address phone number year date"))
WORDS_ANY_BRANCH_SHARES = frozenset(words_in("branch location drive up lobby"))
WORDS_THAT_ONLY_ASK_WHEN = frozenset(words_in("next hold held pass passed happen happened"))
MEMBER = stem("member")
COUNTED_AS_BRANCHES = frozenset(stem(word) for word in ("location", "office"))
WORDS_IN_DUPACOS_OWN_NAME = frozenset(words_in("community credit union"))
WORDS_THAT_NAME_NOTHING_ALONE = WORDS_ANY_BRANCH_SHARES | WORDS_IN_DUPACOS_OWN_NAME
CLOSE = _without_ending(stem("close"))
WORDS_ROUTING_IS_FOUND_BY = frozenset(words_in("routing"))
WORDS_THAT_ASK_FOR_A_FEE = frozenset(words_in("fee cost charge charged price penalty amount"))
BUSINESS = next(iter(words_in("business")))
NO_IF_CLOSED = ("No.", "Yes, for now.")
YES_IF_CLOSED = ("Yes.", "Not yet.")
WORDS_NAMING_A_KIND_OF_HOURS = frozenset(words_in("lobby drive"))
WORDS_ABOUT_REACHING_DUPACO = frozenset(
    words_in(
        "call contact information update change customer member service support main general credit union talk speak "
        "reach someone charge credit card debit visa mortgage loan rate question"
    )
)


def trust_of(path: str) -> float:
    if path.startswith(LEAST_TRUSTED_PREFIXES):
        return TRUST_OF_LEAST_TRUSTED
    if path.startswith(LESS_TRUSTED_PREFIXES) or path.endswith(LANDING_PAGE_SUFFIX):
        return TRUST_OF_LESS_TRUSTED
    if path.startswith(NEWS_PREFIX):
        return TRUST_OF_NEWS
    return TRUST_OF_SITE_PAGE


def published_date(markdown: str) -> Optional[str]:
    found = PUBLISHED.search(markdown[:CHARS_SEARCHED_FOR_PUBLISHED_DATE]) or BYLINE.search(markdown)
    if not found:
        return None
    month, day, year = found.groups()
    return f"{year}-{MONTH_NUMBERS[month[:LETTERS_IN_A_SHORT_MONTH]]:02d}-{int(day):02d}"


def _is_a_page_address(target: str) -> bool:
    return target.startswith("http") and "/hubfs/" not in target and not target.endswith("#") and "/tag/" not in target


def is_listing_page(path: str) -> bool:
    return path in LISTING_PATHS or any(part in path + "/" for part in LISTING_PATH_PARTS)


def _is_noise(block: str) -> bool:
    return bool(TEASER.search(block)) or len(LINK.findall(block)) >= FEWEST_LINKS_IN_A_LINK_LIST


def _plain(block: str, keep_urls: bool) -> str:
    def link(found: re.Match) -> str:
        label, target = found.groups()
        return f"{label} ({target})" if keep_urls and _is_a_page_address(target) else label

    plain = re.sub(r"\s+", " ", MARKUP.sub("", LINK.sub(link, IMAGE.sub("", block))))
    return BYLINE.sub("", plain).strip()


def split_into_blocks(markdown: str) -> list[str]:
    blocks: list[str] = []
    for paragraph in re.split(r"\n\s*\n", markdown):
        paragraph = paragraph.strip()
        if not paragraph or paragraph.startswith("|") or paragraph == "* * *":
            continue
        starts_a_section = paragraph.startswith("#")
        previous_line = _plain(blocks[-1].rsplit("\n", 1)[-1], keep_urls=False) if blocks else ""
        previous_is_short = bool(blocks) and len(previous_line) <= LONGEST_LINE_MERGED_INTO_A_BLOCK
        answers_the_previous_line = previous_line.endswith("?")
        fits = bool(blocks) and len(blocks[-1]) + len(paragraph) <= LONGEST_PASSAGE_CHARS
        short = len(_plain(paragraph, keep_urls=False)) <= LONGEST_LINE_MERGED_INTO_A_BLOCK
        if blocks and fits and not starts_a_section and (answers_the_previous_line or (short and previous_is_short)):
            blocks[-1] += "\n" + paragraph
        else:
            blocks.append(paragraph)
    return blocks


class PassageIndex:
    def __init__(self, pages: list, taken_on: str) -> None:
        self._taken_on = taken_on
        self._passages: list[Passage] = []
        self._postings: dict[str, list[int]] = defaultdict(list)
        self._document_frequency: Counter = Counter()
        self._links: list[tuple[str, str]] = []
        self._fee_rows: dict[str, FeeRow] = {}
        seen_paths: set[str] = set()
        newest_by_text: dict[str, Passage] = {}
        pages_repeating: Counter = Counter()
        for page in pages:
            path = page_path(page.url)
            if path in seen_paths or path.startswith(EXCLUDED_PAGE_PREFIXES) or is_listing_page(path):
                continue
            seen_paths.add(path)
            if FEE_SCHEDULE_PATH_PART in path:
                for row in _fee_rows_in(page.markdown, page.url):
                    self._fee_rows.setdefault(row.label, row)
            title_words = frozenset(words_in(page.title) + words_in(path.replace("-", " ").replace("/", " ")))
            own_date = published_date(page.markdown)
            published = own_date or taken_on
            article = END_OF_ARTICLE.sub("", page.markdown)
            self._links.extend(
                (label, target) for label, target in LINK.findall(IMAGE.sub("", article)) if _is_a_page_address(target)
            )
            for block in split_into_blocks(article):
                if _is_noise(block):
                    continue
                text = _plain(block, keep_urls=False)
                words = frozenset(words_in(text))
                if not words:
                    continue
                self._document_frequency.update(words)
                pages_repeating[text] += 1
                passage = Passage(
                    text,
                    _plain(block, keep_urls=True),
                    page.url,
                    page.title,
                    words,
                    title_words,
                    words | title_words,
                    published,
                    own_date is not None,
                    trust_of(path),
                )
                kept = newest_by_text.get(text)
                if kept is None or passage.published > kept.published:
                    newest_by_text[text] = passage
        self._passages = list(newest_by_text.values())
        self._passages_of: dict[str, list[Passage]] = defaultdict(list)
        self._pages_repeating = pages_repeating
        for position, passage in enumerate(self._passages):
            self._passages_of[passage.url].append(passage)
            for word in passage.searchable_words:
                self._postings[word].append(position)

    def _rarity(self, word: str) -> float:
        return math.log(1 + len(self._passages) / (1 + self._document_frequency[word]))

    def _coverage(self, terms: set[str], passage: Passage) -> float:
        total = sum(self._rarity(term) for term in terms)
        matched = sum(self._rarity(term) for term in terms if term in passage.searchable_words)
        return matched / total if total else 0.0

    def _ranked(
        self,
        terms: set[str],
        names: set[str],
        required_shape: Optional[re.Pattern],
        fewest_body_matches: int = FEWEST_MATCHED_TERMS_WITHOUT_A_TITLE_MATCH,
    ) -> list[tuple[float, Passage]]:
        candidates = {position for term in terms for position in self._postings.get(term, [])}
        ranked = []
        for position in candidates:
            passage = self._passages[position]
            if not names <= passage.searchable_words:
                continue
            if required_shape is not None and not required_shape.search(passage.text):
                continue
            coverage = self._coverage(terms, passage)
            matched_in_body = terms & passage.words
            title_matched = terms & passage.title_words
            specific_enough = title_matched or len(matched_in_body) >= fewest_body_matches
            if coverage >= LOWEST_COVERAGE_TO_ANSWER and specific_enough:
                title_share = len(terms & passage.title_words) / len(terms)
                ranked.append((coverage * passage.trust * (1 + TITLE_MATCH_BONUS * title_share), passage))
        ranked.sort(key=lambda scored: scored[0], reverse=True)
        return ranked

    def search(self, question: str) -> Optional[Found]:
        question = SHUT_DOWN.sub("close", question)
        return self._search_by_kind_of_question(question) or self._date_from_the_article(question)

    def _date_from_the_article(self, question: str) -> Optional[Found]:
        names = _names_in(question)
        asked = _asked_beyond_the_name(question, names)
        whether_it_closed = STILL_OPEN_ASKED.search(question) or CLOSED_ASKED.search(question)
        if not names or not asked or whether_it_closed or _shape_asked_for(question) is not DATE_OR_YEAR:
            return None
        if not ASKED_IN_THE_PAST.search(question):
            return None
        statements = [
            (sentence, passage)
            for passage in self._passages
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

    def _search_by_kind_of_question(self, question: str) -> Optional[Found]:
        if DUPACO_ORIGIN_ASKED.search(question):
            return self._search_as_worded(WHEN_DUPACO_WAS_FOUNDED)
        if COUNTED_THING.search(question):
            question = FULL_SERVICE.sub(" ", question)
        closes = WHEN_IT_CLOSES_ASKED.search(question)
        if closes and not _search_terms(closes.group(1)):
            return None
        last_day = LAST_DAY_ASKED.search(question)
        if last_day and _names_in(_when_will_it_close(last_day.group(1))):
            return self._search_as_worded(_when_will_it_close(last_day.group(1)))
        still_open = STILL_OPEN_ASKED.search(question)
        closed = CLOSED_ASKED.search(question)
        if still_open or closed:
            place = next(group for group in (still_open or closed).groups() if group)
            leads = YES_IF_CLOSED if closed else NO_IF_CLOSED
            if _names_in(_when_will_it_close(place)):
                return self._has_it_closed(place, leads)
            beyond_any_branch = _search_terms(place) - WORDS_ANY_BRANCH_SHARES
            if A_BRANCH_ASKED_ABOUT.search(place) and beyond_any_branch:
                return self._has_it_closed(place.title(), leads)
            if _search_terms(place) and not beyond_any_branch:
                return self._which_branch()
            if not _search_terms(place):
                return None
        if not (DATE_ASKED.search(question) and FOUNDING_ASKED.search(question)):
            return self._search_as_worded(question)
        names = _names_in(question)
        if not names:
            return self._search_as_worded(FOUNDING_ASKED.sub("founded", question))
        found = (
            self._search_as_worded(question)
            or self._search_as_worded(FOUNDING_ASKED.sub("established", question))
            or self._search_as_worded(FOUNDING_ASKED.sub("founded", question))
        )
        return found and replace(found, conflict_note=self._disagreement_about_founding(names))

    def _which_branch(self) -> Found:
        locator = self._locator_url()
        return Found("That depends on the branch; which branch do you need?", (locator,) if locator else (), "")

    def _has_it_closed(self, place: str, leads: tuple[str, str]) -> Optional[Found]:
        found = self._search_as_worded(_when_will_it_close(place))
        if not found or not CLOSING_STATED.search(found.text) or not DATE_OR_YEAR.search(found.text):
            return None
        lead = leads[0] if self._has_passed(found.text) else leads[1]
        return replace(found, text=f"{lead} {found.text}")

    def founding_year_statements(self, names: set[str]) -> list[tuple[str, Passage]]:
        return [
            (year, passage)
            for passage in self._passages
            if names <= passage.words
            for sentence in SENTENCE_END.split(passage.text)
            if names <= set(words_in(sentence))
            for year in FOUNDING_YEAR.findall(sentence)
        ]

    def _disagreement_about_founding(self, names: set[str]) -> Optional[str]:
        years = {year for year, _ in self.founding_year_statements(names)}
        if len(years) < 2:
            return None
        return f"The site gives more than one year for this: {', '.join(sorted(years))}. This answer uses the best matching page."

    def _search_as_worded(self, question: str) -> Optional[Found]:
        names = _names_in(question)
        if _asks_when_a_branch_is_open(question, names):
            return self._hours(question)
        shape = _shape_asked_for(question)
        fewest_body_matches = 1 if shape else FEWEST_MATCHED_TERMS_WITHOUT_A_TITLE_MATCH
        terms = _search_terms(question) - (WORDS_A_SHAPE_ALREADY_SATISFIES if shape else frozenset())
        if shape is ROUTING_NUMBER:
            terms = WORDS_ROUTING_IS_FOUND_BY
        if shape is DATE_OR_YEAR:
            terms = terms - WORDS_THAT_ONLY_ASK_WHEN
        ranked = self._ranked(terms, names, shape, fewest_body_matches)
        if shape is ADDRESS and not ATM_ASKED.search(question):
            ranked = [scored for scored in ranked if DUPACO_BRANCH_LISTING.search(scored[1].text)]
        if shape is PHONE:
            return self._phone_answer(ranked, terms)
        if not ranked:
            return None
        if COUNTED_THING.search(question):
            return self._most_stated_count(question, ranked, shape)
        if shape is DATE_OR_YEAR:
            if not _names_what_it_asks_the_date_of(question, names):
                return None
            ranked = _stating_any_first_or_last_asked_about(question, ranked)
            if not ranked:
                return None
            if not names and A_BRANCH_ASKED_ABOUT.search(question):
                return self._date_of_an_unnamed_branch(question, terms, ranked)
            ranked = [scored for scored in ranked if names <= scored[1].words]
            if not ranked:
                return None
        best = _newest_among_the_tied(_titled_with_the_name(question, names, shape, ranked) or ranked)
        if shape in (ADDRESS, ROUTING_NUMBER):
            value = shape.search(best.text).group(0)
            return Found(value + ".", self._pages_stating(value, best), best.text)
        passages_to_try = _dated_passages_to_try(best, terms, ranked) if shape is DATE_OR_YEAR else [best]
        found = next(
            (
                answer
                for passage in passages_to_try
                if (answer := _answer_from_page(question, passage, self._passages_of[passage.url], names, shape))
            ),
            None,
        )
        if found and shape is DATE_OR_YEAR and ASKED_IN_THE_PAST.search(question):
            if WRITTEN_AS_STILL_AHEAD.search(found.text) and not self._has_passed(found.text):
                return None
        if not found or shape is not DATE_OR_YEAR or not STILL_AHEAD_ASKED.search(question):
            return found
        if self._reads_ahead_but_passed(found.text):
            newer = self._most_recent_statement(question, names, ranked)
            if newer and _latest_date_in(newer.text)[0] > _latest_date_in(found.text)[0]:
                return newer
            return replace(found, text=f"{_latest_date_in(found.text)[1]} has passed. The site said: {found.text}")
        if self._has_passed(found.text) and not AHEAD_NOT_NOW_ASKED.search(question):
            return self._most_recent_statement(question, names, ranked) or found
        return found

    def _date_of_an_unnamed_branch(
        self, question: str, terms: set[str], ranked: list[tuple[float, Passage]]
    ) -> Optional[Found]:
        stating_it = [
            passage
            for _, passage in ranked
            if terms <= passage.searchable_words and passage.trust > TRUST_OF_LEAST_TRUSTED
        ]
        titled_with_it = [passage for passage in stating_it if terms <= passage.title_words]
        by_page: dict[str, Passage] = {}
        for passage in titled_with_it or stating_it:
            by_page.setdefault(passage.url, passage)
        if not by_page:
            return None
        pages = list(by_page.values())[:SCHEDULES_IN_AN_ANSWER]
        dated = [(page, found) for page in pages if (found := self._date_on_page(question, page))]
        if not dated:
            return None
        if STILL_AHEAD_ASKED.search(question):
            upcoming = [(page, found) for page, found in dated if not self._has_passed(found.text)]
            if not upcoming:
                earlier = " | ".join(f"{_title_of(page)}: {found.text}" for page, found in dated)
                return Found(f"The site shows nothing upcoming. Earlier: {earlier}", tuple(p.url for p, _ in dated), dated[0][0].text)
            dated = upcoming
        if len(dated) > 1:
            titles = " | ".join(_title_of(page) for page, _ in dated)
            return Found(f"That depends on the branch; which branch do you need? {titles}", tuple(p.url for p, _ in dated), dated[0][0].text)
        page, found = dated[0]
        return Found(f"{_title_of(page)}: {found.text}", found.urls, found.quote)

    def _date_on_page(self, question: str, passage: Passage) -> Optional[Found]:
        return _answer_from_page(question, passage, self._passages_of[passage.url], set(), DATE_OR_YEAR)

    def _most_recent_statement(self, question: str, names: set[str], ranked: list[tuple[float, Passage]]) -> Optional[Found]:
        asked = _asked_beyond_the_name(question, names)
        statements = [
            (sentence, passage)
            for _, passage in ranked
            for sentence in SENTENCE_END.split(passage.display)
            if _can_state_a_date(sentence)
            and _mentions(_through_the_date(sentence), asked)
            and not self._reads_ahead_but_passed(sentence)
        ]
        if not statements:
            return None
        sentence, passage = max(statements, key=lambda statement: _latest_date_in(statement[0])[0])
        lead = "Most recently: " if self._has_passed(sentence) else ""
        return Found(lead + _through_the_date(sentence), (passage.url,), passage.text)

    def _reads_ahead_but_passed(self, sentence: str) -> bool:
        return bool(WRITTEN_AS_STILL_AHEAD.search(sentence)) and self._has_passed(sentence)

    def _has_passed(self, sentence: str) -> bool:
        return _latest_date_in(sentence)[0] < self._taken_on

    def _most_stated_count(
        self, question: str, ranked: list[tuple[float, Passage]], shape: re.Pattern
    ) -> Optional[Found]:
        terms = _search_terms(question) - set(words_in(COUNTED_THING.search(question).group(1)))
        names = _names_in(question)
        statements = [
            (sentence, shape.search(sentence).group(0).lower(), passage)
            for _, passage in ranked
            for sentence in SENTENCE_END.split(passage.text)
            if shape.search(sentence)
            and STATED_ABOUT_DUPACO.search(sentence)
            and names <= set(words_in(sentence))
            and (len(terms) < FEWEST_WORDS_THAT_NARROW_A_COUNT or _mentions(sentence, terms))
        ]
        if not statements:
            return None
        pages_stating: Counter = Counter()
        for _, count, passage in statements:
            pages_stating[count] += self._pages_repeating[passage.text]

        def strength(statement: tuple[str, str, Passage]) -> tuple[int, bool, str]:
            sentence, count, passage = statement
            repeated = pages_stating[count] >= FEWEST_PAGES_FOR_A_REPEATED_COUNT
            return len(terms & set(words_in(sentence))), repeated, passage.published if passage.has_its_own_date else ""

        sentence, _, passage = max(statements, key=strength)
        return Found(sentence, (passage.url,), passage.text)

    def fee_for(self, question: str) -> Optional[Found]:
        terms = _search_terms(question) - WORDS_THAT_ASK_FOR_A_FEE
        stating = [row for row in self._fee_rows.values() if terms and terms <= row.words]
        if BUSINESS not in terms and any(BUSINESS not in row.words for row in stating):
            stating = [row for row in stating if BUSINESS not in row.words]
        if not stating:
            return None
        chosen = stating[:FEE_ROWS_IN_AN_ANSWER]
        listed = "; ".join(f"{row.label}: {row.amount}" for row in chosen)
        return Found(f"{listed}.", (chosen[0].url,), listed)

    def _phone_answer(self, ranked: list[tuple[float, Passage]], terms: set[str]) -> Optional[Found]:
        stating = [passage for _, passage in ranked if passage.trust == TRUST_OF_SITE_PAGE]
        if terms <= WORDS_ABOUT_REACHING_DUPACO:
            stating += [p for p in self._passages if page_path(p.url) == LOCATOR_PATH and PHONE.search(p.text)]
        best = next(iter(stating), None)
        return Found(f"Call {PHONE.search(best.text).group(0)}.", (best.url,), best.text) if best else None

    def branch_count_statements(self) -> tuple[Optional[tuple[str, Passage]], list[tuple[str, Passage]]]:
        statements = [(found.group(1), p) for p in self._passages if (found := BRANCH_COUNT.search(p.text))]
        dated = [statement for statement in statements if statement[1].has_its_own_date]
        newest = max(dated, key=lambda statement: statement[1].published, default=None)
        undated_site_pages = [
            statement for statement in statements if not statement[1].has_its_own_date and statement[1].trust == TRUST_OF_SITE_PAGE
        ]
        newest_first = sorted(dated, key=lambda statement: statement[1].published, reverse=True)
        return newest, undated_site_pages + newest_first

    def _pages_stating(self, value: str, best: Passage) -> tuple[str, ...]:
        stating = [p for p in self._passages if value in p.text]
        by_trust = sorted(stating, key=lambda passage: (passage is not best, -passage.trust, passage.url))
        return tuple(dict.fromkeys(passage.url for passage in by_trust))[:PAGES_CITED]

    def _hours(self, question: str) -> Optional[Found]:
        kinds = {word for word in words_in(question) if word in WORDS_NAMING_A_KIND_OF_HOURS}
        names = _names_in(question)
        ranked = self._ranked(kinds | names or {stem("branch")}, names, HOURS_BLOCK, fewest_body_matches=1)
        if not ranked:
            return None
        schedules: dict[str, Passage] = {}
        for _, passage in sorted(ranked, key=lambda scored: scored[1].published, reverse=True):
            schedules.setdefault(_schedule_key(passage), passage)
        chosen = list(schedules.values())
        if names or len(chosen) == 1:
            return Found(_schedule_of(chosen[0]), (chosen[0].url,), chosen[0].text)
        chosen = chosen[:SCHEDULES_IN_AN_ANSWER]
        listed = " | ".join(f"{_title_of(p)}: {_schedule_of(p)}" for p in chosen)
        cited = tuple(dict.fromkeys((self._locator_url(), chosen[0].url)))
        return Found(f"Hours vary by branch; which branch do you need? {listed}", tuple(u for u in cited if u), chosen[0].text)

    def _locator_url(self) -> Optional[str]:
        return next((p.url for p in self._passages if page_path(p.url) == LOCATOR_PATH), None)

    def link_for(self, question: str) -> Optional[Found]:
        terms = _search_terms(question)
        votes: Counter = Counter()
        labels: dict[str, str] = {}
        for label, target in self._links:
            label_words = set(words_in(label)) | set(words_in(target.replace("-", " ").replace("/", " ")))
            if terms and len(terms & label_words) / len(terms) >= LOWEST_COVERAGE_TO_ANSWER:
                page = target.split("#")[0]
                votes[page] += 1
                labels.setdefault(page, label)
        if not votes:
            return None
        page = votes.most_common(1)[0][0]
        return Found(page, (page,), labels[page])


def _fee_rows_in(markdown: str, url: str) -> list[FeeRow]:
    rows = []
    for line in markdown.splitlines():
        cells = [html.unescape(html.unescape(cell)).strip() for cell in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) >= 2 and FEE_AMOUNT.search(cells[1]):
            label = cells[0]
            rows.append(FeeRow(label, FOOTNOTE_AFTER_THE_AMOUNT.sub("", cells[1]), frozenset(words_in(label)), url))
    return rows


def _title_of(passage: Passage) -> str:
    return TITLE_SITE_SUFFIX.sub("", passage.title)


def _schedule_of(passage: Passage) -> str:
    start = SCHEDULE_START.search(passage.text)
    return SCHEDULE_END.sub("", passage.text[start.start():]).strip()


def _schedule_key(passage: Passage) -> str:
    return re.sub(r"[^a-z0-9:]", "", _schedule_of(passage).lower())


def _asks_when_a_branch_is_open(question: str, names: set[str]) -> bool:
    closing_time = not names and CLOSING_TIME_ASKED.search(question)
    return bool(
        HOURS_ASKED.search(question)
        or OPENING_TIME_ASKED.search(question)
        or TIME_OF_DAY_ASKED.search(question)
        or closing_time
    )


def _stating_any_first_or_last_asked_about(
    question: str, ranked: list[tuple[float, Passage]]
) -> list[tuple[float, Passage]]:
    asked = [" ".join(words_in(found)) for found in FIRST_OR_LAST_OF_A_KIND.findall(question)]
    return [scored for scored in ranked if all(phrase in " ".join(words_in(scored[1].text)) for phrase in asked)]


def _search_terms(question: str) -> set[str]:
    expanded = BECOMING_A_MEMBER.sub(lambda found: found.group(0) + " join", question)
    return {word for word in words_in(expanded) if word not in WORDS_THAT_DO_NOT_SEARCH}


def _names_in(question: str) -> set[str]:
    names = set()
    for capitalized in CAPITALIZED_AFTER_FIRST_WORD.findall(question):
        for word in words_in(capitalized):
            if word not in WORDS_THAT_DO_NOT_SEARCH and word not in WORDS_THAT_NAME_NOTHING_ALONE:
                names.add(word)
    return names


def _shape_asked_for(question: str) -> Optional[re.Pattern]:
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


def _titled_with_the_name(
    question: str, names: set[str], shape: Optional[re.Pattern], ranked: list[tuple[float, Passage]]
) -> list[tuple[float, Passage]]:
    if not names or shape is not None or DEFINITION_ASKED.search(question):
        return []
    return [scored for scored in ranked if names <= scored[1].title_words]


def _tied_for_the_top(ranked: list[tuple[float, Passage]]) -> list[Passage]:
    top_score = ranked[0][0]
    return [passage for score, passage in ranked if score >= top_score * SHARE_OF_TOP_SCORE_CONSIDERED_TIED]


def _newest_among_the_tied(ranked: list[tuple[float, Passage]]) -> Passage:
    return max(_tied_for_the_top(ranked), key=lambda passage: passage.published)


def _dated_passages_to_try(best: Passage, terms: set[str], ranked: list[tuple[float, Passage]]) -> list[Passage]:
    on_the_same_page = [passage for _, passage in ranked if passage.url == best.url]
    titled_with_what_was_asked = sorted(
        (passage for _, passage in ranked if terms <= passage.title_words),
        key=lambda passage: passage.published,
        reverse=True,
    )
    return [best, *on_the_same_page, *titled_with_what_was_asked]


def _written_out(published: str) -> str:
    year, month, day = published.split("-")
    return f"{MONTH_NAMES[int(month) - 1]} {int(day)}, {year}"


def _belongs_beside_the_best_passage(sentence: str, names: set[str], shape: Optional[re.Pattern]) -> bool:
    if names:
        return names <= set(words_in(sentence))
    return shape is None


def _sentence_stating_the_date(question: str, sentences: list[str], names: set[str]) -> str:
    terms = _search_terms(question)
    asked = _asked_beyond_the_name(question, names)

    def strength(sentence: str) -> tuple[bool, int, int, bool]:
        words = set(words_in(_through_the_date(sentence)))
        mentions_it = _states_it_about_the_name(sentence, asked, names)
        return mentions_it, len(asked & words), len(terms & words), bool(FULL_DATE.search(sentence))

    return max(sentences, key=strength)


def _can_state_a_date(sentence: str) -> bool:
    return (
        bool(DATE_OR_YEAR.search(sentence))
        and bool(LOWERCASE_WORD.search(sentence))
        and not RATE_SHEET_FOOTER.search(sentence)
        and not sentence.endswith(("?", ":"))
    )


def _states_it_about_the_name(sentence: str, asked: set[str], names: set[str]) -> bool:
    about_the_name = names <= set(words_in(sentence)) or bool(REFERS_BACK_TO_THE_SUBJECT.search(sentence))
    return about_the_name and _mentions(_through_the_date(sentence), asked)


def _names_what_it_asks_the_date_of(question: str, names: set[str]) -> bool:
    if names or A_BRANCH_ASKED_ABOUT.search(question) or FOUNDING_ASKED.search(question):
        return True
    return len(_asked_beyond_the_name(question, names)) >= FEWEST_ASKED_WORDS_WITHOUT_A_NAME


def _latest_date_in(sentence: str) -> tuple[str, str]:
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


def _asked_beyond_the_name(question: str, names: set[str]) -> set[str]:
    return (
        _search_terms(question)
        - names
        - WORDS_A_SHAPE_ALREADY_SATISFIES
        - WORDS_ANY_BRANCH_SHARES
        - WORDS_IN_DUPACOS_OWN_NAME
        - WORDS_THAT_ONLY_ASK_WHEN
    )


def _mentions(sentence: str, asked: set[str]) -> bool:
    if not asked:
        return True
    matched = asked & set(words_in(sentence))
    if CLOSE in asked and CLOSING_STATED.search(sentence):
        matched = matched | {CLOSE}
    return 2 * len(matched) >= len(asked)


def _when_will_it_close(place: str) -> str:
    return f"When will {place} close?"


def _through_the_date(sentence: str) -> str:
    end_of_date = [found.end() for found in DATE_OR_YEAR.finditer(sentence)][-1]
    clause_break = CLAUSE_BREAK.search(sentence, end_of_date)
    return sentence[: clause_break.start()] + "." if clause_break else sentence


def _answer_from_page(
    question: str, best: Passage, page: list[Passage], names: set[str], shape: Optional[re.Pattern]
) -> Optional[Found]:
    terms = _search_terms(question) | {stem("dupaco")}
    passage_of: dict[str, Passage] = {}
    for passage in page:
        for sentence in SENTENCE_END.split(passage.display):
            shape_fits = _can_state_a_date(sentence) if shape is DATE_OR_YEAR else shape is None or shape.search(sentence)
            belongs = passage is best or _belongs_beside_the_best_passage(sentence, names, shape)
            if shape_fits and belongs and not sentence.endswith("?"):
                passage_of.setdefault(sentence, passage)
    overlap = {sentence: len(terms & set(words_in(sentence))) for sentence in passage_of}
    best_overlap = max(overlap.values(), default=0)
    if best_overlap == 0:
        return None
    if shape is DATE_OR_YEAR:
        sentence = _sentence_stating_the_date(question, list(passage_of), names)
        if not _states_it_about_the_name(sentence, _asked_beyond_the_name(question, names), names):
            return None
        return Found(_through_the_date(sentence), (best.url,), passage_of[sentence].text)
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
