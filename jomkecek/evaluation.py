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

_JUDGE_PROMPT_TRANSLATION = """You are an objective evaluator for a Kelantan dialect translation system.

Translation direction: {direction}
Input text: {question}
Retrieved example sentence pairs from dataset:
{context}
System translation output: {answer}

IMPORTANT: The input and output are in DIFFERENT languages/dialects. A correct translation will look different from the input.
- Dialect→BM: Kelantan dialect words are translated into Standard Malay
- BM→Dialect: Standard Malay words are translated into Kelantan dialect

Rate each dimension 0.0 to 1.0:
CONTEXT_RELEVANCE: Do the retrieved example sentences contain words or phrases from the input text? (1.0=highly relevant, 0.0=no overlap)
GROUNDEDNESS: Is the translation output consistent with the vocabulary shown in the example sentences? (1.0=fully consistent, 0.0=contradicts examples)
ANSWER_RELEVANCE: Is the translation output different from the input AND a plausible translation? Score 1.0 if output differs from input and could be a valid translation. Score 0.0 only if output is identical to input or completely unrelated.

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
    direction: str = "",
) -> dict[str, float]:
    try:
        from .llm import ollama_judge
        if mode == "translation":
            dir_label = (
                "Bahasa Melayu Standard → Dialek Kelantan" if direction == "bm_to_dialect"
                else "Dialek Kelantan → Bahasa Melayu Standard"
            )
            prompt = _JUDGE_PROMPT_TRANSLATION.format(
                direction=dir_label,
                question=question,
                context=context[:600],
                answer=answer[:400],
            )
        else:
            prompt = _JUDGE_PROMPT_TOURISM.format(
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


def _format_translation_context(contexts: list[str]) -> str:
    """Extract clean dialek↔BM pairs from raw contoh_ayat document texts for the judge."""
    pairs = []
    for text in contexts[:4]:
        dialek, bm = "", ""
        for part in str(text).split("|"):
            part = part.strip()
            if part.lower().startswith("dialek_ayat:"):
                dialek = part.split(":", 1)[1].strip()
            elif part.lower().startswith("bm_ayat:"):
                bm = part.split(":", 1)[1].strip()
        if dialek and bm:
            pairs.append(f"  Dialek: {dialek}\n  BM: {bm}")
        elif text.strip():
            pairs.append(f"  {text[:200]}")
    return "\n".join(pairs) if pairs else "\n".join(c[:150] for c in contexts[:3])


def evaluate(
    answer: str,
    contexts: list[str],
    confidence: float,
    strict_translation: bool = False,
    question: str = "",
    reference: str = "",
    mode: str = "tourism",
    direction: str = "",
) -> dict:
    context = "\n".join(contexts)
    # ROUGE-L: compare against human reference if provided, else against retrieved context
    rouge_ref = reference if reference else context
    rouge = rouge_l(rouge_ref, answer)

    result = {"rouge_l": round(rouge, 2)}

    if question and context:
        judge_context = _format_translation_context(contexts) if mode == "translation" else context
        result.update(llm_judge(question, judge_context, answer, mode=mode, direction=direction))

    return result
