import re


def normalize_repeated_chars(text: str) -> str:
    """Reduce noisy spellings such as gapooo -> gapoo before fuzzy matching."""
    return re.sub(r"(.)\1{2,}", r"\1\1", text)


def normalize_text(text: str) -> str:
    text = str(text).lower()
    text = normalize_repeated_chars(text)
    text = re.sub(r"[^\w\s']", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    replacements = {
        "dareh": "daerah",
        "daerah": "jajahan",
        "paling besar": "terbesar",
        "paling luas": "terbesar dari segi keluasan",
        "dooh": "doh",
        "dohh": "doh",
        "makang": "makey",
    }
    for source, target in replacements.items():
        text = re.sub(rf"\b{re.escape(source)}\b", target, text)
    return text


def normalize_query(text: str) -> str:
    return normalize_text(text)


def tokenize(text: str) -> list[str]:
    return re.findall(r"[\w']+", normalize_text(text), flags=re.UNICODE)
