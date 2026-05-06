"""Extract leave-request data from a photo using Claude vision."""
import base64
import json
import os
import re
from datetime import date, datetime

import anthropic

_CLIENT = None


def _client():
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _CLIENT


_PROMPT = """You are an HR assistant for a Romanian company. You are reading a scanned or photographed Romanian leave request form (cerere de concediu).

The form is typically structured like this (fields may be handwritten):
  - "De la:" or "Subsemnatul(a):" → employee full name
  - "Funcția:" → job title (not needed)
  - "Cerere concediu de odihnă" = annual leave | "concediu medical" = sick leave | "concediu fără plată" = unpaid | "delegație" = business trip
  - "în perioada:" followed by a START DATE and an END DATE written as DD.MM.YYYY
  - "respectiv X zile lucrătoare" → number of working days (useful for validation)

Your task — extract ONLY these fields:

1. employee_name: Full name as written in "De la:" or "Subsemnatul(a):" (e.g. "DOBOS LEVENTE")
2. leave_type: One of these codes:
     CO  = Concediu Odihnă (annual/vacation leave — most common)
     CM  = Concediu Medical (sick leave / medical certificate)
     CFP = Concediu Fără Plată (unpaid leave)
     CIC = Concediu Îngrijire Copil (parental / child care)
     DO  = Delegație (business trip / work travel)
     REC = Recuperare (compensatory rest day)
     NN  = Nemotivat (unjustified absence)
3. start_date: First day of leave in ISO format YYYY-MM-DD
4. end_date:   Last day of leave (inclusive) in ISO format YYYY-MM-DD
   — If only one date is written, start_date == end_date
   — Dates in the form are written as DD.MM.YYYY — convert carefully

Reply ONLY with a single valid JSON object, no markdown, no explanation:
{
  "employee_name": "...",
  "leave_type": "CO",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "working_days": <integer or null>,
  "confidence": "high|medium|low",
  "notes": "..."
}

Rules:
- If a date is partially illegible, make your best guess based on context.
- If you cannot determine a field at all, use null.
- Set confidence "high" when all fields are clearly legible, "medium" for minor uncertainty, "low" when significant parts are unreadable."""


def extract_leave_from_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """Call Claude vision to extract leave data from the form image."""
    b64 = base64.standard_b64encode(image_bytes).decode()

    message = _client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": _PROMPT},
                ],
            }
        ],
    )

    raw = message.content[0].text.strip()
    # strip any accidental markdown fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)
