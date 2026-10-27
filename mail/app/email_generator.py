"""OpenAI subject/body generation for a single brand.

Every draft is built differently so the mailboxes do not send near-identical emails (identical
bodies are one of the strongest spam signals). Python picks a random opening style, angle,
call to action, greeting, length and opt-out wording for each lead; the model writes a plain,
personal note from that brief; the result is checked for spam triggers and retried once.
"""

from __future__ import annotations

import json
import random
import re

from app.config_loader import BrandConfig, RuntimeConfig


EMAIL_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "subject": {"type": "string"},
        "body": {"type": "string"},
    },
    "required": ["subject", "body"],
    "additionalProperties": False,
}

OPENINGS = [
    "Open with one specific thing from the recipient details (their business, role, city or what they do) and why it caught your attention.",
    "Open with a short, genuine question about how they currently handle the problem this brand solves.",
    "Open with a one-line observation about a common challenge in their line of work, then connect it to them.",
    "Open by saying plainly, in one short sentence, who you are and why you are writing to them specifically.",
    "Open with a brief compliment that is specific to the recipient details (never generic praise).",
]

ANGLES = {
    "marketing": [
        "saving them time on posting and content planning",
        "getting more enquiries from social media without them running it day to day",
        "finding the right creators or influencers for their audience",
        "making their paid ads spend work harder",
        "keeping their brand consistent across Instagram, Facebook and LinkedIn",
    ],
    "staffing": [
        "filling open roles faster",
        "taking candidate sourcing and screening off their plate",
        "handling seasonal or sudden hiring spikes",
        "reducing the time their team spends on interviews that go nowhere",
        "finding reliable staff for hard-to-fill positions",
    ],
    "property": [
        "shortlisting properties that match what they actually want",
        "saving them wasted site visits",
        "getting clear guidance on a project before committing",
        "helping them compare options in one place",
        "handling the coordination so they only see serious options",
    ],
    "skyline": [
        "selling their business at a fair value through a confidential, structured process",
        "knowing what their business is really worth before they talk to any buyer or investor",
        "finding and evaluating the right business to buy, instead of chasing scattered listings",
        "meeting serious, screened buyers or investors rather than time-wasting enquiries",
        "raising growth funding with investor-ready documents such as a pitch deck and financial model",
        "franchising or leasing out their business to grow into new cities without running every outlet",
        "having one advisor run the deal from valuation to closing so they can keep running the business",
    ],
    "shaadi": [
        "a personal, one-to-one approach to matchmaking",
        "meeting genuine, verified profiles only",
        "having a dedicated relationship manager guide the search",
        "a private and respectful process for the family",
    ],
}
DEFAULT_ANGLES = ["saving them time", "making one part of their work simpler", "a practical next step that fits their situation"]

CALLS_TO_ACTION = [
    "Ask if they would be open to a 10-minute call this week.",
    "Ask if you can send over two or three relevant examples.",
    "Ask who is the right person to speak with about this, if not them.",
    "Ask if this is something they are looking at right now.",
    "Ask what would make this worth a short conversation for them.",
]

GREETINGS = ["Hi {name},", "Hello {name},", "{name},", "Hi {name}, hope your week is going well."]
GREETINGS_NO_NAME = ["Hi there,", "Hello,", "Hi,"]

OPT_OUTS = [
    "If this is not relevant, just reply and I will not contact you again.",
    "Not the right fit? A one-line reply is enough and I will not follow up.",
    "If you would rather not hear from us, reply and I will take you off my list.",
    "If now is not a good time or this is not for you, let me know and I will not write again.",
]

LENGTHS = [(60, 80), (70, 95), (85, 110)]

# Words and phrases that push cold email into spam or read like a template.
SPAM_PHRASES = [
    "free", "guarantee", "guaranteed", "100%", "act now", "limited time", "urgent", "risk-free", "risk free",
    "no obligation", "no-obligation", "click here", "buy now", "special offer", "offer expires", "cheap",
    "discount", "cash", "winner", "congratulations", "dear friend", "quick question", "earn", "best price",
    "amazing", "incredible", "exclusive deal", "once in a lifetime", "increase sales", "double your",
    "hope this email finds you well", "i hope this finds you well", "touch base", "circle back",
    "synergy", "leverage", "revolutionary", "game-changer", "game changer",
    "didn't see any details", "did not see any details", "no details", "your profile caught",
]
# Template placeholders the model sometimes leaves in ("I'm [Name] from ..."): never send these.
PLACEHOLDER = re.compile(r"\[[^\]\n]{1,40}\]|\{[^}\n]{1,40}\}|<[A-Za-z][A-Za-z _]{1,30}>")
SENDER_FIRST_NAME = "Ajay"
# "I'm Alex from ..." / "This is Sam at ...": the writer introduced with a name that is not the signature's
WRONG_INTRO = re.compile(r"\b(?:I[’']m|I am|This is|My name is)\s+(?!" + SENDER_FIRST_NAME + r"\b)([A-Z][a-z]+)\b(?:\s+[A-Z][a-z]+)?(?:\s*,|\s+(?:from|with|at|here)\b)")
_LINK = re.compile(r"(https?://|www\.|\.com\b|\.in\b)", re.IGNORECASE)


def signature_for(brand: BrandConfig) -> str:
    """Brand contact footer added outside the AI text. No website link: links in a first cold email hurt delivery."""
    lines = [
        "Ajay Veer",
        "Sales Executive",
        brand.brand_name,
    ]
    if brand.phone:
        lines.append(f"Phone: {brand.phone}")
    if brand.mandatory_cc:
        lines.append(f"Email: {brand.mandatory_cc}")
    return "\n".join(lines)


def first_name(person_name: str) -> str:
    """'Mr. Aryan Sharma' -> 'Aryan'; company-looking or empty names -> ''."""
    words = [w for w in re.split(r"\s+", (person_name or "").strip()) if w]
    while words and words[0].rstrip(".").lower() in {"mr", "mrs", "ms", "miss", "dr", "shri", "smt", "sir"}:
        words = words[1:]
    if not words:
        return ""
    name = words[0].strip(",.")
    # a single long word ("Amarjeetmvplchd", "rajeshkumarbuilders") is a username or business handle, not a first name
    if len(words) == 1 and len(name) > 12:
        return ""
    if not name.isalpha() or len(name) < 2 or any(w.lower() in {"pvt", "ltd", "llp", "inc", "services", "solutions"} for w in words):
        return ""
    return name[:1].upper() + name[1:].lower() if name.isupper() or name.islower() else name


# Openings that need something specific about the recipient (used only when Details is filled in).
DETAIL_OPENINGS = {0, 4}


def pick_brief(brand: BrandConfig, person_name: str, rng: random.Random | None = None, details: str = "") -> dict:
    rng = rng or random.Random()
    name = first_name(person_name)
    low, high = rng.choice(LENGTHS)
    openings = OPENINGS if str(details or "").strip() else [o for i, o in enumerate(OPENINGS) if i not in DETAIL_OPENINGS]
    return {
        "opening": rng.choice(openings),
        "angle": rng.choice(ANGLES.get(brand.brand_id, DEFAULT_ANGLES)),
        "cta": rng.choice(CALLS_TO_ACTION),
        "greeting": (rng.choice(GREETINGS).format(name=name) if name else rng.choice(GREETINGS_NO_NAME)),
        "opt_out": rng.choice(OPT_OUTS),
        "words": (low, high),
    }


def spam_problems(subject: str, body: str) -> list[str]:
    """Reasons a draft is likely to land in spam (empty list = fine)."""
    problems = []
    text = f"{subject}\n{body}".lower()
    found = sorted({p for p in SPAM_PHRASES if re.search(r"(?<![a-z])" + re.escape(p) + r"(?![a-z])", text)})
    if found:
        problems.append("spam words: " + ", ".join(found))
    if "!" in subject or body.count("!") > 0:
        problems.append("exclamation marks")
    if PLACEHOLDER.search(body) or PLACEHOLDER.search(subject):
        problems.append("a placeholder like [Name] - write real words or leave it out")
    if WRONG_INTRO.search(body):
        problems.append(f"the writer must be {SENDER_FIRST_NAME}, not '{WRONG_INTRO.search(body).group(1)}'")
    if _LINK.search(body) or _LINK.search(subject):
        problems.append("a link or web address")
    if re.search(r"^\s*([-*•]|\d+[.)])\s", body, re.MULTILINE):
        problems.append("bullet points")
    words = len(subject.split())
    if words < 2 or words > 7:
        problems.append(f"subject should be 2-6 words (has {words})")
    if sum(1 for c in subject if c.isupper()) > max(3, len(subject) // 3):
        problems.append("too many capital letters in the subject")
    return problems


def _extract_json(text: str) -> dict:
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("OpenAI returned no final text; the draft was not generated")
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("OpenAI response did not contain a JSON object")
    return json.loads(cleaned[start : end + 1])


def _instructions(brand: BrandConfig) -> str:
    return (
        f"You write short, personal first-contact emails for {brand.brand_name}, one real person writing to another. "
        f"You are {SENDER_FIRST_NAME} from {brand.brand_name}; if you introduce yourself, say \"I'm {SENDER_FIRST_NAME} from {brand.brand_name}\". "
        "Never use placeholders or brackets such as [Name], [Company], {name} or <city>; if you do not know something, leave it out. "
        f"Approved facts about the company (use only these, never invent clients, numbers, years, awards or locations): {brand.brand_facts}\n"
        "Style rules:\n"
        "- Plain conversational English, like a note typed in Gmail. Short sentences. Two or three short paragraphs.\n"
        "- Personalise with the recipient details when they exist; never pretend to know something that is not given.\n"
        "- One call to action only.\n"
        "- No exclamation marks, no bullet points, no links or web addresses, no emojis, no ALL CAPS, no attachments.\n"
        "- Never use these words or phrases: " + ", ".join(SPAM_PHRASES) + ".\n"
        "- Subject: 2 to 6 words, lowercase except names, specific to the recipient or the angle, no punctuation at the end. "
        "Not salesy, not clickbait, never 'quick question'.\n"
        "- Do not write a greeting line, a sign-off, a name, job title, phone, email or signature; the application adds them."
    )


def _input(brief: dict, person_name: str, details: str, feedback: str = "") -> str:
    low, high = brief["words"]
    text = (
        f"Recipient name: {person_name or 'Not provided'}\n"
        f"Recipient details: {details or 'No additional details provided'}\n\n"
        f"Brief for this email:\n"
        f"- {brief['opening']}\n"
        f"- Angle to focus on: {brief['angle']}.\n"
        f"- {brief['cta']}\n"
        f"- Length: {low} to {high} words (body only).\n"
        f"- End the body with this exact sentence on its own line: {brief['opt_out']}"
    )
    if not str(details or "").strip():
        text += ("\n- Nothing is known about this recipient. Do NOT say that, do NOT mention details, a profile, "
                 "their business or anything you 'saw' or 'noticed' about them. Write a short general note that fits anyone.")
    if feedback:
        text += f"\n\nYour previous draft had problems ({feedback}). Rewrite it without them."
    return text


_CLIENTS: dict = {}


def _client(runtime: RuntimeConfig):
    """One OpenAI client per key for the whole run (a new client per draft leaked memory in long runs)."""
    from openai import OpenAI

    key = runtime.openai_api_key
    if key not in _CLIENTS:
        _CLIENTS[key] = OpenAI(api_key=key)
    return _CLIENTS[key]


def _ask(client, runtime: RuntimeConfig, brand: BrandConfig, prompt: str) -> tuple[str, str]:
    response = client.responses.create(
        model=runtime.openai_model,
        max_output_tokens=1000,
        reasoning={"effort": "minimal"},
        text={"format": {"type": "json_schema", "name": "outreach_email", "strict": True, "schema": EMAIL_RESPONSE_SCHEMA}},
        instructions=_instructions(brand),
        input=prompt,
    )
    data = _extract_json(response.output_text)
    subject = re.sub(r"\s+", " ", str(data.get("subject", ""))).strip().strip('"').rstrip(".!?:")
    body = str(data.get("body", "")).strip()
    if not subject or not body:
        raise ValueError("OpenAI returned an empty subject or body")
    return subject, body


def _tidy(body: str, brief: dict) -> str:
    body = body.replace("!", ".")
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    if brief["opt_out"] not in body:
        body = f"{body}\n\n{brief['opt_out']}"
    return f"{brief['greeting']}\n\n{body}"


def generate_email(
    runtime: RuntimeConfig, brand: BrandConfig, person_name: str, details: str, rng: random.Random | None = None
) -> tuple[str, str]:
    if not runtime.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is missing (Secret Manager secret openai-api-key)")
    client = _client(runtime)
    brief = pick_brief(brand, person_name, rng, details)
    subject, body = _ask(client, runtime, brand, _input(brief, person_name, details))
    problems = spam_problems(subject, body)
    if problems:
        subject, body = _ask(client, runtime, brand, _input(brief, person_name, details, "; ".join(problems)))
        still = [p for p in spam_problems(subject, body) if p != "exclamation marks"]
        if still:
            raise ValueError("Draft kept spam-risk wording (" + "; ".join(still) + "); will retry next run")
    return subject, f"{_tidy(body, brief)}\n\n{signature_for(brand)}"
