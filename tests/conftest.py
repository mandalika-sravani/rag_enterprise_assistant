"""Test helpers: a fake embedding model and a fake Claude, so tests run offline in seconds.

The fakes let us test what the system GUARANTEES (permissions, citation checks, abstention,
error handling, the graph's routing and limits) whatever the model says. Answer quality is
measured by eval/run_eval.py with the real model.
"""

import hashlib
import re
import shutil
from pathlib import Path

import pytest
from langchain_core.embeddings import Embeddings

from app.assistant import Assistant
from app.auth import load_users
from app.config import Settings
from app.ingest import load_folder
from app.search import Search, tokenize

ROOT = Path(__file__).resolve().parents[1]


class FakeEmbeddings(Embeddings):
    """Word-hashing vectors (a LangChain Embeddings class): texts sharing words get similar vectors."""

    def _vector(self, text):
        v = [0.0] * 256
        for word in tokenize(text):
            v[int(hashlib.md5(word.encode()).hexdigest(), 16) % 256] += 1.0
        return v

    def embed_documents(self, texts):
        return [self._vector(t) for t in texts]

    def embed_query(self, text):
        return self._vector(text)


class FakeClaude:
    """Returns scripted replies per schema (or raises scripted errors) and records every prompt.
    With no script, an answer cites the first sentence of document S1."""

    def __init__(self, **scripts):
        self.scripts = {k: list(v) for k, v in scripts.items()}
        self.prompts = []

    def ask_json(self, system, prompt, schema, trace=None):
        self.prompts.append(prompt)
        if trace is not None:
            trace["llm_calls"].append({"schema": schema.__name__, "input_tokens": 100, "output_tokens": 20, "ms": 1})
        queue = self.scripts.get(schema.__name__)
        if queue:
            item = queue.pop(0) if len(queue) > 1 else queue[0]
            if isinstance(item, Exception):
                raise item
            return schema.model_validate(item)
        if schema.__name__ == "AnswerOut":
            m = re.search(r'<document id="S1"[^>]*>\n(.*?)(?<=[.!?])', prompt, re.S)
            return schema(status="answered", answer=f"{m.group(1).strip()} [S1]", sources=["S1"])
        if schema.__name__ == "RewriteOut":
            return schema(question=re.search(r"<latest>(.*?)</latest>", prompt).group(1))
        if schema.__name__ == "Plan":
            q = re.search(r"<question>(.*?)</question>", prompt).group(1)
            return schema(sub_questions=[p.strip() for p in q.split(" and ")])
        if schema.__name__ == "Check":
            return schema(supported=True)
        raise AssertionError(schema)


@pytest.fixture
def make_assistant(tmp_path):
    def make(llm=None, **overrides):
        docs = tmp_path / "docs"
        if not docs.exists():
            shutil.copytree(ROOT / "sample_docs", docs)
        options = {"min_score": 0.2, **overrides}
        settings = Settings(_env_file=None, docs_dir=docs, index_dir=tmp_path / "data",
                            log_file=tmp_path / "requests.jsonl", users_file=ROOT / "users.yaml", **options)
        search = Search(FakeEmbeddings())
        search.build(load_folder(docs, settings.chunk_size, settings.chunk_overlap)[0])
        return Assistant(settings, llm or FakeClaude(), search, load_users(settings.users_file))
    return make


@pytest.fixture
def assistant(make_assistant):
    return make_assistant()
