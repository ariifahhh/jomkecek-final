import requests

from .config import JUDGE_MODEL_NAME, MODEL_NAME, OLLAMA_URL

GENERAL_KELANTAN_PROMPT = """Anda ialah JomKecek, chatbot tempatan Kelantan.
Peraturan WAJIB:
1. Gunakan HANYA maklumat dari konteks RAG yang diberikan.
2. Jika konteks tidak mengandungi jawapan, katakan "Maklumat ini tidak tersedia dalam pangkalan data JomKecek."
3. JANGAN reka atau teka fakta — terutama nama tempat, nama masjid, nama lapangan terbang, nama jalan, atau angka statistik.
4. JANGAN confuse Kelantan dengan negeri lain (Kedah, Perak, Pahang, Perlis, dll).
5. Jawab dalam Bahasa Melayu, ringkas dan berdasarkan konteks sahaja.
"""

TRANSLATION_FORMATTER_PROMPT = """Anda ialah formatter jawapan Dialek Kelantan.
Jangan ubah maksud terjemahan. Jangan cipta maksud baru.
Susun jawapan dengan ringkas sahaja.
"""


def ollama_generate(prompt: str, temperature: float = 0.2, timeout: int = 120, model: str | None = None) -> str:
    """Send a prompt via /api/chat (works correctly for instruct-tuned models)."""
    payload = {
        "model": model or MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": temperature, "num_ctx": 4096},
    }
    response = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json().get("message", {}).get("content", "").strip()


def ollama_judge(prompt: str, timeout: int = 60) -> str:
    return ollama_generate(prompt, temperature=0.0, timeout=timeout, model=JUDGE_MODEL_NAME)
