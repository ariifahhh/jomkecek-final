from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

try:
    from rapidfuzz import fuzz, process
except Exception:
    fuzz = None
    process = None

from .config import LOW_TRANSLATION_CONFIDENCE
from .preprocessing import normalize_text, tokenize


DIALECT_DICT = {
    "mu": {"bm": "awak", "contoh": "Mu gi mano petang ni?"},
    "mung": {"bm": "awak", "contoh": "Mung nok gi mano?"},
    "demo": {"bm": "awak", "contoh": "Demo sihat ko hari ni?", "contoh_bm": "Awak sihat ke hari ini?"},
    "kawe": {"bm": "saya", "contoh": "Kawe nok makey nasi."},
    "ambo": {"bm": "saya", "contoh": "Ambo nok gi pasar."},
    "dio": {"bm": "dia", "contoh": "Dio kato nok mari esok."},
    "nok": {"bm": "nak", "contoh": "Mu nok gi mano?"},
    "gi": {"bm": "pergi", "contoh": "Kawe gi Kota Bharu."},
    "mano": {"bm": "mana", "contoh": "Mano rumah mu?"},
    "gapo": {"bm": "apa", "contoh": "Mu nok makey gapo?"},
    "gapey": {"bm": "apa", "contoh": "Gapey demo cari?"},
    "makey": {"bm": "makan", "contoh": "Mu nok makey gapo?"},
    "make": {"bm": "makan", "contoh": "Kawe make nasi kerabu."},
    "sihat": {"bm": "sihat", "contoh": "Demo sihat ko?"},
    "ko": {"bm": "ke", "contoh": "Demo sihat ko?"},
    "tok": {"bm": "tidak", "contoh": "Demo tok makey ko?", "contoh_bm": "Awak tidak makan ke?"},
    "dok": {"bm": "tidak", "contoh": "Demo dok gi ko?"},
    "ore": {"bm": "orang", "contoh": "Ore Kelate ramah."},
    "kelate": {"bm": "Kelantan", "contoh": "Kawe ore Kelate."},
    "rumoh": {"bm": "rumah", "contoh": "Rumoh mu mano?"},
    "mok": {"bm": "mak / ibu", "contoh": "Mok gi pasar pagi takdih.", "contoh_bm": "Mak pergi pasar pagi tadi."},
    "pasar": {"bm": "pasar", "contoh": "Kawe gi pasar pagi takdih."},
    "pagi": {"bm": "pagi", "contoh": "Kawe gi pasar pagi takdih."},
    "takdih": {"bm": "tadi", "contoh": "Kawe gi pasar pagi takdih."},
    "sedak": {"bm": "sedap", "contoh": "Nasi kerabu ni sedak doh.", "contoh_bm": "Nasi kerabu ini sedap sangat."},
    "doh": {"bm": "penegas / sangat", "contoh": "Nasi kerabu ni sedak doh.", "contoh_bm": "Nasi kerabu ini sedap sangat."},
}


KNOWN_SENTENCES = {
    "mu nok gi mano": "Awak nak pergi mana?",
    "mu nok makey gapo": "Awak nak makan apa?",
    "demo sihat ko": "Awak sihat ke?",
    "mano rumah mu": "Mana rumah awak?",
    "sedak doh": "Sedap sangat.",
    "mok gi pasar pagi takdih": "Mak pergi pasar pagi tadi.",
}

BM_TO_DIALECT = {
    "saya": {"dialek": "ambo", "contoh": "Ambo nok makey nasi kerabu.", "contoh_bm": "Saya nak makan nasi kerabu."},
    "awak": {"dialek": "mu", "contoh": "Mu nok gi mano?"},
    "kamu": {"dialek": "mu", "contoh": "Mu nok gi mano?"},
    "orang": {"dialek": "ore", "contoh": "Ore tu mari dari Kota Bharu."},
    "itu": {"dialek": "tu", "contoh": "Ore tu mari dari Kota Bharu."},
    "datang": {"dialek": "mari", "contoh": "Ore tu mari dari Kota Bharu."},
    "dari": {"dialek": "dari", "contoh": "Ore tu mari dari Kota Bharu."},
    "nak": {"dialek": "nok", "contoh": "Ambo nok makey nasi kerabu."},
    "mahu": {"dialek": "nok", "contoh": "Ambo nok makey nasi kerabu."},
    "sedang": {"dialek": "tengah", "contoh": "Mu tengah buat gapo?"},
    "buat": {"dialek": "buat", "contoh": "Mu tengah buat gapo?"},
    "makan": {"dialek": "makey", "contoh": "Ambo nok makey nasi kerabu."},
    "pergi": {"dialek": "gi", "contoh": "Kawe gi Kota Bharu."},
    "mana": {"dialek": "mano", "contoh": "Mu gi mano?"},
    "apa": {"dialek": "gapo", "contoh": "Mu nok makey gapo?"},
    "tidak": {"dialek": "tok", "contoh": "Demo tok makey ko?"},
    "tahu": {"dialek": "tahu", "contoh": "Ambo tok tahu jalan gi ko Pasar Siti Khadijah."},
    "jalan": {"dialek": "jalan", "contoh": "Ambo tok tahu jalan gi ko Pasar Siti Khadijah."},
    "ke": {"dialek": "ko", "contoh": "Demo sihat ko?"},
    "pasar": {"dialek": "pasar", "contoh": "Ambo tok tahu jalan gi ko Pasar Siti Khadijah."},
    "kota": {"dialek": "Kota", "contoh": "Ore tu mari dari Kota Bharu."},
    "bharu": {"dialek": "Bharu", "contoh": "Ore tu mari dari Kota Bharu."},
    "siti": {"dialek": "Siti", "contoh": "Ambo tok tahu jalan gi ko Pasar Siti Khadijah."},
    "khadijah": {"dialek": "Khadijah", "contoh": "Ambo tok tahu jalan gi ko Pasar Siti Khadijah."},
}


def sentence_match(query: str, threshold: int = 88) -> tuple[str | None, int]:
    clean = normalize_text(query)
    if clean in KNOWN_SENTENCES:
        return KNOWN_SENTENCES[clean], 100
    choices = list(KNOWN_SENTENCES)
    if process:
        match = process.extractOne(clean, choices, scorer=fuzz.ratio)
        if match and match[1] >= threshold:
            return KNOWN_SENTENCES[match[0]], int(match[1])
    else:
        best = max(choices, key=lambda c: SequenceMatcher(None, clean, c).ratio())
        score = int(SequenceMatcher(None, clean, best).ratio() * 100)
        if score >= threshold:
            return KNOWN_SENTENCES[best], score
    return None, 0


def word_lookup(word: str, threshold: int = 82) -> tuple[str | None, dict[str, str] | None, int]:
    if word in DIALECT_DICT:
        return word, DIALECT_DICT[word], 100
    choices = list(DIALECT_DICT)
    if process:
        match = process.extractOne(word, choices, scorer=fuzz.ratio)
        if match and match[1] >= threshold:
            return match[0], DIALECT_DICT[match[0]], int(match[1])
    else:
        best = max(choices, key=lambda c: SequenceMatcher(None, word, c).ratio())
        score = int(SequenceMatcher(None, word, best).ratio() * 100)
        if score >= threshold:
            return best, DIALECT_DICT[best], score
    return None, None, 0


def clean_translation(text: str) -> str:
    replacements = {
        "awak nak pergi mana": "Awak nak pergi mana?",
        "awak nak makan apa": "Awak nak makan apa?",
        "awak sihat ke": "Awak sihat ke?",
        "awak tidak makan ke": "Awak tidak makan ke?",
    }
    lower = text.lower().strip(" ?!.")
    if lower in replacements:
        return replacements[lower]
    if text and not text.endswith((".", "?", "!")):
        text += "."
    return text[:1].upper() + text[1:]


def detect_language_mode(clean_query: str) -> str:
    tokens = tokenize(clean_query)
    dialect_hits = sum(1 for token in tokens if token in DIALECT_DICT)
    bm_hits = sum(1 for token in tokens if token in BM_TO_DIALECT)
    if bm_hits > dialect_hits:
        return "bm"
    if dialect_hits and bm_hits:
        return "mixed"
    if dialect_hits:
        return "dialect"
    if bm_hits:
        return "bm"
    return "unknown"


def _confidence_label(coverage: float) -> str:
    if coverage >= 0.85:
        return "Tinggi"
    if coverage >= 0.50:
        return "Sederhana"
    return "Rendah"


def _translate_bm_to_dialect(words: list[str]) -> dict[str, Any]:
    translated = []
    breakdown = []
    known = 0
    for word in words:
        data = BM_TO_DIALECT.get(word)
        if data:
            known += 1
            translated.append(data["dialek"])
            breakdown.append(
                {
                    "dialect": word,
                    "matched": word,
                    "bm": data["dialek"],
                    "contoh": data["contoh"],
                    "contoh_bm": data.get("contoh_bm", ""),
                    "contoh_bm": data.get("contoh_bm", ""),
                    "confidence": 1.0,
                }
            )
        else:
            translated.append(word)
            breakdown.append(
                {
                    "dialect": word,
                    "matched": None,
                    "bm": "makna kurang pasti dalam pangkalan data",
                    "contoh": "",
                    "confidence": 0.0,
                }
            )

    coverage = known / max(len(words), 1)
    sentence = clean_translation(" ".join(translated))
    example = next((item["contoh"] for item in breakdown if item.get("contoh")), "")
    example_meaning = next((item["contoh_bm"] for item in breakdown if item.get("contoh_bm")), "")
    return {
        "translation": sentence,
        "breakdown": breakdown,
        "confidence": round(coverage, 2),
        "confidence_label": _confidence_label(coverage),
        "direction": "bm_to_dialect",
        "example": example,
        "example_meaning": example_meaning,
        "strict": True,
    }


def translate(query: str) -> dict[str, Any]:
    clean = normalize_text(query)
    language_mode = detect_language_mode(clean)
    sentence_translation, sentence_score = sentence_match(clean)
    words = tokenize(clean)

    if language_mode == "bm":
        return _translate_bm_to_dialect(words)

    breakdown = []
    translated = []
    known = 0

    for word in words:
        matched, data, score = word_lookup(word)
        if data:
            known += 1
            translated.append(data["bm"])
            breakdown.append(
                {
                    "dialect": word,
                    "matched": matched,
                    "bm": data["bm"],
                    "contoh": data["contoh"],
                    "contoh_bm": data.get("contoh_bm", ""),
                    "confidence": round(score / 100, 2),
                }
            )
        else:
            translated.append("")
            breakdown.append(
                {
                    "dialect": word,
                    "matched": None,
                    "bm": "makna kurang pasti dalam pangkalan data",
                    "contoh": "",
                    "contoh_bm": "",
                    "confidence": 0.0,
                }
            )

    confidence = known / max(len(words), 1)
    if sentence_translation:
        confidence = max(confidence, sentence_score / 100)
    translation_words = [word for word in translated if word]
    translation = sentence_translation or clean_translation(" ".join(translation_words))

    if not words or confidence < LOW_TRANSLATION_CONFIDENCE:
        translation = "Maaf, saya kurang pasti dengan maksud tersebut."

    example = next((item["contoh"] for item in breakdown if item.get("contoh")), "")
    example_meaning = next((item["contoh_bm"] for item in breakdown if item.get("contoh_bm")), "")
    query_tokens = set(words)
    if {"demo", "tok", "makey", "ko"}.issubset(query_tokens):
        example = "Demo tok makey ko?"
        example_meaning = "Awak tidak makan ke?"

    return {
        "translation": translation,
        "breakdown": breakdown,
        "confidence": round(confidence, 2),
        "confidence_label": _confidence_label(confidence),
        "direction": "dialect_to_bm",
        "example": example,
        "example_meaning": example_meaning,
        "strict": True,
    }


def translate_dialect(query: str) -> dict[str, Any]:
    return translate(query)
