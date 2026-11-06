# Notes

Rules on the Python standard library answer rates, fees, dates, counts, addresses and hours. An optional LLM helps the rules understand questions and judges answers to open-ended ones. It never writes an answer of its own.

## API key

`ANTHROPIC_API_KEY` is optional and uses a paid API, Claude Sonnet 5.5, through `submission/llm.py`. Without a key, without the package, or when a call fails, the rules answer alone.

- **Rewording.** The model restates each question in the wording the rules understand, such as "five year car loan" as "60-month auto loan". It sees only the question and the wording of the public practice questions, never the site. If the rules refuse the rewording, they answer the original question.
- **Judging open-ended answers.** Questions with no dedicated rule get a wider search, and the model reads the rules' answer and the passages found. If the rules have an answer, the model can keep it or reject it, which refuses, but never replace it. If the rules have none, the model picks a passage and an excerpt, which is used only if it appears word for word in that passage.

Rate and fee answers do not use the judging step, so every value still comes from the snapshots.

| Questions | Measure | Rules only | With the LLM, 3 runs |
|---|---|---|---|
| `eval/public_eval.jsonl` | Accuracy | 0.941 | 0.941 |
| | Final score | 0.941 | 0.928 to 0.934 |
| `eval/blind_rewordings.jsonl` | Accuracy | 0.760 | 0.962 to 0.973 |
| | Paraphrase consistency | 0.732 | 1.0 |
| | Final score | 0.742 | 0.955 to 0.968 |
| `eval/dev_rewordings.jsonl` | Accuracy | 0.697 | 0.971 |
| `eval/topic_questions.jsonl` | Accuracy | 0.406 | 0.580 to 0.587 |

Final scores leave out conflicts. No run gave a stale value. p95 latency is about 2.5 to 3.4 seconds on these sets, and about 6 on the topic questions, where refusals make more calls, against 0.01 to 0.02 for rules alone. Snapshots load in about 5 seconds.

Logging from `knowledge` and `llm` records what the model decided and every failed call. Member questions appear only at debug level.

## What the evals decided

- **Measured the claim first.** The public eval said 0.94, but it had been tuned against. A blind set in members' own words scored 0.72 with rules alone, which is why the LLM was added at all.
- **Chose the model by score.** Blind accuracy was 0.91 on Opus 5.5, 0.95 on Sonnet 5.5 and 0.93 on Haiku 5.5, with Haiku also losing public points. Sonnet costs half what Opus does.
- **Took away the model's power to replace answers.** Letting it swap a rule answer for its own excerpt helped new topics but dropped public accuracy to 0.84 to 0.89, so it can now only reject one.
- **Removed a structured classifier that missed its bar.** Replacing the rewording with structured fields scored 0.94 to 0.96 on the blind set, or 0.95 for rates only, and was slower. It also could not remove any regexes, since the rules still need them without a key.
- **Pinned behaviour before refactoring.** Moving site details into `site_profile.py` and search into question kinds changed none of the 675 pinned answers.

Rates and fees stay in rules on purpose: one stale number zeroes a question, and tiers such as 60-month and 84-month are near-identical text that needs exact matching. The rules are tuned to this site, and no RAG or knowledge graph version was built to compare.

## What "current" means

- **Answers come from one snapshot.** Without `as_of`, the newest. With `as_of`, or a date in the words of a rate question, the newest on or before that date. Earlier than the first snapshot refuses.
- **Rates come from rate tables only:** `/rates`, `/business-rates` and the `/personal` and `/business` product pages, never calculators, blogs, news or landing pages. Within a row the newest stated effective date wins, and the rate sheet wins ties and undated rows.
- **Fees come from the fee schedule rows.** The schedule leaves card fees to disclosures, so those come from the credit card pages.
- **Other facts come from page text.** Site pages beat news, news beats blogs, and PDFs come last. Among close matches the newest wins.
- **Counts** come from the newest dated statement Dupaco makes about itself.
- **Dates** must come from a sentence that states what was asked. A date that has passed is called out. A past event with no date in its sentence is given its article's date, labelled as such.
- **Refusal is the default.** A named product with no matching row, or a question no passage answers, gets "I can't confirm that" and no numbers.

## Conflicts

`conflicts()` lists contradictions still live in the latest snapshot. A rate that simply changed between snapshots is not a conflict.

- Table rows on any page are compared with the rate pages by product, term, balance tier and overlapping model years, and only the same kind of value, so tiers and rate vs APY never look like conflicts. The rate page wins. Auto loans get one entry per term; mortgages get one entry per page.
- Branch counts: the newest dated statement wins over older and undated pages.
- The Foundation's founding year: the year most statements give wins.
- Five more come from `submission/reviewed_conflicts.json`, each listed only while every wording it names is still in the latest snapshot. It stores short wordings, and quotes are read from the snapshot.

Rates and fees stated in page text are not compared, apart from any in that file.

That file is specific to this site and was not found by rules. A one-off scan, not in this repository, had Haiku 5.5 extract 2,018 claims from 530 pages of the latest snapshot and then look for contradictions. Two runs gave 10 and 12 candidates, and a person checked them against the pages: five were real and new, one was already listed, and the rest were false, such as a press dateline read as a headquarters and a discount that changed between years. A second check by Sonnet 5.5 still let false ones through and changed between runs, so the scan does not run at scoring: `conflicts()` needs no key and gives the same list every time. Picking the winners was a judgment call. The site cannot settle the Mini Max age, and the Voices Building's newest statement is the one outnumbered.

`eval/own_conflicts_gold.json` is a hand-labelled list of 14 and only tests our own judgment, since we wrote both sides. New contradictions on later snapshots would need another scan and review.

## Known limits

- General how-to and "what do you offer" questions can return loosely related text.
- A count can come from a sentence about the total when the question narrows it, such as `How many Dubuque branches does Dupaco have?`.
- `eval/own_rewordings.jsonl` was written to find misses and then used to fix them, so its score is not a blind measure.
- `eval/blind_rewordings.jsonl` was written before seeing any answers and only its aggregate scores were read. The model and the design of the LLM steps were chosen partly by that score, and it was checked many times, so it is flattered and is now a development score. It moves by about one question between runs.
- `eval/dev_rewordings.jsonl` rewords the public questions, the same wording the model is shown, so it says little about new topics. `eval/topic_questions.jsonl` covers those: an LLM wrote it from 69 pages of the latest snapshot, half answerable, half asking what the page does not state. Answers must contain one exact phrase, so its scores understate correct answers worded differently.
- Answerable questions on topics outside the practice set are still mostly missed, at about 0.36.
