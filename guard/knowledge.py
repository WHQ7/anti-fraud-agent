"""Small, fully local lexical retrieval. Not embeddings or a vector database."""

import json
import math
import re
from collections import Counter
from pathlib import Path

KNOWLEDGE_PATH = Path(__file__).resolve().parent.parent / "data" / "knowledge.json"


def terms(text: str) -> list[str]:
    text = text.lower()
    tokens = re.findall(r"[a-z0-9_]{2,}", text)
    for chunk in re.findall(r"[\u4e00-\u9fff]+", text):
        tokens.extend(chunk[i:i + 2] for i in range(len(chunk) - 1))
    return tokens


class KnowledgeBase:
    def __init__(self, path: Path = KNOWLEDGE_PATH):
        self.documents = json.loads(path.read_text(encoding="utf-8"))
        self.by_id = {doc["id"]: doc for doc in self.documents}
        self.index = [Counter(terms(" ".join([doc["title"], *doc["keywords"], doc["content"]])))
                      for doc in self.documents]
        self.average_length = sum(map(lambda item: sum(item.values()), self.index)) / max(len(self.index), 1)

    def search(self, query: str, limit: int = 3) -> list[dict]:
        if not isinstance(query, str) or not query.strip() or len(query) > 6000:
            return []
        query_terms = set(terms(query))
        results = []
        for doc, counts in zip(self.documents, self.index):
            score = 0.0
            length = sum(counts.values())
            for term in query_terms:
                frequency = counts.get(term, 0)
                if not frequency:
                    continue
                document_frequency = sum(term in item for item in self.index)
                idf = math.log(1 + (len(self.index) - document_frequency + 0.5) / (document_frequency + 0.5))
                score += idf * frequency * 2.2 / (frequency + 1.2 * (0.25 + 0.75 * length / self.average_length))
            # Small transparent keyword bonus improves a tiny Chinese corpus.
            score += sum(2 for keyword in doc["keywords"] if keyword.lower() in query.lower())
            if score > 0:
                results.append({**doc, "retrieval_score": round(score, 3)})
        return sorted(results, key=lambda doc: doc["retrieval_score"], reverse=True)[:max(1, min(limit, 4))]
