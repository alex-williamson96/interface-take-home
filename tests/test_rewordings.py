import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "harness"), str(ROOT / "submission")]

from knowledge import KnowledgeSystem  # noqa: E402
from run_eval import load_snapshots  # noqa: E402

SNAPSHOTS = ROOT / "snapshots"
SNAPSHOT_ZIPS = ROOT / "snapshots_zip"

REWORDED_AND_PLAIN = (
    ("What do certificates of deposit pay?", "What are your CD rates?"),
    ("What do your CDs pay these days?", "What are your CD rates?"),
    ("What are Dupaco CD rates?", "What are your CD rates?"),
    ("What is the annual percentage yield on a 12 month CD?", "What is the APY on a 12 month CD?"),
    ("What is the rate on a 12 month CD for a member?", "What is the rate on a 12 month CD?"),
    ("Could you share the 15-year mortgage rate?", "What is the 15-year mortgage rate?"),
    ("Could you share your savings rates?", "What are your savings rates?"),
    ("What are your business card rates?", "What are your business credit card rates?"),
    ("What is the cash-out refinance rate?", "What is the home equity refinance rate?"),
    ("What is the auto loan rate for my new Honda?", "What is the auto loan rate?"),
)

QUESTIONS_THAT_ARE_NOT_ASKING_FOR_A_RATE = (
    "Does my savings account interest compound daily?",
    "Will my CD earn interest if I close it early?",
    "How is interest calculated on a certificate?",
    "When are dividends paid on savings accounts?",
    "What percent down do I need for a mortgage?",
    "Why did my credit card interest go up?",
)

PRODUCTS_FROM_ELSEWHERE_NAMED_AFTER_THE_NOUN = (
    "What is the rate on a mortgage backed by the VA?",
    "What is the rate on a mortgage insured by the FHA?",
    "What is the savings rate for an account called Jump Start?",
    "What is the rate on a savings account at Chase?",
    "What rate does Wells Fargo charge on a mortgage?",
)

NOTHING_ON_THE_SITE_ANSWERS_THESE = (
    "Can you give me the lobby hours for the Mullan Avenue branch?",
    "What is the address of the Chicago branch?",
    "What's the routing number for Chase?",
    "When did Dupaco open its first branch?",
    "Who won the Super Bowl?",
    "Tell me a joke",
)

DATES_THE_SITE_STATES = (
    ("When did the Asbury branch close?", "Oct. 1, 2024"),
    ("When did the Asbury branch open?", "2003"),
    ("When does the Hy-Vee branch close?", "March 31, 2026"),
    ("What date is the Hy-Vee branch closing?", "March 31, 2026"),
    ("When was Dupaco founded?", "1948"),
    ("What year was Dupaco founded?", "1948"),
    ("When was Dupaco established?", "1948"),
    ("When was the Dupaco Foundation established?", "2011"),
    ("When was the Dupaco Foundation founded?", "2011"),
    ("When is the next Gift of Innovation grant cycle?", "2026"),
)

UNLISTED_PRODUCTS = (
    "What is the rate on a 5/1 ARM?",
    "What is the 7/1 ARM rate?",
    "What is the FHA mortgage rate?",
    "What is the VA mortgage rate?",
    "What is the jumbo mortgage rate?",
    "What is the student loan rate?",
    "What is the construction loan rate?",
    "What is the land loan rate?",
    "What is the rate on a 7-month CD?",
    "What is the 3-year auto loan rate?",
    "What is the APY on Prime Business Savings?",
    "What is the Jump Start savings APY?",
)


@unittest.skipUnless(
    any(SNAPSHOTS.glob("*/manifest.json")) or any(SNAPSHOT_ZIPS.glob("*.zip")),
    "needs the snapshot zips, which are not committed",
)
class RewordingsAgainstRealSnapshots(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.system = KnowledgeSystem()
        for snapshot in load_snapshots(SNAPSHOTS):
            cls.system.ingest(snapshot)

    def test_a_reworded_question_gets_the_same_answer_as_its_plain_wording(self):
        for reworded, plain in REWORDED_AND_PLAIN:
            with self.subTest(reworded):
                plain_answer = self.system.answer(plain)
                self.assertTrue(plain_answer.confident, plain)
                self.assertEqual(self.system.answer(reworded).text, plain_answer.text)

    def test_a_date_question_gets_the_date_the_site_states_in_one_sentence(self):
        for question, date in DATES_THE_SITE_STATES:
            with self.subTest(question):
                answer = self.system.answer(question)
                self.assertTrue(answer.confident)
                self.assertIn(date, answer.text)
                self.assertNotIn("membership", answer.text)

    def test_a_will_question_about_closures_already_past_says_nothing_is_upcoming(self):
        answer = self.system.answer("When will the branch close?").text
        self.assertTrue(answer.startswith("The site shows nothing upcoming."), answer)
        self.assertIn("March 31, 2026", answer)
        self.assertIn("Oct. 1, 2024", answer)

    def test_a_date_question_about_an_unnamed_branch_asks_which_and_lists_only_those_closing(self):
        answer = self.system.answer("When did the branch close?").text
        self.assertIn("which branch", answer)
        self.assertIn("Hy-Vee", answer)
        self.assertIn("Asbury", answer)
        self.assertNotIn("Visa", answer)

    def test_a_closed_branch_is_described_as_closed_however_the_question_is_worded(self):
        for question, opening in (
            ("Is the Hy-Vee branch still open today (October 2026)?", "No. "),
            ("Is the Asbury branch still open?", "No. "),
            ("When does the Hy-Vee branch close?", "That date has passed: "),
            ("When will the Hy-Vee branch close?", "That date has passed: "),
        ):
            with self.subTest(question):
                self.assertTrue(self.system.answer(question).text.startswith(opening))

    def test_when_a_branch_opens_is_answered_with_hours(self):
        self.assertTrue(self.system.answer("When does the branch open?").text.startswith("Hours vary by branch"))

    def test_the_two_years_the_site_gives_for_the_foundation_are_noted(self):
        self.assertIn("2011, 2012", self.system.answer("When was the Dupaco Foundation established?").conflict_note)

    def test_a_product_or_fact_the_site_does_not_list_is_refused(self):
        for question in UNLISTED_PRODUCTS + PRODUCTS_FROM_ELSEWHERE_NAMED_AFTER_THE_NOUN + NOTHING_ON_THE_SITE_ANSWERS_THESE:
            with self.subTest(question):
                self.assertFalse(self.system.answer(question).confident)

    def test_a_question_about_how_rates_work_is_refused_rather_than_answered_with_a_rate_list(self):
        for question in QUESTIONS_THAT_ARE_NOT_ASKING_FOR_A_RATE:
            with self.subTest(question):
                self.assertFalse(self.system.answer(question).confident)


if __name__ == "__main__":
    unittest.main()
