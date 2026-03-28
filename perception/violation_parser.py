"""
violation_parser.py
Perception Agent — Step 3
Parses Gemini raw text into a typed ViolationType.
Carries borough and preferred_language through to the A2A payload.
"""

from dataclasses import dataclass
from typing import Literal, Optional

VALID_VIOLATIONS = {
    "mold", "water_damage", "pest_damage", "pest_infestation",
    "broken_fixture", "structural_damage", "heating_issue", "none",
}

SUPPORTED_LANGUAGES = {"en", "es", "zh", "bn", "ru", "ar", "fr", "pt", "ko", "hi"}


@dataclass
class ViolationType:
    violation_type: str
    confidence: Literal["high", "medium", "low"]
    description: str
    preferred_language: str = "en"

    def to_a2a_payload(self, address: str, borough: str, preferred_language: str = "en") -> dict:
        return {
            "violation_type": self.violation_type,
            "confidence": self.confidence,
            "description": self.description,
            "address": address,
            "borough": borough,
            "preferred_language": preferred_language,
        }


def parse(raw_text: str, preferred_language: str = "en") -> ViolationType:
    violation = "none"
    confidence = "low"
    description = "Could not parse response."

    lang = preferred_language.strip().lower() if preferred_language else "en"
    if lang not in SUPPORTED_LANGUAGES:
        lang = "en"

    for line in raw_text.strip().splitlines():
        line = line.strip()
        if line.startswith("VIOLATION:"):
            v = line.split(":", 1)[1].strip().lower().replace(" ", "_")
            violation = v if v in VALID_VIOLATIONS else "none"
        elif line.startswith("CONFIDENCE:"):
            c = line.split(":", 1)[1].strip().lower()
            confidence = c if c in ("high", "medium", "low") else "low"
        elif line.startswith("DESCRIPTION:"):
            description = line.split(":", 1)[1].strip()

    return ViolationType(
        violation_type=violation,
        confidence=confidence,
        description=description,
        preferred_language=lang,
    )


if __name__ == "__main__":
    import json

    sample = (
        "VIOLATION: mold\n"
        "CONFIDENCE: high\n"
        "DESCRIPTION: Black mold visible on bathroom ceiling, ~30% coverage."
    )
    result = parse(sample)
    print(result)
    print("\nA2A payload to Agent 2:")
    print(json.dumps(result.to_a2a_payload("243 94th St", "Brooklyn"), indent=2))
