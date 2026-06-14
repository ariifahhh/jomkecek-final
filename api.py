from __future__ import annotations

import re
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from jomkecek.data import load_documents
from jomkecek.pipeline import metrics as get_metrics, run_chatbot as chatbot_pipeline


ROOT = Path(__file__).parent
ASSETS = ROOT / "assets"
WIKI_HEADERS = {"User-Agent": "JomKecek-FYP/1.0 (academic demo; local app)"}

app = FastAPI(
    title="JomKecek API",
    description="FastAPI backend for the JomKecek Kelantan dialect and knowledge chatbot.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if ASSETS.exists():
    app.mount("/assets", StaticFiles(directory=ASSETS), name="assets")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    mode: str = Field(default="Auto")


class ImageSearchRequest(BaseModel):
    keywords: list[str] = Field(default_factory=list, max_length=8)
    limit_per_keyword: int = Field(default=2, ge=1, le=4)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> dict:
    try:
        return get_metrics()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _catalog_description(metadata: dict[str, str], fallback: str) -> str:
    for key in ("deskripsi_ringkas", "deskripsi", "penerangan", "description", "maklumat"):
        value = metadata.get(key)
        if value:
            return value
    text = metadata.get("combined_content") or fallback
    parts = [part.strip() for part in str(text).split("|") if ":" in part]
    for part in parts:
        key, _, value = part.partition(":")
        if key.strip().lower() in {"deskripsi_ringkas", "deskripsi", "penerangan"}:
            return value.strip()
    return "Maklumat ringkas tersedia dalam pangkalan data JomKecek."


def _title_case_ms(value: str) -> str:
    small = {"dan", "atau", "di", "ke", "dari", "dalam", "yang", "dengan", "bin", "binti"}
    upper = {"abc", "kb", "pcb"}
    words = []
    for raw in str(value).replace("_", " ").split():
        word = raw.strip()
        if not word:
            continue
        lower = word.lower()
        if lower in upper:
            words.append(lower.upper())
        elif lower in small and words:
            words.append(lower)
        elif "-" in lower:
            words.append("-".join(part[:1].upper() + part[1:] if part else part for part in lower.split("-")))
        else:
            words.append(lower[:1].upper() + lower[1:])
    return " ".join(words)


def _sentence_case(value: str) -> str:
    text = " ".join(str(value).split())
    if not text:
        return text
    return text[:1].upper() + text[1:]


@app.get("/catalog")
def catalog() -> dict[str, list[dict[str, str | int]]]:
    try:
        docs = load_documents()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    allowed = {
        "tourism": "Tempat Menarik",
        "food": "Makanan Tradisional",
        "culture": "Budaya",
    }
    seen: set[tuple[str, str]] = set()
    items: list[dict[str, str | int]] = []

    for doc in docs:
        if doc.collection not in allowed:
            continue
        name = _title_case_ms(str(doc.title).strip())
        if not name or name.lower() in {"tempat_menarik", "makanan_tradisional", "budaya"}:
            continue
        key = (doc.collection, name.lower())
        if key in seen:
            continue
        seen.add(key)
        district = _title_case_ms(doc.metadata.get("asal_jajahan") or doc.metadata.get("daerah") or "")
        description = _sentence_case(_catalog_description(doc.metadata, doc.text))
        image_keyword = re.sub(r"\s+", " ", re.sub(r"\([^)]*\)", "", name)).strip()
        items.append(
            {
                "id": f"{doc.collection}-{doc.row}",
                "name": name,
                "collection": doc.collection,
                "category": allowed[doc.collection],
                "district": district,
                "description": description,
                "prompt": f"Ceritakan tentang {name}",
                "image_keyword": image_keyword,
            }
        )

    return {"items": items}


@app.post("/chat")
def chat(payload: ChatRequest) -> dict:
    try:
        return chatbot_pipeline(payload.message.strip(), payload.mode)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


_SKIP_EXTS = {".svg", ".ogg", ".ogv", ".webm", ".mp3", ".pdf", ".tif", ".tiff"}


def _commons_image_hits(query: str, limit: int) -> list[dict[str, str]]:
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": 6,
        "gsrlimit": min(limit + 4, 12),
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "format": "json",
        "origin": "*",
    }
    try:
        resp = requests.get("https://commons.wikimedia.org/w/api.php", params=params, headers=WIKI_HEADERS, timeout=10)
        resp.raise_for_status()
    except Exception:
        return []

    pages = resp.json().get("query", {}).get("pages", {})
    hits: list[dict[str, str]] = []
    for page in sorted(pages.values(), key=lambda p: p.get("index", 999)):
        info = (page.get("imageinfo") or [{}])[0]
        url = info.get("url", "")
        if not url or any(url.lower().endswith(e) for e in _SKIP_EXTS):
            continue
        hits.append(
            {
                "url": url,
                "title": page.get("title", query).replace("File:", ""),
                "source": info.get("descriptionurl", url),
            }
        )
        if len(hits) >= limit:
            break
    return hits


def _wikipedia_image_hits(query: str, limit: int, lang: str = "ms") -> list[dict[str, str]]:
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": 0,
        "gsrlimit": limit + 2,
        "prop": "pageimages",
        "piprop": "original",
        "format": "json",
        "origin": "*",
    }
    try:
        resp = requests.get(f"https://{lang}.wikipedia.org/w/api.php", params=params, timeout=10)
        resp.raise_for_status()
    except Exception:
        return []

    pages = resp.json().get("query", {}).get("pages", {})
    hits: list[dict[str, str]] = []
    for page in pages.values():
        info = page.get("original") or {}
        url = info.get("source", "")
        if not url or any(url.lower().endswith(e) for e in _SKIP_EXTS):
            continue
        hits.append(
            {
                "url": url,
                "title": page.get("title", query),
                "source": f"https://{lang}.wikipedia.org/wiki/{page.get('title', '').replace(' ', '_')}",
            }
        )
        if len(hits) >= limit:
            break
    return hits


@app.post("/images")
def images(payload: ImageSearchRequest) -> dict[str, list[dict[str, str]]]:
    results: list[dict[str, str]] = []
    seen: set[str] = set()

    def query_variants(keyword: str) -> list[str]:
        full = re.sub(r"\s+", " ", keyword.strip())
        no_parens = re.sub(r"\([^)]*\)", "", full)
        no_parens = re.sub(r"\s+", " ", no_parens).strip()
        words = no_parens.split()
        short = " ".join(words[:3]) if len(words) > 3 else ""
        seen_v: list[str] = []
        for v in [full, no_parens, short]:
            if v and v not in seen_v:
                seen_v.append(v)
        return seen_v

    for keyword in payload.keywords:
        variants = query_variants(keyword)
        keyword_results: list[dict[str, str]] = []

        # 1. Wikimedia Commons (File namespace) — best for cultural images
        for query in variants:
            hits = [h for h in _commons_image_hits(query, payload.limit_per_keyword) if h["url"] not in seen]
            if hits:
                keyword_results.extend(hits[:payload.limit_per_keyword])
                break

        # 2. Malay Wikipedia pageimages — good for Malaysian content
        if not keyword_results:
            for query in variants:
                hits = [h for h in _wikipedia_image_hits(query, payload.limit_per_keyword, "ms") if h["url"] not in seen]
                if hits:
                    keyword_results.extend(hits)
                    break

        # 3. English Wikipedia pageimages — broad fallback
        if not keyword_results:
            for query in variants[:2]:
                hits = [h for h in _wikipedia_image_hits(query, payload.limit_per_keyword, "en") if h["url"] not in seen]
                if hits:
                    keyword_results.extend(hits)
                    break

        for hit in keyword_results[:payload.limit_per_keyword]:
            if hit["url"] not in seen:
                seen.add(hit["url"])
                results.append(hit)

    return {"images": results[:8]}
