"""Runs the LangGraph flow for one question and turns the result into the API response."""

import json
import time
import uuid
from typing import Literal

from pydantic import BaseModel

from .auth import User
from .config import Settings
from .graph import build_graph


class Citation(BaseModel):
    n: int
    file: str
    title: str
    section: str | None = None
    page: int | None = None
    snippet: str


class AskResponse(BaseModel):
    answer: str
    status: str
    evidence_sufficient: bool
    citations: list[Citation]
    standalone_question: str
    mode: Literal["simple", "agent"]
    agent_steps: list[str] | None = None
    session_id: str
    usage: dict
    latency_ms: int


class SessionNotFound(Exception):
    pass


class Assistant:
    def __init__(self, settings: Settings, llm, search, users: dict[str, User]):
        self.settings, self.llm, self.search, self.users = settings, llm, search, users
        self.graph = build_graph(self)

    def ask(self, user: User, question: str, session_id: str | None = None, mode: str = "auto") -> AskResponse:
        start = time.perf_counter()
        trace = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "user": user.id, "question": question,
                 "retrieval": [], "llm_calls": [], "events": [], "error": None}
        try:
            if session_id:
                # A conversation belongs to one user; someone else's id looks exactly like an unknown id.
                saved = self.graph.get_state({"configurable": {"thread_id": session_id}}).values
                if saved.get("owner") != user.id:
                    raise SessionNotFound(session_id)
            else:
                session_id = uuid.uuid4().hex
            config = {"configurable": {"thread_id": session_id, "user": user, "trace": trace}}
            # Fields for this turn are reset; `history` is kept by the checkpointer.
            state = self.graph.invoke({"question": question, "owner": user.id, "mode": mode, "route": "simple",
                                       "standalone": "", "sub_questions": [], "hits": [], "result": {},
                                       "steps": [], "feedback": "", "revised": False, "verdict": ""}, config)
            result = state["result"]
            tokens_in = sum(c["input_tokens"] for c in trace["llm_calls"])
            tokens_out = sum(c["output_tokens"] for c in trace["llm_calls"])
            usage = {"llm_calls": len(trace["llm_calls"]), "input_tokens": tokens_in, "output_tokens": tokens_out,
                     "cost_usd": round(tokens_in * self.settings.price_in / 1e6 + tokens_out * self.settings.price_out / 1e6, 5)}
            trace.update(standalone=state["standalone"], status=result["status"], usage=usage,
                         citations=[c["file"] for c in result["citations"]])
            agent = state["route"] == "agent"
            return AskResponse(answer=result["answer"], status=result["status"],
                               evidence_sufficient=result["status"] == "answered",
                               citations=[Citation(**c) for c in result["citations"]],
                               standalone_question=state["standalone"], mode="agent" if agent else "simple",
                               agent_steps=state["steps"] if agent else None, session_id=session_id, usage=usage,
                               latency_ms=round((time.perf_counter() - start) * 1000))
        except Exception as exc:
            trace["error"] = type(exc).__name__
            raise
        finally:  # one JSON line per request: retrieval, model calls, tokens, latency, errors
            trace["latency_ms"] = round((time.perf_counter() - start) * 1000)
            log = self.settings.log_file
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open("a", encoding="utf-8") as f:
                f.write(json.dumps(trace) + "\n")


def build_assistant(settings: Settings | None = None) -> Assistant:
    """Create the real assistant: users, embeddings, search index (load or build), Claude."""
    from .auth import load_users
    from .ingest import load_folder
    from .llm import Claude
    from .search import Search, make_embeddings

    settings = settings or Settings()
    if settings.anthropic_api_key is None:
        raise RuntimeError("Set ANTHROPIC_API_KEY in the .env file.")
    search = Search(make_embeddings(settings.embedding_model, settings.index_dir / "models"))
    if not search.load(settings.index_dir):
        chunks, _ = load_folder(settings.docs_dir, settings.chunk_size, settings.chunk_overlap)
        search.build(chunks)
        search.save(settings.index_dir)
    llm = Claude(settings.anthropic_api_key.get_secret_value(), settings.claude_model, settings.llm_timeout)
    return Assistant(settings, llm, search, load_users(settings.users_file))
