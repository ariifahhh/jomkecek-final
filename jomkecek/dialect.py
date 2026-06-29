from __future__ import annotations

from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any

try:
    from rapidfuzz import fuzz, process
except Exception:
    fuzz = None
    process = None

from .config import LOW_TRANSLATION_CONFIDENCE
from .preprocessing import normalize_text, tokenize


# Phonological suffix transformation rules for words NOT in dictionary.
# Longer suffixes checked first to avoid partial matches.
# Based on standard Kelantanese dialect phonology patterns.
# Common BM words that are phonologically identical in Kelantan dialect.
# These are passed through unchanged rather than mangled by suffix rules.
_KELANTAN_SAME: frozenset[str] = frozenset({
    "pantai", "sungai", "padang", "bukit", "pulau", "tasik",
    "nasi", "ayam", "ikan", "daging", "kerabu", "keropok", "budu",
    "jalan", "lorong", "bandar", "kampung", "kampong", "mukim",
    "masjid", "surau", "sekolah", "hospital", "balai", "dewan",
    "pasar", "bazaar", "taman", "hutan", "kebun", "sawah",
    "hotel", "resort", "terminal", "stesen",
    "polis", "bomba", "tentera",
    "kereta", "moto", "bas", "bot", "kapal", "lori", "van",
    "telefon", "komputer", "internet", "radio", "televisyen",
    "ringgit", "sen", "wang",
    "doktor", "guru", "peguam", "arkitek", "jurutera",
    # Common nouns same in both BM and Kelantan
    "beli", "dikir", "cenderamata", "persembahan",
    # Common function words and particles same in both BM and Kelantan
    "lagi", "pun", "pula", "juga", "kalau", "bila",
    "atau", "tapi", "tetapi", "sebab", "kerana",
    "boleh", "perlu", "mesti", "kena",
    "balik",  # return/go back — same in both BM and Kelantan
    # Proper noun components that should not be transformed
    "bharu", "bahru", "besar", "lama", "bahagian",
    "kota", "kuala", "gua", "pasir", "tumpat", "bachok",
})

# Core BM→Kelantan vocabulary not reliably covered by Excel data
_BM_TO_KELANTAN_CORE: dict[str, str] = {
    "pergi": "gi",
    "pi": "gi",
    "hendak": "nok",
    "mahu": "nok",
    "nak": "nok",
    "saya": "ambo",
    "aku": "ambo",
    "awak": "mu",
    "kamu": "mu",
    "anda": "mu",
    "dia": "dio",
    "mereka": "deme",
    "kita": "kito",
    "kami": "kito",
    "makan": "makey",
    "tidur": "tido",
    "tidak": "tak",
    "bukan": "buke",
    "ada": "ado",
    "cakap": "kecek",
    "bercakap": "kecek",
    "apa": "gapo",
    "mana": "mano",
    "ini": "ni",
    "itu": "tu",
    "kenapa": "bakpo",
    "mengapa": "bakpo",
    "sudah": "doh",
    "bila": "bilo",
    "dengan": "nga",
    "rumah": "ghuma",
    "pulang": "balik",
    "nama": "name",
    "hari": "ari",
    "bulan": "bule",
    "tahun": "taun",
    "sekarang": "kini",
    "nanti": "jap gi",
    "kejap": "sekejap",
    "bagaimana": "guano",
    "berapa": "ropo",
    "siapa": "siapo",
    "di mana": "kat mano",
    "di": "kat",
    "pada": "kat",
    "boleh": "buleh",
    "kurang": "kughe",
    "harga": "ghego",
    "kasih": "kaseh",
    "terima": "teghimo",
    "terima kasih": "teghimo kaseh",
    "membantu": "tulong",
    "bantu": "tulong",
    "tolong": "tulong",
    "datang": "maghi",
    "tengok": "kelih",
    "lihat": "kelih",
    "ambil": "amek",
    "gambar": "gamba",
    "untuk": "untok",
    "sewa": "sewo",
    "tempah": "tepoh",
    "tempat": "tepak",
    "malam": "male",
    "semalam": "semale",
    "jalan": "jale",
    "sampai": "sapa",
    "duduk": "duk",
    "keluar": "tubek",
    "masuk": "masok",
    "berapa": "bapo",
    "pukul": "puko",
    "orang": "oghe",
    "duit": "pitih",
    "wang": "pitih",
    "sekarang": "loni",
    "cenderamata": "cenderamato",
    "dikir": "dikir",
    "beli": "beli",
}

# Core Kelantan→BM vocabulary — takes priority over Excel for these basic words
# because Excel entries may have incorrect or overly literal BM translations.
_KELANTAN_TO_BM_CORE: dict[str, str] = {
    "gi": "pergi",
    "pi": "pergi",
    "nok": "hendak / nak",
    "ambo": "saya",
    "mu": "awak / kamu",
    "dio": "dia",
    "deme": "mereka",
    "kito": "kita",
    "kawe": "saya / kami",
    "demo": "awak / anda",
    "ko": "ke / tak",
    "makey": "makan",
    "tido": "tidur",
    "gapo": "apa",
    "mano": "mana",
    "ni": "ini",
    "tu": "itu",
    "bakpo": "kenapa",
    "doh": "sudah",
    "bilo": "bila",
    "nga": "dengan",
    "ghuma": "rumah",
    "rumoh": "rumah",
    "name": "nama",
    "ari": "hari",
    "bule": "bulan",
    "kini": "sekarang",
    "guano": "bagaimana",
    "ropo": "berapa",
    "siapo": "siapa",
    "kecek": "cakap / bercakap",
    "ado": "ada",
    "dok": "tidak ada / tidak",
    "buke": "bukan",
    "taun": "tahun",
    "ore": "orang",
    "sedak": "sedap / enak",
    "make": "makan",
    "makey": "makan",
    "keghabu": "kerabu",
    "kepok": "keropok",
    "leko": "lekor",
    "pata": "pantai",
    # --- perkataan tambahan ---
    "kat": "di / pada",
    "buleh": "boleh",
    "cenderamato": "cenderamata",
    "hadioh": "hadiah / barangan",
    "kughe": "kurang",
    "ghego": "harga",
    "rego": "harga",
    "pitih": "duit / wang",
    "oghe": "orang",
    "tepak": "tempat",
    "male": "malam",
    "pagi": "pagi",
    "haghi": "hari",
    "semale": "semalam",
    "loni": "sekarang / hari ini",
    "jale": "jalan",
    "sapa": "sampai",
    "duk": "duduk / tinggal",
    "tubek": "keluar",
    "masok": "masuk",
    "bapo": "berapa",
    "puko": "pukul",
    "kaseh": "kasih",
    "teghimo": "terima",
    "tulong": "tolong / bantu",
    "maghi": "datang",
    "diki": "dikir",
    "baghat": "barat",
    "tengok": "tengok / lihat",
    "kelih": "lihat / tengok",
    "amek": "ambil",
    "gamba": "gambar",
    "untok": "untuk",
    "sewo": "sewa",
    "tepoh": "tempah",
    # --- takdih / lain ---
    "takdih": "tidak ada",
    "dale": "dalam",
    "lamo": "lama",
    "beso": "besar",
    "kecik": "kecil",
    "cepak": "cepat",
    "lambak": "lambat",
    "cantik": "cantik",
    "molek": "cantik / elok",
    "hok": "yang",
    "pasa": "pasal / tentang",
}

SUFFIX_RULES: list[tuple[str, str]] = [
    # 3-char (most specific first)
    ("lak", "lak"),
    ("lah", "lah"),
    ("ang", "e"),
    ("ing", "ing"),
    ("eng", "eng"),
    ("ong", "ong"),
    ("ung", "ung"),
    # 2-char
    ("in", "ing"),
    ("en", "eng"),
    ("on", "ong"),
    ("un", "ung"),
    ("us", "uh"),
    ("au", "a"),
    ("ai", "a"),
    ("ar", "a"),
    ("ut", "uk"),
    ("is", "ih"),
    ("at", "ak"),
    ("ap", "ak"),
    ("as", "ah"),
    ("ur", "o"),
    ("ah", "oh"),
    ("ak", "ok"),
    ("am", "e"),
    ("an", "e"),
    ("la", "la"),
    # 1-char (least specific)
    ("a", "o"),
]


def apply_suffix_rule(word: str) -> str | None:
    """Apply Kelantanese phonological suffix transformation for unknown words."""
    if len(word) < 2:
        return None
    for suffix, replacement in SUFFIX_RULES:
        if word.endswith(suffix) and len(word) > len(suffix):
            return word[: -len(suffix)] + replacement
    return None


@lru_cache(maxsize=1)
def _dialect_dict() -> dict[str, dict]:
    """Load dialect word dictionary from perkataan sheet in Excel."""
    from .data import load_documents
    result: dict[str, dict] = {}
    for doc in load_documents():
        if doc.collection != "perkataan":
            continue
        meta = doc.metadata
        dialek_raw = meta.get("dialek_perkataan", "").strip()
        bm = meta.get("bm_perkataan", "").strip()
        if not dialek_raw or not bm:
            continue
        # Index all slash-separated variants e.g. "agah / hagah"
        for variant in dialek_raw.replace("/", "|").split("|"):
            key = variant.strip().lower()
            if key and key not in result:
                result[key] = {"bm": bm, "contoh": ""}
    return result


@lru_cache(maxsize=1)
def _known_sentences() -> dict[str, str]:
    """Load example sentences from contoh_ayat sheet: dialect → BM."""
    from .data import load_documents
    result: dict[str, str] = {}
    for doc in load_documents():
        if doc.collection != "contoh_ayat":
            continue
        meta = doc.metadata
        dialek = normalize_text(meta.get("dialek_ayat", ""))
        bm = meta.get("bm_ayat", "").strip()
        if dialek and bm:
            result[dialek] = bm
    return result


@lru_cache(maxsize=1)
def _bm_to_dialect() -> dict[str, dict]:
    """Reverse mapping: BM word → dialect word, built from perkataan sheet."""
    from .data import load_documents
    result: dict[str, dict] = {}
    for doc in load_documents():
        if doc.collection != "perkataan":
            continue
        meta = doc.metadata
        dialek_raw = meta.get("dialek_perkataan", "").strip()
        bm_raw = meta.get("bm_perkataan", "").strip()
        if not dialek_raw or not bm_raw:
            continue
        primary_dialek = dialek_raw.split("/")[0].strip().lower()
        # Index each BM word/phrase variant
        for bm_variant in bm_raw.replace("/", "|").split("|"):
            bm_key = bm_variant.strip().lower()
            if bm_key and bm_key not in result:
                result[bm_key] = {"dialek": primary_dialek, "contoh": ""}
    return result


def sentence_match(query: str, threshold: int = 88) -> tuple[str | None, int]:
    sentences = _known_sentences()
    if not sentences:
        return None, 0
    clean = normalize_text(query)
    if clean in sentences:
        return sentences[clean], 100
    choices = list(sentences)
    if process:
        match = process.extractOne(clean, choices, scorer=fuzz.ratio)
        if match and match[1] >= threshold:
            return sentences[match[0]], int(match[1])
    else:
        best = max(choices, key=lambda c: SequenceMatcher(None, clean, c).ratio())
        score = int(SequenceMatcher(None, clean, best).ratio() * 100)
        if score >= threshold:
            return sentences[best], score
    return None, 0


def word_lookup(word: str, threshold: int = 82) -> tuple[str | None, dict | None, int]:
    d = _dialect_dict()
    if not d:
        return None, None, 0
    if word in d:
        return word, d[word], 100
    choices = list(d)
    if process:
        match = process.extractOne(word, choices, scorer=fuzz.ratio)
        if match and match[1] >= threshold:
            return match[0], d[match[0]], int(match[1])
    else:
        best = max(choices, key=lambda c: SequenceMatcher(None, word, c).ratio())
        score = int(SequenceMatcher(None, word, best).ratio() * 100)
        if score >= threshold:
            return best, d[best], score
    return None, None, 0


def clean_translation(text: str) -> str:
    if text and not text.endswith((".", "?", "!")):
        text += "."
    return text[:1].upper() + text[1:] if text else text


def detect_language_mode(clean_query: str) -> str:
    d = _dialect_dict()
    b = _bm_to_dialect()
    tokens = tokenize(clean_query)
    # Count hits from Excel dicts plus hardcoded core vocab
    dialect_hits = sum(1 for t in tokens if t in d or t in _KELANTAN_TO_BM_CORE)
    bm_hits = sum(1 for t in tokens if t in b or t in _BM_TO_KELANTAN_CORE)
    # Words in _KELANTAN_SAME are ambiguous — don't count them for either side
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
    b = _bm_to_dialect()
    translated = []
    breakdown = []
    known = 0
    for word in words:
        data = b.get(word)
        if data:
            known += 1
            translated.append(data["dialek"])
            breakdown.append({
                "dialect": word,
                "matched": word,
                "bm": data["dialek"],
                "contoh": data.get("contoh", ""),
                "contoh_bm": "",
                "confidence": 1.0,
            })
        elif word in _KELANTAN_SAME:
            known += 1
            translated.append(word)
            breakdown.append({
                "dialect": word,
                "matched": word,
                "bm": word,
                "contoh": "",
                "contoh_bm": "",
                "confidence": 0.8,
            })
        elif word in _BM_TO_KELANTAN_CORE:
            kelantan_word = _BM_TO_KELANTAN_CORE[word]
            known += 1
            translated.append(kelantan_word)
            breakdown.append({
                "dialect": word,
                "matched": word,
                "bm": kelantan_word,
                "contoh": "",
                "contoh_bm": "",
                "confidence": 0.85,
            })
        else:
            # Apply suffix rule as phonological approximation
            approx = apply_suffix_rule(word)
            if approx:
                translated.append(approx)
                breakdown.append({
                    "dialect": word,
                    "matched": None,
                    "bm": approx,
                    "contoh": "",
                    "contoh_bm": "",
                    "confidence": 0.3,
                    "approximated": True,
                })
            else:
                translated.append(word)
                breakdown.append({
                    "dialect": word,
                    "matched": None,
                    "bm": "tiada dalam pangkalan data",
                    "contoh": "",
                    "confidence": 0.0,
                })

    coverage = known / max(len(words), 1)
    sentence = clean_translation(" ".join(translated))
    example = next((item["contoh"] for item in breakdown if item.get("contoh")), "")
    return {
        "translation": sentence,
        "breakdown": breakdown,
        "confidence": round(coverage, 2),
        "confidence_label": _confidence_label(coverage),
        "direction": "bm_to_dialect",
        "example": example,
        "example_meaning": "",
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
        # Check hardcoded core vocab first — Excel can have wrong BM for basic pronouns/verbs
        if word in _KELANTAN_TO_BM_CORE:
            bm_word = _KELANTAN_TO_BM_CORE[word]
            known += 1
            translated.append(bm_word.split("/")[0].strip())
            breakdown.append({
                "dialect": word,
                "matched": word,
                "bm": bm_word,
                "contoh": "",
                "contoh_bm": "",
                "confidence": 0.9,
            })
            continue
        matched, data, score = word_lookup(word)
        if data:
            known += 1
            translated.append(data["bm"])
            breakdown.append({
                "dialect": word,
                "matched": matched,
                "bm": data["bm"],
                "contoh": data.get("contoh", ""),
                "contoh_bm": "",
                "confidence": round(score / 100, 2),
            })
        elif word in _KELANTAN_TO_BM_CORE:
            bm_word = _KELANTAN_TO_BM_CORE[word]
            known += 1
            translated.append(bm_word.split("/")[0].strip())
            breakdown.append({
                "dialect": word,
                "matched": word,
                "bm": bm_word,
                "contoh": "",
                "contoh_bm": "",
                "confidence": 0.85,
            })
        elif word in _KELANTAN_SAME:
            known += 1
            translated.append(word)
            breakdown.append({
                "dialect": word,
                "matched": word,
                "bm": word,
                "contoh": "",
                "contoh_bm": "",
                "confidence": 0.8,
            })
        else:
            # Try suffix rule as fallback approximation
            approx = apply_suffix_rule(word)
            if approx:
                translated.append(approx)
                breakdown.append({
                    "dialect": word,
                    "matched": None,
                    "bm": approx,
                    "contoh": "",
                    "contoh_bm": "",
                    "confidence": 0.3,
                    "approximated": True,
                })
            else:
                translated.append("")
                breakdown.append({
                    "dialect": word,
                    "matched": None,
                    "bm": "tiada dalam pangkalan data",
                    "contoh": "",
                    "contoh_bm": "",
                    "confidence": 0.0,
                })

    confidence = known / max(len(words), 1)
    if sentence_translation:
        confidence = max(confidence, sentence_score / 100)
    translation_words = [w for w in translated if w]
    translation = sentence_translation or clean_translation(" ".join(translation_words))

    if not words or confidence < LOW_TRANSLATION_CONFIDENCE:
        translation = "Maaf, perkataan ini tiada dalam pangkalan data dialek JomKecek."

    example = next((item["contoh"] for item in breakdown if item.get("contoh")), "")
    return {
        "translation": translation,
        "breakdown": breakdown,
        "confidence": round(confidence, 2),
        "confidence_label": _confidence_label(confidence),
        "direction": "dialect_to_bm",
        "example": example,
        "example_meaning": "",
        "strict": True,
    }


def translate_dialect(query: str) -> dict[str, Any]:
    return translate(query)
