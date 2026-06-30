import json
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open('rouge_l_results.json', encoding='utf-8') as f:
    rouge = json.load(f)
with open('llm_judge_results.json', encoding='utf-8') as f:
    judge = json.load(f)

t_rows = list(rouge['KU-01']) + list(rouge['KU-02'])
p_rows = list(rouge['KU-03'])

t_judge = list(judge['KU-01']) + list(judge['KU-02'])
p_judge = list(judge['KU-03'])

def avg(lst, key):
    vals = [r[key] for r in lst]
    return round(sum(vals)/len(vals), 3) if vals else 0.0

# ── ROUGE-L ─────────────────────────────────────────────────────────────────
print("=" * 65)
print("JADUAL 7.6  Keputusan Ujian ROUGE-L")
print("=" * 65)
print(f"{'ID':<5} {'Precision':>10} {'Recall':>8} {'F1-Skor':>9}")
print("-" * 35)

labels_t = ['T1','T2','T3','T4','T5','T6','T7','T8','T9','T10']
for lbl, r in zip(labels_t, t_rows):
    print(f"{lbl:<5} {r['precision']:>10.3f} {r['recall']:>8.3f} {r['f1']:>9.3f}")

labels_p = ['P1','P2','P3','P4','P5','P6','P7','P8','P9','P10']
for lbl, r in zip(labels_p, p_rows):
    print(f"{lbl:<5} {r['precision']:>10.3f} {r['recall']:>8.3f} {r['f1']:>9.3f}")

all_rouge = t_rows + p_rows
print("-" * 35)
print(f"{'PURATA':<5} {avg(all_rouge,'precision'):>10.3f} {avg(all_rouge,'recall'):>8.3f} {avg(all_rouge,'f1'):>9.3f}")

# ── LLM-as-a-Judge ──────────────────────────────────────────────────────────
print()
print("=" * 65)
print("JADUAL 7.7  Keputusan Ujian LLM-as-a-Judge")
print("=" * 65)
print(f"{'ID':<5} {'Kerelevanan Konteks':>21} {'Ketepatan Maklumat':>20} {'Kerelevanan Jawapan':>21}")
print("-" * 70)

for lbl, r in zip(labels_t, t_judge):
    print(f"{lbl:<5} {r['kerelevanan_konteks']:>21.3f} {r['ketepatan_maklumat']:>20.3f} {r['kerelevanan_jawapan']:>21.3f}")

jenis_map = ['Direct','Direct','Recommendation','Recommendation','Recommendation','Detail','Detail','Reasoning','Reasoning','Reasoning']
for lbl, r, j in zip(labels_p, p_judge, jenis_map):
    print(f"{lbl:<5} {r['kerelevanan_konteks']:>21.3f} {r['ketepatan_maklumat']:>20.3f} {r['kerelevanan_jawapan']:>21.3f}")

all_judge = t_judge + p_judge
print("-" * 70)
print(f"{'PURATA':<5} {avg(all_judge,'kerelevanan_konteks'):>21.3f} {avg(all_judge,'ketepatan_maklumat'):>20.3f} {avg(all_judge,'kerelevanan_jawapan'):>21.3f}")
