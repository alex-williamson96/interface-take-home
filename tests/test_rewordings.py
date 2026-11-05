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

    def test_a_product_the_site_does_not_list_is_refused(self):
        for question in UNLISTED_PRODUCTS + PRODUCTS_FROM_ELSEWHERE_NAMED_AFTER_THE_NOUN:
            with self.subTest(question):
                self.assertFalse(self.system.answer(question).confident)

    def test_a_question_about_how_rates_work_is_refused_rather_than_answered_with_a_rate_list(self):
        for question in QUESTIONS_THAT_ARE_NOT_ASKING_FOR_A_RATE:
            with self.subTest(question):
                self.assertFalse(self.system.answer(question).confident)


if __name__ == "__main__":
    unittest.main()
