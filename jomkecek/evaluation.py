from __future__ import annotations

from .preprocessing import tokenize

try:
    from rouge_score import rouge_scorer
except Exception:
    rouge_scorer = None


def rouge_l(reference: str, candidate: str) -> float:
    if not reference or not candidate:
        return 0.0
    if rouge_scorer:
        scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
        return round(float(scorer.score(reference, candidate)["rougeL"].fmeasure), 2)
    ref = set(tokenize(reference))
    cand = set(tokenize(candidate))
    return round(len(ref & cand) / max(len(ref | cand), 1), 2)


def evaluate(answer: str, contexts: list[str], confidence: float, strict_translation: bool = False) -> dict:
    context = "\n".join(contexts)
    rouge = rouge_l(context, answer)
    if strict_translation:
        faithfulness = confidence
        semantic_similarity = confidence
    else:
        faithfulness = max(confidence, rouge)
        semantic_similarity = max(rouge, confidence * 0.85)

    return {
        "rouge_l": round(rouge, 2),
        "context_precision": round(confidence, 2),
        "faithfulness": round(min(1.0, faithfulness), 2),
        "answer_relevancy": round(min(1.0, semantic_similarity), 2),
        "semantic_similarity": round(min(1.0, semantic_similarity), 2),
        "judge_reason": "ROUGE-L hanya mengukur padanan perkataan; skor lain menggabungkan keyakinan carian dan pertindihan jawapan dengan konteks.",
    }
