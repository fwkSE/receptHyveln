"""Detect imperial/English units and provide Swedish conversion reference."""

import re

CONVERSION_REFERENCE: list[dict[str, str | re.Pattern[str]]] = [
    {
        "key": "tbsp",
        "pattern": re.compile(r"\b(?:tablespoons?|tbsp)\b", re.IGNORECASE),
        "from": "1 tbsp",
        "to": "1 msk (15 ml)",
    },
    {
        "key": "tsp",
        "pattern": re.compile(r"(?<![a-z])\b(?:teaspoons?|tsp)\b", re.IGNORECASE),
        "from": "1 tsp",
        "to": "1 tsk (5 ml)",
    },
    {
        "key": "cup",
        "pattern": re.compile(r"\bcups?\b", re.IGNORECASE),
        "from": "1 cup",
        "to": "2,4 dl",
    },
    {
        "key": "floz",
        "pattern": re.compile(r"\b(?:fluid\s+ounces?|fl\s*oz)\b", re.IGNORECASE),
        "from": "1 fl oz",
        "to": "30 ml",
    },
    {
        "key": "oz",
        "pattern": re.compile(r"(?:\d\s*)?oz\b|\bounces?\b", re.IGNORECASE),
        "from": "1 oz",
        "to": "28 g",
    },
    {
        "key": "lb",
        "pattern": re.compile(r"(?:\d\s*)?(?:lbs?|pounds?)\b", re.IGNORECASE),
        "from": "1 lb",
        "to": "450 g",
    },
    {
        "key": "pint",
        "pattern": re.compile(r"\bpints?\b", re.IGNORECASE),
        "from": "1 pint",
        "to": "4,8 dl",
    },
    {
        "key": "quart",
        "pattern": re.compile(r"\bquarts?\b", re.IGNORECASE),
        "from": "1 quart",
        "to": "9,6 dl",
    },
    {
        "key": "gallon",
        "pattern": re.compile(r"\bgallons?\b", re.IGNORECASE),
        "from": "1 gallon",
        "to": "3,8 liter",
    },
    {
        "key": "servings",
        "pattern": re.compile(r"\bservings?\b", re.IGNORECASE),
        "from": "servings",
        "to": "portioner",
    },
    {
        "key": "cloves",
        "pattern": re.compile(r"\bcloves?\b", re.IGNORECASE),
        "from": "cloves",
        "to": "klyftor (vitlök)",
    },
    {
        "key": "stalks",
        "pattern": re.compile(r"\bstalks?\b", re.IGNORECASE),
        "from": "stalks",
        "to": "stjälkar",
    },
]


def _text_blob(ingredient_groups: list[dict], yield_text: str | None) -> str:
    parts: list[str] = []
    if yield_text:
        parts.append(yield_text)
    for group in ingredient_groups:
        parts.extend(group.get("ingredients", []))
    return "\n".join(parts)


def detect_measurement_hints(
    ingredient_groups: list[dict], yield_text: str | None = None
) -> list[dict[str, str]]:
    """Return conversion hints for units found in the recipe."""
    blob = _text_blob(ingredient_groups, yield_text)
    if not blob:
        return []

    hints: list[dict[str, str]] = []
    for entry in CONVERSION_REFERENCE:
        pattern = entry["pattern"]
        if isinstance(pattern, re.Pattern) and pattern.search(blob):
            hints.append({"from": str(entry["from"]), "to": str(entry["to"])})

    return hints
