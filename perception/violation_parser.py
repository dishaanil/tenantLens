"""
violation_parser.py
Perception Agent — Step 3
Parses Gemini Flash raw text into a typed ViolationType.
This is the frozen output contract — field names must not change.
"""

from dataclasses import dataclass
from typing import Literal

VALID_VIOLATIONS = {
    "mold", "water_damage", "pest_damage", "pest_infestation",
    "broken_fixture", "structural_damage", "heating_issue", "none",
}


@dataclass
class ViolationType:
    violation_type: str
    confidence: Literal["high", "medium", "low"]
    description: str

    def to_a2a_payload(self, address: str) -> dict:
        """
        Exact payload sent to Agent 2 via A2A.
        Field names are frozen — do not rename.
        """
        return {
            "violation_type": self.violation_type,
            "confidence": self.confidence,
            "description": self.description,
            "address": address,
        }


def parse(raw_text: str) -> ViolationType:
    """Parse the structured Gemini response into ViolationType."""
    violation = "none"
    confidence = "low"
    description = "Could not parse response."

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
    print(json.dumps(result.to_a2a_payload("243 94th St, Brooklyn"), indent=2))
