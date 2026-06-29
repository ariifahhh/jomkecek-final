"""
JomKecek Evaluation Script
Run: python run_evaluation.py
Requires: backend running at http://localhost:8000 (uvicorn api:app)
Output : rouge_l_results.json + llm_judge_results.json + markdown tables
"""
from __future__ import annotations

import json
import time
import requests

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

# ─── KU-01: Dialek → BM ──────────────────────────────────────────────────────
KU01 = [
    ("sayo nok awok tunjuk jale gi pata",          "saya nak awak tunjuk jalan ke pantai"),
    ("sayo nok awok tunjuk jale gi hotel",         "saya nak awak tunjuk arah ke hotel"),
    ("sayo buleh pesey makaney loni",              "saya boleh pesan makanan sekarang"),
    ("sayo nok gi pasagh loni",                    "saya nak pergi ke pasar sekarang"),
    ("awok makey nasi dagang semale",              "awak makan nasi dagang semalam"),
    ("kat mano kawe buleh beli hadioh ole-ole?",   "di mana saya boleh beli cenderamata?"),
    ("kawe nok gi pasa male",                      "saya hendak pergi ke pasar malam"),
    ("kawe nok make nasi keghabu hok sedak",       "saya nak makan nasi kerabu yang sedap"),
    ("kawe nok beli kaing batik kelate",           "saya mahu beli kain batik kelantan"),
    ("kawe nok gi panta nok mandi",                "saya hendak ke pantai untuk mandi-manda"),
    ("buleh ko kawe jale kaki gi situ?",           "boleh ke saya jalan kaki ke sana?"),
    ("kawe nok beli kepok leko hok ori",           "saya hendak beli keropok lekor asli"),
    ("buleh tunjuk kat peta kawe duk mano?",       "boleh tolong tunjukkan kedudukan saya dalam peta?"),
    ("kawe nok gi pasa siti khadijah",             "saya mahu pergi ke pasar siti khadijah"),
    ("sayo nok awok tunjuk lokasi hotel",          "saya nak awak tunjuk lokasi hotel"),
]

# ─── KU-02: BM → Dialek ──────────────────────────────────────────────────────
KU02 = [
    ("saya nak awak tunjuk jalan ke pantai",              "sayo nok awok tunjuk jale gi pata"),
    ("saya nak awak tunjuk arah ke hotel",                "sayo nok awok tunjuk jale gi hotel"),
    ("saya boleh pesan makanan sekarang",                 "sayo buleh pesey makaney loni"),
    ("saya nak pergi ke pasar sekarang",                  "sayo nok gi pasagh loni"),
    ("awak makan nasi dagang semalam",                    "awok makey nasi dagang semale"),
    ("di mana saya boleh beli cenderamata?",              "kat mano kawe buleh beli hadioh ole-ole?"),
    ("saya hendak pergi ke pasar malam",                  "kawe nok gi pasa male"),
    ("saya nak makan nasi kerabu yang sedap",             "kawe nok make nasi keghabu hok sedak"),
    ("saya mahu beli kain batik kelantan",                "kawe nok beli kaing batik kelate"),
    ("saya hendak ke pantai untuk mandi-manda",           "kawe nok gi panta nok mandi"),
    ("boleh ke saya jalan kaki ke sana?",                 "buleh ko kawe jale kaki gi situ?"),
    ("saya hendak beli keropok lekor asli",               "kawe nok beli kepok leko hok ori"),
    ("boleh tolong tunjukkan kedudukan saya dalam peta?", "buleh tunjuk kat peta kawe duk mano?"),
    ("saya mahu pergi ke pasar siti khadijah",            "kawe nok gi pasa siti khadijah"),
    ("saya nak awak tunjuk lokasi hotel",                 "sayo nok awok tunjuk lokasi hotel"),
]

# ─── KU-03: Pelancongan ──────────────────────────────────────────────────────
KU03 = [
    ("Apakah ibu negeri Kelantan?",                        "Direct",         "Kota Bharu adalah ibu negeri Kelantan."),
    ("Berapakah jajahan di Kelantan?",                     "Direct",         "Kelantan mempunyai 10 jajahan."),
    ("Berapakah keluasan negeri Kelantan?",                "Direct",         "Keluasan Kelantan ialah 15,099 kilometer persegi."),
    ("Apakah warna bendera Kelantan?",                     "Direct",         "Bendera Kelantan berwarna merah dan kuning."),
    ("Cadangan makanan tradisional Kelantan",              "Recommendation", "Nasi kerabu, nasi dagang, laksam, keropok lekor dan akok merupakan makanan tradisional Kelantan yang terkenal."),
    ("Tempat menarik di Kota Bharu",                       "Recommendation", "Pantai Cahaya Bulan, Pasar Siti Khadijah, Muzium Kelantan dan Istana Jahar merupakan tempat menarik di Kota Bharu."),
    ("Apa budaya terkenal di Kelantan?",                   "Recommendation", "Wayang kulit, dikir barat, mak yong, rebana dan wau bulan merupakan budaya terkenal Kelantan."),
    ("Senaraikan aktiviti menarik untuk pelancong di Kelantan", "Recommendation", "Pelancong boleh menikmati wayang kulit, membeli kraftangan, melawat pantai, mencuba makanan tradisional dan mengunjungi pasar malam."),
    ("Ceritakan tentang Wayang Kulit Kelantan",            "Detail",         "Wayang Kulit Kelantan adalah seni persembahan tradisional menggunakan patung kulit yang dimainkan di sebalik skrin putih dengan iringan muzik gamelan."),
    ("Terangkan tentang Mak Yong",                         "Detail",         "Mak Yong adalah seni persembahan tradisional Kelantan yang menggabungkan tarian, nyanyian dan dialog yang telah diiktiraf UNESCO."),
    ("Huraikan tentang Dikir Barat",                       "Detail",         "Dikir Barat adalah seni persembahan beramai-ramai dengan nyanyian berirama yang dipimpin oleh seorang tok juara dan diikuti oleh awok-awok."),
    ("Mengapakah Kelantan dipanggil Serambi Mekah?",       "Reasoning",      "Kelantan dipanggil Serambi Mekah kerana pengaruh kuat agama Islam dalam kehidupan masyarakat, undang-undang dan adat resam negeri tersebut."),
    ("Bagaimana songket Kelantan ditenun?",                "Reasoning",      "Songket Kelantan ditenun secara tradisional menggunakan alat tenun bingkai dengan benang emas atau perak yang diselitkan ke dalam fabrik sutera atau kapas."),
    ("Kenapa Kelantan terkenal dengan kraftangan tradisional?", "Reasoning",  "Kelantan terkenal dengan kraftangan kerana warisan budaya yang kuat, kemahiran turun-temurun dalam tenunan songket, anyaman, ukiran kayu dan pembuatan wau."),
    ("Bagaimanakah permainan gasing dimainkan?",           "Reasoning",      "Gasing dimainkan dengan melilitkan tali pada cakera besar kemudian dilempar kuat ke tanah supaya berpusing lama, dan pertandingan menilai tempoh putaran terlama."),
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

        # ROUGE-L — KU-03 compute locally, KU-01/KU-02 use API f1 + recompute P/R locally
        if name == "KU-03":
            rl = _rouge_l_full(ref, answer)
        else:
            rl_local = _rouge_l_full(ref, answer)
            api_f1   = ev.get("rouge_l", rl_local["f1"])
            rl = {"precision": rl_local["precision"], "recall": rl_local["recall"], "f1": api_f1}

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
    vals = [r[key] for r in lst if r[key] > 0]
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
    print("HASIL LENGKAP — SALIN KE D7")
    print("="*60)

    print_rouge_table("KU-01 (Dialek → BM)", ku01)
    print_judge_table("KU-01 (Dialek → BM)", ku01)

    print_rouge_table("KU-02 (BM → Dialek)", ku02)
    print_judge_table("KU-02 (BM → Dialek)", ku02)

    print_rouge_table("KU-03 (Pelancongan)", ku03)
    print_judge_table("KU-03 (Pelancongan)", ku03)

    # Ringkasan
    print("\n### Ringkasan Keseluruhan\n")
    print("| KU | F1-Skor | Kerelevanan Konteks | Ketepatan Maklumat | Kerelevanan Jawapan | Status |")
    print("|----|---------|--------------------|--------------------|---------------------|--------|")
    for name, data, thresh in [("KU-01", ku01, 0.45), ("KU-02", ku02, 0.40), ("KU-03", ku03, 0.40)]:
        f1 = avg(data, "f1")
        c  = avg(data, "kerelevanan_konteks")
        g  = avg(data, "ketepatan_maklumat")
        a  = avg(data, "kerelevanan_jawapan")
        lulus  = f1 >= thresh and c >= 0.70 and g >= 0.70 and a >= 0.70
        status = "LULUS ✓" if lulus else "GAGAL ✗"
        print(f"| {name} | {f1:.3f} | {c:.3f} | {g:.3f} | {a:.3f} | **{status}** |")

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
