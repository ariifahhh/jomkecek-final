from __future__ import annotations

import re
from typing import Any

from .config import LOW_RETRIEVAL_CONFIDENCE, MODEL_NAME
from .data import active_data_path, load_documents
from .dialect import translate_dialect
from .evaluation import evaluate
from .guards import OUT_OF_SCOPE_MESSAGE, WEAK_RAG_MESSAGE, final_response_guard
from .llm import GENERAL_KELANTAN_PROMPT, ollama_generate
from .retriever import retrieval_context, retrieve
from .router import route_query
from .preprocessing import tokenize


def _get_dialect_examples(matched_words: list[str]) -> tuple[list[dict], list]:
    """Retrieve example sentences from contoh_ayat sheet for the matched dialect words.
    Returns (examples, raw_hits) so hits can be used for evaluation context."""
    if not matched_words:
        return [], []
    query = " ".join(matched_words[:4])
    hits = retrieve(query, top_k=4, collections={"contoh_ayat"})
    examples = []
    for hit in hits[:3]:
        meta = hit.document.metadata
        dialek = (
            meta.get("dialek_ayat") or meta.get("dialek") or meta.get("ayat_dialek") or
            meta.get("contoh") or meta.get("ayat") or ""
        )
        bm = (
            meta.get("bm_ayat") or meta.get("bm") or meta.get("terjemahan") or
            meta.get("ayat_bm") or meta.get("maksud") or ""
        )
        if dialek:
            examples.append({"dialek": dialek, "bm": bm})
    return examples, hits


def _llm_translate(query: str, examples: list[dict], breakdown: list[dict], direction: str) -> str:
    """RAG path: generate natural translation using retrieved examples as context."""
    if direction == "dialect_to_bm":
        from_lang, to_lang = "dialek Kelantan", "Bahasa Melayu standard"
    else:
        from_lang, to_lang = "Bahasa Melayu standard", "dialek Kelantan"

    context_lines = "\n".join(
        f"- {ex['dialek']} → {ex['bm']}"
        for ex in examples
        if ex.get("dialek") and ex.get("bm")
    )
    word_hints = "\n".join(
        f"- {item['dialect']} → {item['bm']}"
        for item in breakdown
        if item.get("bm") and item.get("bm") != "tiada dalam pangkalan data" and item.get("confidence", 0) > 0
    )

    prompt = f"""Anda ialah penterjemah dialek Kelantan yang pakar.

Contoh terjemahan dari pangkalan data JomKecek:
{context_lines}

Padanan perkataan:
{word_hints}

Terjemahkan ayat berikut dari {from_lang} kepada {to_lang}:
"{query}"

Berikan HANYA terjemahan sahaja, tanpa penjelasan atau nota tambahan."""

    try:
        result = ollama_generate(prompt, temperature=0.1)
        return result.strip().strip('"').strip("'").strip()
    except Exception:
        return ""


def detect_answer_type(query: str) -> str:
    q = query.lower()
    if any(term in q for term in ("mengapakah", "bagaimanakah", "kenapa", "bagaimana", "pada pendapat anda")):
        return "reasoning"
    if any(term in q for term in ("maklumat lanjut", "terangkan", "huraikan", "jelaskan", "ceritakan", "bercerita", "kongsikan")):
        return "detail"
    if any(term in q for term in ("cadangkan", "tempat menarik", "makanan", "aktiviti", "pantai popular")):
        return "recommendation"
    if any(term in q for term in ("apakah", "siapakah", "berapakah", "di manakah", "bila", "berapa")):
        return "direct"
    return "direct"


def expand_query_for_detail(query: str) -> str:
    tokens = set(tokenize(query))
    expansions = [query]
    if {"nasi", "kerabu"} & tokens:
        expansions.append("nasi kerabu budu ulam ayam percik makanan tradisional kelantan")
    if {"cuaca", "monsun", "banjir", "hujan"} & tokens:
        expansions.append("cuaca monsun hujan banjir sungai kelantan")
    if "sultan" in tokens:
        expansions.append("Sultan Kelantan sejarah istana budaya diraja")
    if "budaya" in tokens:
        expansions.append("budaya Kelantan seni tradisi permainan kraftangan")
    return " ".join(dict.fromkeys(expansions))


def _collections_from_route(route: dict[str, Any]) -> set[str] | None:
    mapped = {c for c in route.get("collection_filter", []) if c in {"tempat_menarik", "makanan_tradisional", "budaya"}}
    return mapped or None


def _shorten(text: str, limit: int = 230) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def _clean_item_name(name: str) -> str:
    small_words = {"di", "ke", "dan", "atau", "dari", "dalam", "yang"}
    words = []
    for word in str(name).replace("_", " ").split():
        lower = word.lower()
        words.append(lower if lower in small_words else lower[:1].upper() + lower[1:])
    return " ".join(words)


def _item_from_doc(hit) -> dict[str, Any]:
    doc = hit.document
    meta = doc.metadata
    name = (
        meta.get("nama")
        or meta.get("nama_tempat")
        or meta.get("nama_makanan")
        or meta.get("nama_budaya")
        or doc.title
    )
    description = meta.get("deskripsi") or meta.get("deskripsi_ringkas") or doc.text
    return {
        "name": _clean_item_name(name),
        "district": meta.get("daerah") or meta.get("asal_jajahan", ""),
        "category": meta.get("kategori", doc.category),
        "description": _shorten(description),
        "confidence": round(hit.score, 2),
    }


def build_tourism_items(query: str, hits) -> list[dict[str, Any]]:
    seen = set()
    items = []
    for hit in hits:
        item = _item_from_doc(hit)
        key = item["name"].lower()
        if key in seen:
            continue
        seen.add(key)
        items.append(item)
        if len(items) == 3:
            break
    return items


def _top_items_by_row(collection: str, limit: int = 3) -> list[dict[str, Any]]:
    """Return the top N items from a collection sorted by row number (row 1 = most popular)."""
    docs = load_documents()
    domain_docs = sorted(
        [d for d in docs if d.collection == collection],
        key=lambda d: d.row,
    )
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for doc in domain_docs:
        name = _clean_item_name(
            doc.metadata.get("nama_makanan") or doc.metadata.get("nama_tempat") or
            doc.metadata.get("nama_budaya") or doc.metadata.get("nama") or doc.title
        )
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        description = doc.metadata.get("deskripsi_ringkas") or doc.metadata.get("deskripsi") or doc.text
        items.append({
            "name": name,
            "district": doc.metadata.get("asal_jajahan") or doc.metadata.get("daerah", ""),
            "category": doc.metadata.get("kategori", doc.category),
            "description": _shorten(description),
            "confidence": 1.0,
        })
        if len(items) >= limit:
            break
    return items


def _is_specific_item_query(query: str) -> bool:
    """Returns True if the query mentions a specific item name (not a general browse request)."""
    general_words = {
        "cadangan", "senarai", "listkan", "berikan", "apa", "apakah", "ada",
        "mana", "semua", "popular", "terkenal", "menarik", "tradisional",
        "kelantan", "kota bharu", "tumpat", "pasir mas"
    }
    tokens = set(query.lower().split())
    # If mostly general words and no proper noun hint, treat as general query
    specific = tokens - general_words
    return len(specific) >= 3  # has 3+ specific non-general words = likely specific item


def _merge_with_top(top_items: list, hit_items: list, total: int = 3) -> list:
    """Merge top-by-row items first, then fill with retrieval hits, deduplicating."""
    seen = {item["name"].lower() for item in top_items}
    result = list(top_items)
    for item in hit_items:
        if item["name"].lower() not in seen:
            seen.add(item["name"].lower())
            result.append(item)
        if len(result) >= total:
            break
    return result[:total]


def validate_context_relevance(query: str, hit, intent: str, answer_type: str) -> bool:
    if not hit:
        return False
    query_tokens = {
        t
        for t in tokenize(query)
        if len(t) > 2 and t not in {"yang", "dan", "atau", "dalam", "kepada", "kelantan", "negeri"}
    }
    doc_tokens = set(tokenize(f"{hit.document.title} {hit.document.text} {' '.join(hit.document.metadata.values())}"))
    overlap = len(query_tokens & doc_tokens)
    if intent == "makanan_tradisional" and hit.document.collection != "makanan_tradisional":
        return False
    if intent == "tempat_menarik" and hit.document.collection != "tempat_menarik":
        return False
    if intent == "budaya" and hit.document.collection != "budaya":
        return False
    if intent == "geography":
        query_weather = {"cuaca", "monsun", "hujan", "banjir"} & set(tokenize(query))
        if "monsun" in query_weather:
            required = {"cuaca", "monsun", "banjir"}
        else:
            required = {"cuaca", "hujan", "banjir"} if query_weather else {"sungai", "jajahan", "lokasi"}
        if not (required & doc_tokens):
            return False
    minimum_overlap = 1 if answer_type in {"reasoning", "detail"} else 2
    return overlap >= minimum_overlap or hit.score >= 0.55


def validate_rag_context(route: dict[str, Any], hits, answer_type: str = "direct") -> bool:
    if not hits:
        return False
    best = hits[0]
    threshold = 0.22 if answer_type in {"reasoning", "detail"} else LOW_RETRIEVAL_CONFIDENCE
    if best.score < threshold:
        return False
    allowed = set(route.get("collection_filter") or [])
    if allowed and best.document.collection not in allowed and "qa_umum_kelantan" not in allowed:
        return False
    if not any(validate_context_relevance(route["normalized_query"], hit, route.get("intent", ""), answer_type) for hit in hits[:5]):
        return False
    return True


def retrieve_expanded_context(query: str, intent: str, answer_type: str, route: dict[str, Any]):
    top_k = 12 if answer_type in {"reasoning", "detail"} else 6
    expanded = expand_query_for_detail(query) if answer_type in {"reasoning", "detail"} else query
    hits = retrieve(expanded, top_k=top_k, collections=_collections_from_route(route))
    valid = [hit for hit in hits if validate_context_relevance(query, hit, intent, answer_type)]
    return valid


_CANONICAL_KELANTAN: dict[str, str] = {
    "gelaran": (
        "Kelantan dikenali dengan gelaran 'Serambi Mekah' kerana kedudukannya sebagai pusat "
        "pengajian Islam yang kuat di Malaysia, dengan majoriti penduduknya beragama Islam dan "
        "banyak institusi agama Islam terkenal."
    ),
    "serambi mekah": (
        "Gelaran 'Serambi Mekah' diberikan kepada Kelantan kerana negeri ini diiktiraf sebagai "
        "pusat kehidupan dan pengajian Islam yang kukuh di Malaysia."
    ),
    "ibu negeri": "Ibu negeri Kelantan ialah Kota Bharu.",
    "jajahan": (
        "Kelantan mempunyai 10 jajahan: Kota Bharu, Pasir Mas, Tumpat, Pasir Puteh, Bachok, "
        "Kuala Krai, Machang, Tanah Merah, Jeli dan Gua Musang."
    ),
    "berapa jajahan": (
        "Kelantan mempunyai 10 jajahan: Kota Bharu, Pasir Mas, Tumpat, Pasir Puteh, Bachok, "
        "Kuala Krai, Machang, Tanah Merah, Jeli dan Gua Musang."
    ),
    "bendera": (
        "Bendera Kelantan berwarna merah dengan gambar wau bulan dan bintang berwarna putih "
        "di bahagian tengah."
    ),
    "luas": "Kelantan berkeluasan 15,099 kilometer persegi.",
    "sempadan": (
        "Kelantan bersempadan dengan negeri Terengganu di timur, Perak di barat, Pahang di selatan, "
        "dan Thailand di utara."
    ),
    "sungai": "Sungai Kelantan merupakan sungai utama yang mengalir melalui negeri Kelantan ke Laut China Selatan.",
    "penduduk": (
        "Penduduk Kelantan adalah lebih kurang 1.8 juta orang (anggaran). Sila semak sumber rasmi "
        "seperti Jabatan Perangkaan Malaysia untuk angka terkini."
    ),
    "lapangan terbang": (
        "Lapangan terbang utama di Kelantan ialah Lapangan Terbang Sultan Ismail Petra (IATA: KBR), "
        "terletak di Pengkalan Chepa, Kota Bharu."
    ),
    "airport": (
        "Lapangan terbang utama di Kelantan ialah Lapangan Terbang Sultan Ismail Petra (IATA: KBR), "
        "terletak di Pengkalan Chepa, Kota Bharu."
    ),
    "masjid ikonik": (
        "Masjid ikonik di Kota Bharu ialah Masjid Muhammadi, iaitu masjid negeri Kelantan yang "
        "dibina pada tahun 1867 dan mempunyai seni bina yang unik."
    ),
    "masjid negeri": (
        "Masjid negeri Kelantan ialah Masjid Muhammadi di Kota Bharu."
    ),
    "stadium": (
        "Stadium utama di Kota Bharu ialah Stadium Sultan Muhammad IV, yang merupakan stadium "
        "utama bagi pasukan bola sepak Kelantan FA."
    ),
    "tanah tinggi": (
        "Kawasan tanah tinggi di Kelantan termasuk kawasan sekitar Gua Musang dan hutan di selatan "
        "Kelantan yang bersempadan dengan Cameron Highlands, Pahang."
    ),
    "gua": (
        "Antara gua terkenal di Kelantan ialah kawasan Gua Musang dan Gua Ikan di Kuala Krai. "
        "Kelantan juga mempunyai pelbagai gua lain dalam hutan simpannya."
    ),
    "kraftangan": (
        "Kraftangan tradisional Kelantan yang terkenal termasuk songket (kain benang emas), "
        "batik kelantan, wau bulan, gasing, dan anyaman mengkuang."
    ),
    "songket": (
        "Songket ialah kraftangan tradisional Kelantan yang menggunakan benang emas atau perak "
        "ditenun bersama kain sutera atau kapas, menghasilkan corak yang mewah dan indah."
    ),
    "wayang kulit": (
        "Wayang Kulit Kelantan ialah seni persembahan tradisional yang menggunakan patung kulit "
        "lembu yang diukir halus, dipersembahkan dalam cerita epik Ramayana dan Mahabharata."
    ),
    "gasing": (
        "Permainan gasing adalah permainan tradisional yang sangat terkenal di Kelantan. "
        "Gasing Kelantan adalah antara yang terbesar di dunia dan boleh berputar sehingga berjam-jam."
    ),
}


def _check_canonical(query: str) -> str | None:
    q = query.lower()
    # Check multi-word keys first (more specific), then single-word keys
    sorted_keys = sorted(_CANONICAL_KELANTAN.keys(), key=len, reverse=True)
    for key in sorted_keys:
        if key in q:
            return _CANONICAL_KELANTAN[key]
    return None


def _context_lines(hits, limit: int = 5) -> list[str]:
    lines = []
    for hit in hits[:limit]:
        item = _item_from_doc(hit)
        lines.append(f"{item['name']}: {item['description']}")
    return lines


def generate_answer_by_type(query: str, hits, route: dict[str, Any], answer_type: str) -> str:
    context = retrieval_context(hits)
    cautious = "Berdasarkan maklumat berkaitan dalam pangkalan data JomKecek, "

    if answer_type == "direct":
        first = _context_lines(hits, 1)
        extra = _context_lines(hits[1:], 2)
        return "Jawapan:\n" + (first[0] if first else WEAK_RAG_MESSAGE) + (
            "\n\nMaklumat ringkas:\n" + "\n".join(extra) if extra else ""
        )

    if answer_type == "recommendation":
        items = build_tourism_items(query, hits)
        if not items:
            items = [_item_from_doc(hit) for hit in hits[:3]]
        lines = ["Cadangan:"]
        for i, item in enumerate(items[:3], start=1):
            lines.append(f"{i}. {item['name']}\n{item['description']}")
        return "\n\n".join(lines)

    if answer_type in {"detail", "reasoning"}:
        points = _context_lines(hits, 5)
        context_for_llm = "\n".join(points) if points else context
        detail_prompt = f"""{GENERAL_KELANTAN_PROMPT}

Konteks dari pangkalan data JomKecek:
{context_for_llm}

Soalan: {query}

Arahan:
- Jawab dalam Bahasa Melayu yang natural dan informatif.
- Gunakan maklumat dari konteks di atas sebagai asas jawapan.
- Berikan penerangan yang lengkap dan terperinci.
- Jangan tambah fakta yang tiada dalam konteks.
- Struktur: mulakan dengan jawapan ringkas, kemudian huraikan dengan lebih lanjut.
"""
        try:
            return ollama_generate(detail_prompt, temperature=0.3)
        except Exception:
            if points:
                return (
                    "Jawapan ringkas:\n"
                    f"{cautious}{points[0]}.\n\n"
                    "Maklumat lanjut:\n"
                    + "\n".join(f"{i}. {point}" for i, point in enumerate(points[:5], start=1))
                )
            return WEAK_RAG_MESSAGE

    prompt = f"""{GENERAL_KELANTAN_PROMPT}

Konteks RAG:
{context}

Soalan:
{query}

Arahan:
- Jawab dalam Bahasa Melayu sahaja.
- Jangan tambah fakta di luar konteks.
- Gunakan format bahagian yang sesuai: Jawapan, Maklumat lanjut.
"""
    try:
        return ollama_generate(prompt, temperature=0.2)
    except Exception:
        return WEAK_RAG_MESSAGE


_NO_DATA_MESSAGE = (
    "Maaf, maklumat tepat tentang soalan ini tidak tersedia dalam pangkalan data JomKecek buat masa ini. "
    "Untuk maklumat terkini dan tepat, sila rujuk sumber rasmi seperti laman web Kerajaan Negeri Kelantan "
    "atau Tourism Kelantan."
)


def answer_with_llm_knowledge(query: str) -> dict[str, Any]:
    """LLM fallback — only for genuinely dynamic topics (politik, cuaca, perangkaan semasa).
    Returns a safe 'no data' message for specific factual questions to prevent hallucination."""
    # Specific factual questions should NOT fall through to LLM free-generation
    # because the model hallucinates Kelantan-specific names confidently but wrongly.
    factual_signals = {
        "nama", "apakah", "siapakah", "berapakah", "di manakah",
        "lapangan", "stadium", "masjid", "hospital", "universiti",
        "gua", "gunung", "bukit", "sungai", "pulau",
    }
    q_tokens = set(query.lower().split())
    if factual_signals & q_tokens:
        return {
            "response_type": "no_data",
            "summary": _NO_DATA_MESSAGE,
            "items": [],
            "sections": [],
            "llm_note": _NO_DATA_MESSAGE,
            "used_llm": False,
        }

    prompt = f"""{GENERAL_KELANTAN_PROMPT}

Soalan berkaitan Kelantan (topik semasa/dinamik):
{query}

Arahan: Jawab hanya jika ini soalan umum tentang budaya, adat, atau geografi am Kelantan.
Jika melibatkan fakta spesifik (nama orang, nama tempat, angka), nyatakan bahawa pengguna perlu semak sumber rasmi.
"""
    try:
        answer = ollama_generate(prompt, temperature=0.1)
    except Exception:
        answer = _NO_DATA_MESSAGE

    return {
        "response_type": "llm_knowledge",
        "summary": answer,
        "items": [],
        "sections": [],
        "llm_note": answer,
        "used_llm": True,
    }


_DOMAIN_COLLECTIONS = {"makanan_tradisional", "tempat_menarik", "budaya"}


def answer_kelantan(query: str, hits, route: dict[str, Any], answer_type: str) -> dict[str, Any]:
    intent = route.get("intent", "")

    # For the 3 primary domains, always use dataset documents first.
    # General queries → top-3 by row (most popular) + retrieval hits.
    # Specific item queries → retrieval hits only (relevance matters more).
    if intent in _DOMAIN_COLLECTIONS:
        domain_hits = [h for h in hits if h.document.collection == intent]
        if not domain_hits:
            domain_hits = [h for h in hits if h.document.collection in _DOMAIN_COLLECTIONS]

        if domain_hits or True:
            # detail/reasoning queries → LLM prose response, not cards
            if answer_type in {"detail", "reasoning"} and domain_hits:
                note = generate_answer_by_type(query, domain_hits, route, answer_type)
                return {
                    "response_type": "general",
                    "summary": note,
                    "items": [],
                    "sections": [],
                    "llm_note": note,
                    "used_llm": True,
                }

            hit_items = build_tourism_items(query, domain_hits) if domain_hits else []

            # Always lead with top-3 most popular (by row order in Excel), then fill with retrieval hits
            top_items = _top_items_by_row(intent, limit=3)
            items = _merge_with_top(top_items, hit_items, total=3)

            if items:
                return {
                    "response_type": intent,
                    "summary": "Maklumat daripada pangkalan data JomKecek.",
                    "items": items,
                    "sections": items,
                    "llm_note": "",
                    "used_llm": False,
                }
            # Fallback prose if no card items found
            note = generate_answer_by_type(query, domain_hits, route, answer_type)
            return {
                "response_type": "general",
                "summary": note,
                "items": [],
                "sections": [],
                "llm_note": note,
                "used_llm": True,
            }
        # Truly no docs for this domain — inform user rather than hallucinate
        no_data = (
            f"Maaf, maklumat tentang {query} tidak ditemui dalam pangkalan data JomKecek buat masa ini."
        )
        return {
            "response_type": "no_data",
            "summary": no_data,
            "items": [],
            "sections": [],
            "llm_note": no_data,
            "used_llm": False,
        }

    # General / unknown intent — existing RAG-then-LLM logic
    if not validate_rag_context(route, hits, answer_type):
        return answer_with_llm_knowledge(query)

    if intent == "unknown" and answer_type not in {"reasoning", "detail"}:
        return answer_with_llm_knowledge(query)

    # Cards only for recommendation/direct list queries — NOT for "ceritakan/huraikan"
    card_query = answer_type == "recommendation" or (
        answer_type not in {"detail", "reasoning"}
        and any(word in query.lower() for word in ("tempat", "makanan", "budaya", "pantai", "pasar", "cadangkan"))
    )
    items = build_tourism_items(query, hits) if card_query else []
    if items:
        return {
            "response_type": "general",
            "summary": "Cadangan ringkas berdasarkan konteks JomKecek.",
            "items": items,
            "sections": items,
            "llm_note": "",
            "used_llm": False,
        }

    note = generate_answer_by_type(query, hits, route, answer_type)
    return {
        "response_type": "general",
        "summary": note,
        "items": [],
        "sections": [],
        "llm_note": note,
        "used_llm": True,
    }


def generate_general_answer(query: str, hits, route: dict[str, Any], answer_type: str = "direct") -> dict[str, Any]:
    return answer_kelantan(query, hits, route, answer_type)


def format_answer(result: dict[str, Any]) -> str:
    if result["intent"] == "translation":
        translation = result["translation"]
        heading = "Terjemahan Dialek Kelantan" if translation.get("direction") == "bm_to_dialect" else "Terjemahan"
        lines = [heading, translation["translation"], "", "Pecahan"]
        if translation["breakdown"]:
            lines.extend(f"- {item['dialect']} -> {item['bm']}" for item in translation["breakdown"])
            example = translation.get("example") or next((item["contoh"] for item in translation["breakdown"] if item.get("contoh")), "")
            example_meaning = translation.get("example_meaning", "")
            if example:
                lines.extend(["", "Contoh", example])
            if example_meaning:
                lines.extend(["Maksud", example_meaning])
            lines.extend(["", "Keyakinan", translation.get("confidence_label", "Rendah")])
        else:
            lines.append("- Tiada padanan yakin.")
        return "\n".join(lines)

    kelantan = result["kelantan"]
    if kelantan["items"]:
        lines = [kelantan["summary"], ""]
        lines.extend(f"- {item['name']}: {item['description']}" for item in kelantan["items"])
        return "\n".join(lines)
    return kelantan["summary"]


def run_chatbot(user_input: str, mode: str = "Auto") -> dict[str, Any]:
    route = route_query(user_input, mode)
    answer_type = detect_answer_type(route["normalized_query"])

    if route["mode"] == "out_of_scope":
        return {
            "intent": "out_of_scope",
            "mode": "Luar Skop",
            "translation": {},
            "kelantan": {"response_type": "out_of_scope", "summary": OUT_OF_SCOPE_MESSAGE, "items": [], "used_llm": False},
            "answer": OUT_OF_SCOPE_MESSAGE,
            "eval": evaluate(OUT_OF_SCOPE_MESSAGE, [], 1.0, False),
            "contexts": [],
            "visual_keywords": [],
            "route": route,
        }

    # Dynamic topics — bypass RAG, use LLM parametric knowledge directly
    if route["mode"] == "llm_knowledge":
        kelantan = answer_with_llm_knowledge(route["normalized_query"])
        answer = final_response_guard(kelantan["summary"])
        return {
            "intent": "kelantan",
            "mode": "Info Kelantan",
            "translation": {},
            "kelantan": kelantan,
            "answer": answer,
            "eval": evaluate(answer, [], 0.9, False),
            "contexts": [],
            "visual_keywords": [],
            "route": route,
            "answer_type": answer_type,
        }

    # Canonical facts shortcut — answers well-known Kelantan facts without RAG
    # Runs for all intents since canonical lookup is a fast dict check
    if route["mode"] not in {"out_of_scope", "dialect_translation", "llm_knowledge"}:
        canonical_answer = _check_canonical(route["normalized_query"])
        if canonical_answer:
            kelantan_result = {
                "response_type": "general",
                "summary": canonical_answer,
                "items": [],
                "sections": [],
                "llm_note": canonical_answer,
                "used_llm": False,
            }
            answer = final_response_guard(canonical_answer)
            return {
                "intent": "kelantan",
                "mode": "Info Kelantan",
                "translation": {},
                "kelantan": kelantan_result,
                "answer": answer,
                "eval": evaluate(answer, [canonical_answer], 1.0, False, question=route["normalized_query"]),
                "contexts": [],
                "visual_keywords": [],
                "route": route,
                "answer_type": answer_type,
            }

    intent = "translation" if route["mode"] == "dialect_translation" else "kelantan"
    hits = [] if intent == "translation" else retrieve_expanded_context(
        route["normalized_query"], route.get("intent", ""), answer_type, route
    )
    confidence = hits[0].score if hits else 0.0

    if intent == "translation":
        translation = translate_dialect(route["normalized_query"])
        matched_words = [item["dialect"] for item in translation.get("breakdown", []) if item.get("matched")]
        rag_examples, rag_hits = _get_dialect_examples(matched_words)

        # RAG + LLM path: use retrieved examples as context for LLM to generate natural translation
        used_llm = False
        if rag_examples:
            llm_result = _llm_translate(
                route["normalized_query"],
                rag_examples,
                translation.get("breakdown", []),
                translation.get("direction", "dialect_to_bm"),
            )
            if llm_result:
                translation["translation"] = llm_result
                used_llm = True
        # Fallback: dict-based translation already in translation["translation"]

        translation["rag_examples"] = rag_examples
        hits = rag_hits
        result = {
            "intent": "translation",
            "mode": "Terjemahan Dialek",
            "translation": translation,
            "kelantan": {"summary": "", "items": [], "used_llm": used_llm},
        }
        confidence = translation["confidence"]
        strict = True
    else:
        kelantan = answer_kelantan(route["normalized_query"], hits, route, answer_type)
        result = {
            "intent": "kelantan",
            "mode": "Info Kelantan",
            "translation": {},
            "kelantan": kelantan,
        }
        strict = False

    context_texts = [hit.document.text for hit in hits]
    # For domain recommendation responses, answers are built from _top_items_by_row (Excel row order),
    # not from retrieval hits. Replace context with item descriptions so LLM Judge
    # evaluates against the actual content shown in the answer.
    if intent == "kelantan":
        _domain_types = {"makanan_tradisional", "tempat_menarik", "budaya"}
        if result.get("kelantan", {}).get("response_type") in _domain_types:
            items = result.get("kelantan", {}).get("items", [])
            if items:
                context_texts = [f"{item['name']}: {item['description']}" for item in items]
    answer = format_answer(result)
    answer = final_response_guard(answer, route["normalized_query"], "\n".join(context_texts))

    # For ROUGE-L: translation mode compares only the translated sentence against the
    # ground-truth dialek_ayat/bm_ayat from the retrieved contoh_ayat record.
    # QA mode keeps the retrieved context as reference (no ground truth available).
    rouge_candidate = answer
    rouge_reference = ""
    if intent == "translation":
        rouge_candidate = result["translation"].get("translation", answer)
        direction = result["translation"].get("direction", "dialect_to_bm")
        rag_examples = result["translation"].get("rag_examples", [])
        if rag_examples:
            rouge_reference = rag_examples[0].get("dialek", "") if direction == "bm_to_dialect" else rag_examples[0].get("bm", "")

    result.update(
        {
            "answer": answer,
            "eval": evaluate(
                rouge_candidate,
                context_texts,
                max(confidence, LOW_RETRIEVAL_CONFIDENCE if hits else 0),
                strict,
                question=route["normalized_query"],
                reference=rouge_reference,
                mode=intent,
                direction=result.get("translation", {}).get("direction", "") if intent == "translation" else "",
            ),
            "contexts": [
                {
                    "score": hit.score,
                    "keyword_score": hit.keyword_score,
                    "vector_score": hit.vector_score,
                    "collection": hit.document.collection,
                    "category": hit.document.category,
                    "title": hit.document.title,
                    "text": hit.document.text,
                    "row": hit.document.row,
                }
                for hit in hits[:6]
            ],
            "visual_keywords": [item["name"] + " Kelantan" for item in result["kelantan"].get("items", [])[:3]],
            "route": route,
            "answer_type": answer_type,
        }
    )
    return result


def metrics() -> dict[str, Any]:
    docs = load_documents()
    return {
        "documents": len(docs),
        "categories": sorted(set(doc.category for doc in docs)),
        "collections": sorted(set(doc.collection for doc in docs)),
        "model": MODEL_NAME,
        "dataset": active_data_path(),
    }
