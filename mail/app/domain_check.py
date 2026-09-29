"""Pre-send check that a lead's email domain can receive mail (cuts hard bounces).

Uses Google's public DNS-over-HTTPS resolver (dns.google) - no key, no cost. A domain with no
MX record and no address record cannot receive email; sending there only produces a bounce,
and many bounces hurt the sending mailbox's reputation. If the lookup itself fails (network,
timeout) the email is NOT blocked.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

COMMON = {"gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.in", "outlook.com", "hotmail.com", "live.com",
          "icloud.com", "rediffmail.com", "protonmail.com", "proton.me", "zoho.com", "aol.com", "msn.com"}
_cache: dict[str, str] = {}


def _lookup(name: str, rtype: str) -> dict:
    url = "https://dns.google/resolve?" + urllib.parse.urlencode({"name": name, "type": rtype})
    with urllib.request.urlopen(url, timeout=8) as response:
        return json.load(response)


def domain_problem(email: str, lookup=None) -> str:
    """'' if the domain looks able to receive mail (or the check could not run), else a short reason."""
    domain = email.rsplit("@", 1)[-1].strip().lower().rstrip(".")
    if not domain or domain in COMMON:
        return ""
    if domain in _cache:
        return _cache[domain]
    lookup = lookup or _lookup
    try:
        mx = lookup(domain, "MX")
        if mx.get("Status") == 3:
            reason = "email domain does not exist"
        elif any(a.get("type") == 15 for a in mx.get("Answer", []) or []):
            # "0 ." is a null MX: the domain explicitly accepts no mail.
            if all(str(a.get("data", "")).strip().endswith(" .") for a in mx["Answer"] if a.get("type") == 15):
                reason = "email domain accepts no mail"
            else:
                reason = ""
        elif mx.get("Status") == 0:
            a = lookup(domain, "A")
            reason = "" if any(x.get("type") == 1 for x in a.get("Answer", []) or []) else "email domain cannot receive mail"
        else:
            return ""  # SERVFAIL etc.: do not block, do not cache
    except Exception:
        return ""
    _cache[domain] = reason
    return reason
