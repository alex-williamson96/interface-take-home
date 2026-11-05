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
    "Is Dupaco closed?",
    "Is Dupaco open?",
    "When does the Dupaco Foundation scholarship application open?",
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
    ("What year did Dupaco begin?", "1948"),
    ("What year did Dupaco open?", "1948"),
    ("When did Dupaco start?", "1948"),
    ("How old is Dupaco?", "1948"),
    ("When was Dupaco Credit Union established?", "1948"),
    ("When was the credit union founded?", "1948"),
    ("When did the Hy-Vee branch shut down?", "March 31, 2026"),
    ("When did the scholarship deadline pass?", "February 25, 2026"),
    ("When is the next nonprofit grant cycle?", "2027"),
    ("When was the Mineral Point branch ribbon cutting?", "September 29, 2022"),
    ("When did the Sycamore Street branch renovation finish?", "April 6, 2026"),
    ("When was the Dupaco Voices Building completed?", "May 19, 2022"),
    ("When did Dupaco acquire Home Savings Bank?", "2021"),
)

ANSWERS_THAT_MUST_STATE_A_FACT = (
    ("Can you tell me if the Hy-Vee branch is still open?", "March 31, 2026"),
    ("Is the Hy-Vee branch open?", "March 31, 2026"),
    ("Is the Hy-Vee branch closed?", "March 31, 2026"),
    ("Has the Hy-Vee branch closed?", "March 31, 2026"),
    ("Did the Hy-Vee branch close?", "March 31, 2026"),
    ("Is the Hy-Vee branch closing?", "March 31, 2026"),
    ("What is the last day for the Hy-Vee branch?", "March 31, 2026"),
    ("What is Dupaco's routing transit number?", "273974581"),
    ("What is the routing/transit number?", "273974581"),
    ("What's the routing number for Dupaco Community Credit Union?", "273974581"),
    ("What is your ABA number?", "273974581"),
    ("What has Forbes recognized Dupaco for?", "fifth"),
    ("How has Forbes recognized Dupaco?", "fifth"),
    ("Has Forbes recognized Dupaco?", "fifth"),
    ("What award did Dupaco get from Forbes?", "fifth"),
)

ROUTED_TO_THE_RIGHT_ANSWER = (
    ("What is the stop payment fee?", "$30.00"),
    ("What's the overdraft fee?", "$30.00"),
    ("What is the domestic wire fee?", "$25.00"),
    ("How much is a 60-month auto loan?", "APR"),
    ("What's a 12-month certificate going for?", "3.40%"),
    ("30-year mortgage?", "7.25%"),
    ("Is the Platinum Visa 9.9%?", "12.50%"),
    ("Who do I call about a charge on my credit card?", "800-373-7600"),
    ("What phone number do I call about my Visa charge?", "800-373-7600"),
    ("Who should I talk to about mortgage rates?", "800-373-7600"),
    ("What is the auto loan rate if I apply by phone?", "5.39%"),
    ("What is the savings rate if I open by phone?", "0.20%"),
    ("What APR do I pay on a 60-month auto loan?", "5.39%"),
    ("What rate do I pay on an auto loan?", "5.39%"),
    ("Can I pay with Apple Pay using my Dupaco credit card?", "Apple Pay"),
    ("How much does it cost to join Dupaco?", "$25"),
    ("HOW MANY BRANCHES DO YOU HAVE?", "22"),
    ("is the hy-vee branch still open", "March 31, 2026"),
)

FEES_AND_LIMITS_THE_SITE_DOES_NOT_STATE = (
    "How much is a lost debit card?",
    "What is the fee for a lost debit card?",
    "How much does it cost to replace a debit card?",
    "What is the minimum to open a 12-month certificate?",
    "How do I pay my car loan?",
    "How can I pay my car loan?",
    "How many members voted in the board election?",
    "How do I dispute a charge?",
    "How do I find the rates page?",
    "When will Dupaco close?",
    "When will the certificate special end?",
    "When are holidays?",
    "When did the Dupaco Voices Building open?",
    "When is the Dupaco Foundation nonprofit grant deadline?",
    "Is the Coralville Branch open yet?",
    "Can I pay my mortgage at a branch?",
)

NEWEST_DATE_NOT_AN_OLD_ONE = (
    ("When will Dupaco hold its next annual meeting?", "February 24, 2026", "2022"),
)

COUNTS_THE_SITE_STATES = (
    ("How many locations does Dupaco have?", "22"),
    ("How many Dupaco locations are there?", "22"),
    ("How many offices does Dupaco have?", "22"),
    ("What's the number of Dupaco branches?", "22"),
    ("How many branches are there in total?", "22"),
    ("How many full-service branches does Dupaco have?", "22"),
    ("How many members does Dupaco have?", "179,000"),
)

DATE_SENTENCES_SHARING_ONLY_A_NAME = (
    "When did the Key West branch open?",
    "When was the Key West branch built?",
    "When does the Key West branch close?",
    "When did the Sycamore Street branch open?",
)

QUESTIONS_NAMING_NO_BRANCH_THAT_MUST_NOT_BE_TOLD_ONE_CLOSED = (
    "Are you still open on Saturday?",
    "Is the Branch still open?",
    "Is the Dupaco Branch still open?",
    "Are your branches still open?",
)

FEWEST_CONFLICTS_WORTH_REVIEWING_BY_HAND = 10

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
            ("When does the Hy-Vee branch close?", "March 31, 2026 has passed. The site said: "),
            ("When will the Hy-Vee branch close?", "March 31, 2026 has passed. The site said: "),
        ):
            with self.subTest(question):
                self.assertTrue(self.system.answer(question).text.startswith(opening))

    def test_a_question_naming_no_branch_is_not_told_one_closed(self):
        for question in QUESTIONS_NAMING_NO_BRANCH_THAT_MUST_NOT_BE_TOLD_ONE_CLOSED:
            with self.subTest(question):
                self.assertNotIn("March 31, 2026", self.system.answer(question).text)

    def test_a_reworded_question_still_states_the_fact_it_asks_for(self):
        for question, fact in ANSWERS_THAT_MUST_STATE_A_FACT:
            with self.subTest(question):
                self.assertIn(fact, self.system.answer(question).text)

    def test_a_question_reaches_the_part_of_the_system_that_knows_the_answer(self):
        for question, fact in ROUTED_TO_THE_RIGHT_ANSWER:
            with self.subTest(question):
                self.assertIn(fact, self.system.answer(question).text)

    def test_a_how_do_i_question_about_rewards_is_answered_not_refused(self):
        self.assertIn("earn points", self.system.answer("How do I earn rewards with my Visa?").text)

    def test_a_will_question_prefers_the_newest_statement_to_an_old_one_written_as_ahead(self):
        for question, newest, older in NEWEST_DATE_NOT_AN_OLD_ONE:
            with self.subTest(question):
                answer = self.system.answer(question).text
                self.assertIn(newest, answer)
                self.assertNotIn(older, answer)

    def test_a_link_to_mortgage_rates_is_the_home_loan_page(self):
        self.assertIn("/personal/loans/home-loans", self.system.answer("What is the link for mortgage rates?").text)

    def test_a_what_time_question_about_a_branch_without_hours_is_refused(self):
        self.assertFalse(self.system.answer("What time does the Key West branch close?").confident)

    def test_a_past_tense_question_is_not_answered_with_a_date_still_ahead(self):
        self.assertNotIn("2027", self.system.answer("When were the Foundation grants awarded?").text)

    def test_a_count_is_the_newest_dupaco_states_about_itself(self):
        for question, count in COUNTS_THE_SITE_STATES:
            with self.subTest(question):
                self.assertIn(count, self.system.answer(question).text)

    def test_a_date_sentence_sharing_only_a_name_is_refused(self):
        for question in DATE_SENTENCES_SHARING_ONLY_A_NAME:
            with self.subTest(question):
                self.assertFalse(self.system.answer(question).confident, self.system.answer(question).text)

    def test_an_address_is_only_a_dupaco_branch_not_a_dealer_or_another_banks_atm(self):
        self.assertEqual(self.system.answer("What is the Galena address?").text, "11375 Oldenburg Ln., Galena, IL, 61036.")
        self.assertFalse(self.system.answer("What is the address of the Asbury branch?").confident)

    def test_the_annual_meeting_is_given_as_the_most_recent_one(self):
        answer = self.system.answer("When is the Dupaco annual meeting?").text
        self.assertTrue(answer.startswith("Most recently: "), answer)
        self.assertIn("held Tuesday, February 24, 2026", answer)

    def test_when_a_branch_opens_is_answered_with_hours(self):
        self.assertTrue(self.system.answer("When does the branch open?").text.startswith("Hours vary by branch"))

    def test_the_two_years_the_site_gives_for_the_foundation_are_noted(self):
        self.assertIn("2011, 2012", self.system.answer("When was the Dupaco Foundation established?").conflict_note)

    def test_conflicts_name_the_stale_pages_and_only_those(self):
        found = self.system.conflicts()
        def conflict_naming(*values: str):
            return next(c for c in found if set(values) <= set(c.values))
        self.assertIn("7.29%", conflict_naming("6.037%", "5.954%", "7.29%").resolution)
        self.assertIn("5.39%", conflict_naming("5.34%", "5.39%").resolution)
        self.assertIn("2.50%", conflict_naming("3.00%", "2.50%").resolution)
        self.assertEqual(conflict_naming("18", "22", "23", "24").resolution, "22")
        self.assertEqual(conflict_naming("2011", "2012").resolution, "2011")
        self.assertNotIn("243597822", " ".join(value for c in found for value in c.values))
        self.assertLessEqual(len(found), FEWEST_CONFLICTS_WORTH_REVIEWING_BY_HAND)

    def test_a_product_or_fact_the_site_does_not_list_is_refused(self):
        for question in (
            UNLISTED_PRODUCTS
            + PRODUCTS_FROM_ELSEWHERE_NAMED_AFTER_THE_NOUN
            + NOTHING_ON_THE_SITE_ANSWERS_THESE
            + FEES_AND_LIMITS_THE_SITE_DOES_NOT_STATE
        ):
            with self.subTest(question):
                self.assertFalse(self.system.answer(question).confident)

    def test_a_question_about_how_rates_work_is_refused_rather_than_answered_with_a_rate_list(self):
        for question in QUESTIONS_THAT_ARE_NOT_ASKING_FOR_A_RATE:
            with self.subTest(question):
                self.assertFalse(self.system.answer(question).confident)


if __name__ == "__main__":
    unittest.main()
