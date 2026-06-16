import re
import unicodedata


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", str(text))
    text = text.lower()
    text = re.sub(r"[^\w\s']", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_query(text: str) -> str:
    return normalize_text(text)


def tokenize(text: str) -> list[str]:
    return re.findall(r"[\w']+", normalize_text(text), flags=re.UNICODE)
