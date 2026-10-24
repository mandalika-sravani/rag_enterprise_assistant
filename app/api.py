"""REST API. Start with:  python -m app.cli serve   then open http://127.0.0.1:8000/docs"""

from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from .assistant import AskResponse, Assistant, SessionNotFound, build_assistant
from .auth import User, can_read, find_user_by_key
from .llm import LLMError


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    session_id: str | None = None
    mode: Literal["auto", "simple", "agent"] = "auto"


def create_app(assistant: Assistant | None = None) -> FastAPI:
    app = FastAPI(title="Enterprise Knowledge Assistant",
                  description="Send your key in the X-API-Key header (demo keys are in users.yaml).")
    holder = {"assistant": assistant}

    def get_assistant() -> Assistant:
        if holder["assistant"] is None:
            holder["assistant"] = build_assistant()
        return holder["assistant"]

    def current_user(x_api_key: Annotated[str | None, Header()] = None) -> User:
        user = find_user_by_key(get_assistant().users, x_api_key)
        if user is None:
            raise HTTPException(401, "Missing or invalid X-API-Key header.")
        return user

    def admin_user(user: Annotated[User, Depends(current_user)]) -> User:
        if not user.is_admin:
            raise HTTPException(403, "Admin role required.")
        return user

    # Every model failure becomes a safe JSON error with the right HTTP status.
    @app.exception_handler(LLMError)
    def llm_error(request, exc: LLMError):
        headers = {"Retry-After": "10"} if exc.status == 429 else None
        return JSONResponse({"error": exc.code, "message": exc.message}, status_code=exc.status, headers=headers)

    @app.exception_handler(SessionNotFound)
    def session_error(request, exc):
        return JSONResponse({"error": "session_not_found", "message": "Unknown session_id. Omit it to start over."}, 404)

    @app.get("/", include_in_schema=False)
    def web_page():
        """Chat page: pick a user, ask questions, see citations and agent steps."""
        return FileResponse(Path(__file__).parent / "static" / "index.html")

    @app.post("/ask", response_model=AskResponse)
    def ask(body: AskRequest, user: Annotated[User, Depends(current_user)]):
        """Ask a question. Send back the returned session_id to ask a follow-up."""
        return get_assistant().ask(user, body.question, body.session_id, body.mode)

    @app.get("/documents")
    def documents(user: Annotated[User, Depends(current_user)]):
        """Documents the caller is allowed to read."""
        return sorted({c.metadata["file"] for c in get_assistant().search.chunks if can_read(user, c.metadata)})

    @app.post("/reindex")
    def reindex(_: Annotated[User, Depends(admin_user)]):
        """Admin only: re-read the documents folder and rebuild the index."""
        from .ingest import load_folder

        a = get_assistant()
        chunks, report = load_folder(a.settings.docs_dir, a.settings.chunk_size, a.settings.chunk_overlap)
        a.search.build(chunks)
        a.search.save(a.settings.index_dir)
        return {"report": report, "chunks": len(chunks)}

    @app.get("/health")
    def health():
        return {"status": "ok", "chunks": len(get_assistant().search.chunks)}

    return app


app = create_app()
