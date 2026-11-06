# Knowledge system for a credit union website

Answers members' questions from dated downloads of a credit union's website: the current value, the right tier, a source, and "I can't confirm that" when the site doesn't say. See [NOTES.md](NOTES.md) for how it decides what's current.

`submission/solution.py` provides the `build()` the harness expects, with `ingest`, `answer` and `conflicts`. Python 3.9 or newer. It runs with no packages or keys; set `ANTHROPIC_API_KEY` and install `requirements.txt` (Python 3.10 or newer) to add the optional LLM steps, which [NOTES.md](NOTES.md) explains.

## Layout

```
submission/    the system
  knowledge.py   ingest, answer, conflicts, and choosing rate rows
  question.py    what a question is asking for, in rate and fee terms
  rate_facts.py  reading rate tables
  conflicts.py   contradictions in the latest snapshot
  search.py      the registry of question kinds, and searching page text
  kind_*.py      one kind of question each: hours, dates, counts, contact details, open-ended
  asked.py       what every kind shares: the QuestionKind type and what a question asks for
  page_answers.py  choosing sentences from a page
  passages.py    the passage index built from each snapshot
  fees.py        the fee schedule
  text_basics.py words, search terms, Passage and Found
  site_profile.py everything specific to this credit union
  llm.py         optional steps: reword a question, judge answers to open-ended ones
  phrasings.txt  question wording the LLM is shown, from the public eval
tests/         unit tests, plus rewordings checked against the real snapshots
eval/          public_eval.jsonl from the kit; the others written for this system
harness/       the kit's scorer
starter/       the kit's naive solution
```

## Running it

The snapshots are not in this repository. Put the five zips in `snapshots_zip/`; the scorer unpacks them into `snapshots/` on its first run. Without them there is nothing to score, and the tests that need real snapshots are skipped.

```bash
python3 harness/run_eval.py --submission submission --eval eval/public_eval.jsonl
python3 harness/run_eval.py --submission submission --eval eval/own_rewordings.jsonl
python3 harness/run_eval.py --submission submission --eval eval/blind_rewordings.jsonl
python3 -m unittest discover -s tests
```

The public eval scores 0.9411 accuracy with or without a key. On the blind rewordings, accuracy is 0.76 with rules alone and 0.97 with a key. Neither eval scores conflicts, because the kit ships no gold list for the real site.
