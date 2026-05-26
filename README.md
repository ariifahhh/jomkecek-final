# JomKecek Hybrid Chatbot

JomKecek is a controlled hybrid Streamlit chatbot for Kelantan dialect translation, tourism, culture, food and general Kelantan questions.

## Architecture

```text
User input
  |
  v
Intent detection
  |
  +-- Translation pipeline
  |     dictionary lookup
  |     fuzzy matching
  |     sentence matching
  |     strict formatter only
  |
  +-- Kelantan knowledge pipeline
        metadata filter
        hybrid retrieval
        optional Chroma collections
        controlled Qwen2.5:7B answer
```

Translation is intentionally not embedding-first because short dialect tokens such as `mu`, `nok`, `gapo` and `mano` are better handled by exact and fuzzy matching.

## Main Backend Functions

- `normalize_query()` in `jomkecek.preprocessing`
- `detect_out_of_scope()` in `jomkecek.guards`
- `detect_language_mode()` in `jomkecek.dialect`
- `route_query()` in `jomkecek.router`
- `lookup_canonical_fact()` in `jomkecek.canonical`
- `translate_dialect()` in `jomkecek.dialect`
- `retrieve_rag_context()` in `jomkecek.pipeline`
- `validate_rag_context()` in `jomkecek.pipeline`
- `generate_general_answer()` in `jomkecek.pipeline`
- `validate_bahasa_melayu_only()` in `jomkecek.guards`
- `final_response_guard()` in `jomkecek.guards`

## Scope Rules

JomKecek only answers about Kelantan. Questions about other states or countries return the fixed out-of-scope response. Weak or irrelevant RAG context returns the safe database fallback instead of allowing the model to invent facts.

## Folder Structure

```text
app.py                  Streamlit UI
backend.py              Small compatibility facade
jomkecek/
  config.py             Paths, model and collection config
  preprocessing.py      Normalization and tokenization
  data.py               Excel/CSV loader and collection assignment
  intent.py             Keyword intent detection
  dialect.py            Strict dictionary/fuzzy/sentence translation
  retriever.py          Metadata-filtered hybrid retrieval
  llm.py                Ollama prompt wrappers
  evaluation.py         ROUGE-L plus faithfulness/relevancy proxies
  pipeline.py           Controlled routing logic
  chroma_index.py       Optional separate Chroma collection builder
```

## Run

```powershell
cd "C:\Users\masar\Desktop\FYP SEM 2\FYP SEM 2\CODE TRY BARU DARI COLAB"
& "C:\Users\masar\AppData\Local\Programs\Python\Python312\python.exe" -m streamlit run app.py --server.port 8501
```

The active dataset priority is:

1. `DATA_JOMKECEK_CLEANED copy.xlsx`
2. `DATA_JOMKECEK_CLEANED.csv`
3. `DATA_JOMKECEK_CLEANED.xlsx`

## Optional ChromaDB

The code supports separate Chroma collections:

- `dialect_words`
- `dialect_sentences`
- `tourism`
- `food`
- `culture`

Install Chroma only if you want persistent vector retrieval:

```powershell
pip install chromadb
```

Then rebuild collections:

```powershell
python -c "from jomkecek.chroma_index import rebuild_chroma_collections; print(rebuild_chroma_collections())"
```

Enable Chroma retrieval:

```powershell
$env:JOMKECEK_USE_CHROMA="1"
```

## Recommended Embeddings

For Malay/Kelantan semantic retrieval, prefer:

- `BAAI/bge-m3`
- `intfloat/multilingual-e5-small`
- `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`

`all-MiniLM-L6-v2` is fast but weaker for multilingual and dialect-heavy content.

## Evaluation

The UI reports:

- ROUGE-L
- Context precision
- Faithfulness
- Answer relevancy
- Semantic similarity proxy

ROUGE-L alone is insufficient for translation because it measures lexical overlap, not whether `mu nok gi mano` correctly means `Awak nak pergi mana?`.
