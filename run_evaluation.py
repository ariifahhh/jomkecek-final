"""
JomKecek Evaluation Script
Run: python run_evaluation.py
Requires: backend running at http://localhost:8000 (uvicorn api:app)
Output : rouge_l_results.json + llm_judge_results.json + markdown tables
"""
from __future__ import annotations

import json
import sys
import time
import requests

# Force UTF-8 output on Windows so Unicode arrows/dashes print cleanly
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from rouge_score import rouge_scorer as _rs
    def _rouge_l_full(ref: str, cand: str) -> dict:
        if not ref or not cand:
            return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
        scorer = _rs.RougeScorer(["rougeL"], use_stemmer=False)
        s = scorer.score(ref, cand)["rougeL"]
        return {
            "precision": round(float(s.precision), 3),
            "recall":    round(float(s.recall), 3),
            "f1":        round(float(s.fmeasure), 3),
        }
except Exception:
    def _rouge_l_full(ref: str, cand: str) -> dict:
        ref_t  = ref.lower().split()
        cand_t = cand.lower().split()
        if not ref_t or not cand_t:
            return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
        common = len(set(ref_t) & set(cand_t))
        p = round(common / len(cand_t), 3)
        r = round(common / len(ref_t), 3)
        f = round(2 * p * r / (p + r), 3) if (p + r) else 0.0
        return {"precision": p, "recall": r, "f1": f}

API = "http://localhost:8000/chat"

# ─── KU-01: Dialek → BM (T1–T5 dari Jadual 7.4) ─────────────────────────────
KU01 = [
    ("sayo nok awok tunjuk jale gi pata",    "saya nak awak tunjuk jalan ke pantai"),
    ("sayo buleh pese makane loni",           "saya boleh pesan makanan sekarang"),
    ("kawe nok make nasi keghabu hok sedak", "saya nak makan nasi kerabu yang sedap"),
    ("makane ni pedah do'oh ko?",            "makanan ini pedas sangat ke?"),
    ("buleh ko kawe jale kaki gi sana?",     "boleh ke saya jalan kaki ke sana?"),
]

# ─── KU-02: BM → Dialek (T6–T10 dari Jadual 7.4) ────────────────────────────
KU02 = [
    ("saya nak awak tunjuk jalan ke pantai",  "sayo nok awok tunjuk jale gi pata"),
    ("saya boleh pesan makanan sekarang",     "sayo buleh pese makane loni"),
    ("saya nak makan nasi kerabu yang sedap", "kawe nok make nasi keghabu hok sedak"),
    ("makanan ini pedas sangat ke?",          "makane ni pedah do'oh ko?"),
    ("boleh ke saya jalan kaki ke sana?",     "buleh ko kawe jale kaki gi sana?"),
]

# ─── KU-03: Pelancongan (P1–P10 dari Jadual 7.4) ─────────────────────────────
KU03 = [
    ("Apakah ibu negeri Kelantan?",
     "Direct",
     "Ibu negeri Kelantan ialah Kota Bharu."),
    ("Apakah warna bendera Kelantan?",
     "Direct",
     "Bendera Kelantan berwarna merah dengan gambar wau bulan dan bintang berwarna putih di bahagian tengah."),
    ("Cadangan makanan tradisional Kelantan",
     "Recommendation",
     "nasi kerabu biru: nasi biru asli bunga telang dengan ulaman dan sambal kelapa. nasi dagang kelantan: nasi beras merah dikukus santan bersama gulai darat ikan tongkol. nasi berlauk ikan tongkol: sarapan ruji kelantan dengan gulai kuning ikan yang kaya rasa."),
    ("Tempat menarik di Kota Bharu",
     "Recommendation",
     "pantai cahaya bulan: pantai ikonik kelantan; sesuai untuk riadah keluarga. masjid muhammadi: masjid bersejarah dibina pada 1867 dengan seni bina unik. istana balai besar: istana diraja lama kesultanan kelantan yang megah."),
    ("Apa budaya terkenal di Kelantan?",
     "Recommendation",
     "wayang kulit kelantan: teater bayangan menggunakan patung. dikir barat: persembahan berkumpulan yang menggabungkan nyanyian berbalas pantun dan gerakan tangan. mak yong: drama tari tradisional yang menggabungkan unsur lakonan, dan muzik."),
    ("Ceritakan tentang Wayang Kulit Kelantan",
     "Detail",
     "wayang kulit kelantan: teater bayangan menggunakan patung."),
    ("Huraikan tentang Nasi Kerabu",
     "Detail",
     "nasi kerabu hitam: versi nasi kerabu dengan kuah tumis santan pekat yang gelap. nasi kerabu kuning: variasi nasi kerabu berwarna kuning kunyit dengan ulaman segar. nasi kerabu putih: nasi kerabu asli tanpa pewarna; dimakan dengan sambal tumis."),
    ("Mengapakah Kelantan dipanggil Serambi Mekah?",
     "Reasoning",
     "Gelaran 'Serambi Mekah' diberikan kepada Kelantan kerana negeri ini diiktiraf sebagai pusat kehidupan dan pengajian Islam yang kukuh di Malaysia."),
    ("Kenapa wau bulan dikaitkan dengan Kelantan?",
     "Reasoning",
     "wau bulan: wau ikonik malaysia dengan hiasan motif sobek yang sangat halus dan bersaiz besar. wau seri bulan: variasi wau bulan yang mempunyai ekor lebih lebar dan corak lebih padat. wau jalabudi sobek: wau jalabudi yang dihiasi dengan teknik potongan kertas berwarna yang rumit."),
    ("Kenapa Kelantan terkenal dengan seni ukiran kayu?",
     "Reasoning",
     "seni ukiran kayu kelantan: seni ukiran motif bunga dan geometri pada bangunan dan hulu keris. seni kraf ukiran nisan kayu: ukiran nisan daripada kayu cengal yang mempunyai nilai seni tinggi."),
]


def call_api(message: str, mode: str, retries: int = 2) -> dict:
    for attempt in range(retries + 1):
        try:
            r = requests.post(API, json={"message": message, "mode": mode}, timeout=60)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == retries:
                print(f"  [ERROR] {e}")
                return {}
            time.sleep(2)
    return {}


def run_ku(name: str, cases: list, mode: str) -> list[dict]:
    print(f"\n{'='*60}")
    print(f"Running {name} ({len(cases)} cases) — mode: {mode}")
    print('='*60)
    results = []
    for i, row in enumerate(cases, 1):
        query, ref = (row[0], row[1]) if len(row) == 2 else (row[0], row[2])
        jenis = row[1] if len(row) == 3 else ""
        print(f"  [{i:02d}] {query[:55]}...")
        resp = call_api(query, mode)
        if not resp:
            results.append({
                "id": i, "query": query, "ref": ref, "jenis": jenis, "answer": "",
                "precision": 0.0, "recall": 0.0, "f1": 0.0,
                "kerelevanan_konteks": 0.0, "ketepatan_maklumat": 0.0, "kerelevanan_jawapan": 0.0,
            })
            continue

        ev     = resp.get("eval", {})
        answer = resp.get("answer", "")

        # ROUGE-L — compare human reference against the translated sentence only (not full formatted answer).
        # Using the full answer inflates text length and breaks P/R/F1 consistency.
        if name == "KU-03":
            rl = _rouge_l_full(ref, answer)
        else:
            translation_text = resp.get("translation", {}).get("translation", "") or answer
            rl = _rouge_l_full(ref, translation_text)

        ctx = ev.get("judge_context_relevance", 0.0)
        gnd = ev.get("judge_groundedness", 0.0)
        ans = ev.get("judge_answer_relevance", 0.0)

        print(f"         P={rl['precision']:.3f}  R={rl['recall']:.3f}  F1={rl['f1']:.3f}  "
              f"Konteks={ctx:.3f}  Ketepatan={gnd:.3f}  Jawapan={ans:.3f}")

        results.append({
            "id": i, "query": query, "ref": ref, "jenis": jenis, "answer": answer,
            "precision": rl["precision"], "recall": rl["recall"], "f1": rl["f1"],
            "kerelevanan_konteks": ctx, "ketepatan_maklumat": gnd, "kerelevanan_jawapan": ans,
        })
        time.sleep(1)
    return results


def avg(lst: list[dict], key: str) -> float:
    vals = [r[key] for r in lst]
    return round(sum(vals) / len(vals), 3) if vals else 0.0


def print_rouge_table(name: str, results: list[dict]) -> None:
    print(f"\n### {name} — Keputusan ROUGE-L\n")
    print(f"| ID | Soalan | Precision | Recall | F1-Skor |")
    print(f"|----|--------|-----------|--------|---------|")
    for r in results:
        print(f"| {r['id']:2d} | {r['query'][:45]:<47} | {r['precision']:.3f} | {r['recall']:.3f} | {r['f1']:.3f} |")
    print(f"|    | **Purata** | **{avg(results,'precision'):.3f}** | **{avg(results,'recall'):.3f}** | **{avg(results,'f1'):.3f}** |")


def print_judge_table(name: str, results: list[dict]) -> None:
    print(f"\n### {name} — Keputusan LLM-as-Judge\n")
    if results and results[0].get("jenis"):
        print("| ID | Jenis | Soalan | Kerelevanan Konteks | Ketepatan Maklumat | Kerelevanan Jawapan |")
        print("|----|-------|--------|--------------------|--------------------|---------------------|")
        for r in results:
            print(f"| {r['id']:2d} | {r['jenis']:<14} | {r['query'][:35]:<37} | {r['kerelevanan_konteks']:.3f} | {r['ketepatan_maklumat']:.3f} | {r['kerelevanan_jawapan']:.3f} |")
    else:
        print("| ID | Soalan | Kerelevanan Konteks | Ketepatan Maklumat | Kerelevanan Jawapan |")
        print("|----|--------|--------------------|--------------------|---------------------|")
        for r in results:
            print(f"| {r['id']:2d} | {r['query'][:45]:<47} | {r['kerelevanan_konteks']:.3f} | {r['ketepatan_maklumat']:.3f} | {r['kerelevanan_jawapan']:.3f} |")
    print(f"|    | **Purata** | **{avg(results,'kerelevanan_konteks'):.3f}** | **{avg(results,'ketepatan_maklumat'):.3f}** | **{avg(results,'kerelevanan_jawapan'):.3f}** |")


def main():
    print("JomKecek Evaluation — connecting to", API)
    try:
        requests.get("http://localhost:8000/health", timeout=5).raise_for_status()
        print("Backend OK\n")
    except Exception:
        print("ERROR: Backend not running. Start with: uvicorn api:app --port 8000")
        return

    ku01 = run_ku("KU-01", KU01, "Terjemahan Dialek")
    ku02 = run_ku("KU-02", KU02, "Terjemahan Dialek")
    ku03 = run_ku("KU-03", KU03, "Info Kelantan")

    print("\n\n" + "="*60)
    print("HASIL LENGKAP — JADUAL 7.4 (10 SET SOALAN)")
    print("="*60)

    print_rouge_table("KU-01 T1-T5 (Dialek ke BM)", ku01)
    print_judge_table("KU-01 T1-T5 (Dialek ke BM)", ku01)

    print_rouge_table("KU-02 T6-T10 (BM ke Dialek)", ku02)
    print_judge_table("KU-02 T6-T10 (BM ke Dialek)", ku02)

    print_rouge_table("KU-03 P1–P10 (Pelancongan)", ku03)
    print_judge_table("KU-03 P1–P10 (Pelancongan)", ku03)

    # ── Save JSON ──────────────────────────────────────────────────────────────
    rouge_out = {}
    judge_out = {}
    for name, data in [("KU-01", ku01), ("KU-02", ku02), ("KU-03", ku03)]:
        rouge_out[name] = [
            {"id": r["id"], "query": r["query"], "ref": r["ref"], "answer": r["answer"],
             "precision": r["precision"], "recall": r["recall"], "f1": r["f1"]}
            for r in data
        ]
        judge_out[name] = [
            {"id": r["id"], "query": r["query"], "jenis": r.get("jenis", ""), "answer": r["answer"],
             "kerelevanan_konteks": r["kerelevanan_konteks"],
             "ketepatan_maklumat":  r["ketepatan_maklumat"],
             "kerelevanan_jawapan": r["kerelevanan_jawapan"]}
            for r in data
        ]

    with open("rouge_l_results.json", "w", encoding="utf-8") as f:
        json.dump(rouge_out, f, ensure_ascii=False, indent=2)

    with open("llm_judge_results.json", "w", encoding="utf-8") as f:
        json.dump(judge_out, f, ensure_ascii=False, indent=2)

    print("\nRouge-L  → rouge_l_results.json")
    print("LLM Judge → llm_judge_results.json")


if __name__ == "__main__":
    main()
