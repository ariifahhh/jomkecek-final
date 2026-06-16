import os


DATA_PATHS = (
    "DATA_JOMKECEK_CLEANED copy.xlsx",
    "DATA_JOMKECEK_CLEANED.csv",
    "DATA_JOMKECEK_CLEANED.xlsx",
)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL_NAME = os.getenv("JOMKECEK_MODEL", "qwen2.5:7b")
JUDGE_MODEL_NAME = os.getenv("JOMKECEK_JUDGE_MODEL", "qwen2.5:7b")

USE_CHROMA = os.getenv("JOMKECEK_USE_CHROMA", "1") == "1"
CHROMA_PATH = os.getenv("JOMKECEK_CHROMA_PATH", "./chroma_db_jomkecek")
EMBED_MODEL = os.getenv("JOMKECEK_EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

LOW_TRANSLATION_CONFIDENCE = 0.35
LOW_RETRIEVAL_CONFIDENCE = 0.28
DEFAULT_TOP_K = 6

COLLECTIONS = {
    "dialect_words": {"perkataan"},
    "dialect_sentences": {"contoh_ayat"},
    "tempat_menarik": {"tempat_menarik"},
    "makanan_tradisional": {"makanan_tradisional"},
    "budaya": {"budaya"},
}

