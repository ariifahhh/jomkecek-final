from __future__ import annotations

from .config import CHROMA_PATH
from .data import load_documents


def rebuild_chroma_collections() -> str:
    """Optional helper for users who install chromadb.

    It creates separate collections:
    dialect_words, dialect_sentences, tourism, food, culture.

    Chroma's default embedding function may download a model. For a stronger
    Malay setup, configure bge-m3 or multilingual-e5-small explicitly.
    """
    try:
        import chromadb
    except Exception as exc:
        raise RuntimeError("Install chromadb first to build vector collections.") from exc

    client = chromadb.PersistentClient(path=CHROMA_PATH)
    grouped = {}
    for doc in load_documents():
        grouped.setdefault(doc.collection, []).append(doc)

    for collection_name, docs in grouped.items():
        try:
            client.delete_collection(collection_name)
        except Exception:
            pass
        collection = client.get_or_create_collection(collection_name)
        collection.add(
            ids=[f"{doc.collection}:{doc.row}" for doc in docs],
            documents=[doc.text for doc in docs],
            metadatas=[
                {
                    "category": doc.category,
                    "title": doc.title,
                    "row": doc.row,
                    **{k: str(v) for k, v in doc.metadata.items()},
                }
                for doc in docs
            ],
        )
    return f"Built {len(grouped)} Chroma collections at {CHROMA_PATH}"

