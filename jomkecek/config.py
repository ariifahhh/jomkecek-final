import os


DATA_PATHS = (
    "DATA_JOMKECEK_CLEANED copy.xlsx",
    "DATA_JOMKECEK_CLEANED.csv",
    "DATA_JOMKECEK_CLEANED.xlsx",
)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL_NAME = os.getenv("JOMKECEK_MODEL", "qwen2.5:7b")

# Chroma is optional. The app stays usable with lexical hybrid retrieval when
# Chroma or an embedding model is unavailable on a local machine.
USE_CHROMA = os.getenv("JOMKECEK_USE_CHROMA", "0") == "1"
CHROMA_PATH = os.getenv("JOMKECEK_CHROMA_PATH", "./chroma_db_jomkecek")

LOW_TRANSLATION_CONFIDENCE = 0.35
LOW_RETRIEVAL_CONFIDENCE = 0.28
DEFAULT_TOP_K = 6

COLLECTIONS = {
    "dialect_words": {"perkataan"},
    "dialect_sentences": {"contoh_ayat"},
    "tourism": {"tempat_menarik"},
    "food": {"makanan_tradisional"},
    "culture": {"budaya"},
}

