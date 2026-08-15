import re


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _has_single_camera_bag(source_text: str) -> bool:
    source = _normalized(source_text)
    if "camera bag" not in source:
        return False
    if re.search(r"\bcamera bags\b", source):
        return False
    if re.search(r"\b(?:two|three|four|multiple|several)\s+camera\s+bags?\b", source):
        return False
    return True


def apply_visual_proof_constraints(
    source_text: str,
    prompt: str,
    negative_prompt: str,
) -> tuple[str, str]:
    """Add deterministic, source-grounded constraints for common SDXL drift."""
    source = _normalized(source_text)
    constrained_prompt = prompt.strip()
    normalized_prompt = _normalized(constrained_prompt)
    additions: list[str] = []
    negatives: list[str] = []

    if "cinema" in source or "movie theater" in source or "movie theatre" in source:
        if not (
            "rows of cinema seats" in normalized_prompt
            and "projection screen" in normalized_prompt
        ):
            additions.append(
                "The location must read unmistakably as a cinema auditorium, with visible rows of cinema seats and a projection screen."
            )
        if "abandoned" in source or "forgotten" in source or "derelict" in source:
            additions.append("The cinema is visibly abandoned and decayed.")
        negatives.extend(["warehouse", "industrial hall", "empty factory"])

    if _has_single_camera_bag(source_text):
        constrained_prompt, replacements = re.subn(
            r"\b(?:a|one)\s+small\s+camera\s+bag\b",
            "exactly one small camera bag",
            constrained_prompt,
            count=1,
            flags=re.IGNORECASE,
        )
        if replacements == 0:
            constrained_prompt, replacements = re.subn(
                r"\ba\s+camera\s+bag\b",
                "exactly one small camera bag",
                constrained_prompt,
                count=1,
                flags=re.IGNORECASE,
            )
        if replacements == 0:
            additions.append("Exactly one small camera bag is carried by the principal subject.")
        additions.append("No additional bag, backpack, case, or luggage is present.")
        negatives.extend(
            [
                "extra bag",
                "multiple bags",
                "duplicate bag",
                "additional backpack",
                "extra case",
                "extra luggage",
            ]
        )

    constrained_prompt = " ".join([constrained_prompt, *additions]).strip()
    negative_items = [item.strip() for item in negative_prompt.split(",") if item.strip()]
    for item in negatives:
        if item.lower() not in {existing.lower() for existing in negative_items}:
            negative_items.append(item)

    return constrained_prompt, ", ".join(negative_items)
