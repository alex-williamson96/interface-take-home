import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "harness"), str(ROOT / "submission")]

from contract import Page, Snapshot  # noqa: E402
from knowledge import KnowledgeSystem  # noqa: E402

RATES_URL = "https://www.dupaco.com/rates"
CALCULATOR_URL = "https://www.dupaco.com/calculators/vehicle-affordability"
PRODUCT_URL = "https://www.dupaco.com/personal/savings/certificates"
HOME_EQUITY_URL = "https://www.dupaco.com/personal/loans/home-equity"


def certificate_sheet(jumbo_apy: str) -> str:
    return f"""Special Certificates

| Certificate | Dividend Rate | Annual Percentage Yield (APY) | Min. to Earn |
| --- | --- | --- | --- |
| 10 Month Fixed Jumbo Certificate Special | 3.86% | {jumbo_apy}1 | $100,000 |
| 10 Month Fixed Certificate Special | 3.76% | 3.80%2 | $1,000 |

Share Savings

| Account Type | Balance Tier | Dividend Rate | Annual Percentage Yield (APY)1 | Min. to Open | Min. to Earn |
| --- | --- | --- | --- | --- | --- |
| Share Savings | $25,000+ | 0.20% | 0.20%1 | $25.00 | $25,000.00 |
| Share Savings | $10,000 – $24,999.99 | 0.15% | 0.15%1 | $25.00 | $10,000.00 |
"""


def snapshot(taken_on: str, *pages: tuple[str, str]) -> Snapshot:
    return Snapshot(
        snapshot_id=taken_on,
        taken_on=taken_on,
        pages=[Page(url=url, title="", markdown=text, fetched_at=taken_on) for url, text in pages],
    )


def system_with_two_dates() -> KnowledgeSystem:
    system = KnowledgeSystem()
    system.ingest(snapshot("2026-05-12", (RATES_URL, certificate_sheet("3.90%"))))
    system.ingest(snapshot("2026-09-28", (RATES_URL, certificate_sheet("4.00%"))))
    return system


def dated_certificate_table(apy: str, effective: str) -> str:
    return f"""Special Certificates

| Certificate | Annual Percentage Yield (APY) |
| --- | --- |
| 10 Month Fixed Certificate Special | {apy} |

Rates are effective as of {effective}.
"""


def system_with_sheet_and_product_page(sheet_date: str, product_date: str) -> KnowledgeSystem:
    system = KnowledgeSystem()
    system.ingest(
        snapshot(
            "2026-05-12",
            (RATES_URL, dated_certificate_table("3.80%", sheet_date)),
            (PRODUCT_URL, dated_certificate_table("3.70%", product_date)),
        )
    )
    return system


def article(published: str, body: str) -> str:
    return f"1 min read\n\n{published}\n\n# Article\n\n{body}\n"


def system_with_pages(*pages: tuple[str, str]) -> KnowledgeSystem:
    system = KnowledgeSystem()
    system.ingest(snapshot("2026-09-28", *pages))
    return system


CONTACT_URL = "https://www.dupaco.com/contact"
NEWS_URL = "https://www.dupaco.com/newsroom/"
CONTACT_PAGE = """**Phone:** 800-373-7600

**Routing Number:** 273974581

### Dupaco Credit Union

Dupaco Branch

11375 Oldenburg Ln., Galena, IL, 61036

Closed

[branch or ATM](https://www.dupaco.com/contact#locator)
"""
HOURS_ARTICLE = article(
    "June 1, 2026",
    "Galena branch hours are:\n\n**Lobby**\n\nMonday-Friday: 8:30 a.m.-5 p.m.\n\nSaturday: 9 a.m.-noon",
)


class AnswersFromPageText(unittest.TestCase):
    def test_routing_number_is_stated_alone_and_cited(self):
        answer = system_with_pages((CONTACT_URL, CONTACT_PAGE)).answer("What is the routing number?")
        self.assertEqual(answer.text, "273974581.")
        self.assertEqual(answer.sources[0].url, CONTACT_URL)

    def test_address_of_a_listed_branch_is_found_and_an_unlisted_branch_refuses(self):
        system = system_with_pages((CONTACT_URL, CONTACT_PAGE))
        self.assertIn("11375 Oldenburg", system.answer("What is the address of the Galena branch?").text)
        self.assertFalse(system.answer("What is the address of the Chicago branch?").confident)

    def test_hours_for_a_branch_the_site_gives_no_hours_for_refuse(self):
        system = system_with_pages((NEWS_URL + "galena", HOURS_ARTICLE))
        self.assertIn("8:30", system.answer("What are the lobby hours?").text)
        self.assertFalse(system.answer("What are the lobby hours for the Mullan Avenue branch?").confident)

    def test_a_count_comes_from_the_newest_dated_statement_repeated_across_pages(self):
        older = "It has 23 branch office locations."
        newest = "It has 22 branch office locations."
        system = system_with_pages(
            (NEWS_URL + "a", article("January 1, 2026", older)),
            (NEWS_URL + "b", article("January 2, 2026", older)),
            (NEWS_URL + "c", article("January 3, 2026", older)),
            (NEWS_URL + "d", article("April 1, 2026", newest)),
            (NEWS_URL + "e", article("April 2, 2026", newest)),
            (NEWS_URL + "f", article("May 1, 2026", "Members can visit 5,600 participating branches.")),
            ("https://www.dupaco.com/about", "We now have 18 branches."),
        )
        self.assertIn("22 branch", system.answer("How many branches does Dupaco have?").text)

    def test_a_related_article_teaser_is_not_read(self):
        page = article("June 1, 2026", "Dupaco opened a learning lab.") + (
            "\n## Handpicked for You\n\nThe Forbes award arrived this year in Dubuque.\n"
        )
        self.assertFalse(system_with_pages((NEWS_URL + "a", page)).answer("What Forbes award did Dupaco get?").confident)

    def test_a_rate_or_fee_question_never_falls_back_to_page_text(self):
        system = system_with_pages(
            (NEWS_URL + "a", article("June 1, 2026", "The construction loan interest rate is 9.00%. The overdraft fee is $30."))
        )
        for question in ("What is the construction loan rate?", "What is the overdraft fee?"):
            self.assertFalse(system.answer(question).confident, question)

    def test_a_single_word_match_in_body_text_refuses(self):
        page = article("June 1, 2026", "Protecting your pet is no joke.")
        self.assertFalse(system_with_pages((NEWS_URL + "a", page)).answer("Tell me a joke").confident)

    def test_a_link_question_gets_the_page_people_link_to(self):
        answer = system_with_pages((CONTACT_URL, CONTACT_PAGE)).answer("What is the URL for the branch and ATM locator?")
        self.assertEqual(answer.text, "https://www.dupaco.com/contact")

    def test_a_link_to_rates_is_the_product_page_that_shows_them(self):
        sheet = dated_certificate_table("3.80%", "4/2/2026")
        answer = system_with_pages((RATES_URL, sheet), (PRODUCT_URL, sheet)).answer("What link shows your CD rates?")
        self.assertEqual(answer.text, PRODUCT_URL)

    def test_a_rate_question_without_a_rate_word_never_falls_back_to_page_text(self):
        page = article("June 1, 2026", "The current 30-year fixed averaged 6.04%. The 17-month certificate special is 4.10%.")
        system = system_with_pages((NEWS_URL + "a", page))
        for question in ("What's the current 30-year fixed?", "How much is the 17-month certificate special?"):
            self.assertFalse(system.answer(question).confident, question)


class AnswerBehaviour(unittest.TestCase):
    def test_as_of_answers_from_the_newest_snapshot_on_or_before_that_date(self):
        system = system_with_two_dates()
        question = "What is the 10-month jumbo certificate rate?"
        self.assertIn("3.90%", system.answer(question, as_of="2026-05-31").text)
        self.assertIn("4.00%", system.answer(question).text)

    def test_as_of_before_the_first_snapshot_refuses(self):
        answer = system_with_two_dates().answer("What is the 10-month jumbo certificate rate?", as_of="2026-01-01")
        self.assertFalse(answer.confident)

    def test_no_snapshots_refuses_with_no_numbers(self):
        answer = KnowledgeSystem().answer("What is the 10-month jumbo certificate rate?")
        self.assertFalse(answer.confident)
        self.assertFalse(any(character.isdigit() for character in answer.text))

    def test_footnote_digits_never_reach_the_answer(self):
        text = system_with_two_dates().answer("What is the 10-month jumbo certificate rate?").text
        self.assertNotIn("4.00%1", text)

    def test_jumbo_tier_is_left_out_unless_asked_for(self):
        text = system_with_two_dates().answer("What is the 10-month certificate rate?").text
        self.assertIn("3.80%", text)
        self.assertNotIn("4.00%", text)

    def test_balance_in_the_question_selects_its_tier(self):
        text = system_with_two_dates().answer("What is the APY on Share Savings with $12,000?").text
        self.assertIn("0.15%", text)
        self.assertNotIn("0.20%", text)

    def test_calendar_date_in_a_question_is_not_read_as_a_model_year(self):
        system = KnowledgeSystem()
        sheet = """Auto Loans

| Loan Program | Term | Annual Percentage Rate (As Low As) |
| --- | --- | --- |
| 2017-20 Model Year | 60 Months | 6.34% APR |
"""
        system.ingest(snapshot("2026-09-28", (RATES_URL, sheet)))
        self.assertIn("6.34%", system.answer("What was the 60-month auto rate in May 2026?").text)

    def test_refinance_question_gets_the_refinance_row_not_the_purchase_row(self):
        sheet = """Home Loans

| Program | Rate | Points | APR | \\*Payment Example |
| --- | --- | --- | --- | --- |
| Purchase: 15-Year Fixed Conventional | 6.75% | 0 | 6.88% | $1,327.36 |
| Refinance: 15-Year Fixed Conventional | 6.80% | 0 | 6.90% | $1,330.00 |
"""
        system = KnowledgeSystem()
        system.ingest(snapshot("2026-09-28", (RATES_URL, sheet)))
        text = system.answer("What are your refinance rates for a 15-year loan?").text
        self.assertIn("6.80%", text)
        self.assertNotIn("6.75%", text)

    def test_and_older_model_year_row_excludes_newer_vehicles(self):
        sheet = """Auto Loans

| Loan Program | Term | Annual Percentage Rate (As Low As) |
| --- | --- | --- |
| 2017-20 Model Year | 60 Months | 6.34% APR |
| 2016 Model Year (and older) | 48 Months | 8.59% APR |
"""
        system = KnowledgeSystem()
        system.ingest(snapshot("2026-09-28", (RATES_URL, sheet)))
        self.assertFalse(system.answer("What is the 48-month auto rate on a 2020 car?").confident)

    def test_calculator_pages_never_supply_a_rate(self):
        calculator = """Auto Loans

| Loan Program | Term | Annual Percentage Rate (As Low As) |
| --- | --- | --- |
| 2024-27 Model Year | 60 Months | 5.34% APR |
"""
        system = KnowledgeSystem()
        system.ingest(snapshot("2026-09-28", (CALCULATOR_URL, calculator)))
        self.assertFalse(system.answer("What is the 60-month auto rate?").confident)


MORTGAGE_SHEET = """Home Loans

| Program | Rate | Points | APR | \\*Payment Example |
| --- | --- | --- | --- | --- |
| Purchase: 30-Year Fixed Conventional $300,000 or less | 7.25% | 0 | 7.32% | $2,046.53 |
| Purchase: 30-Year Fixed Conventional $200,000 or less | 7.25% | 0 | 7.34% | $1,364.52 |
| Purchase: 15-Year Fixed Conventional | 6.75% | 0 | 6.88% | $1,327.36 |

Cash-Out Refinance

| Program | Rate | Points | APR | \\*Payment Example |
| --- | --- | --- | --- | --- |
| Refinance: 15-Year Fixed Conventional | 5.75% | 0 | 5.87% | $1,300.00 |

Home Loan Refinance

| Program | Rate | Points | APR | \\*Payment Example |
| --- | --- | --- | --- | --- |
| Refinance: 15-Year Fixed Conventional | 6.00% | 0 | 6.12% | $1,310.00 |
"""

AUTO_SHEET = """Auto Loans

| Loan Program | Term | Annual Percentage Rate (As Low As) |
| --- | --- | --- |
| 2024-27 Model Year | 48 Months | 5.19% APR |
| 2024-27 Model Year | 60 Months | 5.39% APR |
| 2017-20 Model Year | 60 Months | 6.34% APR |
"""

HELOC_SHEET = """Home Equity Line of Credit

| Product | APR (As Low As) |
| --- | --- |
| Home Equity Line of Credit (HELOC) | 6.25% |
| HELOC Intro Rate | 1.99% |
"""

OLD_FORMAT_DEPOSITS = """Certificates

Special

| Term | Dividend Rate | Annual Percentage Yield (APY) | Min. to Earn |
| --- | --- | --- | --- |
| 10 Month Fixed Certificate Special | 3.76% | 3.80% | $1,000 |

[Open my certificate](https://www.dupaco.com/open)

Regular

| Term | Dividend Rate | Annual Percentage Yield (APY)1 | Min. to Earn |
| --- | --- | --- | --- |
| 12 Month | 2.88% | 2.90% | $1,000 |

Money Market

[Explore](https://www.dupaco.com/money-market)

Achieve

| Balance Tier | Dividend Rate for 1st 6 Months | Annual Percentage Yield (APY)\\* for 1st 6 Months | Dividend Rate After Promotional Period | APY\\* After Promotional Period | Min. to Open | Min. to Earn |
| --- | --- | --- | --- | --- | --- | --- |
| $25,000-$99,999.99 | 4.00% | 3.66% | 3.20% | 3.25% | $25,000 | $25,000 |
"""


def system_with(*sheets: str) -> KnowledgeSystem:
    system = KnowledgeSystem()
    system.ingest(snapshot("2026-09-28", *((RATES_URL, sheet) for sheet in sheets)))
    return system


class TableFormats(unittest.TestCase):
    def test_table_under_a_bare_heading_takes_its_family_from_the_section_above(self):
        text = system_with(OLD_FORMAT_DEPOSITS).answer("What is the 12-month certificate rate?").text
        self.assertIn("2.90%", text)

    def test_promotional_table_states_both_the_promotional_and_the_later_apy(self):
        text = system_with(OLD_FORMAT_DEPOSITS).answer("What is the Achieve money market APY?").text
        self.assertIn("3.66%", text)
        self.assertIn("3.25%", text)

    def test_business_rows_with_fewer_matching_words_still_beat_personal_rows(self):
        personal = "Money Market Accounts\n\nInvestor's Choice Money Market\n\n| Balance Tier | Annual Percentage Yield (APY) |\n| --- | --- |\n| $25,000+ | 0.35% |\n"
        business = "Investor's Choice\n\n| Balance Tier | Annual Percentage Yield (APY) |\n| --- | --- |\n| $25,000+ | 0.30% |\n"
        system = KnowledgeSystem()
        system.ingest(snapshot("2026-09-28", (RATES_URL, personal), ("https://www.dupaco.com/business-rates", business)))
        text = system.answer("What is the business Investor's Choice money market APY?").text
        self.assertIn("0.30%", text)


class QuestionWording(unittest.TestCase):
    def test_best_loan_rate_is_the_lowest(self):
        self.assertIn("5.19%", system_with(AUTO_SHEET).answer("What's the best auto loan rate?").text)

    def test_at_least_and_most_current_do_not_pick_a_single_row(self):
        certificates = system_with_two_dates().answer("What certificate rates can I get with at least $1,000?").text
        self.assertIn("3.80%", certificates)
        mortgages = system_with(MORTGAGE_SHEET).answer("What is the most current 30-year mortgage rate?").text
        self.assertIn("7.32%", mortgages)
        self.assertIn("7.34%", mortgages)

    def test_questions_about_paying_or_fees_are_not_rate_questions(self):
        system = system_with(AUTO_SHEET)
        for question in ("Can I pay my auto loan by phone?", "Is there a fee to pay off my car loan early?"):
            self.assertFalse(system.answer(question).confident, question)

    def test_balance_above_the_jumbo_minimum_gets_the_jumbo_rate(self):
        text = system_with_two_dates().answer("What is the 10-month certificate rate on $150,000?").text
        self.assertIn("4.00%", text)
        self.assertNotIn("3.80%", text)

    def test_highest_certificate_rate_considers_jumbo(self):
        self.assertIn("4.00%", system_with_two_dates().answer("What is the highest certificate rate?").text)

    def test_loan_amount_selects_only_the_smallest_ceiling_that_fits(self):
        text = system_with(MORTGAGE_SHEET).answer("What is the 30-year mortgage rate for a $150,000 loan?").text
        self.assertIn("7.34%", text)
        self.assertNotIn("7.32%", text)

    def test_amounts_written_without_a_plain_dollar_figure_select_their_tier(self):
        system = system_with_two_dates()
        for wording in ("$12k", "12,000 dollars", "12,000", "12000"):
            text = system.answer(f"What is the APY on Share Savings with {wording}?").text
            self.assertIn("0.15%", text, wording)
            self.assertNotIn("0.20%", text, wording)

    def test_refinancing_a_car_returns_neither_mortgage_nor_purchase_rates(self):
        system = system_with(MORTGAGE_SHEET, AUTO_SHEET)
        for question in ("What's the rate to refinance my car?", "What rate can I get to refinance my auto loan?"):
            self.assertFalse(system.answer(question).confident, question)

    def test_quantities_and_curly_apostrophes_are_not_read_as_unknown_product_names(self):
        system = system_with_two_dates()
        for question in ("What’s the 10mo certificate rate?", "What is the certificate rate on $10k?"):
            self.assertTrue(system.answer(question).confident, question)

    def test_spelled_out_term_selects_that_term(self):
        text = system_with(AUTO_SHEET).answer("What is the five year auto loan rate on a 2025 car?").text
        self.assertIn("5.39%", text)
        self.assertNotIn("5.19%", text)

    def test_refinance_answer_leaves_out_cash_out_unless_asked(self):
        text = system_with(MORTGAGE_SHEET).answer("What is the 15-year refinance rate?").text
        self.assertIn("6.12%", text)
        self.assertNotIn("5.87%", text)

    def test_heloc_intro_rate_appears_only_when_asked_for(self):
        system = system_with(HELOC_SHEET)
        self.assertNotIn("1.99%", system.answer("What is the HELOC rate?").text)
        self.assertNotIn("6.25%", system.answer("What is the HELOC intro rate?").text)

    def test_apr_followed_by_a_year_is_a_model_year_not_april(self):
        text = system_with(AUTO_SHEET).answer("What is the 60-month auto APR 2025 model year?").text
        self.assertIn("5.39%", text)
        self.assertNotIn("6.34%", text)

    def test_numeric_date_in_a_question_is_not_read_as_a_model_year(self):
        text = system_with(AUTO_SHEET).answer("What was the 60-month auto rate as of 5/15/2026?").text
        self.assertIn("6.34%", text)

    def test_thirty_year_fixed_is_a_mortgage_question_without_the_word_mortgage(self):
        self.assertTrue(system_with(MORTGAGE_SHEET).answer("What's your rate for a 30-year fixed?").confident)

    def test_named_product_with_no_row_refuses(self):
        system = system_with_two_dates()
        for question in ("What is the Jump Start savings APY?", "What is the APY on Prime Business Savings?"):
            self.assertFalse(system.answer(question).confident, question)

    def test_word_shared_by_a_whole_family_does_not_stand_in_for_a_missing_product(self):
        sheet = "Investor's Choice Money Market\n\n| Balance Tier | Annual Percentage Yield (APY) |\n| --- | --- |\n| $25,000+ | 0.35% |\n"
        self.assertFalse(system_with(sheet).answer("What is the Achieve money market APY?").confident)

    def test_a_word_that_names_no_product_does_not_refuse(self):
        system = system_with_two_dates()
        plain = system.answer("What is the 10 month CD APY?").text
        for reworded in (
            "What is the 10 month CD APY for a member?",
            "Could you share the 10 month certificate of deposit annual percentage yield?",
        ):
            self.assertEqual(system.answer(reworded).text, plain, reworded)

    def test_a_capitalized_name_after_the_product_refuses(self):
        self.assertFalse(system_with_two_dates().answer("What is the savings rate at Chase?").confident)

    def test_a_vehicle_make_does_not_refuse(self):
        self.assertTrue(system_with(AUTO_SHEET).answer("What is the 60 month auto rate for my Honda?").confident)

    def test_a_question_about_how_rates_work_refuses(self):
        self.assertFalse(system_with_two_dates().answer("Why did my CD rate go down?").confident)

    def test_a_yes_or_no_percent_question_leads_with_the_answer(self):
        system = system_with_two_dates()
        yes = system.answer("Do any savings tiers pay 0.20% APY?").text
        self.assertTrue(yes.startswith("Yes: Share Savings $25,000+: 0.20% APY."), yes)
        no = system.answer("Do any savings tiers pay 0.35% APY?").text
        self.assertTrue(no.startswith("No. "), no)

    def test_a_percent_compared_against_gets_the_list_without_a_yes_or_no(self):
        answer = system_with_two_dates().answer("Do any savings tiers pay more than 0.10% APY?").text
        self.assertTrue(answer.startswith("Share Savings"), answer)

    def test_a_product_page_dated_after_the_rate_sheet_wins_when_they_disagree(self):
        answer = system_with_sheet_and_product_page("4/2/2026", "4/6/2026").answer("What is the 10 month CD APY?")
        self.assertIn("3.70%", answer.text)
        self.assertNotIn("3.80%", answer.text)
        self.assertEqual(answer.sources[0].url, PRODUCT_URL)

    def test_a_cash_out_question_keeps_rows_taken_from_a_newer_product_page(self):
        def refinance_table(heading, first_rate, effective):
            return f"""{heading}

| Loan | Rate | APR |
| --- | --- | --- |
| Refinance: 20-Year Fixed Conventional | {first_rate} | 6.10% |
| Refinance: 15-Year Fixed Conventional | 5.50% | 5.60% |

Rates are effective as of {effective}.
"""

        system = KnowledgeSystem()
        system.ingest(
            snapshot(
                "2026-05-12",
                (RATES_URL, refinance_table("Home Equity Loan", "6.00%", "4/2/2026")),
                (HOME_EQUITY_URL, refinance_table("Home Equity\n\nCash-Out Refinance", "5.90%", "4/6/2026")),
            )
        )
        text = system.answer("What is the cash-out refinance rate?").text
        self.assertIn("5.90%", text)
        self.assertIn("5.50%", text)
        self.assertNotIn("6.00%", text)

    def test_the_rate_sheet_wins_over_a_product_page_with_an_older_or_equal_date(self):
        for product_date in ("4/1/2026", "4/2/2026"):
            answer = system_with_sheet_and_product_page("4/2/2026", product_date).answer("What is the 10 month CD APY?")
            self.assertIn("3.80%", answer.text, product_date)


class HarnessLoading(unittest.TestCase):
    def test_solution_loads_the_way_the_harness_loads_it_without_a_sys_modules_entry(self):
        spec = importlib.util.spec_from_file_location("solution", ROOT / "submission" / "solution.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertIsInstance(module.build(), KnowledgeSystem)


if __name__ == "__main__":
    unittest.main()
