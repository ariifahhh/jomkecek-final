from __future__ import annotations

import os
from functools import lru_cache

import pandas as pd

from .config import COLLECTIONS, DATA_PATHS
from .models import RagDocument



def active_data_path() -> str:
    for path in DATA_PATHS:
        if os.path.exists(path):
            return path
    raise FileNotFoundError("Dataset JomKecek tidak dijumpai.")


def collection_for_category(category: str) -> str:
    category = category.lower()
    for collection, categories in COLLECTIONS.items():
        if category in categories:
            return collection
    return "general"


def _row_title(row: pd.Series, fallback: str) -> str:
    for col in (
        "nama",
        "nama_tempat",
        "nama_makanan",
        "nama_budaya",
        "tajuk",
        "title",
        "tempat",
        "makanan",
        "perkataan",
        "dialek",
    ):
        if col in row and pd.notna(row[col]) and str(row[col]).strip():
            return str(row[col]).strip()
    return fallback


def _row_to_doc(row: pd.Series, category: str, row_number: int) -> RagDocument | None:
    metadata = {
        str(key).lower(): str(value).strip()
        for key, value in row.items()
        if pd.notna(value) and str(value).strip()
    }
    if not metadata:
        return None

    text = metadata.get("combined_content")
    if not text:
        text = " | ".join(f"{key}: {value}" for key, value in metadata.items())

    return RagDocument(
        text=text,
        category=category,
        title=_row_title(row, category),
        row=row_number,
        collection=collection_for_category(category),
        metadata=metadata,
    )


@lru_cache(maxsize=1)
def load_documents() -> list[RagDocument]:
    path = active_data_path()
    docs: list[RagDocument] = []

    if path.endswith(".csv"):
        df = pd.read_csv(path)
        for i, row in df.iterrows():
            category = str(row.get("kategori", row.get("category", "general"))).lower()
            doc = _row_to_doc(row, category, i + 1)
            if doc:
                docs.append(doc)
    else:
        xls = pd.ExcelFile(path)
        for sheet in xls.sheet_names:
            df = pd.read_excel(path, sheet_name=sheet)
            for i, row in df.iterrows():
                doc = _row_to_doc(row, sheet.lower(), i + 1)
                if doc:
                    docs.append(doc)

    return docs

