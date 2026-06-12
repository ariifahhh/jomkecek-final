from __future__ import annotations

import re
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend import chatbot_pipeline, get_metrics
from jomkecek.data import load_documents


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


@app.post("/images")
def images(payload: ImageSearchRequest) -> dict[str, list[dict[str, str]]]:
    results: list[dict[str, str]] = []
    seen: set[str] = set()

    def query_variants(keyword: str) -> list[str]:
        clean = re.sub(r"\([^)]*\)", "", keyword)
        clean = re.sub(r"\bKelantan\b", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\s+", " ", clean).strip()
        variants = [keyword.strip(), clean]
        words = clean.split()
        if len(words) > 2:
            variants.append(" ".join(words[:2]))
        return [variant for i, variant in enumerate(variants) if variant and variant not in variants[:i]]

    for keyword in payload.keywords:
        variants = query_variants(keyword)
        keyword_results: list[dict[str, str]] = []
        for query in variants:
            if keyword_results:
                break
            params = {
                "action": "query",
                "generator": "search",
                "gsrsearch": query,
                "gsrnamespace": 6,
                "gsrlimit": payload.limit_per_keyword,
                "prop": "imageinfo",
                "iiprop": "url|extmetadata",
                "format": "json",
                "origin": "*",
            }
            try:
                response = requests.get("https://commons.wikimedia.org/w/api.php", params=params, headers=WIKI_HEADERS, timeout=10)
                response.raise_for_status()
            except Exception:
                continue

            pages = response.json().get("query", {}).get("pages", {})
            for page in sorted(pages.values(), key=lambda item: item.get("index", 999)):
                info = (page.get("imageinfo") or [{}])[0]
                url = info.get("url")
                if not url or url in seen:
                    continue
                seen.add(url)
                keyword_results.append(
                    {
                        "url": url,
                        "title": page.get("title", query).replace("File:", ""),
                        "source": info.get("descriptionurl", url),
                    }
                )

        if keyword_results:
            results.extend(keyword_results)
            continue

        params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": variants[-1] if variants else keyword,
            "gsrnamespace": 0,
            "gsrlimit": payload.limit_per_keyword,
            "prop": "pageimages",
            "piprop": "original",
            "format": "json",
            "origin": "*",
        }
        try:
            response = requests.get("https://commons.wikimedia.org/w/api.php", params=params, headers=WIKI_HEADERS, timeout=10)
            response.raise_for_status()
        except Exception:
            continue

        pages = response.json().get("query", {}).get("pages", {})
        for page in pages.values():
            info = page.get("original") or {}
            url = info.get("source")
            if not url or url in seen:
                continue
            seen.add(url)
            results.append(
                {
                    "url": url,
                    "title": page.get("title", keyword).replace("File:", ""),
                    "source": f"https://commons.wikimedia.org/wiki/{page.get('title', '').replace(' ', '_')}",
                }
            )

    return {"images": results[:8]}
