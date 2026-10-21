"""Preserve explicit scene facts when the legacy extractor cannot identify them."""


def source_scene_fallback(source: str, subject: str, environment: str) -> str | None:
    if subject != "the principal subject" and environment != "the described location":
        return None
    # A small vocabulary of human subjects and locations must not erase other
    # products, animals, settings, colours or materials supplied by the user.
    source = " ".join(source.split()).strip()
    return f"Photorealistic still image of the following scene: {source}"
