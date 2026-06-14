# JomKecek — Kelantan AI Chatbot

JomKecek is a controlled hybrid RAG chatbot for Kelantan dialect translation, tourism, food, culture and general knowledge about Kelantan. Built as a Final Year Project (FYP) using Next.js, FastAPI and a locally-hosted Malaysian LLM.

---

## Features

- **Dialect Translation** — Kelantan dialect ↔ Standard Malay using dictionary + fuzzy matching
- **Hybrid RAG Retrieval** — BM25 lexical + ChromaDB vector search (sentence-transformers multilingual)
- **Dynamic Topic Routing** — Queries about Sultan, ekonomi, politik, cuaca bypass RAG and go directly to LLM knowledge
- **LLM-as-Judge Evaluation** — `qwen2.5:7b` scores every answer on faithfulness, relevancy and completeness
- **Catalog Explorer** — Browse 1000+ tourism, food and culture items with Wikimedia images
- **Evaluation Panel** — Live ROUGE-L, faithfulness, context precision and LLM judge scores in the UI
- **Guard Rails** — Out-of-scope detection, weak RAG fallback, Bahasa Melayu enforcement

---

## Architecture

```
Browser (Next.js 14)
        │  REST API calls
        ▼
FastAPI (port 8000)
        │
        ├── /chat ──► jomkecek.router ──► Intent Detection
        │                   │
        │          ┌────────┴──────────────────┐
        │          ▼                           ▼
        │   Dialect Translation         Kelantan QA
        │   (dictionary + fuzzy)              │
        │                         ┌───────────┴────────────┐
        │                         ▼                        ▼
        │                  Dynamic Topics          Dataset RAG
        │                  (LLM knowledge)    (BM25 + ChromaDB)
        │                         │                        │
        │                         └───────────┬────────────┘
        │                                     ▼
        │                         Malaysian-Qwen2.5-7B (Ollama)
        │                                     │
        │                         ┌───────────▼────────────┐
        │                         │   Evaluation            │
        │                         │   ROUGE-L + LLM Judge  │
        │                         └────────────────────────┘
        │
        ├── /catalog ──► Dataset (1000+ items)
        └── /images  ──► Wikimedia Commons API
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, React 18, TypeScript |
| Backend | FastAPI, Python 3.12 |
| LLM (main) | Malaysian-Qwen2.5-7B-Instruct Q4_K_M via Ollama |
| LLM (judge) | qwen2.5:7b via Ollama |
| Vector DB | ChromaDB |
| Embeddings | sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 |
| Dataset | DATA_JOMKECEK_CLEANED.xlsx (dialect, tourism, food, culture) |

---

## Setup (First Time)

### 1. Prerequisites

- Python 3.10+
- Node.js 18+
- [Ollama](https://ollama.com) installed

### 2. Clone & install Python dependencies

```powershell
git clone https://github.com/ariifahhh/jomkecek-final.git
cd jomkecek-final
pip install -r requirements.txt
```

### 3. Pull Ollama models

```powershell
# Judge model (used for evaluation scoring)
ollama pull qwen2.5:7b
```

For Malaysian-Qwen2.5-7B main model (download GGUF from HuggingFace and import):

```powershell
# Download GGUF (~4.5 GB)
hf download mradermacher/Malaysian-Qwen2.5-7B-Instruct-GGUF Malaysian-Qwen2.5-7B-Instruct.Q4_K_M.gguf --local-dir ./models

# Import into Ollama using Modelfile at project root
ollama create malaysian-qwen2.5:7b -f Modelfile
```

### 4. Build ChromaDB vector index

```powershell
python setup_chroma.py
```

This indexes all tourism, food and culture documents using multilingual sentence-transformers (~120 MB model download on first run).

### 5. Install frontend dependencies

```powershell
cd frontend
npm install
cd ..
```

---

## Running the App

### Step 1 — Start Ollama

Open Ollama desktop app, or in a terminal:

```powershell
ollama serve
```

### Step 2 — Start FastAPI + Next.js

```powershell
.\run_webapp.ps1
```

### Step 3 — Open browser

```
http://localhost:3000
```

API docs available at `http://localhost:8000/docs`

---

## Project Structure

```
jomkecek-final/
├── api.py                   FastAPI backend (catalog, chat, images, metrics)
├── setup_chroma.py          Build ChromaDB vector collections
├── run_webapp.ps1           One-command launcher (FastAPI + Next.js)
├── Modelfile                Ollama model definition for Malaysian-Qwen (used by ollama create)
├── .env.example             Environment variable reference
├── requirements.txt
│
├── DATA_JOMKECEK_CLEANED copy.xlsx   Main dataset (5 sheets)
│
├── assets/                  Mascot and UI images
│
├── frontend/                Next.js 14 app
│   └── app/
│       ├── page.tsx         Main UI (chat, catalog, history, home)
│       ├── globals.css      Styling
│       └── layout.tsx
│
└── jomkecek/                Core Python package
    ├── config.py            Model names, paths, thresholds
    ├── data.py              Dataset loader (lru_cache)
    ├── preprocessing.py     Tokenizer, normalizer
    ├── dialect.py           Dialect translation (dict + fuzzy)
    ├── router.py            Query routing + DYNAMIC_TOPICS
    ├── retriever.py         BM25 + ChromaDB hybrid retrieval
    ├── pipeline.py          Main orchestration
    ├── evaluation.py        ROUGE-L + LLM-as-judge
    ├── guards.py            Out-of-scope + response guard
    ├── llm.py               Ollama API wrappers + system prompt
    └── models.py            RagDocument, RetrievalHit dataclasses
```

---

## Evaluation Metrics

Every chat response is evaluated automatically:

| Metric | Method | Good score |
|---|---|---|
| ROUGE-L | Token overlap between answer and retrieved context | 0.10 – 0.40 |
| Faithfulness | max(retrieval confidence, ROUGE-L) | > 0.50 |
| Context Precision | Retrieval confidence score | > 0.40 |
| Judge Faithfulness | LLM judge (qwen2.5:7b) | > 0.60 |
| Judge Relevancy | LLM judge (qwen2.5:7b) | > 0.60 |
| Judge Completeness | LLM judge (qwen2.5:7b) | > 0.60 |

---

## Environment Variables

See `.env.example` for full list. Key variables:

```
JOMKECEK_MODEL=malaysian-qwen2.5:7b
JOMKECEK_JUDGE_MODEL=qwen2.5:3b
JOMKECEK_USE_CHROMA=1
OLLAMA_URL=http://127.0.0.1:11434
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

---

## Dataset

`DATA_JOMKECEK_CLEANED copy.xlsx` contains 5 sheets:

| Sheet | Content |
|---|---|
| perkataan | Kelantan dialect vocabulary |
| contoh_ayat | Dialect example sentences |
| tempat_menarik | Tourism places |
| makanan_tradisional | Traditional food |
| budaya | Cultural practices and arts |

---

*Final Year Project — Universiti Kebangsaan Malaysia (UKM)*  
*Faculty of Information Science and Technology (FTSM)*
