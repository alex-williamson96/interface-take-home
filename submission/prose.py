from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Optional

from rate_facts import page_path, stem

IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]*)[^)]*\)")
MARKUP = re.compile(r"\\?\*+|\\|^#+\s*|^>\s*|^[-•]\s+", re.M)
QUESTION_WORD = re.compile(r"[a-z0-9$]+(?:'[a-z]+)?")
WORD_ENDING = re.compile(r"(?:ibility|ible|ation|ition|tion|ized|izes|ize|ing|ed|es|e)$")
SHORTEST_WORD_WITH_ITS_ENDING_REMOVED = 5
SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"“])")
PUBLISHED = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December) (\d{1,2}), (20\d\d)\b"
)
MONTH_NUMBERS = {
    month: number
    for number, month in enumerate(
        "January February March April May June July August September October November December".split(), start=1
    )
}
CAPITALIZED_AFTER_FIRST_WORD = re.compile(r"(?<=\s)[A-Z][A-Za-z$'-]*")

CHARS_SEARCHED_FOR_PUBLISHED_DATE = 400
LONGEST_LINE_MERGED_INTO_A_BLOCK = 80
LONGEST_PASSAGE_CHARS = 1500
SENTENCES_IN_AN_ANSWER = 3
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
    repeat should so some still tell that the their them there these they this to today us was we were what what's
    when where which who why will with would you your link url website webpage page use see
"""

LOCATOR_PATH = "/contact"
HOURS_ASKED = re.compile(r"\bhours?\b", re.I)
DATE_ASKED = re.compile(r"\bwhen\b|\bwhat date\b|\bstill open\b", re.I)
ADDRESS_ASKED = re.compile(r"\baddress\b", re.I)
ROUTING_ASKED = re.compile(r"\brouting\b", re.I)
HOW_TO_REACH_ASKED = re.compile(
    r"\bphone (?:numbers?|for)\b|\b(?:your|dupaco's) phone\b|\bcontact information\b"
    r"|\b(?:who|number)\b.*\bcall\b|\bcall (?:you|dupaco|someone)\b",
    re.I,
)

DATE_OR_YEAR = re.compile(PUBLISHED.pattern + r"|\b(?:19|20)\d\d\b")
TIME_OF_DAY = re.compile(r"\d(?::\d\d)?\s*[ap]\.?m\b", re.I)
HOURS_BLOCK = re.compile(r"\b(?:lobby|drive-up)\b.*" + TIME_OF_DAY.pattern, re.I | re.S)
SCHEDULE_START = re.compile(r"\b(?:lobby|drive-up)\b", re.I)
SCHEDULE_END = re.compile(r"\s*\bABOUT DUPACO\b.*$", re.S)
TITLE_SITE_SUFFIX = re.compile(r"\s*\|.*$")
BECOMING_A_MEMBER = re.compile(r"\bbecome a(?: dupaco)? member\b|\bmembership\b", re.I)
END_OF_ARTICLE = re.compile(r"^#+\s*Handpicked for You.*", re.M | re.S)
TEASER = re.compile(r"\b(?:min read|keep reading|read more)\b", re.I)
COUNTED_THING = re.compile(r"\bhow many\s+(?:dupaco\s+)?([a-z]+)", re.I)
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
class Found:
    text: str
    urls: tuple[str, ...]
    quote: str


def _without_ending(word: str) -> str:
    if len(word) < SHORTEST_WORD_WITH_ITS_ENDING_REMOVED:
        return word
    return WORD_ENDING.sub("", word)


def words_in(text: str) -> list[str]:
    return [_without_ending(stem(word)) for word in QUESTION_WORD.findall(text.lower().replace("’", "'"))]


WORDS_THAT_DO_NOT_SEARCH = frozenset(words_in(WORDS_THAT_DO_NOT_SEARCH_TEXT))
WORDS_A_SHAPE_ALREADY_SATISFIES = frozenset(words_in("address phone number"))
WORDS_NAMING_A_KIND_OF_HOURS = frozenset(words_in("lobby drive"))


def trust_of(path: str) -> float:
    if path.startswith(LEAST_TRUSTED_PREFIXES):
        return TRUST_OF_LEAST_TRUSTED
    if path.startswith(LESS_TRUSTED_PREFIXES) or path.endswith(LANDING_PAGE_SUFFIX):
        return TRUST_OF_LESS_TRUSTED
    if path.startswith(NEWS_PREFIX):
        return TRUST_OF_NEWS
    return TRUST_OF_SITE_PAGE


def published_date(markdown: str) -> Optional[str]:
    found = PUBLISHED.search(markdown[:CHARS_SEARCHED_FOR_PUBLISHED_DATE])
    if not found:
        return None
    month, day, year = found.groups()
    return f"{year}-{MONTH_NUMBERS[month]:02d}-{int(day):02d}"


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

    return re.sub(r"\s+", " ", MARKUP.sub("", LINK.sub(link, IMAGE.sub("", block)))).strip()


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
        self._passages: list[Passage] = []
        self._postings: dict[str, list[int]] = defaultdict(list)
        self._document_frequency: Counter = Counter()
        self._links: list[tuple[str, str]] = []
        seen_paths: set[str] = set()
        newest_by_text: dict[str, Passage] = {}
        pages_repeating: Counter = Counter()
        for page in pages:
            path = page_path(page.url)
            if path in seen_paths or path.startswith(EXCLUDED_PAGE_PREFIXES) or is_listing_page(path):
                continue
            seen_paths.add(path)
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
        if HOURS_ASKED.search(question):
            return self._hours(question)
        shape = _shape_asked_for(question)
        fewest_body_matches = 1 if shape else FEWEST_MATCHED_TERMS_WITHOUT_A_TITLE_MATCH
        terms = _search_terms(question) - (WORDS_A_SHAPE_ALREADY_SATISFIES if shape else frozenset())
        names = _names_in(question)
        ranked = self._ranked(terms, names, shape, fewest_body_matches)
        if shape is PHONE:
            return self._phone_answer(ranked, names)
        if not ranked:
            return None
        if COUNTED_THING.search(question):
            return self._most_stated_count(question, ranked, shape)
        best = _newest_among_the_tied(ranked)
        if shape in (ADDRESS, ROUTING_NUMBER):
            value = shape.search(best.text).group(0)
            return Found(value + ".", self._pages_stating(value, best), best.text)
        return _answer_from_page(question, best, self._passages_of[best.url], names, shape)

    def _most_stated_count(
        self, question: str, ranked: list[tuple[float, Passage]], shape: re.Pattern
    ) -> Found:
        terms = _search_terms(question)
        statements = [
            (sentence, shape.search(sentence).group(0).lower(), passage)
            for _, passage in ranked
            for sentence in SENTENCE_END.split(passage.text)
            if shape.search(sentence)
        ]
        pages_stating: Counter = Counter()
        for _, count, passage in statements:
            pages_stating[count] += self._pages_repeating[passage.text]

        def strength(statement: tuple[str, str, Passage]) -> tuple[int, bool, str]:
            sentence, count, passage = statement
            repeated = pages_stating[count] >= FEWEST_PAGES_FOR_A_REPEATED_COUNT
            return len(terms & set(words_in(sentence))), repeated, passage.published if passage.has_its_own_date else ""

        sentence, _, passage = max(statements, key=strength)
        return Found(sentence, (passage.url,), passage.text)

    def _phone_answer(self, ranked: list[tuple[float, Passage]], names: set[str]) -> Optional[Found]:
        stating = [passage for _, passage in ranked if passage.trust == TRUST_OF_SITE_PAGE]
        if not names:
            stating += [p for p in self._passages if page_path(p.url) == LOCATOR_PATH and PHONE.search(p.text)]
        best = next(iter(stating), None)
        return Found(f"Call {PHONE.search(best.text).group(0)}.", (best.url,), best.text) if best else None

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
        listed = " | ".join(f"{TITLE_SITE_SUFFIX.sub('', p.title)}: {_schedule_of(p)}" for p in chosen)
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


def _schedule_of(passage: Passage) -> str:
    start = SCHEDULE_START.search(passage.text)
    return SCHEDULE_END.sub("", passage.text[start.start():]).strip()


def _schedule_key(passage: Passage) -> str:
    return re.sub(r"[^a-z0-9:]", "", _schedule_of(passage).lower())


def _search_terms(question: str) -> set[str]:
    expanded = BECOMING_A_MEMBER.sub(lambda found: found.group(0) + " join", question)
    return {word for word in words_in(expanded) if word not in WORDS_THAT_DO_NOT_SEARCH}


def _names_in(question: str) -> set[str]:
    names = set()
    for capitalized in CAPITALIZED_AFTER_FIRST_WORD.findall(question):
        for word in words_in(capitalized):
            if word not in WORDS_THAT_DO_NOT_SEARCH:
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
        singular = _without_ending(stem(counted.group(1).lower()))
        return re.compile(rf"\b(?!(?:19|20)\d\d\b)\d+(?:,\d{{3}})*\s+(?:\w+\s+)?{re.escape(singular)}", re.I)
    return None


def _newest_among_the_tied(ranked: list[tuple[float, Passage]]) -> Passage:
    top_score = ranked[0][0]
    tied = [passage for score, passage in ranked if score >= top_score * SHARE_OF_TOP_SCORE_CONSIDERED_TIED]
    return max(tied, key=lambda passage: passage.published)


def _answer_from_page(
    question: str, best: Passage, page: list[Passage], names: set[str], shape: Optional[re.Pattern]
) -> Optional[Found]:
    terms = _search_terms(question) | {stem("dupaco")}
    passage_of: dict[str, Passage] = {}
    for passage in page:
        for sentence in SENTENCE_END.split(passage.display):
            shape_fits = shape is None or shape.search(sentence)
            about_the_names = passage is best or names <= set(words_in(sentence))
            if shape_fits and about_the_names and not sentence.endswith("?"):
                passage_of.setdefault(sentence, passage)
    overlap = {sentence: len(terms & set(words_in(sentence))) for sentence in passage_of}
    best_overlap = max(overlap.values(), default=0)
    if best_overlap == 0:
        return None
    worth_keeping = [s for s in passage_of if overlap[s] >= best_overlap * LOWEST_SHARE_OF_BEST_SENTENCE_KEPT]
    kept = set(sorted(worth_keeping, key=lambda s: overlap[s], reverse=True)[:SENTENCES_IN_AN_ANSWER])
    answer = [s for s in passage_of if s in kept]
    quoted = dict.fromkeys(passage_of[s].text for s in answer)
    return Found(" ".join(answer), (best.url,), " ".join(quoted))
