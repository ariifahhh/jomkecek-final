from __future__ import annotations

import re

from .preprocessing import tokenize

try:
    from rouge_score import rouge_scorer
except Exception:
    rouge_scorer = None

_JUDGE_PROMPT_TOURISM = """You are an objective evaluator for a Kelantan tourism chatbot. Score the response below.

Question: {question}
Context retrieved from database: {context}
Chatbot answer: {answer}

Rate each dimension 0.0 to 1.0:
CONTEXT_RELEVANCE: Are the retrieved context documents relevant to the question? (1.0=fully relevant, 0.0=irrelevant)
GROUNDEDNESS: Is the answer grounded in and supported by the retrieved context? (1.0=fully grounded, 0.0=hallucinated)
ANSWER_RELEVANCE: Does the answer address the question? (1.0=very relevant, 0.0=off-topic)

Output ONLY this line, nothing else:
CONTEXT_RELEVANCE=0.X|GROUNDEDNESS=0.X|ANSWER_RELEVANCE=0.X"""

_JUDGE_PROMPT_TRANSLATION = """You are an objective evaluator for a Kelantan dialect translation system. Score the output below.

Input (text to translate): {question}
Dictionary entries retrieved (_CANONICAL_KELANTAN): {context}
Translation output: {answer}

Rate each dimension 0.0 to 1.0:
CONTEXT_RELEVANCE: Are the retrieved dictionary entries relevant to the input text? (1.0=fully relevant, 0.0=irrelevant)
GROUNDEDNESS: Is the translation supported by the retrieved dictionary entries? (1.0=fully grounded in dictionary, 0.0=not supported)
ANSWER_RELEVANCE: Does the translation correctly answer the translation request? (1.0=accurate translation, 0.0=incorrect)

Output ONLY this line, nothing else:
CONTEXT_RELEVANCE=0.X|GROUNDEDNESS=0.X|ANSWER_RELEVANCE=0.X"""


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


def llm_judge(
    question: str,
    context: str,
    answer: str,
    mode: str = "tourism",
) -> dict[str, float]:
    try:
        from .llm import ollama_judge
        template = _JUDGE_PROMPT_TRANSLATION if mode == "translation" else _JUDGE_PROMPT_TOURISM
        prompt = template.format(
            question=question,
            context=context[:600],
            answer=answer[:400],
        )
        raw = ollama_judge(prompt)
        scores = _parse_judge_scores(raw)
        return {
            "judge_context_relevance": scores.get("context_relevance", 0.0),
            "judge_groundedness": scores.get("groundedness", 0.0),
            "judge_answer_relevance": scores.get("answer_relevance", 0.0),
        }
    except Exception:
        return {
            "judge_context_relevance": 0.0,
            "judge_groundedness": 0.0,
            "judge_answer_relevance": 0.0,
        }


def evaluate(
    answer: str,
    contexts: list[str],
    confidence: float,
    strict_translation: bool = False,
    question: str = "",
    reference: str = "",
    mode: str = "tourism",
) -> dict:
    context = "\n".join(contexts)
    # ROUGE-L: compare against human reference if provided, else against retrieved context
    rouge_ref = reference if reference else context
    rouge = rouge_l(rouge_ref, answer)

    result = {"rouge_l": round(rouge, 2)}

    if question and context:
        result.update(llm_judge(question, context, answer, mode=mode))

    return result
