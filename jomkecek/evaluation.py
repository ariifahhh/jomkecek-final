from __future__ import annotations

import re

from .preprocessing import tokenize

try:
    from rouge_score import rouge_scorer
except Exception:
    rouge_scorer = None

_LLM_JUDGE_PROMPT = """Kau adalah hakim AI yang menilai kualiti jawapan chatbot Kelantan.

Soalan pengguna: {question}
Konteks yang diambil daripada pangkalan data: {context}
Jawapan chatbot: {answer}

Nilai setiap aspek dengan skor 0.0 hingga 1.0:
- Faithfulness: Adakah jawapan berdasarkan konteks yang diberikan? (1.0 = sepenuhnya berdasarkan konteks, tiada fakta rekaan)
- Relevancy: Adakah jawapan menjawab soalan pengguna? (1.0 = sangat relevan dan tepat)
- Completeness: Adakah jawapan lengkap dan tidak terpotong? (1.0 = lengkap)

Balas HANYA dalam format ini, tiada penjelasan lain:
FAITHFULNESS=0.X|RELEVANCY=0.X|COMPLETENESS=0.X"""


def rouge_l(reference: str, candidate: str) -> float:
    if not reference or not candidate:
        return 0.0
    if rouge_scorer:
        scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
        return round(float(scorer.score(reference, candidate)["rougeL"].fmeasure), 2)
    ref = set(tokenize(reference))
    cand = set(tokenize(candidate))
    return round(len(ref & cand) / max(len(ref | cand), 1), 2)


def _parse_judge_scores(raw: str) -> dict[str, float]:
    scores: dict[str, float] = {}
    for part in re.split(r"[|\n]", raw):
        m = re.match(r"(\w+)\s*=\s*([\d.]+)", part.strip(), re.IGNORECASE)
        if m:
            try:
                scores[m.group(1).lower()] = min(1.0, max(0.0, float(m.group(2))))
            except ValueError:
                pass
    return scores


def llm_judge(question: str, context: str, answer: str) -> dict[str, float]:
    try:
        from .llm import ollama_judge
        prompt = _LLM_JUDGE_PROMPT.format(
            question=question,
            context=context[:600],
            answer=answer[:400],
        )
        raw = ollama_judge(prompt)
        scores = _parse_judge_scores(raw)
        return {
            "judge_faithfulness": scores.get("faithfulness", 0.0),
            "judge_relevancy": scores.get("relevancy", 0.0),
            "judge_completeness": scores.get("completeness", 0.0),
        }
    except Exception:
        return {"judge_faithfulness": 0.0, "judge_relevancy": 0.0, "judge_completeness": 0.0}


def evaluate(
    answer: str,
    contexts: list[str],
    confidence: float,
    strict_translation: bool = False,
    question: str = "",
) -> dict:
    context = "\n".join(contexts)
    rouge = rouge_l(context, answer)

    if strict_translation:
        faithfulness = confidence
        semantic_similarity = confidence
    else:
        faithfulness = max(confidence, rouge)
        semantic_similarity = max(rouge, confidence * 0.85)

    result = {
        "rouge_l": round(rouge, 2),
        "context_precision": round(confidence, 2),
        "faithfulness": round(min(1.0, faithfulness), 2),
        "answer_relevancy": round(min(1.0, semantic_similarity), 2),
        "semantic_similarity": round(min(1.0, semantic_similarity), 2),
        "judge_reason": "ROUGE-L mengukur padanan perkataan; skor lain menggabungkan keyakinan carian dan pertindihan jawapan dengan konteks.",
    }

    if question and context:
        judge = llm_judge(question, context, answer)
        result.update(judge)

    return result
