from dataclasses import dataclass


@dataclass
class RagDocument:
    text: str
    category: str
    title: str
    row: int
    collection: str
    metadata: dict[str, str]


@dataclass
class RetrievalHit:
    score: float
    document: RagDocument
    keyword_score: float
    vector_score: float

