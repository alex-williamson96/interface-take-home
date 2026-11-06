"""Ask models for contradictions in the latest snapshot, for a person to review.

    python3 tools/scan_for_conflicts.py [--out results/conflict_scan.json]

Needs ANTHROPIC_API_KEY and the snapshots. The candidates include false ones, so
nothing reads the output: entries a person confirms go in submission/reviewed_conflicts.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "harness"), str(ROOT / "submission")]

from passages import PassageIndex  # noqa: E402
from rate_facts import page_path  # noqa: E402
from run_eval import load_snapshots  # noqa: E402

EXTRACTING_AND_CROSS_CHECKING_MODEL = "claude-haiku-5-5"
VERIFYING_MODEL = "claude-sonnet-5-5"
MAX_TOKENS_FOR_ONE_PAGE = 4000
MAX_TOKENS_FOR_THE_CROSS_CHECK = 48000
MAX_TOKENS_FOR_ONE_VERDICT = 1500
PAGES_READ_AT_ONCE = 10
VERDICTS_AT_ONCE = 6

EXTRACT = """From this page of a credit union's website, list factual claims stated as true now about the credit union's own products, services, branches, policies or organisation that could be checked against another page: hours, addresses, phone numbers, membership rules, minimums and limits, amounts, terms, counts, eligibility, dates of its own programs.
Skip general financial advice, marketing, third parties, and events described as past news. Skip interest rates and APYs.
subject: the specific thing, such as "Galena branch" or "Holiday Club account". attribute: what is stated, such as "lobby hours" or "minimum to open". value: the stated value, short. quote: the sentence, copied character for character.
Return an empty list if there are none."""

CROSS_CHECK = """These are claims from different pages of one credit union's website. Find real contradictions: claims about the same specific thing, for the same tier and conditions, whose values cannot both be true. Different branches, products, tiers, account types or conditions are not contradictions, and neither are a general statement and a more specific one, or the same value written differently. Return each contradiction with at least two claim ids. Return few and only clear ones."""

VERIFY = """You check a claimed contradiction on one credit union's website. Decide whether a careful member could be told two things that cannot both be true right now, about the same specific thing. Answer false for: a dateline or place an article was written; disclosure boilerplate; the same fact worded differently; different tiers, products, conditions or programs; a general statement beside a specific one; old how-to steps for an app; marketing. Each quote is exact, so judge what the sentences really say."""


def _schema(**properties: dict) -> dict:
    return {
        "type": "json_schema",
        "schema": {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        },
    }


def _list_of(**properties: dict) -> dict:
    return {"type": "array", "items": _schema(**properties)["schema"]}


TEXT = {"type": "string"}
CLAIMS = _schema(claims=_list_of(subject=TEXT, attribute=TEXT, value=TEXT, quote=TEXT))
CONTRADICTIONS = _schema(
    contradictions=_list_of(topic=TEXT, claim_ids={"type": "array", "items": {"type": "integer"}}, why=TEXT)
)
VERDICT = _schema(real={"type": "boolean"}, reason=TEXT)


def _parsed(response, name: str) -> dict:
    if response.stop_reason != "end_turn":
        raise ValueError(f"{name} stopped early: {response.stop_reason}")
    return json.loads(next(block.text for block in response.content if block.type == "text"))


def _whole_words(text: str) -> str:
    return " ".join(text.split())


def claims_on_page(client: anthropic.Anthropic, url: str, passages: list) -> list[dict]:
    text = "\n".join(passage.text for passage in passages)
    response = client.messages.create(
        model=EXTRACTING_AND_CROSS_CHECKING_MODEL,
        max_tokens=MAX_TOKENS_FOR_ONE_PAGE,
        system=EXTRACT,
        output_config={"effort": "low", "format": CLAIMS},
        messages=[{"role": "user", "content": f"{passages[0].title}\n{url}\n\n{text}"}],
    )
    if response.stop_reason != "end_turn":
        print(f"skipped {url}: {response.stop_reason}", file=sys.stderr)
        return []
    published = passages[0].published if passages[0].has_its_own_date else None
    on_the_page = _whole_words(text)
    return [
        {**claim, "url": url, "published": published}
        for claim in _parsed(response, url)["claims"]
        if _whole_words(claim["quote"]) in on_the_page
    ]


def contradictions_among(client: anthropic.Anthropic, claims: list[dict]) -> list[dict]:
    lines = "\n".join(
        f"[{number}] {claim['subject']} | {claim['attribute']} | {claim['value']} | {page_path(claim['url'])}"
        for number, claim in enumerate(claims)
    )
    with client.messages.stream(
        model=EXTRACTING_AND_CROSS_CHECKING_MODEL,
        max_tokens=MAX_TOKENS_FOR_THE_CROSS_CHECK,
        system=CROSS_CHECK,
        output_config={"effort": "medium", "format": CONTRADICTIONS},
        messages=[{"role": "user", "content": lines}],
    ) as stream:
        return _parsed(stream.get_final_message(), "cross-check")["contradictions"]


def candidate_with_verdict(client: anthropic.Anthropic, found: dict, claims: list[dict]) -> dict:
    statements = [claims[number] for number in found["claim_ids"] if number < len(claims)]
    described = "\n".join(
        f"- {claim['url']} ({claim['published'] or 'undated'}): {claim['quote']}" for claim in statements
    )
    response = client.messages.create(
        model=VERIFYING_MODEL,
        max_tokens=MAX_TOKENS_FOR_ONE_VERDICT,
        system=VERIFY,
        output_config={"effort": "low", "format": VERDICT},
        messages=[{"role": "user", "content": f"{found['topic']}\n{described}"}],
    )
    verdict = _parsed(response, found["topic"])
    return {
        "topic": found["topic"],
        "why": found["why"],
        "kept_by_verifier": verdict["real"],
        "verifier_reason": verdict["reason"],
        "statements": statements,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="List candidate contradictions for a person to review.")
    parser.add_argument("--out", type=Path, default=ROOT / "results" / "conflict_scan.json")
    arguments = parser.parse_args()

    latest = load_snapshots(ROOT / "snapshots")[-1]
    index = PassageIndex(latest.pages, latest.taken_on)
    client = anthropic.Anthropic(max_retries=4, timeout=500)

    with ThreadPoolExecutor(PAGES_READ_AT_ONCE) as pool:
        pages = [
            pool.submit(claims_on_page, client, url, passages) for url, passages in index.passages_of.items()
        ]
        claims = [claim for page in pages for claim in page.result()]
    print(f"{len(claims)} claims from {len(pages)} pages")

    found = contradictions_among(client, claims)
    with ThreadPoolExecutor(VERDICTS_AT_ONCE) as pool:
        candidates = list(pool.map(lambda each: candidate_with_verdict(client, each, claims), found))

    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    arguments.out.write_text(json.dumps(candidates, indent=1), encoding="utf-8")
    kept = sum(candidate["kept_by_verifier"] for candidate in candidates)
    print(f"{len(candidates)} candidates, {kept} kept by the verifier, written to {arguments.out}")


if __name__ == "__main__":
    main()
