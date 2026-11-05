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

    def test_a_when_question_whose_only_date_is_inside_a_question_refuses(self):
        page = article("x", "Did you know the Galena branch opened in 1948?")
        self.assertFalse(system_with_pages((NEWS_URL + "a", page)).answer("When did the Galena branch open?").confident)

    def test_a_question_naming_a_branch_leaves_out_sentences_elsewhere_on_the_page_about_others(self):
        page = article(
            "June 1, 2026",
            "The Galena branch will close March 31, 2026.\n\n# Elsewhere\n\nThe Asbury branch will close June 1, 2026.",
        )
        answer = system_with_pages((NEWS_URL + "a", page)).answer("When will the Galena branch close?")
        self.assertIn("March 31, 2026", answer.text)
        self.assertNotIn("Asbury", answer.text)

    def test_a_date_question_naming_nothing_states_one_date_not_every_date_on_the_page(self):
        page = article(
            "June 1, 2026",
            "The Galena branch will close March 31, 2026.\n\n# Elsewhere\n\nThe Asbury branch will close June 1, 2026.",
        )
        answer = system_with_pages((NEWS_URL + "a", page)).answer("When will the branch close?").text
        self.assertEqual(("Galena" in answer) + ("Asbury" in answer), 1, answer)

    def test_an_initial_does_not_end_a_sentence(self):
        page = article("June 1, 2026", "The Hoefer Foundation was established in 2011 to honor Robert W. Hoefer of Dubuque.")
        answer = system_with_pages((NEWS_URL + "a", page)).answer("When was the Hoefer Foundation established?").text
        self.assertTrue(answer.endswith("Robert W. Hoefer of Dubuque."), answer)

    def test_a_will_question_about_a_date_already_past_says_so(self):
        page = article("June 1, 2025", "The Galena branch will close March 31, 2026.")
        system = system_with_pages((NEWS_URL + "a", page))
        said = "March 31, 2026 has passed. The site said: "
        self.assertTrue(system.answer("When will the Galena branch close?").text.startswith(said))
        self.assertTrue(system.answer("When does the Galena branch close?").text.startswith(said))
        self.assertNotIn("passed", system.answer("When did the Galena branch close?").text)

    def test_a_date_sentence_sharing_only_the_name_does_not_answer_what_was_asked(self):
        page = article("June 1, 2026", "The Hoefer Foundation was established in 2011.")
        answer = system_with_pages((NEWS_URL + "a", page)).answer("When does the Hoefer Foundation scholarship application open?")
        self.assertFalse(answer.confident)

    def test_a_present_tense_question_about_a_past_event_gets_the_latest_as_most_recent(self):
        older = article("June 1, 2021", "The Galena branch ribbon cutting was held June 1, 2021.")
        newer = article("June 1, 2024", "The Galena branch ribbon cutting was held June 1, 2024.")
        answer = system_with_pages((NEWS_URL + "a", older), (NEWS_URL + "b", newer)).answer("When is the Galena branch ribbon cutting?").text
        self.assertIn("Most recently: ", answer)
        self.assertIn("June 1, 2024", answer)
        self.assertNotIn("2021", answer)

    def test_most_recent_skips_a_later_date_still_written_as_ahead(self):
        held = article("June 3, 2024", "The Galena branch ribbon cutting was held June 1, 2024.")
        recording = article("June 2, 2024", "The Galena branch ribbon cutting recording will be online June 9, 2024.")
        system = system_with_pages((NEWS_URL + "a", held), (NEWS_URL + "b", recording))
        self.assertIn("was held June 1, 2024", system.answer("When is the Galena branch ribbon cutting?").text)

    def test_which_branch_leaves_out_a_page_with_no_date_about_what_was_asked(self):
        system = KnowledgeSystem()
        system.ingest(Snapshot("s", "2026-09-28", [
            Page(NEWS_URL + "a", "Galena branch closing", article("June 1, 2026", "Our Galena team began work in 2020."), "2026-09-28"),
        ]))
        self.assertFalse(system.answer("When did the branch close?").confident)

    def test_a_sentence_already_in_the_past_tense_is_not_told_its_date_has_passed(self):
        page = article("June 1, 2021", "The Galena branch ribbon cutting was held June 1, 2021.")
        answer = system_with_pages((NEWS_URL + "a", page)).answer("When is the Galena branch ribbon cutting?").text
        self.assertNotIn("passed", answer)
        self.assertIn("June 1, 2021", answer)

    def test_still_open_is_answered_no_after_a_stated_closing_and_yes_before_it(self):
        def asked_with(closing: str) -> str:
            page = article("June 1, 2025", f"The Galena branch will close {closing}.")
            return system_with_pages((NEWS_URL + "a", page)).answer("Is the Galena branch still open?").text
        self.assertTrue(asked_with("March 31, 2026").startswith("No. "))
        self.assertTrue(asked_with("March 31, 2027").startswith("Yes, for now. "))

    def test_still_open_refuses_when_only_a_schedule_says_closed(self):
        page = article("June 1, 2026", "Galena branch hours are:\n\n**Lobby**\n\nMonday-Friday: 8:30 a.m.-5 p.m.\n\nSunday: Closed")
        self.assertFalse(system_with_pages((NEWS_URL + "a", page)).answer("Are the Galena branch hours still open?").confident)

    def test_a_count_another_organization_states_about_itself_is_not_dupacos(self):
        page = article("June 1, 2026", "We work together with over 1,200 member institutions.")
        self.assertFalse(system_with_pages((NEWS_URL + "a", page)).answer("How many members does Dupaco have?").confident)

    def test_still_open_refuses_when_the_site_states_no_closing(self):
        page = article("June 1, 2025", "Dupaco opened the Galena branch in 2003.")
        self.assertFalse(system_with_pages((NEWS_URL + "a", page)).answer("Is the Galena branch still open?").confident)

    def test_a_will_question_about_an_unnamed_branch_lists_only_upcoming_dates(self):
        closing = article("June 1, 2026", "This branch will close on {}.")
        def asked_with(*dates: str) -> str:
            system = KnowledgeSystem()
            system.ingest(Snapshot("s", "2026-09-28", [
                Page(f"{NEWS_URL}{date[-4:]}", f"Branch closing {date[-4:]}", closing.format(date), "2026-09-28")
                for date in dates
            ]))
            return system.answer("When will the branch close?").text
        self.assertTrue(asked_with("March 31, 2026", "Oct. 1, 2024").startswith("The site shows nothing upcoming."))
        upcoming = asked_with("March 31, 2027", "Oct. 1, 2024")
        self.assertIn("March 31, 2027", upcoming)
        self.assertNotIn("Oct. 1, 2024", upcoming)

    def test_a_date_question_about_an_unnamed_branch_asks_which_when_pages_differ(self):
        closing = article("June 1, 2026", "This branch closed on {}.")
        system = KnowledgeSystem()
        system.ingest(Snapshot("s", "2026-09-28", [
            Page(NEWS_URL + "a", "Galena branch closing | Dupaco", closing.format("March 31, 2026"), "2026-09-28"),
            Page(NEWS_URL + "b", "Asbury branch closing | Dupaco", closing.format("Oct. 1, 2024"), "2026-09-28"),
        ]))
        answer = system.answer("When did the branch close?").text
        self.assertIn("which branch", answer)
        self.assertIn("Galena branch closing", answer)
        self.assertIn("Asbury branch closing", answer)

    def test_which_branch_keeps_the_best_matching_pages_when_more_match_than_it_lists(self):
        site_page_that_ranks_above_news = "https://www.dupaco.com/about/closing"
        def page(url: str, number: int) -> Page:
            return Page(url, f"Branch closing {number}", article("June 1, 2026", f"This branch closed on March {number}, 2026."), "2026-09-28")
        pages = [page(f"{NEWS_URL}{number}", number) for number in range(1, 6)]
        pages.append(page(site_page_that_ranks_above_news, 6))
        system = KnowledgeSystem()
        system.ingest(Snapshot("s", "2026-09-28", pages))
        self.assertIn(site_page_that_ranks_above_news, [source.url for source in system.answer("When did the branch close?").sources])

    def test_when_a_branch_opens_is_answered_with_its_hours(self):
        system = system_with_pages((NEWS_URL + "galena", HOURS_ARTICLE))
        for question in ("When does the branch open?", "When does the Galena branch open?"):
            self.assertIn("8:30 a.m.-5 p.m.", system.answer(question).text, question)

    def test_a_first_of_something_the_site_never_mentions_refuses(self):
        page = article("June 1, 2026", "Dupaco will open the first floor of its new branch in 2022.")
        self.assertFalse(system_with_pages((NEWS_URL + "a", page)).answer("When did Dupaco open its first branch?").confident)

    def test_founded_is_not_read_as_foundation_or_as_the_past_of_find(self):
        founded = article("June 1, 2026", "Dupaco was founded in 1948 by ten employees.")
        foundation = article("June 1, 2026", "The Dupaco Foundation started in 2011.")
        found = article("June 1, 2026", "In 2020 we found Dupaco to be the best.")
        system = system_with_pages((NEWS_URL + "a", foundation), (NEWS_URL + "b", found), (NEWS_URL + "c", founded))
        for question in ("When was Dupaco founded?", "What year was Dupaco founded?"):
            self.assertIn("1948", system.answer(question).text, question)

    def test_an_article_dated_only_by_its_byline_does_not_count_as_new(self):
        old = "# Old news\n\nWritten by [Emily](https://www.dupaco.com/a) | Oct 8, 2021 12:57:34 PM\n\nFounded in 1948, Dupaco has 143,000 members."
        new = article("May 5, 2026", "Founded in 1948, Dupaco has 179,000 members.")
        answer = system_with_pages((NEWS_URL + "old", old), (NEWS_URL + "new", new)).answer("When was Dupaco founded?")
        self.assertEqual(answer.sources[0].url, NEWS_URL + "new")

    def test_a_date_question_answers_with_one_sentence_preferring_a_full_date_over_a_year(self):
        page = article(
            "June 1, 2024",
            "Dupaco opened the Asbury branch in 2003.\n\n# Closing\n\nThe Asbury branch last day of service is Oct. 1, 2024.",
        )
        answer = system_with_pages((NEWS_URL + "a", page)).answer("When did the Asbury branch close?").text
        self.assertIn("Oct. 1, 2024", answer)
        self.assertNotIn("2003", answer)

    def test_a_date_sentence_about_what_was_asked_beats_one_that_only_shares_the_name(self):
        page = article("June 1, 2026", "Hoefer Foundation awards announced April 2026. Established in 2011 to honor Robert.")
        answer = system_with_pages((NEWS_URL + "a", page)).answer("When was the Hoefer Foundation established?").text
        self.assertIn("2011", answer)
        self.assertNotIn("April 2026", answer)

    def test_a_date_question_refuses_when_the_name_is_only_in_the_page_title(self):
        page = article("June 1, 2026", "The credit union was founded in 1948.")
        system = KnowledgeSystem()
        system.ingest(Snapshot("s", "2026-09-28", [Page(NEWS_URL + "a", "Hoefer Foundation awards", page, "2026-09-28")]))
        self.assertFalse(system.answer("When was the Hoefer Foundation founded?").confident)

    def test_a_named_thing_founded_is_answered_by_established_but_dupaco_itself_stays_founded(self):
        system = system_with_pages(
            (NEWS_URL + "a", article("June 1, 2026", "The Hoefer Foundation was established in 2011.")),
            (NEWS_URL + "b", article("May 1, 2026", "Dupaco was founded in 1948.")),
        )
        self.assertIn("2011", system.answer("When was the Hoefer Foundation founded?").text)
        self.assertIn("1948", system.answer("When was Dupaco established?").text)

    def test_years_that_disagree_about_a_founding_are_noted_and_agreement_is_not(self):
        established = article("June 1, 2026", "The Hoefer Foundation was established in 2011.")
        founding = article("June 2, 2026", "Since its founding in 2012, the Hoefer Foundation has given grants.")
        question = "When was the Hoefer Foundation established?"
        self.assertIsNone(system_with_pages((NEWS_URL + "a", established)).answer(question).conflict_note)
        note = system_with_pages((NEWS_URL + "a", established), (NEWS_URL + "b", founding)).answer(question).conflict_note
        self.assertIn("2011, 2012", note)

    def test_a_date_answer_stops_at_the_clause_holding_the_date(self):
        page = article("June 1, 2026", "Founded in 1948 by ten employees, membership has grown to more than 179,000.")
        answer = system_with_pages((NEWS_URL + "a", page)).answer("When was Dupaco founded?").text
        self.assertTrue(answer.endswith("Founded in 1948 by ten employees."), answer)

    def test_which_branch_lists_only_pages_titled_with_what_was_asked(self):
        system = KnowledgeSystem()
        system.ingest(Snapshot("s", "2026-09-28", [
            Page(NEWS_URL + "a", "Galena branch closure", article("June 1, 2026", "This branch did close in 2026."), "2026-09-28"),
            Page(NEWS_URL + "b", "Asbury branch closing", article("June 1, 2026", "This branch did close in 2024."), "2026-09-28"),
            Page(NEWS_URL + "c", "Bank acquisition", article("June 1, 2026", "Old branches did close in 2022."), "2026-09-28"),
        ]))
        answer = system.answer("When did the branch close?").text
        self.assertIn("Galena branch closure", answer)
        self.assertIn("Asbury branch closing", answer)
        self.assertNotIn("Bank acquisition", answer)

    def test_a_byline_date_is_not_the_answer_to_a_date_question(self):
        page = "New branch office to open in Coralville\n\nWritten by [Emily](https://www.dupaco.com/a) | Oct 8, 2021 12:57:34 PM"
        answer = system_with_pages((NEWS_URL + "a", page)).answer("When will the new branch office in Coralville open?")
        self.assertFalse(answer.confident)

    def test_a_question_naming_nothing_can_answer_from_elsewhere_on_the_page_and_quotes_it(self):
        page = article(
            "June 1, 2026",
            "Members earn rewards on every savings deposit made online.\n\n# Joining\n\nMembers join online with a savings deposit.",
        )
        answer = system_with_pages((NEWS_URL + "a", page)).answer("Can members join with a savings deposit online?")
        for sentence in ("Members earn rewards", "Members join online"):
            self.assertIn(sentence, answer.text)
            self.assertIn(sentence, answer.sources[0].quote)

    def test_a_phone_number_for_another_company_refuses(self):
        system = system_with_pages((CONTACT_URL, CONTACT_PAGE))
        self.assertFalse(system.answer("What is Chase's phone number?").confident)

    def test_a_phone_number_for_another_company_refuses_even_in_lowercase(self):
        system = system_with_pages((CONTACT_URL, CONTACT_PAGE))
        self.assertFalse(system.answer("what is the phone number for chase?").confident)

    def test_a_question_mentioning_a_phone_is_not_asking_for_a_number(self):
        system = system_with_pages((CONTACT_URL, CONTACT_PAGE))
        self.assertFalse(system.answer("Can I deposit a check with my phone?").confident)

    def test_a_phone_question_naming_no_one_gets_the_locator_number(self):
        system = system_with_pages((CONTACT_URL, CONTACT_PAGE))
        for question in ("What is your phone number?", "What is the customer service phone number?"):
            self.assertEqual(system.answer(question).text, "Call 800-373-7600.", question)

    def test_a_link_to_business_rates_is_the_business_product_page(self):
        business_url = "https://www.dupaco.com/business/savings/certificates"
        sheet = dated_certificate_table("3.80%", "4/2/2026")
        system = system_with_pages((PRODUCT_URL, sheet), (business_url, sheet))
        self.assertEqual(system.answer("What link shows your business CD rates?").text, business_url)

    def test_hours_asked_by_kind_only_read_schedules_of_that_kind(self):
        lobby_only = article("June 1, 2026", "Asbury branch hours are:\n\n**Lobby**\n\nMonday-Friday: 8 a.m.-4 p.m.")
        drive_up = article("June 1, 2026", "Galena branch hours are:\n\n**Drive-up**\n\nMonday-Friday: 7 a.m.-6 p.m.")
        system = system_with_pages((NEWS_URL + "asbury", lobby_only), (NEWS_URL + "galena", drive_up))
        answer = system.answer("What are the drive-up hours?").text
        self.assertIn("7 a.m.-6 p.m.", answer)
        self.assertNotIn("8 a.m.-4 p.m.", answer)


    def test_a_what_is_question_answers_from_the_passage_that_defines_it(self):
        page = article(
            "June 1, 2026",
            "The Home$tart program helps first-time buyers. It provides up to $15,000 in assistance.\n\n# More\n\nHome$tart is popular.",
        )
        answer = system_with_pages((NEWS_URL + "a", page)).answer("What is the Home$tart program?").text
        self.assertIn("$15,000", answer)

    def test_a_charter_area_answer_says_which_states(self):
        page = "You can join if you live within our charter area.\n\n# Local\n\nYou can find us in Iowa, Illinois and Wisconsin."
        answer = system_with_pages((NEWS_URL + "a", page)).answer("Who can join if they live in the charter area?").text
        self.assertIn("Iowa, Illinois and Wisconsin", answer)


class Conflicts(unittest.TestCase):
    LANDING_URL = "https://www.dupaco.com/offer-lp"

    @staticmethod
    def rows(*rows: str) -> str:
        return "Rates\n\n| Loan | Rate | APR |\n| --- | --- | --- |\n" + "\n".join(rows) + "\n"

    def conflicts_between(self, sheet: str, landing: str) -> list:
        return system_with_pages((RATES_URL, sheet), (self.LANDING_URL, landing)).conflicts()

    def test_a_page_still_showing_an_old_rate_is_a_conflict_the_rate_page_wins(self):
        found = self.conflicts_between(
            self.rows("| Mortgage 30-Year Fixed | 7.25% | 7.29% |"), self.rows("| Mortgage 30-Year Fixed | 6.00% | 6.04% |")
        )
        self.assertEqual(len(found), 1)
        self.assertTrue({"6.00%", "6.04%", "7.25%", "7.29%"} <= set(found[0].values))
        self.assertIn("7.29%", found[0].resolution)
        self.assertIn("/rates", found[0].reason)
        self.assertIn("/offer-lp", found[0].reason)

    def test_tiers_and_the_same_number_written_differently_are_not_conflicts(self):
        sheet = self.rows("| Mortgage 15-Year Fixed | 6.75% | 6.88% |", "| Mortgage 30-Year Fixed | 7.25% | 7.29% |")
        landing = self.rows("| Mortgage 15-Year Fixed | 6.750% | 6.880% |", "| Mortgage 30-Year Fixed | 7.250% | 7.290% |")
        self.assertEqual(self.conflicts_between(sheet, landing), [])

    def test_a_rate_and_an_apr_are_different_facts_not_a_conflict(self):
        landing = "Rates\n\n| Loan | Rate |\n| --- | --- |\n| Mortgage 30-Year Fixed | 7.25% |\n"
        apr_only = "Rates\n\n| Loan | APR |\n| --- | --- |\n| Mortgage 30-Year Fixed | 7.29% |\n"
        self.assertEqual(self.conflicts_between(apr_only, landing), [])

    def test_another_product_at_the_same_balance_tier_is_not_a_conflict(self):
        table = "Rates\n\n| Account | Balance | APY |\n| --- | --- | --- |\n| {} | $25,000 - $99,999.99 | {} |\n"
        found = self.conflicts_between(table.format("Investor's Choice Money Market", "0.35%"), table.format("Achieve Money Market", "3.25%"))
        self.assertEqual(found, [])

    def test_two_rows_on_one_page_are_never_compared_with_each_other(self):
        sheet = self.rows("| Platinum Visa | 12.50% | 12.50% |", "| Platinum Visa Introductory | 2.90% | 2.90% |")
        self.assertEqual(system_with_pages((RATES_URL, sheet)).conflicts(), [])

    def test_several_pages_repeating_the_same_old_rate_are_one_conflict(self):
        old = self.rows("| Mortgage 30-Year Fixed | 6.00% | 6.04% |")
        found = system_with_pages(
            (RATES_URL, self.rows("| Mortgage 30-Year Fixed | 7.25% | 7.29% |")),
            ("https://www.dupaco.com/one-lp", old),
            ("https://www.dupaco.com/two-lp", old),
        ).conflicts()
        self.assertEqual(len(found), 1)
        self.assertIn("/one-lp", found[0].topic)
        self.assertIn("/two-lp", found[0].topic)

    def test_a_model_year_tier_relabelled_since_is_still_compared(self):
        sheet = "Rates\n\n| Auto Loans | APR |\n| --- | --- |\n| 2024-27 Model Year 60 Months | 5.39% |\n| 2021-23 Model Year 60 Months | 5.64% |\n"
        landing = "Rates\n\n| Auto Loans | APR |\n| --- | --- |\n| 2023-26 Model Year 60 Months | 5.34% |\n"
        found = self.conflicts_between(sheet, landing)
        self.assertEqual(len(found), 1)
        self.assertTrue({"5.34%", "5.39%"} <= set(found[0].values))
        self.assertNotIn("5.64%", found[0].values)

    def test_only_the_latest_snapshot_counts(self):
        system = KnowledgeSystem()
        system.ingest(snapshot("2026-05-12", (RATES_URL, self.rows("| Mortgage 30-Year Fixed | 7.25% | 7.29% |")),
                               (self.LANDING_URL, self.rows("| Mortgage 30-Year Fixed | 6.00% | 6.04% |"))))
        system.ingest(snapshot("2026-09-28", (RATES_URL, self.rows("| Mortgage 30-Year Fixed | 7.25% | 7.29% |"))))
        self.assertEqual(system.conflicts(), [])

    def test_an_undated_page_disagreeing_with_the_newest_branch_count_is_a_conflict(self):
        found = system_with_pages(
            ("https://www.dupaco.com/about", "Leaders across our 18 branches work together."),
            (NEWS_URL + "old", article("March 1, 2026", "It has 23 branch office locations.")),
            (NEWS_URL + "new", article("May 1, 2026", "It has 22 branch office locations.")),
        ).conflicts()
        self.assertEqual(found[0].resolution, "22")
        self.assertEqual(set(found[0].values), {"18", "22"})


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
