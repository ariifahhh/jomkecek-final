from __future__ import annotations

from .preprocessing import normalize_query


CANONICAL_FACTS = {
    "bilangan_jajahan": {
        "keywords": ("berapa jajahan", "jumlah jajahan", "berapa jajahan kelantan"),
        "answer": (
            "Jawapan:\nKelantan mempunyai 10 jajahan.\n\n"
            "Maklumat ringkas:\nJajahan tersebut ialah Kota Bharu, Pasir Mas, Tumpat, "
            "Pasir Puteh, Bachok, Kuala Krai, Machang, Tanah Merah, Jeli dan Gua Musang."
        ),
    },
    "jajahan_terbesar": {
        "keywords": ("jajahan terbesar", "jajahan paling luas", "terbesar dari segi keluasan"),
        "answer": (
            "Jawapan:\nGua Musang ialah jajahan terbesar di Kelantan dari segi keluasan.\n\n"
            "Maklumat ringkas:\nJajahan ini terletak di bahagian selatan Kelantan."
        ),
    },
    "ibu_negeri": {
        "keywords": ("ibu negeri", "bandar utama"),
        "answer": "Jawapan:\nIbu negeri Kelantan ialah Kota Bharu.",
    },
    "sungai_utama": {
        "keywords": ("sungai utama", "sungai kelantan"),
        "answer": "Jawapan:\nSungai utama di Kelantan ialah Sungai Kelantan.",
    },
    "gelaran_kelantan": {
        "keywords": ("gelaran kelantan", "gelaran terkenal", "gelaran terkenal bagi negeri kelantan", "serambi mekah"),
        "answer": "Jawapan:\nKelantan terkenal dengan gelaran Serambi Mekah.",
    },
    "lokasi_kelantan": {
        "keywords": ("lokasi kelantan", "kelantan di malaysia", "di mana kelantan"),
        "answer": "Jawapan:\nKelantan terletak di Pantai Timur Semenanjung Malaysia.",
    },
    "bendera_kelantan": {
        "keywords": ("warna bendera", "bendera kelantan"),
        "answer": "Jawapan:\nBendera Kelantan menggunakan warna merah dengan lambang berwarna putih.",
    },
}


def lookup_canonical_fact(query: str) -> dict | None:
    normalized = normalize_query(query)
    for intent, fact in CANONICAL_FACTS.items():
        if any(keyword in normalized for keyword in fact["keywords"]):
            return {
                "intent": intent,
                "answer": fact["answer"],
                "source": "canonical_facts",
            }
    return None
