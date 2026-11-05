from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from rate_facts import parse_term_months, stem, TERM, WORD

RATE_INTENT = re.compile(
    r"\b(rates?|apys?|aprs?|interest|dividends?|yields?|earns?|earning|pays?|paying|charges?|percent|would i get)\b",
    re.I,
)
NON_RATE_TOPIC = re.compile(
    r"\b(fees?|penalt(?:y|ies)|overdr(?:aft|aw\w*)|stop payment|deductible|minimum|"
    r"(?:apple|google|samsung) pay|earn (?:points|rewards|cash back)|percent down|down payment)\b",
    re.I,
)
ASKS_HOW_RATES_WORK = re.compile(r"^\s*(?:why|when|will|how (?:is|are|often|does|do)|(?:does|do) my)\b", re.I)
PAYING_A_BILL = re.compile(r"\b(?:can|do|should|must|have to)(?: i)? pay\b|\bpay (?:off|my)\b", re.I)
CALENDAR_DATE = re.compile(
    r"\b(jan|feb|mar|april|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+(\d{1,2},?\s+)?20\d\d\b"
    r"|\b\d{1,2}/\d{1,2}/20\d\d\b"
    r"|\b20\d\d-\d{2}-\d{2}\b"
    r"|\b(?:as of|in|during)\s+20\d\d\b(?!\s+(?:model|vehicle|car|truck))",
    re.I,
)
LINK_INTENT = re.compile(r"\b(link|url|website|web page|webpage)\b", re.I)
HOW_TO_ASKED = re.compile(r"\bhow (do|can|should) (i|we)\b|\bhow to\b", re.I)
DIVIDEND_ASKED = re.compile(r"\bdividends?\b", re.I)
BUSINESS_ASKED = re.compile(r"\bbusiness\b", re.I)
BEST_ASKED = re.compile(r"\bbest\b", re.I)
HIGHEST_ASKED = re.compile(r"\b(highest|top|(?:pays?|earns?) the most)\b", re.I)
LOWEST_ASKED = re.compile(r"\b(lowest|cheapest)\b|(?<!\bat )\bleast\b", re.I)
YES_OR_NO_ABOUT_A_PERCENT = re.compile(r"^\s*(?:do|does|is|are)\b.*?(\d+(?:\.\d+)?)\s*%", re.I)
MODEL_YEAR = re.compile(r"\b(20\d\d)\b")
AMOUNT = re.compile(r"(\$\s*)?\b(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\s*(k|thousand|dollars)?\b", re.I)
SHORTEST_BARE_AMOUNT_DIGITS = 5
DOLLARS_PER_THOUSAND = 1000
LOAN_FAMILIES = frozenset({"home_improvement", "home_equity", "mortgage", "auto", "recreation", "personal_loan", "card"})

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "twelve": 12, "fifteen": 15, "seventeen": 17, "eighteen": 18, "twenty": 20, "twenty-four": 24, "thirty": 30,
    "thirty-six": 36, "forty-eight": 48, "sixty": 60, "seventy-two": 72, "eighty-four": 84,
}
SPELLED_OUT_TERM = re.compile(
    r"\b(" + "|".join(sorted(NUMBER_WORDS, key=len, reverse=True)) + r")(?=[\s-]+(?:months?|mos?\b|years?|yrs?\b))",
    re.I,
)

REFINANCE_SYNONYM = re.compile(r"\brefi\b|\brefinanc\w*", re.I)
PHRASES_AS_ONE_WORD = (
    (REFINANCE_SYNONYM, "refinance"),
    (re.compile(r"\bcash[- ]out\b", re.I), "refinance"),
    (re.compile(r"\bannual percentage yield\b", re.I), "apy"),
    (re.compile(r"\bannual percentage rate\b", re.I), "apr"),
    (re.compile(r"\bcertificates? of deposit\b", re.I), "certificate"),
    (re.compile(r"\b(?:can|could|would|will) you share\b", re.I), "tell"),
)

FAMILY_SYNONYMS = (
    ("ira", re.compile(r"\biras?\b|\broth\b|retirement", re.I)),
    ("home_improvement", re.compile(r"home improvement", re.I)),
    ("home_equity", re.compile(r"home equity|\bheloc\b|\bcash[- ]out\b", re.I)),
    ("mortgage", re.compile(r"mortgages?\b|home loans?\b|\b\d+[- ]year fixed\b|\bhouse\b", re.I)),
    ("auto", re.compile(r"\b(auto|car|cars|vehicles?|truck|motorcycles?)\b", re.I)),
    ("recreation", re.compile(r"\b(boats?|rv|rvs|atvs?|snowmobiles?|jet skis?)\b", re.I)),
    ("personal_loan", re.compile(r"personal loans?", re.I)),
    ("card", re.compile(r"\bvisa\b|credit cards?|business cards?|balance transfers?|\bplatinum\b|\brewards card\b", re.I)),
    ("certificate", re.compile(r"\bcds?\b|certificates?|\b\d+[\s-]*months?\s+(?:fixed\s+)?special\b", re.I)),
    ("money_market", re.compile(r"money market|investor[’']?s choice|\bachieve\b", re.I)),
    ("checking", re.compile(r"checking", re.I)),
    ("savings", re.compile(r"saving|holiday club|launchpad|you[- ]name[- ]it|high[- ]yield|\bbright\b|\bhsas?\b", re.I)),
    ("mortgage", REFINANCE_SYNONYM),
)

WORDS_THAT_DO_NOT_NARROW = frozenset(
    stem(word)
    for word in """
    a about account all also an and any are as at available balance be because been best between borrow borrowing
    both business but buy buying by can car card cd certificate charge checking cheapest come could credit current
    currently did dollar do does dupaco each every finance financing find fixed for from get getting give go going
    good got had has have hello help here hi highest home house how i i'd i'll i'm i've if in interest interested
    into is it just know lately latest least like list loan looking lowest make many may me might mo model money
    month more mortgage most much must my need new not of offer on only open opening or our out over per percent
    planning please provide purchase rate really recent regular retirement right same savings say see should so
    some standard still take taking tell thank thanks than that the their them there these they think this those
    thousand to today too top truck trying under up us used very vehicle visa want wanted was we we're were what
    whats what's when where which who will with wondering would year yet yr you you're your
    apy apr dividend yield earn earning pay paying now auto equity market motorcycle personal
    """.split()
)
PRODUCT_NOUNS = frozenset(
    stem(word)
    for word in """
    rate apy apr yield dividend interest savings account checking money market certificate cd ira loan mortgage
    refinance heloc card visa club special
    """.split()
)
MODIFIER_BETWEEN_NAME_AND_NOUN = stem("business")
CAPITALIZED_AFTER_FIRST_WORD = re.compile(r"(?<=[\s-])[A-Z][A-Za-z']*")
FAMILIES_WHERE_CAPITALS_ARE_VEHICLE_MAKES = frozenset({"auto", "recreation"})


@dataclass(frozen=True)
class RateQuestion:
    family: str
    words: frozenset[str]
    product_words: frozenset[str]
    term_months: Optional[int]
    amount: Optional[float]
    model_year: Optional[int]
    business: bool
    wants_dividend: bool
    wants_highest: bool
    wants_lowest: bool
    percent_asked_about: Optional[float] = None


def parse_rate_question(question: str) -> Optional[RateQuestion]:
    if not _asks_for_a_rate(question):
        return None
    family = next((name for name, pattern in FAMILY_SYNONYMS if pattern.search(question)), None)
    if family is None:
        return None
    undated = CALENDAR_DATE.sub(" ", _with_digit_terms(question))
    year = MODEL_YEAR.search(undated)
    best_means_highest = bool(BEST_ASKED.search(question)) and family not in LOAN_FAMILIES
    best_means_lowest = bool(BEST_ASKED.search(question)) and family in LOAN_FAMILIES
    expanded = _with_phrases_as_one_word(undated)
    words_in_order = [stem(word) for word in WORD.findall(expanded.lower())]
    capitals_name_products = family not in FAMILIES_WHERE_CAPITALS_ARE_VEHICLE_MAKES
    percent_asked = YES_OR_NO_ABOUT_A_PERCENT.search(question)
    return RateQuestion(
        percent_asked_about=float(percent_asked.group(1)) if percent_asked else None,
        family=family,
        words=frozenset(word for word in words_in_order if _can_narrow(word)),
        product_words=_words_before_a_product_noun(words_in_order)
        | (_capitalized_words(expanded) if capitals_name_products else frozenset()),
        term_months=parse_term_months(undated),
        amount=_amount_in(undated),
        model_year=int(year.group(1)) if year else None,
        business=bool(BUSINESS_ASKED.search(question)),
        wants_dividend=bool(DIVIDEND_ASKED.search(question)),
        wants_highest=best_means_highest or bool(HIGHEST_ASKED.search(question)),
        wants_lowest=best_means_lowest or bool(LOWEST_ASKED.search(question)),
    )


def _asks_for_a_rate(question: str) -> bool:
    if not RATE_INTENT.search(question):
        return False
    other_topics = (NON_RATE_TOPIC, PAYING_A_BILL, LINK_INTENT, HOW_TO_ASKED, ASKS_HOW_RATES_WORK)
    return not any(topic.search(question) for topic in other_topics)


def _with_digit_terms(question: str) -> str:
    return SPELLED_OUT_TERM.sub(lambda spelled: str(NUMBER_WORDS[spelled.group(1).lower()]), question)


def _amount_in(question: str) -> Optional[float]:
    for found in AMOUNT.finditer(question):
        dollar_sign, whole, fraction, unit = found.groups()
        comma_grouped = "," in whole
        too_long_for_a_year_or_term = len(whole) >= SHORTEST_BARE_AMOUNT_DIGITS
        if dollar_sign or unit or comma_grouped or too_long_for_a_year_or_term:
            value = float(whole.replace(",", "") + (fraction or ""))
            in_thousands = bool(unit) and unit.lower() in ("k", "thousand")
            return value * DOLLARS_PER_THOUSAND if in_thousands else value
    return None


def _with_phrases_as_one_word(question: str) -> str:
    expanded = AMOUNT.sub(" ", TERM.sub(" ", question)).replace("’", "'")
    for phrase, word in PHRASES_AS_ONE_WORD:
        expanded = phrase.sub(word, expanded)
    return expanded


def _can_narrow(word: str) -> bool:
    return word not in WORDS_THAT_DO_NOT_NARROW and not word.isdigit()


def _capitalized_words(question: str) -> frozenset[str]:
    stems = (stem(word.lower()) for word in CAPITALIZED_AFTER_FIRST_WORD.findall(question))
    return frozenset(word for word in stems if _can_narrow(word))


def _words_before_a_product_noun(words_in_order: list[str]) -> frozenset[str]:
    named = set()
    for position, word in enumerate(words_in_order):
        if word not in PRODUCT_NOUNS:
            continue
        before = position - 1
        if before >= 0 and words_in_order[before] == MODIFIER_BETWEEN_NAME_AND_NOUN:
            before -= 1
        if before >= 0 and _can_narrow(words_in_order[before]):
            named.add(words_in_order[before])
    return frozenset(named)
