from __future__ import annotations

import re

from .preprocessing import tokenize

try:
    from rouge_score import rouge_scorer
except Exception:
    rouge_scorer = None

_LLM_JUDGE_PROMPT = """You are an evaluation AI for a Kelantan chatbot. Score the response below.

Question: {question}
Context from database: {context}
Chatbot answer: {answer}

Rate each dimension 0.0 to 1.0:
FAITHFULNESS: Is answer grounded in context? (1.0=fully grounded, 0.0=hallucinated)
RELEVANCY: Does it answer the question? (1.0=very relevant, 0.0=off-topic)
COMPLETENESS: Is answer complete? (1.0=complete, 0.0=empty/cut off)

Output ONLY this line, nothing else:
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

    result = {"rouge_l": round(rouge, 2)}

    if question and context:
        result.update(llm_judge(question, context, answer))

    return result
