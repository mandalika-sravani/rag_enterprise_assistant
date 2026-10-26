"""Draw docs/architecture.svg (the LangGraph version's architecture). Run: python docs/make_architecture.py"""

from html import escape as esc
from pathlib import Path

W, H = 1500, 1120
INK, QUIET, EDGE = "#1d2330", "#5b6475", "#8a93a6"
BLUE, BLUE_BG = "#2f5bea", "#eaf0ff"  # calls Claude
GREEN, GREEN_BG = "#127a46", "#e6f5ec"  # uses Search (permission-filtered)
AMBER, AMBER_BG = "#a15c00", "#fff4e0"  # stores
out = []


def box(x, y, w, h, title, lines=(), fill="#ffffff", stroke=EDGE, bold=True, badge=None):
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="1.4"/>')
    ty = y + (h - 16 * len(lines)) / 2 + (4 if lines else 5)
    out.append(f'<text x="{x + w / 2}" y="{ty}" text-anchor="middle" font-size="14" font-weight="{600 if bold else 400}" fill="{INK}">{esc(title)}</text>')
    for i, line in enumerate(lines):
        out.append(f'<text x="{x + w / 2}" y="{ty + 18 + 16 * i}" text-anchor="middle" font-size="12" fill="{QUIET}">{esc(line)}</text>')
    if badge:
        label, color = badge
        bw = 9 + 6.6 * len(label)
        out.append(f'<rect x="{x + w - bw - 6}" y="{y - 9}" width="{bw}" height="18" rx="9" fill="{color}"/>')
        out.append(f'<text x="{x + w - bw / 2 - 6}" y="{y + 4}" text-anchor="middle" font-size="11" font-weight="600" fill="#fff">{label}</text>')


def diamond(cx, cy, w, h, l1, l2=""):
    out.append(f'<polygon points="{cx - w / 2},{cy} {cx},{cy - h / 2} {cx + w / 2},{cy} {cx},{cy + h / 2}" fill="#fff" stroke="{EDGE}" stroke-width="1.4"/>')
    out.append(f'<text x="{cx}" y="{cy - (2 if l2 else -4)}" text-anchor="middle" font-size="13" font-weight="600" fill="{INK}">{l1}</text>')
    if l2:
        out.append(f'<text x="{cx}" y="{cy + 14}" text-anchor="middle" font-size="13" font-weight="600" fill="{INK}">{l2}</text>')


def cylinder(x, y, w, h, title, lines=(), color=AMBER, bg=AMBER_BG):
    out.append(f'<path d="M{x} {y + 8} v{h - 16} a{w / 2} 8 0 0 0 {w} 0 v{-(h - 16)}" fill="{bg}" stroke="{color}" stroke-width="1.4"/>')
    out.append(f'<ellipse cx="{x + w / 2}" cy="{y + 8}" rx="{w / 2}" ry="8" fill="{bg}" stroke="{color}" stroke-width="1.4"/>')
    ty = y + h / 2 - 8 * len(lines) + 8
    out.append(f'<text x="{x + w / 2}" y="{ty}" text-anchor="middle" font-size="13" font-weight="600" fill="{INK}">{esc(title)}</text>')
    for i, line in enumerate(lines):
        out.append(f'<text x="{x + w / 2}" y="{ty + 17 + 15 * i}" text-anchor="middle" font-size="11.5" fill="{QUIET}">{esc(line)}</text>')


def group(x, y, w, h, title, color="#c9cfdb", bg="#f7f8fb"):
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{bg}" stroke="{color}" stroke-width="1.2"/>')
    out.append(f'<text x="{x + 14}" y="{y + 22}" font-size="13" font-weight="700" fill="{QUIET}">{esc(title)}</text>')


def arrow(points, label=None, at=None, dashed=False, color=EDGE, anchor="start", both=False):
    d = "M" + " L".join(f"{px} {py}" for px, py in points)
    dash = ' stroke-dasharray="5 4"' if dashed else ""
    marker = "arrow-blue" if color == BLUE else "arrow-green" if color == GREEN else "arrow"
    out.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.4"{dash} marker-end="url(#{marker})"{f' marker-start="url(#{marker})"' if both else ""}/>')
    if label:
        lx, ly = at
        out.append(f'<text x="{lx}" y="{ly}" font-size="12" text-anchor="{anchor}" fill="{QUIET}">{esc(label)}</text>')


# ---------------------------------------------------------------- title + legend
out.append(f'<text x="40" y="40" font-size="20" font-weight="700" fill="{INK}">Enterprise Knowledge Assistant: LangChain + LangGraph architecture</text>')
out.append(f'<text x="40" y="62" font-size="13" fill="{QUIET}">Permissions are applied inside Search before ranking, so restricted text never reaches Claude or the saved history.</text>')
for i, (label, color, text) in enumerate([("Claude", BLUE, "node calls Claude (ChatAnthropic)"),
                                          ("Search", GREEN, "node searches with the user's permissions")]):
    x = 40 + i * 300
    bw = 9 + 6.6 * len(label)
    out.append(f'<rect x="{x}" y="74" width="{bw}" height="18" rx="9" fill="{color}"/>')
    out.append(f'<text x="{x + bw / 2}" y="87" text-anchor="middle" font-size="11" font-weight="600" fill="#fff">{label}</text>')
    out.append(f'<text x="{x + bw + 8}" y="87" font-size="12" fill="{QUIET}">{text}</text>')
out.append('<g transform="translate(0,24)">')

# ---------------------------------------------------------------- clients, API, assistant
group(40, 90, 960, 84, "Clients")
box(70, 118, 220, 44, "Chat page  /", ["app/static/index.html"])
box(330, 118, 220, 44, "Swagger /docs, curl", ["documented API"])
box(740, 118, 230, 44, "CLI", ["python -m app.cli ask / chat"])
box(70, 196, 480, 54, "FastAPI + Pydantic  (api.py)", ["X-API-Key -> User: department + clearance (auth.py)"])
box(70, 276, 900, 54, "Assistant.ask  (assistant.py)", ["checks the session belongs to this user, runs the graph, builds the validated response, logs it"])
arrow([(180, 162), (180, 194)])
arrow([(440, 162), (440, 194)])
arrow([(310, 250), (310, 274)])
arrow([(855, 162), (855, 274)])
cylinder(1040, 270, 220, 66, "logs/requests.jsonl", ["retrieval, tokens, latency, cost"])
arrow([(970, 303), (1038, 303)])

# ---------------------------------------------------------------- LangGraph
group(40, 356, 960, 620, "LangGraph StateGraph  (graph.py)", color="#b9c4ea", bg="#f6f8ff")
arrow([(520, 330), (520, 386)])
box(390, 388, 260, 50, "rewrite", ["follow-up -> standalone question"], fill=BLUE_BG, stroke=BLUE, badge=("Claude", BLUE))
arrow([(520, 438), (520, 456)])
diamond(520, 488, 170, 62, "multi-part?")
arrow([(435, 488), (250, 488), (250, 538)], "no", (330, 480))
arrow([(605, 488), (790, 488), (790, 538)], "yes", (690, 480))

box(140, 540, 220, 50, "retrieve", ["top 5 chunks"], fill=GREEN_BG, stroke=GREEN, badge=("Search", GREEN))
arrow([(250, 590), (250, 612)])
diamond(250, 646, 150, 64, "similar", "enough?")
box(670, 540, 240, 50, "plan", ["up to 3 sub-questions"], fill=BLUE_BG, stroke=BLUE, badge=("Claude", BLUE))
arrow([(790, 590), (790, 620)])
box(670, 622, 240, 50, "research", ["search each sub-question (k=3)"], fill=GREEN_BG, stroke=GREEN, badge=("Search", GREEN))

box(390, 716, 260, 62, "generate", ["clean + label chunks S1..S5", "check citations, renumber [1] [2]"], fill=BLUE_BG, stroke=BLUE, badge=("Claude", BLUE))
arrow([(325, 646), (520, 646), (520, 714)], "yes", (420, 638))
arrow([(790, 672), (790, 696), (560, 696), (560, 714)])
diamond(820, 800, 180, 70, "verify", "claims OK?")
arrow([(650, 770), (700, 770), (700, 800), (728, 800)], "agent", (656, 792))
arrow([(820, 765), (820, 736), (652, 736)], "no: revise once", (662, 728))

box(110, 870, 180, 50, "abstain", ["'not enough information'"])
arrow([(250, 678), (250, 700), (200, 700), (200, 868)], "no", (210, 790))
arrow([(910, 800), (950, 800), (950, 964), (200, 964), (200, 922)], "still not OK", (942, 890), anchor="end")
box(400, 900, 240, 56, "remember", ["save question + answer,", "drop document text"])
arrow([(820, 835), (820, 928), (642, 928)], "yes", (828, 880))
arrow([(470, 778), (470, 898)], "simple path", (478, 845))
arrow([(290, 895), (398, 920)])

cylinder(400, 1000, 240, 70, "InMemorySaver checkpointer", ["history per session_id (thread)"])
arrow([(520, 958), (520, 998)], both=True)

# ---------------------------------------------------------------- right column: Claude, Search, indexing
group(1040, 356, 420, 150, "Claude  (llm.py)", color="#b9c4ea", bg="#f6f8ff")
box(1060, 388, 380, 50, "ChatAnthropic.with_structured_output", ["reply parsed into a Pydantic model; retry once"], fill=BLUE_BG, stroke=BLUE)
box(1060, 448, 180, 44, "Claude API", ["claude-haiku-5-5"])
box(1260, 448, 180, 44, "safe errors", ["504 / 429 / 503 / 502"], bold=False)
arrow([(1150, 438), (1150, 446)])
arrow([(1000, 413), (1058, 413)], color=BLUE)

group(1040, 526, 420, 250, "Search  (search.py, LangChain core)", color="#a9d6bd", bg="#f3faf6")
box(1060, 558, 380, 50, "can_read(user, chunk)  runs BEFORE ranking", ["department is 'all' or mine, level <= my clearance"], fill=GREEN_BG, stroke=GREEN)
cylinder(1060, 628, 180, 66, "InMemoryVectorStore", ["bge-small vectors"], color=GREEN, bg="#ffffff")
box(1260, 638, 180, 50, "BM25", ["rank-bm25, keywords"])
box(1060, 714, 380, 44, "Reciprocal Rank Fusion", ["merge both rankings -> top k"])
arrow([(1150, 608), (1150, 626)], color=GREEN)
arrow([(1350, 608), (1350, 636)], color=GREEN)
arrow([(1150, 694), (1150, 712)])
arrow([(1350, 688), (1350, 712)])
arrow([(1000, 615), (1058, 590)], color=GREEN)

group(1040, 800, 420, 254, "Indexing  (ingest.py)   python -m app.cli index", color="#e3c48c", bg="#fffaf0")
box(1060, 834, 380, 50, "sample_docs: MD, HTML, PDF, DOCX", ["+ manifest.yaml: department + access level per file"])
box(1060, 904, 380, 62, "LangChain splitters", ["Markdown/HTML header splitters (sections),", "RecursiveCharacterTextSplitter 900 chars / 150 overlap"])
box(1060, 986, 380, 50, "FastEmbedEmbeddings  (LangChain Embeddings)", ["BAAI/bge-small-en-v1.5, local CPU"])
arrow([(1250, 884), (1250, 902)])
arrow([(1250, 966), (1250, 984)])
arrow([(1050, 1011), (1020, 1011), (1020, 661), (1058, 661)], "vectors", (1014, 840), color=GREEN, anchor="end")

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
       f'font-family="Segoe UI, Arial, sans-serif"><defs>'
       + "".join(f'<marker id="{mid}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                 f'<path d="M0 0L10 5L0 10z" fill="{c}"/></marker>' for mid, c in [("arrow", EDGE), ("arrow-blue", BLUE), ("arrow-green", GREEN)])
       + f'</defs><rect width="{W}" height="{H}" fill="#ffffff"/>' + "".join(out) + "</g></svg>")
Path(__file__).with_name("architecture.svg").write_text(svg, encoding="utf-8")
print("wrote docs/architecture.svg")
