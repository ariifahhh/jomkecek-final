from __future__ import annotations

from .guards import detect_out_of_scope
from .preprocessing import normalize_query, tokenize


DIALECT_WORDS = {
    "mu",
    "mung",
    "demo",
    "kawe",
    "ambo",
    "nok",
    "gapo",
    "mano",
    "makey",
    "gi",
    "ko",
    "tok",
    "dok",
    "doh",
    "sedak",
    "takdih",
}


def _intent_and_collections(normalized: str) -> tuple[str, list[str]]:
    tokens = set(tokenize(normalized))
    if {"makanan", "tradisional"} & tokens:
        return "food", ["food"]
    if {"nasi", "kerabu", "budu", "ulam", "percik", "laksa", "laksam", "akok", "kuih"} & tokens:
        return "food", ["food"]
    if "budaya" in tokens:
        return "culture", ["culture"]
    if {"tempat", "menarik", "pantai", "pasar", "muzium", "pelancongan"} & tokens:
        return "tourism", ["tourism"]
    if {"jajahan", "ibu", "negeri", "sungai", "bendera", "gelaran", "sultan", "muhammad"} & tokens:
        return "general_fact", ["canonical_facts", "qa_umum_kelantan"]
    if {"cuaca", "monsun", "banjir", "hujan"} & tokens:
        return "geography", ["qa_umum_kelantan"]
    return "unknown", ["qa_umum_kelantan", "tourism", "food", "culture"]


def route_query(query: str, selected_mode: str = "Auto") -> dict:
    normalized = normalize_query(query)
    tokens = tokenize(normalized)
    dialect_count = sum(1 for token in tokens if token in DIALECT_WORDS)

    if detect_out_of_scope(normalized):
        return {
            "mode": "out_of_scope",
            "intent": "out_of_scope",
            "normalized_query": normalized,
            "collection_filter": [],
        }

    if selected_mode == "Terjemahan Dialek" or "terjemah" in normalized or "maksud" in normalized:
        return {
            "mode": "dialect_translation",
            "intent": "dialect",
            "normalized_query": normalized,
            "collection_filter": ["dialect_words", "dialect_phrases", "dialect_sentences"],
        }

    if selected_mode == "Info Kelantan":
        intent, collections = _intent_and_collections(normalized)
        return {
            "mode": "general_qa",
            "intent": intent,
            "normalized_query": normalized,
            "collection_filter": collections,
        }

    coverage = dialect_count / max(len(tokens), 1)
    if dialect_count >= 2 or coverage >= 0.5:
        return {
            "mode": "dialect_translation",
            "intent": "dialect",
            "normalized_query": normalized,
            "collection_filter": ["dialect_words", "dialect_phrases", "dialect_sentences"],
        }

    intent, collections = _intent_and_collections(normalized)
    kelantan_signal = "kelantan" in normalized or intent != "unknown"
    return {
        "mode": "general_qa" if kelantan_signal else "dialect_translation",
        "intent": intent if kelantan_signal else "unknown",
        "normalized_query": normalized,
        "collection_filter": collections if kelantan_signal else ["dialect_words"],
    }
