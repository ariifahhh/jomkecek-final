import requests

from .config import MODEL_NAME, OLLAMA_URL


def ollama_generate(prompt: str, temperature: float = 0.2, timeout: int = 120) -> str:
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature, "num_ctx": 4096},
    }
    response = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json().get("response", "").strip()


TRANSLATION_FORMATTER_PROMPT = """Anda ialah formatter jawapan Dialek Kelantan.
Jangan ubah maksud terjemahan. Jangan cipta maksud baru.
Susun jawapan dengan ringkas sahaja.
"""

GENERAL_KELANTAN_PROMPT = """Anda ialah JomKecek, chatbot tempatan Kelantan.
Peraturan:
1. Utamakan konteks RAG jika ada.
2. Untuk soalan umum Kelantan, boleh guna pengetahuan model secara terhad.
3. Jika maklumat semasa atau tidak pasti, nyatakan ketidakpastian.
4. Jangan keluar daripada konteks Kelantan.
5. Jawab ringkas, natural dan tidak berbentuk esei panjang.
"""

