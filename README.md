# JomKecek — Kelantan AI Chatbot

JomKecek is a hybrid RAG chatbot for Kelantan dialect translation, tourism, food, culture and general knowledge about Kelantan. Built as a Final Year Project (FYP) using Next.js 14, FastAPI and a locally-hosted Malaysian LLM.

**Live demo:** [jomkecek.vercel.app](https://jomkecek.vercel.app) *(frontend — requires backend running locally or via ngrok)*

---

## Features

- **Dialect Translation** — Kelantan dialect ↔ Standard Malay using dictionary + fuzzy matching
- **Hybrid RAG Retrieval** — BM25 lexical + ChromaDB vector search (multilingual sentence-transformers)
- **Dynamic Topic Routing** — Sultan, ekonomi, politik, cuaca queries bypass RAG and go directly to LLM
- **LLM-as-Judge Evaluation** — `qwen2.5:7b` scores every answer on context relevance, groundedness and answer relevance
- **Catalog Explorer** — Browse 1,000+ tourism, food and culture items with Wikimedia images
- **Evaluation Panel** — Live ROUGE-L and Triad RAG scores in the UI
- **Guard Rails** — Out-of-scope detection, weak RAG fallback, Bahasa Melayu enforcement

---

## Architecture

```
Browser (Next.js 14 — Vercel)
        │  REST API calls
        ▼
FastAPI (port 8000 — run locally)
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
        ├── /catalog ──► Dataset (1,000+ items)
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
| Deployment | Vercel (frontend) + local/ngrok (backend) |

---

## Local Setup (First Time)

### 1. Prerequisites

- Python 3.10+
- Node.js 18+
- [Ollama](https://ollama.com) installed and running

### 2. Clone & install Python dependencies

```bash
git clone https://github.com/ariifahhh/jomkecek-final.git
cd jomkecek-final
pip install -r requirements.txt
```

### 3. Pull Ollama models

```bash
# Judge model
ollama pull qwen2.5:7b
```

For the main Malaysian-Qwen2.5-7B model (download GGUF from HuggingFace):

```bash
# Download GGUF (~4.5 GB)
huggingface-cli download mradermacher/Malaysian-Qwen2.5-7B-Instruct-GGUF \
  Malaysian-Qwen2.5-7B-Instruct.Q4_K_M.gguf --local-dir ./models

# Import into Ollama using Modelfile
ollama create malaysian-qwen2.5:7b -f Modelfile
```

### 4. Build ChromaDB vector index

```bash
python setup_chroma.py
```

Indexes all tourism, food and culture documents using multilingual sentence-transformers (~120 MB model download on first run).

### 5. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

---

## Running the App (Local)

> **Windows note:** If `uvicorn` or `npm` is not recognised, see Troubleshooting below.

### Step 1 — Start Ollama

```powershell
ollama serve
```

### Step 2 — Start FastAPI backend (new terminal)

```powershell
cd "C:\path\to\jomkecek-final"
$env:PATH += ";C:\Users\<YourUsername>\AppData\Local\Python\pythoncore-3.14-64\Scripts"
uvicorn api:app --reload
```

Backend available at `http://localhost:8000` — API docs at `http://localhost:8000/docs`

### Step 3 — Install frontend dependencies (first time only)

```powershell
cd frontend
npm install
```

### Step 4 — Start Next.js frontend (new terminal)

```powershell
cd "C:\path\to\jomkecek-final\frontend"
npm run dev
```

Open `http://localhost:3000`

---

## Troubleshooting (Windows)

### `uvicorn` not recognised
Add Python Scripts to PATH in the same terminal before running:
```powershell
$env:PATH += ";C:\Users\<YourUsername>\AppData\Local\Python\pythoncore-3.14-64\Scripts"
uvicorn api:app --reload
```

### `npm` not recognised / execution policy error
Run once to allow scripts:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```
Then install dependencies and start:
```powershell
cd frontend
npm install
npm run dev
```

### `next` not recognised
`node_modules` belum install. Run `npm install` dalam folder `frontend/` dulu.

---

## Vercel Deployment (Frontend)

The Next.js frontend can be deployed on Vercel. The FastAPI backend must run separately (locally via ngrok, or on a cloud server).

### Deploy frontend on Vercel

1. Import `ariifahhh/jomkecek-final` on [vercel.com](https://vercel.com)
2. Set **Root Directory** to `frontend`
3. Add environment variable:
   ```
   NEXT_PUBLIC_API_BASE_URL = https://your-backend-url.com
   ```
4. Deploy

### Run backend for demo via ngrok

```bash
# Terminal 1 — backend
uvicorn api:app --reload

# Terminal 2 — expose to internet
ngrok http 8000
```

Copy the ngrok URL (e.g. `https://abc123.ngrok-free.app`) and set it as `NEXT_PUBLIC_API_BASE_URL` in Vercel, then redeploy.

Set `CORS_ORIGIN` in your backend `.env` to your Vercel URL:
```
CORS_ORIGIN=https://jomkecek-final.vercel.app
```

---

## Project Structure

```
jomkecek-final/
├── api.py                          FastAPI backend (catalog, chat, images, metrics)
├── setup_chroma.py                 Build ChromaDB vector collections
├── Modelfile                       Ollama model definition for Malaysian-Qwen
├── .env.example                    Environment variable reference
├── requirements.txt
│
├── DATA_JOMKECEK_CLEANED.xlsx Main dataset (5 sheets, ~1,949 records)
│
├── frontend/                       Next.js 14 app (deploy this on Vercel)
│   ├── public/
│   │   └── kijang_bukamata.png     Mascot image (served by Next.js)
│   └── app/
│       ├── page.tsx                Main UI (chat, catalog, history, home)
│       ├── globals.css             Styling
│       └── layout.tsx
│
└── jomkecek/                       Core Python package
    ├── config.py                   Model names, paths, thresholds
    ├── data.py                     Dataset loader (lru_cache)
    ├── preprocessing.py            Tokenizer, normalizer
    ├── dialect.py                  Dialect translation (dict + fuzzy)
    ├── router.py                   Query routing + DYNAMIC_TOPICS
    ├── retriever.py                BM25 + ChromaDB hybrid retrieval
    ├── pipeline.py                 Main orchestration
    ├── evaluation.py               ROUGE-L + LLM-as-judge
    ├── guards.py                   Out-of-scope + response guard
    ├── llm.py                      Ollama API wrappers + system prompt
    └── models.py                   RagDocument, RetrievalHit dataclasses
```

---

## Environment Variables

See `.env.example` for full list. Key variables:

```env
# Backend
JOMKECEK_MODEL=malaysian-qwen2.5:7b
JOMKECEK_JUDGE_MODEL=qwen2.5:7b
JOMKECEK_USE_CHROMA=1
OLLAMA_URL=http://127.0.0.1:11434
CORS_ORIGIN=https://your-vercel-app.vercel.app

# Frontend (Next.js / Vercel)
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

---

## Dataset

`DATA_JOMKECEK_CLEANED.xlsx` contains 5 sheets:

| Sheet | Records | Content |
|---|---|---|
| perkataan | 1,214 | Kelantan dialect vocabulary |
| contoh_ayat | 396 | Dialect example sentences |
| tempat_menarik | 143 | Tourism places |
| makanan_tradisional | 115 | Traditional food |
| budaya | 81 | Cultural practices and arts |

---

## Evaluation Metrics

Every chat response is evaluated automatically:

| Metric | Method | Threshold |
|---|---|---|
| ROUGE-L | LCS overlap: system output vs reference translation | ≥ 0.40 |
| Kerelevanan Konteks | LLM-as-judge (qwen2.5:7b) | ≥ 0.70 |
| Groundedness | LLM-as-judge (qwen2.5:7b) | ≥ 0.70 |
| Kerelevanan Jawapan | LLM-as-judge (qwen2.5:7b) | ≥ 0.70 |

---

*Final Year Project — Universiti Kebangsaan Malaysia (UKM)*  
*Faculty of Information Science and Technology (FTSM)*
