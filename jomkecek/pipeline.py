from __future__ import annotations

import re
from typing import Any

from .canonical import lookup_canonical_fact
from .config import LOW_RETRIEVAL_CONFIDENCE, MODEL_NAME
from .data import TOURISM_SEEDS, active_data_path, load_documents
from .dialect import translate_dialect
from .evaluation import evaluate
from .guards import OUT_OF_SCOPE_MESSAGE, WEAK_RAG_MESSAGE, final_response_guard
from .llm import GENERAL_KELANTAN_PROMPT, ollama_generate
from .retriever import retrieval_context, retrieve
from .router import route_query
from .preprocessing import tokenize


def detect_answer_type(query: str) -> str:
    q = query.lower()
    if any(term in q for term in ("mengapakah", "bagaimanakah", "kenapa", "bagaimana", "pada pendapat anda")):
        return "reasoning"
    if any(term in q for term in ("maklumat lanjut", "terangkan", "huraikan", "jelaskan")):
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
    mapped = {c for c in route.get("collection_filter", []) if c in {"tourism", "food", "culture"}}
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


def _kota_bharu_defaults() -> list[dict[str, Any]]:
    return [
        {
            "name": seed["nama"],
            "district": seed["daerah"],
            "category": seed["kategori"],
            "description": seed["deskripsi"],
            "confidence": 0.95,
        }
        for seed in TOURISM_SEEDS
    ]


def build_tourism_items(query: str, hits) -> list[dict[str, Any]]:
    if "tempat" in query.lower() and "kota bharu" in query.lower():
        return _kota_bharu_defaults()

    seen = set()
    items = []
    for hit in hits:
        item = _item_from_doc(hit)
        key = item["name"].lower()
        if key in seen:
            continue
        seen.add(key)
        items.append(item)
        if len(items) == 4:
            break
    return items


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
    if intent == "food" and hit.document.collection != "food":
        return False
    if intent == "tourism" and hit.document.collection != "tourism":
        return False
    if intent == "culture" and hit.document.collection != "culture":
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
            items = [_item_from_doc(hit) for hit in hits[:4]]
        lines = ["Cadangan:"]
        for i, item in enumerate(items[:4], start=1):
            lines.append(f"{i}. {item['name']}\n{item['description']}")
        return "\n\n".join(lines)

    if answer_type == "detail":
        points = _context_lines(hits, 5)
        if points:
            return (
                "Jawapan ringkas:\n"
                f"{cautious}{points[0]}.\n\n"
                "Maklumat lanjut:\n"
                + "\n".join(f"{i}. {point}" for i, point in enumerate(points[:5], start=1))
                + "\n\nKesimpulan:\nMaklumat lanjut yang tersedia adalah berdasarkan rekod berkaitan dalam pangkalan data JomKecek."
            )

    if answer_type == "reasoning":
        points = _context_lines(hits, 5)
        if points:
            reasons = points[:3]
            lines = [
                "Jawapan:",
                "Perkara ini boleh dijelaskan melalui beberapa sebab:",
                "",
            ]
            for i, point in enumerate(reasons, start=1):
                name, _, desc = point.partition(":")
                lines.append(f"{i}. {name.strip()}")
                lines.append(desc.strip() or "Maklumat ini berkaitan dengan rekod dalam pangkalan data JomKecek.")
                lines.append("")
            lines.extend(
                [
                    "Kesimpulan:",
                    "Berdasarkan maklumat berkaitan dalam pangkalan data JomKecek, jawapan ini disusun daripada konteks yang sepadan dengan topik soalan.",
                ]
            )
            return "\n".join(lines)

    prompt = f"""{GENERAL_KELANTAN_PROMPT}

Konteks RAG:
{context}

Soalan:
{query}

Jenis jawapan: {answer_type}

Arahan:
- Jawab dalam Bahasa Melayu sahaja.
- Jangan tambah fakta di luar konteks.
- Jika membuat penaakulan, mulakan dengan frasa "{cautious.strip()}".
- Gunakan format bahagian yang sesuai: Jawapan, Maklumat lanjut, Kesimpulan.
"""
    try:
        return ollama_generate(prompt, temperature=0.2)
    except Exception:
        return WEAK_RAG_MESSAGE


def answer_with_llm_knowledge(query: str) -> dict[str, Any]:
    """Direct LLM answer for dynamic/current-events topics — no RAG retrieval."""
    prompt = f"""{GENERAL_KELANTAN_PROMPT}

Soalan berkaitan Kelantan:
{query}

Arahan tambahan:
- Jawab berdasarkan pengetahuan umum tentang Kelantan.
- Jika maklumat bersifat semasa (pemimpin semasa, cuaca terkini, perangkaan terbaru), nyatakan bahawa maklumat mungkin telah berubah dan cadangkan pengguna semak sumber rasmi.
- Jawab dalam Bahasa Melayu, ringkas dan tepat.
"""
    try:
        answer = ollama_generate(prompt, temperature=0.3)
    except Exception:
        answer = "Maaf, tidak dapat mendapatkan maklumat buat masa ini. Sila semak sumber rasmi."

    return {
        "response_type": "llm_knowledge",
        "summary": answer,
        "items": [],
        "sections": [],
        "llm_note": answer,
        "used_llm": True,
    }


def answer_kelantan(query: str, hits, route: dict[str, Any], answer_type: str) -> dict[str, Any]:
    # Static canonical facts (ibu negeri, jajahan count, gelaran, etc.)
    known = lookup_canonical_fact(query)
    if known:
        summary = known["answer"]
        if answer_type == "detail":
            summary += "\n\nMaklumat lanjut:\nMaklumat yang tersedia dalam JomKecek adalah berdasarkan rekod yang telah disahkan."
        return {
            "response_type": "fact",
            "summary": summary,
            "items": [],
            "sections": [],
            "llm_note": summary,
            "used_llm": False,
        }

    if not validate_rag_context(route, hits, answer_type):
        return {
            "response_type": "fallback",
            "summary": WEAK_RAG_MESSAGE,
            "items": [],
            "sections": [],
            "llm_note": "",
            "used_llm": False,
        }

    if route.get("intent") == "unknown" and answer_type not in {"reasoning", "detail"}:
        return {
            "response_type": "fallback",
            "summary": WEAK_RAG_MESSAGE,
            "items": [],
            "sections": [],
            "llm_note": "",
            "used_llm": False,
        }

    card_query = answer_type == "recommendation" or any(word in query.lower() for word in ("tempat", "makanan", "budaya", "pantai", "pasar"))
    items = build_tourism_items(query, hits) if card_query else []
    if items:
        response_type = "tourism"
        if route.get("intent") == "food":
            response_type = "food"
        elif route.get("intent") == "culture":
            response_type = "culture"
        return {
            "response_type": response_type,
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
        "items": items,
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

    intent = "translation" if route["mode"] == "dialect_translation" else "kelantan"
    hits = [] if intent == "translation" else retrieve_expanded_context(
        route["normalized_query"], route.get("intent", ""), answer_type, route
    )
    confidence = hits[0].score if hits else 0.0

    if intent == "translation":
        translation = translate_dialect(route["normalized_query"])
        result = {
            "intent": "translation",
            "mode": "Terjemahan Dialek",
            "translation": translation,
            "kelantan": {"summary": "", "items": [], "used_llm": False},
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
    answer = format_answer(result)
    answer = final_response_guard(answer, route["normalized_query"], "\n".join(context_texts))
    result.update(
        {
            "answer": answer,
            "eval": evaluate(
                answer,
                context_texts,
                max(confidence, LOW_RETRIEVAL_CONFIDENCE if hits else 0),
                strict,
                question=route["normalized_query"],
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
            "visual_keywords": [item["name"] + " Kelantan" for item in result["kelantan"].get("items", [])[:4]],
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
