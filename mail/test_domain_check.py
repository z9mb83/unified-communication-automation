import unittest

from app import domain_check
from app.domain_check import domain_problem


def fake(answers):
    calls = []

    def lookup(name, rtype):
        calls.append((name, rtype))
        return answers[(name, rtype)]
    lookup.calls = calls
    return lookup


class DomainCheckTest(unittest.TestCase):
    def setUp(self):
        domain_check._cache.clear()

    def test_common_providers_skip_lookup(self):
        lk = fake({})
        self.assertEqual(domain_problem("a@Gmail.com", lk), "")
        self.assertEqual(lk.calls, [])

    def test_mx_ok(self):
        self.assertEqual(domain_problem("a@acme.in", fake({("acme.in", "MX"): {"Status": 0, "Answer": [{"type": 15, "data": "10 mx.acme.in."}]}})), "")

    def test_nxdomain(self):
        self.assertEqual(domain_problem("a@nope.xyz", fake({("nope.xyz", "MX"): {"Status": 3}})), "email domain does not exist")

    def test_no_mx_no_a(self):
        lk = fake({("site.in", "MX"): {"Status": 0}, ("site.in", "A"): {"Status": 0}})
        self.assertEqual(domain_problem("a@site.in", lk), "email domain cannot receive mail")

    def test_no_mx_but_a_record(self):
        lk = fake({("site2.in", "MX"): {"Status": 0}, ("site2.in", "A"): {"Status": 0, "Answer": [{"type": 1, "data": "1.2.3.4"}]}})
        self.assertEqual(domain_problem("a@site2.in", lk), "")

    def test_null_mx(self):
        lk = fake({("nomail.in", "MX"): {"Status": 0, "Answer": [{"type": 15, "data": "0 ."}]}})
        self.assertEqual(domain_problem("a@nomail.in", lk), "email domain accepts no mail")

    def test_lookup_error_never_blocks(self):
        def boom(name, rtype):
            raise OSError("offline")
        self.assertEqual(domain_problem("a@x-corp.in", boom), "")


if __name__ == "__main__":
    unittest.main()
