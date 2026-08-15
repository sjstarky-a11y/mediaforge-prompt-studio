import re


_AUTO_CORRECTABLE_LIGHTING_ISSUES = {
    "INVENTION: the final prompt adds specific lighting treatment that was not specified in the source.",
    "INVENTION: the final prompt adds cold visual treatment that was not specified in the source.",
}

_SPECIFIC_LIGHTING_TERMS = [
    "dimly lit",
    "predominantly dark",
    "dark lighting",
    "deep shadows",
    "utilize shadows",
    "use shadows",
]

_COLD_VISUAL_TERMS = [
    "cold visual",
    "cold lighting",
    "feel cold",
    "cool-toned",
]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _has_any(text: str, phrases: list[str]) -> bool:
    normalized = _normalize(text)
    return any(_normalize(phrase) in normalized for phrase in phrases)


def _clean_inline_spacing(text: str) -> str:
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"[ \t]+([,.;:])", r"\1", text)
    text = re.sub(r",[ \t]*([,.;:])", r"\1", text)
    return text


def _neutralize_unrequested_lighting(
    source: str,
    target: str,
    mode: str,
) -> tuple[str, list[str]]:
    """Remove only narrow, non-source lighting treatments from Improve output."""
    if mode != "improve":
        return target, []

    cleaned = target
    corrections: list[str] = []

    if not _has_any(source, _SPECIFIC_LIGHTING_TERMS):
        replacements = [
            (r"\bdimly lit\b", ""),
            (r"\bpredominantly dark\b", "controlled"),
            (r"\bdark lighting\b", "controlled lighting"),
            (r"\bdeep shadows\b", "controlled contrast"),
            (r"\butilize shadows\b", "use controlled lighting"),
            (r"\buse shadows\b", "use controlled lighting"),
        ]
        for pattern, replacement in replacements:
            updated, count = re.subn(
                pattern,
                replacement,
                cleaned,
                flags=re.IGNORECASE,
            )
            if count:
                cleaned = updated
                corrections.append("specific lighting treatment")

    if not _has_any(source, _COLD_VISUAL_TERMS):
        replacements = [
            (r"\bcold visual\b", "neutral visual"),
            (r"\bcold lighting\b", "controlled lighting"),
            (r"\bfeel cold\b", "feel visually coherent"),
            (r"\bcool-toned\b", "neutrally lit"),
        ]
        for pattern, replacement in replacements:
            updated, count = re.subn(
                pattern,
                replacement,
                cleaned,
                flags=re.IGNORECASE,
            )
            if count:
                cleaned = updated
                corrections.append("cold visual treatment")

    return _clean_inline_spacing(cleaned), list(dict.fromkeys(corrections))


def auto_correct_narrow_lighting_review(
    source: str,
    target: str,
    mode: str,
    issues: list[str],
) -> tuple[str, list[str]]:
    """Correct lighting-only Improve reviews without weakening other guards."""
    if (
        mode != "improve"
        or not issues
        or any(issue not in _AUTO_CORRECTABLE_LIGHTING_ISSUES for issue in issues)
    ):
        return target, []

    return _neutralize_unrequested_lighting(source, target, mode)


def detect_unrequested_creative_issues(
    source: str,
    target: str,
    mode: str,
) -> list[str]:
    """Detect concrete creative inventions that a weaker model may add."""
    source_normalized = _normalize(source)
    target_normalized = _normalize(target)
    issues: list[str] = []

    concept_groups = [
        (
            "emotional tone",
            [
                "introspective",
                "introspection",
                "determined",
                "determination",
                "melancholic",
                "melancholy",
                "unease",
                "unsettling",
                "isolated",
                "isolation",
            ],
        ),
        (
            "narrative premise",
            ["mystery", "mysterious", "journey"],
        ),
    ]

    if mode in {"improve", "shotlist"}:
        concept_groups.extend(
            [
                (
                    "specific lighting treatment",
                    _SPECIFIC_LIGHTING_TERMS,
                ),
                (
                    "cold visual treatment",
                    _COLD_VISUAL_TERMS,
                ),
            ]
        )

    for label, terms in concept_groups:
        if not _has_any(source_normalized, terms) and _has_any(
            target_normalized,
            terms,
        ):
            issues.append(
                f"INVENTION: the final prompt adds {label} that was not specified in the source."
            )

    return issues


def output_structure_issues(
    result: str,
    mode: str,
    require_mode_structure: bool = True,
) -> list[str]:
    if not require_mode_structure:
        return []

    if mode != "improve":
        return []

    upper = result.upper()
    diagnosis_position = upper.find("PROMPT DIAGNOSIS")
    improved_position = upper.rfind("IMPROVED PROMPT")

    if (
        diagnosis_position == -1
        or improved_position == -1
        or diagnosis_position >= improved_position
    ):
        return [
            "FORMAT: Improve mode did not return the required PROMPT DIAGNOSIS and IMPROVED PROMPT structure."
        ]

    diagnosis = result[diagnosis_position:improved_position]
    bullet_count = len(re.findall(r"(?m)^\s*[-*•]\s+", diagnosis))
    if bullet_count < 1 or bullet_count > 4:
        return [
            f"FORMAT: Improve mode requires 1 to 4 diagnosis bullets; detected {bullet_count}."
        ]

    return []
