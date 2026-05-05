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


_PROMPT = """You are helping a Romanian company's HR system extract data from a scanned leave request form (cerere de concediu).

Analyze the image and extract:
1. Employee full name (Nume și Prenume)
2. Leave type — map to one of these codes:
   CO = Concediu Odihnă (annual/vacation leave)
   CM = Concediu Medical (sick leave)
   CFP = Concediu Fără Plată (unpaid leave)
   CIC = Concediu Îngrijire Copil (parental/child care)
   DO = Delegație (business trip)
   REC = Recuperare (compensatory leave)
3. Start date (first day of leave)
4. End date (last day of leave, inclusive)

Reply ONLY with valid JSON in this exact format (no extra text):
{
  "employee_name": "...",
  "leave_type": "CO",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "confidence": "high|medium|low",
  "notes": "any relevant notes or uncertainties"
}

If you cannot read the form clearly, still return JSON with your best guess and set confidence to "low".
If a field is completely unreadable, use null for that field."""


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
