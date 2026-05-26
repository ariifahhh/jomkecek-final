"""Compatibility facade for the Streamlit app.

The production logic lives in the `jomkecek/` package:
- jomkecek.dialect: strict dictionary/fuzzy/sentence translation
- jomkecek.retriever: metadata-filtered hybrid retrieval
- jomkecek.pipeline: controlled routing and limited LLM usage
"""

from jomkecek.pipeline import metrics, run_chatbot


def chatbot_pipeline(user_input: str, mode: str = "Auto") -> dict:
    return run_chatbot(user_input, mode)


def get_metrics() -> dict:
    return metrics()

