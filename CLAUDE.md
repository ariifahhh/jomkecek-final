# JomKecek — Claude Code Project Context

## Project Overview
JomKecek is a Kelantan dialect translation + tourism chatbot (Final Year Project).
- **Frontend**: Next.js 14, TypeScript — `frontend/app/page.tsx`
- **Backend**: FastAPI — `api.py`
- **Core logic**: `jomkecek/` package

## Architecture Flow
User input → `pipeline.py:run_chatbot()` → route (translation or kelantan QA) → retrieve docs → LLM → evaluate → return

## Dataset Documents (HIGHEST PRIORITY for answers)
All data lives in `DATA_JOMKECEK_CLEANED copy.xlsx`, loaded by `jomkecek/data.py`.

### Sheet: makanan_tradisional
| Field | Description |
|---|---|
| doc_id | makanan_001, makanan_002, ... |
| nama_makanan | e.g. nasi kerabu biru |
| jenis | hidangan utama / kuih / minuman |
| bahan_utama | comma-separated ingredients |
| asal_jajahan | district of origin |
| deskripsi_ringkas | short description |
| status_halal | halal / tidak |

Example rows:
- makanan_001 | nasi kerabu biru | hidangan utama | beras,ulam,kelapa,solok lada | kota bharu | nasi biru asli bunga telang dengan ulaman dan sambal kelapa | halal
- makanan_002 | nasi dagang kelantan | hidangan utama | beras merah,santan,ikan tongkol | tumpat | nasi beras merah dikukus santan bersama gulai darat ikan tongkol | halal

### Sheet: tempat_menarik
| Field | Description |
|---|---|
| doc_id | tempat_001, tempat_002, ... |
| nama_tempat | place name |
| kategori | pantai / muzium / pasar / istana / alam semula jadi |
| asal_jajahan | district |
| deskripsi_ringkas | short description |

### Sheet: budaya
| Field | Description |
|---|---|
| doc_id | budaya_001, budaya_002, ... |
| nama_budaya | e.g. wau bulan, wayang kulit |
| kategori | seni / permainan / kraftangan / adat |
| deskripsi_ringkas | short description |

### Sheet: contoh_ayat (for dialect translation)
| Field | Description |
|---|---|
| no_ayat | ayat_001, ayat_002, ... |
| bm_ayat | Standard Malay sentence |
| dialek_ayat | Kelantan dialect equivalent |
| domain | pelancongan (all 396 records) |

Example:
- ayat_001 | saya nak awak tunjuk jalan ke pantai | sayo nok awok tunjuk jale gi pata

### Sheet: perkataan (dialect dictionary)
| Field | Description |
|---|---|
| dialek | Kelantan dialect word |
| bm | Standard Malay equivalent |
| contoh | example sentence |

## Priority Rule for Answers
1. **Dataset documents FIRST** — if question matches makanan/tempat/budaya, use those docs
2. **contoh_ayat SECOND** — for dialect translation, use matched sentence pairs
3. **_CANONICAL_KELANTAN dict** — for well-known facts (gelaran, ibu negeri, jajahan)
4. **LLM knowledge LAST** — only for dynamic topics (cuaca, politik, perangkaan semasa)

Never hallucinate names, places, or facts not in the dataset.

## Key Files
- `jomkecek/pipeline.py` — main orchestration, `run_chatbot()`
- `jomkecek/retriever.py` — BM25 + ChromaDB hybrid retrieval
- `jomkecek/dialect.py` — dialect translation (dictionary + fuzzy)
- `jomkecek/evaluation.py` — ROUGE-L + LLM-as-judge (qwen2.5:7b)
- `jomkecek/router.py` — intent detection, query routing
- `jomkecek/data.py` — dataset loader (lru_cache)
- `jomkecek/config.py` — model names, thresholds

## Models
- Main LLM: `malaysian-qwen2.5:7b` via Ollama (port 11434)
- Judge LLM: `qwen2.5:7b` via Ollama
- Embeddings: `paraphrase-multilingual-MiniLM-L12-v2`

## Running Locally
```powershell
# Terminal 1 — backend
$env:PATH += ";C:\Users\User\AppData\Local\Python\pythoncore-3.14-64\Scripts"
uvicorn api:app --reload

# Terminal 2 — frontend
cd frontend
npm run dev
```

## Deployment
- Frontend: https://jomkecek.vercel.app (Vercel, root dir = `frontend`)
- Backend: local only (Ollama cannot run on Vercel)
