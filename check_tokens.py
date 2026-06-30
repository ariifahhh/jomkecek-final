import json
import sys
import re
from rouge_score import rouge_scorer

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def tokenize(text):
    text = text.lower()
    tokens = re.split(r'[^a-zA-Z0-9]+', text)
    return [t for t in tokens if t]

scorer = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=False)

with open('rouge_l_results.json', encoding='utf-8') as f:
    data = json.load(f)

print("=== Nilai P/R/F1 yang TERSIMPAN dalam JSON (dikira dari translation_text) ===")
print(f"{'ID':<5} {'P (stored)':<12} {'R (stored)':<12} {'F1 (stored)':<12} {'P==R'}")
print("-"*55)
for ku, label in [('KU-01','T'), ('KU-02','T')]:
    offset = 0 if ku == 'KU-01' else 5
    for r in data[ku]:
        tid = f"{label}{r['id']+offset}"
        same = abs(r['precision'] - r['recall']) < 0.001
        print(f"{tid:<5} {r['precision']:<12.3f} {r['recall']:<12.3f} {r['f1']:<12.3f} {same}")

print()
print("=== Semak: jika recompute dari 'answer' (jawapan penuh) ===")
print(f"{'ID':<5} {'P (recompute)':<15} {'R (recompute)':<15} {'F1 (recompute)'}")
print("-"*55)
for ku, label in [('KU-01','T'), ('KU-02','T')]:
    offset = 0 if ku == 'KU-01' else 5
    for r in data[ku]:
        tid = f"{label}{r['id']+offset}"
        s = scorer.score(r['ref'], r['answer'])['rougeL']
        print(f"{tid:<5} {s.precision:<15.3f} {s.recall:<15.3f} {s.fmeasure:.3f}")
