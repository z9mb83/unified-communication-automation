"""OpenAI subject/body generation for a single brand."""

from __future__ import annotations

import json
import re

from openai import OpenAI

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


def signature_for(brand: BrandConfig) -> str:
    """Build the exact brand contact footer outside the AI-generated content."""
    lines = [
        "Ajay Veer",
        "Sales Executive",
        brand.brand_name,
    ]
    if brand.phone:
        lines.append(f"Phone: {brand.phone}")
    if brand.mandatory_cc:
        lines.append(f"Email: {brand.mandatory_cc}")
    if brand.website:
        website = brand.website.removeprefix("https://").removeprefix("http://").rstrip("/")
        lines.append(f"Website: {website}")
    return "\n".join(lines)


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


def generate_email(runtime: RuntimeConfig, brand: BrandConfig, person_name: str, details: str) -> tuple[str, str]:
    if not runtime.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is missing from .env")

    client = OpenAI(api_key=runtime.openai_api_key)
    response = client.responses.create(
        model=runtime.openai_model,
        max_output_tokens=1000,
        reasoning={"effort": "minimal"},
        text={
            "format": {
                "type": "json_schema",
                "name": "outreach_email",
                "strict": True,
                "schema": EMAIL_RESPONSE_SCHEMA,
            }
        },
        instructions=(
            f"You write compliant first-contact business outreach for {brand.brand_name}. "
            "Use only the recipient name and details supplied by the user plus these approved facts: "
            f"{brand.brand_facts} Do not invent achievements, years, client counts, locations, "
            "partnerships or personal facts."
        ),
        input=(
            f"Recipient name: {person_name or 'Not provided'}\n"
            f"Recipient details: {details or 'No additional details provided'}\n\n"
            "Requirements:\n"
            "- Subject must be short and natural.\n"
            "- Body must be approximately 80 to 130 words before the signature.\n"
            "- Use one simple call to action.\n"
            "- Avoid aggressive language and avoid attachments.\n"
            "- End with: If this is not relevant, please reply and we will not contact you again.\n"
            "- Do not add a name, job title, phone number, email address, website, or signature. "
            "The application adds the approved signature separately.\n"
            "- Do not include a subject line inside the body."
        ),
    )

    data = _extract_json(response.output_text)
    subject = str(data.get("subject", "")).strip()
    body = str(data.get("body", "")).strip()
    if not subject or not body:
        raise ValueError("OpenAI returned an empty subject or body")
    return subject, f"{body}\n\n{signature_for(brand)}"
