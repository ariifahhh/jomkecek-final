from __future__ import annotations

from .guards import detect_out_of_scope
from .preprocessing import normalize_query, tokenize


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
        return "makanan_tradisional", ["makanan_tradisional"]
    if {"nasi", "kerabu", "budu", "ulam", "percik", "laksa", "laksam", "akok", "kuih",
            "gulai", "sambal", "rendang", "lemang", "satay", "budu", "solok"} & tokens:
        return "makanan_tradisional", ["makanan_tradisional"]
    if {"budaya", "kraftangan", "wayang", "dikir", "gasing", "wau", "batik",
            "songket", "tarian", "silat", "persembahan", "tradisional", "seni",
            "permainan", "kulit", "patung", "anyaman", "ukiran"} & tokens:
        return "budaya", ["budaya"]
    if {"tempat", "menarik", "pantai", "pasar", "muzium", "pelancongan"} & tokens:
        return "tempat_menarik", ["tempat_menarik"]
    if {"jajahan", "ibu", "negeri", "sungai", "bendera", "gelaran", "lokasi",
            "lapangan", "terbang", "stadium", "tanah", "tinggi", "gua"} & tokens:
        return "general_fact", ["canonical_facts", "qa_umum_kelantan"]
    return "unknown", ["qa_umum_kelantan", "tempat_menarik", "makanan_tradisional", "budaya"]


def route_query(query: str, selected_mode: str = "Terjemahan Dialek") -> dict:
    normalized = normalize_query(query)
    token_set = set(tokenize(normalized))

    if detect_out_of_scope(normalized):
        return {
            "mode": "out_of_scope",
            "intent": "out_of_scope",
            "normalized_query": normalized,
            "collection_filter": [],
        }

    if selected_mode == "Terjemahan Dialek":
        return {
            "mode": "dialect_translation",
            "intent": "dialect",
            "normalized_query": normalized,
            "collection_filter": ["perkataan", "dialect_phrases", "contoh_ayat"],
        }

    # selected_mode == "Info Kelantan"
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
