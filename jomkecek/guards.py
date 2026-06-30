from __future__ import annotations

import re

from .preprocessing import normalize_query


OUT_OF_SCOPE_MESSAGE = (
    "Maaf, JomKecek hanya menyediakan maklumat berkaitan negeri Kelantan sahaja. "
    "Tiada maklumat diberikan untuk negeri atau negara lain."
)

WEAK_RAG_MESSAGE = "Maaf, maklumat ini tiada dalam pangkalan data JomKecek buat masa ini."

OUT_OF_SCOPE_TERMS = {
    "johor",
    "kedah",
    "melaka",
    "negeri sembilan",
    "pahang",
    "perak",
    "perlis",
    "pulau pinang",
    "penang",
    "sabah",
    "sarawak",
    "selangor",
    "terengganu",
    "kuala lumpur",
    "putrajaya",
    "labuan",
    "thailand",
    "indonesia",
    "singapore",
    "singapura",
    "brunei",
    "vietnam",
    "japan",
    "korea",
    "china",
    "india",
}

ENGLISH_REPLACEMENTS = {
    "current": "semasa",
    "website": "laman web",
    "beach": "pantai",
    "directions": "arah ke lokasi",
    "tourist attraction": "tempat pelancongan",
    "confidence": "keyakinan",
    "source": "sumber",
    "context": "konteks",
    "makanan_tradisional": "makanan",
    "history": "sejarah",
    "direct": "langsung",
    "reasoning": "penaakulan",
    "detail": "perincian",
    "recommendation": "cadangan",
}

PROPER_NOUNS = (
    "Kota Bharu",
    "Pasar Siti Khadijah",
    "Sultan Muhammad V",
    "Sungai Kelantan",
    "Gua Musang",
    "Pantai Cahaya Bulan",
    "Muzium Negeri Kelantan",
    "Istana Jahar",
    "Nasi Kerabu",
    "Ayam Percik",
)


def detect_out_of_scope(query: str) -> bool:
    normalized = normalize_query(query)
    if "kelantan di malaysia" in normalized or "lokasi kelantan di malaysia" in normalized:
        return False
    for term in OUT_OF_SCOPE_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", normalized):
            return True
    return False


def validate_bahasa_melayu_only(answer: str) -> str:
    cleaned = answer
    for english, malay in ENGLISH_REPLACEMENTS.items():
        cleaned = re.sub(rf"\b{re.escape(english)}\b", malay, cleaned, flags=re.I)
    return cleaned


def format_capitalization(answer: str) -> str:
    text = answer.strip()
    for name in PROPER_NOUNS:
        text = re.sub(re.escape(name), name, text, flags=re.I)

    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if stripped in {"Jawapan:", "Maklumat ringkas:", "Maklumat lanjut:", "Kesimpulan:", "Cadangan:", "Jawapan ringkas:"}:
            lines.append(stripped)
            continue
        if re.match(r"^\d+\.\s", stripped):
            prefix, rest = stripped.split(" ", 1)
            rest = rest[:1].upper() + rest[1:] if rest else rest
            lines.append(f"{prefix} {rest}")
            continue
        stripped = stripped[:1].upper() + stripped[1:] if stripped else stripped
        lines.append(stripped)
    return "\n".join(lines)


def final_response_guard(
    answer: str,
    query: str | None = None,
    context: str | None = None,
    out_of_scope: bool = False,
    weak_context: bool = False,
) -> str:
    if out_of_scope:
        return OUT_OF_SCOPE_MESSAGE
    if weak_context:
        return WEAK_RAG_MESSAGE
    return format_capitalization(validate_bahasa_melayu_only(answer))
