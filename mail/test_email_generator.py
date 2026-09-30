import random
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import email_generator as eg

BRAND = SimpleNamespace(brand_id="marketing", brand_name="99 Marketing Services", brand_facts="We do social media.",
                        phone="+91 1", mandatory_cc="info@x.com", website="https://www.x.com")
RUNTIME = SimpleNamespace(openai_api_key="k", openai_model="m")


class FakeClient:
    def __init__(self, replies):
        self.replies, self.prompts = list(replies), []
        self.responses = self

    def create(self, **kw):
        self.prompts.append(kw["input"])
        s, b = self.replies.pop(0)
        return SimpleNamespace(output_text='{"subject": "%s", "body": "%s"}' % (s, b.replace("\n", "\\n")))


GOOD = ("your cafe's instagram", "Saw that you run a cafe in Pune.\nWould a short call this week make sense?")


class GeneratorTest(unittest.TestCase):
    def run_gen(self, replies, seed=1):
        client = FakeClient(replies)
        with patch.object(eg, "_client", lambda runtime: client):
            return eg.generate_email(RUNTIME, BRAND, "Mr. ARYAN Sharma", "cafe owner, Pune", random.Random(seed)), client

    def test_signature_has_no_website(self):
        sig = eg.signature_for(BRAND)
        self.assertNotIn("Website", sig)
        self.assertIn("Phone: +91 1", sig)

    def test_first_name(self):
        self.assertEqual(eg.first_name("Mr. ARYAN Sharma"), "Aryan")
        self.assertEqual(eg.first_name("Acme Solutions Pvt Ltd"), "")
        self.assertEqual(eg.first_name(""), "")
        self.assertEqual(eg.first_name("Amarjeetmvplchd"), "")          # handle, not a name
        self.assertEqual(eg.first_name("Amarjeet Singh"), "Amarjeet")
        self.assertEqual(eg.first_name("Christopher"), "Christopher")

    def test_briefs_vary(self):
        rng = random.Random(7)
        briefs = {tuple(sorted((k, str(v)) for k, v in eg.pick_brief(BRAND, "Aryan", rng).items())) for _ in range(20)}
        self.assertGreater(len(briefs), 10)

    def test_clean_draft_used_as_is(self):
        (subject, body), client = self.run_gen([GOOD])
        self.assertEqual(subject, "your cafe's instagram")
        self.assertTrue(body.split("\n")[0].startswith(("Hi Aryan", "Hello Aryan", "Aryan,")))
        self.assertTrue(any(o in body for o in eg.OPT_OUTS))
        self.assertTrue(body.endswith("Email: info@x.com"))
        self.assertEqual(len(client.prompts), 1)

    def test_spammy_draft_is_rewritten_once(self):
        (subject, body), client = self.run_gen([("Quick question!", "Get a FREE audit now! Visit www.x.com"), GOOD])
        self.assertEqual(len(client.prompts), 2)
        self.assertIn("previous draft had problems", client.prompts[1])
        self.assertEqual(subject, GOOD[0])

    def test_still_spammy_raises(self):
        bad = ("quick question", "Guaranteed results for free.")
        with self.assertRaises(ValueError):
            self.run_gen([bad, bad])

    def test_no_details_brief(self):
        rng = random.Random(3)
        for _ in range(30):
            b = eg.pick_brief(BRAND, "Aryan", rng, details="")
            self.assertNotIn(b["opening"], [eg.OPENINGS[i] for i in eg.DETAIL_OPENINGS])
        client = FakeClient([GOOD])
        with patch.object(eg, "_client", lambda runtime: client):
            eg.generate_email(RUNTIME, BRAND, "Aryan", "", random.Random(1))
        self.assertIn("Nothing is known about this recipient", client.prompts[0])
        self.assertTrue(eg.spam_problems("hello there", "I didn't see any details about you."))

    def test_spam_problems(self):
        self.assertEqual(eg.spam_problems("ideas for your cafe", "We could help you learn more."), [])
        p = eg.spam_problems("Act Now", "- one\n- two\nhttps://x.com")
        self.assertTrue(any("bullet" in x for x in p) and any("link" in x for x in p) and any("spam words" in x for x in p))


if __name__ == "__main__":
    unittest.main()
