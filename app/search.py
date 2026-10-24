"""Hybrid search with LangChain: vector store (meaning) + BM25 (keywords), permission-filtered.

* InMemoryVectorStore (langchain-core) applies a filter function to every document BEFORE ranking,
  so chunks the user may not read are never scored. It saves to / loads from one JSON file.
* BM25 (rank-bm25) scores the allowed chunks only.
* The two ranked lists are merged with Reciprocal Rank Fusion (score = sum of 1 / (60 + rank)).

langchain-community (which had FastEmbedEmbeddings and BM25Retriever) is being sunset, so this
file uses two small adapters on langchain-core's interfaces instead.
"""

import re
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore
from rank_bm25 import BM25Okapi

from .auth import User, can_read

STOPWORDS = set("a an and are as at be by can do does for from has have how i in is it of on or "
                "the to was what when where which who why will with you your".split())


def tokenize(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS]


class FastEmbedEmbeddings(Embeddings):
    """LangChain Embeddings adapter: BAAI/bge-small-en-v1.5 run locally on CPU by fastembed (ONNX, no PyTorch)."""

    def __init__(self, model_name: str, cache_dir: Path):
        from fastembed import TextEmbedding

        self.model = TextEmbedding(model_name=model_name, cache_dir=str(cache_dir))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self.model.embed(texts)]

    QUERY_PREFIX = "Represent this sentence for searching relevant passages: "  # bge models were trained with it

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([self.QUERY_PREFIX + text])[0]


def make_embeddings(model_name: str, cache_dir: Path) -> Embeddings:
    return FastEmbedEmbeddings(model_name, cache_dir)


class Search:
    def __init__(self, embeddings: Embeddings):
        self.embeddings = embeddings
        self.store = InMemoryVectorStore(embeddings)
        self.chunks: list[Document] = []

    def build(self, chunks: list[Document]) -> None:
        self.store = InMemoryVectorStore(self.embeddings)
        if chunks:
            self.store.add_documents(chunks, ids=[c.metadata["id"] for c in chunks])
        self.chunks = chunks

    def save(self, folder: Path) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        self.store.dump(str(folder / "vectorstore.json"))

    def load(self, folder: Path) -> bool:
        path = folder / "vectorstore.json"
        if not path.exists():
            return False
        self.store = InMemoryVectorStore.load(str(path), self.embeddings)
        self.chunks = [Document(page_content=v["text"], metadata=v["metadata"]) for v in self.store.store.values()]
        return True

    def search(self, query: str, user: User, k: int = 5) -> list[dict]:
        """Return up to k hits: {"doc": Document, "similarity": cosine similarity 0-1}."""
        allowed = [c for c in self.chunks if can_read(user, c.metadata)]
        if not allowed:
            return []

        # 1. Meaning: the filter runs inside the vector store, before ranking.
        dense = self.store.similarity_search_with_score(query, k=20, filter=lambda d: can_read(user, d.metadata))
        similarity = {d.metadata["id"]: score for d, score in dense}

        # 2. Keywords: BM25 over the allowed chunks only (chunks sharing no word with the query are skipped).
        scores = BM25Okapi([tokenize(c.page_content) for c in allowed]).get_scores(tokenize(query))
        keyword = [allowed[i] for i in sorted(range(len(allowed)), key=lambda i: -scores[i])[:20] if scores[i] > 0]

        # 3. Reciprocal Rank Fusion of the two rankings.
        fused, docs = {}, {}
        for ranking in ([d for d, _ in dense], keyword):
            for rank, d in enumerate(ranking):
                cid = d.metadata["id"]
                fused[cid] = fused.get(cid, 0.0) + 1 / (60 + rank + 1)
                docs[cid] = d
        best = sorted(fused, key=fused.get, reverse=True)[:k]
        return [{"doc": docs[cid], "similarity": similarity.get(cid, 0.0)} for cid in best]
