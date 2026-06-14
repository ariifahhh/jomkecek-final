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

# Topics that require live LLM knowledge — not answerable from a static dataset.
# Queries hitting these tokens (with a Kelantan signal) skip RAG entirely and go
# straight to the LLM so answers stay up-to-date.
DYNAMIC_TOPICS = frozenset({
    "sultan",
    "menteri",
    "mb",
    "ekonomi",
    "kerajaan",
    "politik",
    "penduduk",
    "populasi",
    "cuaca",
    "banjir",
    "monsun",
})


def _is_dynamic_topic(tokens: set[str]) -> bool:
    return bool(tokens & DYNAMIC_TOPICS)


def _intent_and_collections(normalized: str) -> tuple[str, list[str]]:
    tokens = set(tokenize(normalized))
    if "makanan" in tokens:
        return "food", ["food"]
    if {"nasi", "kerabu", "budu", "ulam", "percik", "laksa", "laksam", "akok", "kuih",
            "gulai", "sambal", "rendang", "lemang", "satay", "budu", "solok"} & tokens:
        return "food", ["food"]
    if {"budaya", "kraftangan", "wayang", "dikir", "gasing", "wau", "batik",
            "songket", "tarian", "silat", "persembahan", "tradisional", "seni",
            "permainan", "kulit", "patung", "anyaman", "ukiran"} & tokens:
        return "culture", ["culture"]
    if {"tempat", "menarik", "pantai", "pasar", "muzium", "pelancongan"} & tokens:
        return "tourism", ["tourism"]
    if {"jajahan", "ibu", "negeri", "sungai", "bendera", "gelaran", "lokasi",
            "lapangan", "terbang", "stadium", "tanah", "tinggi", "gua"} & tokens:
        return "general_fact", ["canonical_facts", "qa_umum_kelantan"]
    return "unknown", ["qa_umum_kelantan", "tourism", "food", "culture"]


def route_query(query: str, selected_mode: str = "Auto") -> dict:
    normalized = normalize_query(query)
    tokens = tokenize(normalized)
    token_set = set(tokens)
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
        # Even in explicit Info mode, dynamic topics go to LLM knowledge
        if _is_dynamic_topic(token_set):
            return {
                "mode": "llm_knowledge",
                "intent": "dynamic",
                "normalized_query": normalized,
                "collection_filter": [],
            }
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

    kelantan_signal = "kelantan" in normalized
    if kelantan_signal and _is_dynamic_topic(token_set):
        return {
            "mode": "llm_knowledge",
            "intent": "dynamic",
            "normalized_query": normalized,
            "collection_filter": [],
        }

    intent, collections = _intent_and_collections(normalized)
    has_kelantan = kelantan_signal or intent != "unknown"
    return {
        "mode": "general_qa" if has_kelantan else "dialect_translation",
        "intent": intent if has_kelantan else "unknown",
        "normalized_query": normalized,
        "collection_filter": collections if has_kelantan else ["dialect_words"],
    }
