"""Build ChromaDB vector collections from the JomKecek dataset.

Run once before starting the app so hybrid retrieval is active:

    python setup_chroma.py

The script indexes tourism, food, and culture documents using
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 (multilingual,
works for Malay).  Re-running it rebuilds all collections from scratch.

Override paths with env vars:
    JOMKECEK_CHROMA_PATH   (default: ./chroma_db_jomkecek)
    JOMKECEK_EMBED_MODEL   (default: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)
"""
from __future__ import annotations

import sys

try:
    import chromadb
    import chromadb.utils.embedding_functions as ef
except ImportError:
    print("chromadb not installed. Run: pip install chromadb sentence-transformers")
    sys.exit(1)

try:
    from sentence_transformers import SentenceTransformer  # noqa: F401 — validates install
except ImportError:
    print("sentence-transformers not installed. Run: pip install sentence-transformers")
    sys.exit(1)

from jomkecek.config import CHROMA_PATH, EMBED_MODEL
from jomkecek.data import load_documents

TARGET_COLLECTIONS = {"tempat_menarik", "makanan_tradisional", "budaya"}
BATCH_SIZE = 128


def main() -> None:
    print(f"Loading documents from dataset...")
    docs = load_documents()
    by_collection: dict[str, list] = {}
    for doc in docs:
        if doc.collection in TARGET_COLLECTIONS:
            by_collection.setdefault(doc.collection, []).append(doc)

    total = sum(len(v) for v in by_collection.items())
    print(f"Found {len(docs)} total docs — {sum(len(v) for v in by_collection.values())} in target collections")

    print(f"Loading embedding model: {EMBED_MODEL}")
    embed_fn = ef.SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)

    client = chromadb.PersistentClient(path=CHROMA_PATH)

    for collection_name, collection_docs in by_collection.items():
        print(f"\n[{collection_name}] {len(collection_docs)} docs — rebuilding...")

        try:
            client.delete_collection(collection_name)
        except Exception:
            pass
        col = client.create_collection(collection_name, embedding_function=embed_fn)

        for i in range(0, len(collection_docs), BATCH_SIZE):
            batch = collection_docs[i : i + BATCH_SIZE]
            texts = [f"{doc.title} {doc.text}" for doc in batch]
            ids = [f"{doc.collection}:{doc.row}" for doc in batch]
            col.add(ids=ids, documents=texts)
            done = min(i + BATCH_SIZE, len(collection_docs))
            print(f"  {done}/{len(collection_docs)}", end="\r")

        print(f"  Done: {collection_name} ({len(collection_docs)} docs indexed)")

    print(f"\nChromaDB ready at: {CHROMA_PATH}")
    print("Start the app normally — JOMKECEK_USE_CHROMA=1 is now the default.")


if __name__ == "__main__":
    main()
