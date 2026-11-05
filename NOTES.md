# Notes

No API keys and no packages: plain rules on the Python standard library, no LLM.

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

- Table rows on any page are compared with the rate pages by product, term, balance tier and overlapping model years, and only the same kind of value, so tiers and rate vs APY never look like conflicts. The rate page wins.
- Branch counts: the newest dated statement wins over older and undated pages.
- The Foundation's founding year: the year most statements give wins.

Rates and fees stated in page text are not compared.

## Known limits

- General how-to and "what do you offer" questions can return loosely related text.
- A count can come from a sentence about the total when the question narrows it, such as `How many Dubuque branches does Dupaco have?`.
- `eval/own_rewordings.jsonl` was written to find misses and then used to fix them, so its score is not a blind measure.
