# Knowledge system for a credit union website

Answers members' questions from dated downloads of a credit union's website: the current value, the right tier, a source, and "I can't confirm that" when the site doesn't say. See [NOTES.md](NOTES.md) for how it decides what's current.

`submission/solution.py` provides the `build()` the harness expects, with `ingest`, `answer` and `conflicts`. No API keys or packages are needed. Python 3.9 or newer.

## Layout

```
submission/    the system
  knowledge.py   ingest, answer, conflicts, and choosing rate rows
  question.py    what a question is asking for
  rate_facts.py  reading rate tables
  prose.py       searching page text; dates, counts, fees
  conflicts.py   contradictions in the latest snapshot
tests/         unit tests, plus rewordings checked against the real snapshots
eval/          public_eval.jsonl from the kit, own_rewordings.jsonl written for this system
harness/       the kit's scorer
starter/       the kit's naive solution
```

## Running it

The snapshots are not in this repository. Put the five zips in `snapshots_zip/`; the scorer unpacks them into `snapshots/` on its first run. Without them there is nothing to score, and the tests that need real snapshots are skipped.

```bash
python3 harness/run_eval.py --submission submission --eval eval/public_eval.jsonl
python3 harness/run_eval.py --submission submission --eval eval/own_rewordings.jsonl
python3 -m unittest discover -s tests
```

The public eval scores 0.9411. It doesn't score conflicts, because the kit ships no gold list for the real site.
