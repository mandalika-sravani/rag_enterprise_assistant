"""Run the 23 evaluation conversations with the real model and write eval/results.md.

    python -m eval.run_eval
"""

import json
import statistics
import time
from pathlib import Path

import yaml

from app.assistant import build_assistant

HERE = Path(__file__).parent


def check(case, resp, retrieved_files):
    exp, answer = case.get("expect", {}), resp.answer.lower()
    statuses = exp.get("status")
    results = {}
    if statuses:
        results["status"] = resp.status in (statuses if isinstance(statuses, list) else [statuses])
    if "docs" in exp:
        results["cites_expected_doc"] = any(c.file in exp["docs"] for c in resp.citations)
    if "must_contain" in exp:
        results["contains"] = all(s.lower() in answer for s in exp["must_contain"])
    if "must_not_contain" in exp:
        results["does_not_contain"] = not any(s.lower() in answer for s in exp["must_not_contain"])
    if "forbidden_docs" in exp:  # checked against everything retrieved on every turn
        results["no_leak"] = not (set(exp["forbidden_docs"]) & retrieved_files)
    return results


def main():
    assistant = build_assistant()
    cases = yaml.safe_load((HERE / "questions.yaml").read_text(encoding="utf-8"))["cases"]
    log = assistant.settings.log_file
    rows = []
    for case in cases:
        user = assistant.users[case["user"]]
        session, retrieved, t0 = None, set(), time.perf_counter()
        for turn in case["turns"]:
            resp = assistant.ask(user, turn, session_id=session)
            session = resp.session_id
            trace = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
            retrieved |= {h["chunk"].split("#")[0] for r in trace["retrieval"] for h in r["hits"]}
        results = check(case, resp, retrieved)
        rows.append({"id": case["id"], "category": case["category"], "user": case["user"],
                     "passed": all(results.values()), "failed_checks": [k for k, v in results.items() if not v],
                     "status": resp.status, "mode": resp.mode, "answer": resp.answer,
                     "ms": round((time.perf_counter() - t0) * 1000), **resp.usage})

    passed = sum(r["passed"] for r in rows)
    latencies = sorted(r["ms"] for r in rows)
    lines = [f"# Evaluation results ({assistant.settings.claude_model})", "",
             f"**{passed}/{len(rows)} passed.** Median {statistics.median(latencies)} ms, slowest {latencies[-1]} ms. "
             f"Tokens {sum(r['input_tokens'] for r in rows)} in / {sum(r['output_tokens'] for r in rows)} out, "
             f"about ${sum(r['cost_usd'] for r in rows):.3f}.", "",
             "| Case | Category | User | Pass | Status | Mode | Failed checks |", "|---|---|---|---|---|---|---|"]
    lines += [f"| {r['id']} | {r['category']} | {r['user']} | {'yes' if r['passed'] else '**no**'} | {r['status']} | "
              f"{r['mode']} | {', '.join(r['failed_checks']) or '-'} |" for r in rows]
    lines += ["", "## Answers", ""] + [f"- **{r['id']}**: {r['answer']}" for r in rows]
    (HERE / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:3]))
    print("failed:", [r["id"] for r in rows if not r["passed"]] or "none")


if __name__ == "__main__":
    main()
