"""Command line.

    python -m app.cli index                        read sample_docs and build the index
    python -m app.cli users                        demo users and what they can read
    python -m app.cli ask "question" --user alice  ask once
    python -m app.cli chat --user alice            conversation with follow-ups
    python -m app.cli graph                        print the LangGraph flow (Mermaid)
    python -m app.cli serve                        chat page on http://127.0.0.1:8000 (API docs at /docs)
"""

import argparse

from .config import Settings


def show(resp) -> None:
    print(f"\n{resp.answer}")
    for c in resp.citations:
        where = ", ".join(x for x in [c.section, f"page {c.page}" if c.page else None] if x)
        print(f"  [{c.n}] {c.file}" + (f" - {where}" if where else ""))
    for step in resp.agent_steps or []:
        print(f"  agent: {step}")
    if resp.standalone_question:
        print(f"  (searched for: {resp.standalone_question})")
    print(f"  status={resp.status} mode={resp.mode} {resp.latency_ms} ms "
          f"calls={resp.usage['llm_calls']} tokens={resp.usage['input_tokens']}/{resp.usage['output_tokens']}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Enterprise knowledge assistant (LangChain + LangGraph)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("index", help="build the index from the documents folder")
    sub.add_parser("users", help="list demo users")
    p_ask = sub.add_parser("ask", help="ask one question")
    p_ask.add_argument("question")
    p_ask.add_argument("--user", default="alice")
    p_ask.add_argument("--mode", default="auto", choices=["auto", "simple", "agent"])
    p_chat = sub.add_parser("chat", help="interactive conversation")
    p_chat.add_argument("--user", default="alice")
    sub.add_parser("graph", help="print the LangGraph flow as a Mermaid diagram")
    sub.add_parser("serve", help="start the API")
    args = parser.parse_args()
    settings = Settings()

    if args.command == "index":
        from .ingest import load_folder
        from .search import Search, make_embeddings

        chunks, report = load_folder(settings.docs_dir, settings.chunk_size, settings.chunk_overlap)
        for r in report:
            print(f"{r['status']:8} {r['file']:32} {r.get('chunks', '')} {r.get('error', '')}")
        search = Search(make_embeddings(settings.embedding_model, settings.index_dir / "models"))
        search.build(chunks)
        search.save(settings.index_dir)
        print(f"{len(chunks)} chunks saved to {settings.index_dir}")

    elif args.command == "users":
        from .auth import load_users

        for u in load_users(settings.users_file).values():
            print(f"{u.id:6} key={u.api_key:16} departments={u.departments} clearance={u.clearance}")

    elif args.command in ("ask", "chat"):
        from .assistant import build_assistant
        from .llm import LLMError

        assistant = build_assistant(settings)
        user = assistant.users[args.user]
        if args.command == "ask":
            show(assistant.ask(user, args.question, mode=args.mode))
            return
        session = None
        print(f"Chatting as {user.name}. Type 'quit' to stop, 'new' to start over.")
        while (q := input(f"{user.id}> ").strip()) != "quit":
            if q == "new":
                session = None
                continue
            try:
                resp = assistant.ask(user, q, session_id=session)
                session = resp.session_id
                show(resp)
            except LLMError as exc:
                print(f"error: {exc.message}")

    elif args.command == "graph":
        from .assistant import Assistant
        from .search import Search

        # Ask LangGraph to draw the flow as a Mermaid diagram (no model or API key needed).
        graph = Assistant(settings, llm=None, search=Search(embeddings=None), users={}).graph
        print(graph.get_graph().draw_mermaid())

    elif args.command == "serve":
        import uvicorn

        uvicorn.run("app.api:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
