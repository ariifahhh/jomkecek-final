from __future__ import annotations

import math
from collections import Counter

from .config import DEFAULT_TOP_K, EMBED_MODEL, LOW_RETRIEVAL_CONFIDENCE, USE_CHROMA
from .data import load_documents
from .models import RagDocument, RetrievalHit
from .preprocessing import tokenize

# Cached embedding function — loaded once on first ChromaDB query.
_embed_fn = None


def _get_embed_fn():
    global _embed_fn
    if _embed_fn is None:
        try:
            import chromadb.utils.embedding_functions as ef
            _embed_fn = ef.SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
        except Exception:
            pass
    return _embed_fn


def collections_for_query(query: str) -> set[str]:
    q = set(tokenize(query))
    food_terms = {
        "makanan",
        "tradisional",
        "nasi",
        "kerabu",
        "budu",
        "ulam",
        "percik",
        "laksa",
        "laksam",
        "akok",
        "kuih",
        "ayam",
        "sarapan",
    }
    if food_terms & q:
        return {"food"}
    if "budaya" in q:
        return {"culture"}
    if {"tempat", "pantai", "pasar", "muzium", "hotel", "menarik"} & q:
        return {"tourism"}
    return {"tourism", "food", "culture"}


def keyword_score(query_tokens: list[str], doc: RagDocument, df: Counter, total: int) -> float:
    doc_tokens = tokenize(f"{doc.title} {doc.category} {doc.text} {' '.join(doc.metadata.values())}")
    counts = Counter(doc_tokens)
    score = 0.0
    for token in query_tokens:
        if token in counts:
            tf = 1 + math.log(counts[token])
            idf = math.log((total + 1) / (df[token] + 1)) + 1
            score += tf * idf

    q_text = " ".join(query_tokens)
    district = (doc.metadata.get("daerah") or doc.metadata.get("asal_jajahan") or "").lower()
    if district and district in q_text:
        score += 3.0
    return score


def _lexical_hits(query: str, collections: set[str], top_k: int) -> list[RetrievalHit]:
    docs = [doc for doc in load_documents() if doc.collection in collections]
    query_tokens = tokenize(query)
    if not query_tokens or not docs:
        return []

    df = Counter()
    for doc in docs:
        df.update(set(tokenize(f"{doc.title} {doc.text} {' '.join(doc.metadata.values())}")))

    raw = []
    for doc in docs:
        score = keyword_score(query_tokens, doc, df, len(docs))
        if score > 0:
            raw.append((score, doc))
    raw.sort(key=lambda item: item[0], reverse=True)
    max_score = raw[0][0] if raw else 1.0

    hits = []
    for score, doc in raw[:top_k]:
        normalized = score / max_score
        hits.append(RetrievalHit(round(normalized, 3), doc, round(normalized, 3), round(normalized, 3)))
    return hits


def _chroma_hits(query: str, collections: set[str], top_k: int) -> list[RetrievalHit]:
    if not USE_CHROMA:
        return []
    try:
        import chromadb
    except Exception:
        return []

    embed_fn = _get_embed_fn()
    if embed_fn is None:
        return []

    from .config import CHROMA_PATH
    try:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
    except Exception:
        return []

    hits: list[RetrievalHit] = []
    docs_by_id = {f"{doc.collection}:{doc.row}": doc for doc in load_documents()}

    for collection in collections:
        try:
            col = client.get_collection(collection, embedding_function=embed_fn)
            result = col.query(query_texts=[query], n_results=top_k)
        except Exception:
            continue
        ids = result.get("ids", [[]])[0]
        distances = result.get("distances", [[]])[0]
        for doc_id, distance in zip(ids, distances):
            doc = docs_by_id.get(doc_id)
            if not doc:
                continue
            # Cosine distance: 0 = identical, 1 = orthogonal → convert to similarity
            vector_score = max(0.0, 1.0 - float(distance))
            hits.append(RetrievalHit(vector_score, doc, 0.0, round(vector_score, 3)))
    return hits


def retrieve(query: str, top_k: int = DEFAULT_TOP_K, collections: set[str] | None = None) -> list[RetrievalHit]:
    collections = collections or collections_for_query(query)
    lexical = _lexical_hits(query, collections, top_k * 2)
    chroma = _chroma_hits(query, collections, top_k * 2)

    combined: dict[str, RetrievalHit] = {}
    for hit in lexical:
        key = f"{hit.document.collection}:{hit.document.row}"
        combined[key] = hit
    for hit in chroma:
        key = f"{hit.document.collection}:{hit.document.row}"
        existing = combined.get(key)
        keyword = existing.keyword_score if existing else 0.0
        score = 0.7 * hit.vector_score + 0.3 * keyword
        combined[key] = RetrievalHit(round(score, 3), hit.document, keyword, hit.vector_score)

    ranked = sorted(combined.values(), key=lambda h: h.score, reverse=True)
    return [hit for hit in ranked[:top_k] if hit.score >= LOW_RETRIEVAL_CONFIDENCE]


def retrieval_context(hits: list[RetrievalHit]) -> str:
    return "\n\n".join(
        f"[{i}] collection={hit.document.collection}; title={hit.document.title}; score={hit.score}; text={hit.document.text}"
        for i, hit in enumerate(hits, start=1)
    )
