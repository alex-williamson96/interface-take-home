from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Optional

from fees import FEE_SCHEDULE_PATH, FeeRow, fee_rows_in, keep_the_cleanest_label
from rate_facts import page_path
from site_profile import SITE
from text_basics import Passage, words_in

IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]*)[^)]*\)")
MARKUP = re.compile(r"\\?\*+|\\|^#+\s*|^>\s*|^[-•]\s+", re.M)
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
BYLINE = re.compile(r"Written by .*?\|\s*([A-Z][a-z]{2}) (\d{1,2}), (\d{4}) [\d:]+ [AP]M")
END_OF_ARTICLE = re.compile(rf"^#+\s*{re.escape(SITE.heading_after_an_article)}.*", re.M | re.S)
TEASER = re.compile(r"\b(?:min read|keep reading|read more)\b", re.I)

CHARS_SEARCHED_FOR_PUBLISHED_DATE = 400
LONGEST_LINE_MERGED_INTO_A_BLOCK = 80
LONGEST_PASSAGE_CHARS = 1500
FEWEST_LINKS_IN_A_LINK_LIST = 3
FEWEST_MATCHED_TERMS_WITHOUT_A_TITLE_MATCH = 2
LISTING_PATH_PARTS = ("/tag/", "/author/", "/page/")
LOWEST_COVERAGE_TO_ANSWER = 0.6
TITLE_MATCH_BONUS = 0.25
DIGITS_THAT_RANK_A_PASSAGE = 9
PAGES_CITED = 4
TRUST_OF_LEAST_TRUSTED = 0.5
TRUST_OF_LESS_TRUSTED = 0.6
TRUST_OF_NEWS = 0.9
TRUST_OF_SITE_PAGE = 1.0


def trust_of(path: str) -> float:
    if path.startswith(SITE.least_trusted_prefixes):
        return TRUST_OF_LEAST_TRUSTED
    if path.startswith(SITE.less_trusted_prefixes) or path.endswith(SITE.landing_page_suffix):
        return TRUST_OF_LESS_TRUSTED
    if path.startswith(SITE.news_prefix):
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
    return path in SITE.listing_paths or any(part in path + "/" for part in LISTING_PATH_PARTS)


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
        self.taken_on = taken_on
        self.links: list[tuple[str, str]] = []
        self.fee_rows: dict[str, FeeRow] = {}
        self._postings: dict[str, list[int]] = defaultdict(list)
        self._document_frequency: Counter = Counter()
        seen_paths: set[str] = set()
        newest_by_text: dict[str, Passage] = {}
        pages_repeating: Counter = Counter()
        for page in pages:
            path = page_path(page.url)
            if path in seen_paths or path.startswith(SITE.prefixes_not_searched) or is_listing_page(path):
                continue
            seen_paths.add(path)
            if FEE_SCHEDULE_PATH.search(path):
                for row in fee_rows_in(page.markdown, page.url):
                    keep_the_cleanest_label(self.fee_rows, row)
                continue
            title_words = frozenset(words_in(page.title) + words_in(path.replace("-", " ").replace("/", " ")))
            own_date = published_date(page.markdown)
            published = own_date or taken_on
            article = END_OF_ARTICLE.sub("", page.markdown)
            self.links.extend(
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
        self.passages: list[Passage] = list(newest_by_text.values())
        self.passages_of: dict[str, list[Passage]] = defaultdict(list)
        self.pages_repeating = pages_repeating
        for position, passage in enumerate(self.passages):
            self.passages_of[passage.url].append(passage)
            for word in passage.searchable_words:
                self._postings[word].append(position)

    def _rarity(self, word: str) -> float:
        return math.log(1 + len(self.passages) / (1 + self._document_frequency[word]))

    def _coverage(self, terms: set[str], passage: Passage) -> float:
        total = sum(self._rarity(term) for term in terms)
        matched = sum(self._rarity(term) for term in terms if term in passage.searchable_words)
        return matched / total if total else 0.0

    def ranked(
        self,
        terms: set[str],
        names: set[str],
        required_shape: Optional[re.Pattern],
        fewest_body_matches: int = FEWEST_MATCHED_TERMS_WITHOUT_A_TITLE_MATCH,
    ) -> list[tuple[float, Passage]]:
        candidates = {position for term in terms for position in self._postings.get(term, [])}
        ranked = []
        for position in sorted(candidates):
            passage = self.passages[position]
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
                score = round(coverage * passage.trust * (1 + TITLE_MATCH_BONUS * title_share), DIGITS_THAT_RANK_A_PASSAGE)
                ranked.append((score, passage))
        ranked.sort(key=lambda scored: scored[0], reverse=True)
        return ranked

    def best_matches_at_any_coverage(self, terms: set[str], how_many: int) -> list[Passage]:
        positions = sorted({position for term in terms for position in self._postings.get(term, [])})

        def relevance(position: int) -> float:
            passage = self.passages[position]
            title_share = len(terms & passage.title_words) / len(terms)
            return self._coverage(terms, passage) * passage.trust * (1 + TITLE_MATCH_BONUS * title_share)

        return [self.passages[position] for position in sorted(positions, key=relevance, reverse=True)[:how_many]]

    def pages_stating(self, value: str, best: Passage) -> tuple[str, ...]:
        stating = [passage for passage in self.passages if value in passage.text]
        by_trust = sorted(stating, key=lambda passage: (passage is not best, -passage.trust, passage.url))
        return tuple(dict.fromkeys(passage.url for passage in by_trust))[:PAGES_CITED]

    def locator_url(self) -> Optional[str]:
        return next((passage.url for passage in self.passages if page_path(passage.url) == SITE.locator_path), None)
