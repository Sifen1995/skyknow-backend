#!/usr/bin/env python3
"""SkyKnow Phase 0: retrieval prototype (English only).

  python phase0.py ingest             load pages/*.md into PostgreSQL + pgvector
  python phase0.py eval               score questions.jsonl (vector search)
  python phase0.py eval --hybrid      score with vector + keyword search merged
  python phase0.py ask "your question"   try one question and see the top chunks
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector

load_dotenv()

ROOT = Path(__file__).parent
PAGES_DIR = ROOT / "pages"
QUESTIONS_FILE = ROOT / "questions.jsonl"
RESULTS_DIR = ROOT / "results"

DB_URL = os.getenv("DATABASE_URL", "postgresql://skyknow:skyknow@localhost:5433/skyknow")
MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
DIMS = int(os.getenv("EMBEDDING_DIMS", "1536"))
USE_FAKE = os.getenv("EMBEDDER", "openai").lower() == "fake"
MAX_WORDS = 250  # a section longer than this is split at paragraph breaks

STOPWORDS = set(
    "the a an and or of to in on for with is are was were be do does did how what when where which who "
    "can could should would my your our their me you we they it this that these those i not no from by at "
    "as if so than then there here about have has had get got".split()
)


# --------------------------------------------------------------------------- chunking
def load_pages():
    """Yield (slug, title, lines) for every pages/*.md file. First '# ' line is the title."""
    files = sorted(PAGES_DIR.glob("*.md"))
    if not files:
        sys.exit(f"No pages found in {PAGES_DIR}. Add .md files first.")
    for path in files:
        lines = path.read_text(encoding="utf-8").splitlines()
        title = path.stem
        if lines and lines[0].startswith("# "):
            title = lines[0][2:].strip()
            lines = lines[1:]
        yield path.stem, title, lines


def split_sections(lines):
    """Split at '## ' headings. Text before the first heading is called 'Overview'."""
    sections, name, buf = [], "Overview", []
    for line in lines:
        if line.startswith("## "):
            if "".join(buf).strip():
                sections.append((name, "\n".join(buf).strip()))
            name, buf = line[3:].strip(), []
        else:
            buf.append(line)
    if "".join(buf).strip():
        sections.append((name, "\n".join(buf).strip()))
    return sections


def split_long(text):
    """Split a long section into pieces of at most MAX_WORDS, at paragraph breaks."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    pieces, current, count = [], [], 0
    for p in paragraphs:
        words = len(p.split())
        if current and count + words > MAX_WORDS:
            pieces.append("\n\n".join(current))
            current, count = [], 0
        current.append(p)
        count += words
    if current:
        pieces.append("\n\n".join(current))
    return pieces


def make_chunks():
    chunks = []
    for slug, title, lines in load_pages():
        position = 0
        for section, text in split_sections(lines):
            for piece in split_long(text):
                chunks.append(
                    {
                        "page_slug": slug,
                        "title": title,
                        "section": section,
                        "position": position,
                        "text": piece,
                        # what the model sees: the title and section give each chunk context
                        "embed_text": f"{title} > {section}\n{piece}",
                    }
                )
                position += 1
    return chunks


# --------------------------------------------------------------------------- embeddings
def fake_embed(text):
    """Offline stand-in used only to test the plumbing. Scores with it mean nothing."""
    vec = np.zeros(DIMS, dtype=np.float32)
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        if word in STOPWORDS:
            continue
        idx = int(hashlib.md5(word.encode()).hexdigest(), 16) % DIMS
        vec[idx] += 1.0
    norm = np.linalg.norm(vec)
    return vec / norm if norm else vec


def embed(texts):
    if USE_FAKE:
        return [fake_embed(t) for t in texts]
    from openai import OpenAI

    client = OpenAI()  # reads OPENAI_API_KEY
    out = []
    for i in range(0, len(texts), 96):
        batch = texts[i : i + 96]
        kwargs = {"model": MODEL, "input": batch}
        if MODEL.startswith("text-embedding-3"):
            kwargs["dimensions"] = DIMS
        for attempt in range(5):
            try:
                resp = client.embeddings.create(**kwargs)
                break
            except Exception as exc:  # network or rate limit: wait and retry
                if attempt == 4:
                    raise
                print(f"  embedding call failed ({exc}); retrying...")
                time.sleep(2**attempt)
        out.extend(np.array(d.embedding, dtype=np.float32) for d in resp.data)
    return out


# --------------------------------------------------------------------------- database
def connect():
    conn = psycopg.connect(DB_URL, autocommit=True)
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    register_vector(conn)
    return conn


def cmd_ingest():
    chunks = make_chunks()
    print(f"{len(chunks)} chunks from {len({c['page_slug'] for c in chunks})} pages")
    print(f"Embedding with {'FAKE (plumbing test)' if USE_FAKE else MODEL} ({DIMS} dims)...")
    vectors = embed([c["embed_text"] for c in chunks])

    conn = connect()
    conn.execute("DROP TABLE IF EXISTS chunks")
    conn.execute(
        f"""
        CREATE TABLE chunks (
            id        serial PRIMARY KEY,
            page_slug text NOT NULL,
            title     text NOT NULL,
            section   text NOT NULL,
            position  int  NOT NULL,
            text      text NOT NULL,
            embedding vector({DIMS}) NOT NULL,
            tsv       tsvector GENERATED ALWAYS AS
                      (to_tsvector('simple', title || ' ' || section || ' ' || text)) STORED
        )
        """
    )
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO chunks (page_slug, title, section, position, text, embedding) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            [(c["page_slug"], c["title"], c["section"], c["position"], c["text"], v) for c, v in zip(chunks, vectors)],
        )
    conn.execute("CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops)")
    conn.execute("CREATE INDEX ON chunks USING gin (tsv)")
    print("Done. Now run: python phase0.py eval")


# --------------------------------------------------------------------------- search
def to_tsquery(question):
    """Turn a question into an OR query of its useful words, e.g. 'sim | lost'."""
    words = [w for w in re.findall(r"[a-z0-9]+", question.lower()) if len(w) > 2 and w not in STOPWORDS]
    return " | ".join(dict.fromkeys(words))


VECTOR_SQL = """
SELECT page_slug, title, section, text, 1 - (embedding <=> %(q)s) AS sim
FROM chunks
ORDER BY embedding <=> %(q)s
LIMIT %(k)s
"""

HYBRID_SQL = """
WITH vec AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> %(q)s) AS rnk
    FROM chunks ORDER BY embedding <=> %(q)s LIMIT 40
),
kw AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY ts_rank_cd(tsv, to_tsquery('simple', %(t)s)) DESC) AS rnk
    FROM chunks WHERE tsv @@ to_tsquery('simple', %(t)s)
    ORDER BY ts_rank_cd(tsv, to_tsquery('simple', %(t)s)) DESC LIMIT 40
),
fused AS (
    SELECT id, SUM(1.0 / (60 + rnk)) AS score
    FROM (SELECT * FROM vec UNION ALL SELECT * FROM kw) r GROUP BY id
)
SELECT c.page_slug, c.title, c.section, c.text, 1 - (c.embedding <=> %(q)s) AS sim
FROM fused f JOIN chunks c ON c.id = f.id
ORDER BY f.score DESC
LIMIT %(k)s
"""


def search(conn, question, qvec, k=5, hybrid=False):
    tsq = to_tsquery(question) if hybrid else ""
    if hybrid and tsq:
        rows = conn.execute(HYBRID_SQL, {"q": qvec, "t": tsq, "k": k}).fetchall()
    else:
        rows = conn.execute(VECTOR_SQL, {"q": qvec, "k": k}).fetchall()
    return [dict(slug=r[0], title=r[1], section=r[2], text=r[3], sim=float(r[4])) for r in rows]


def rank_pages(chunks):
    """Collapse chunks into a ranked page list (first appearance wins)."""
    pages, seen = [], set()
    for c in chunks:
        if c["slug"] not in seen:
            seen.add(c["slug"])
            pages.append(c["slug"])
    return pages


# --------------------------------------------------------------------------- evaluation
def best_threshold(answerable_sims, unanswerable_sims):
    """Find the similarity cut-off that best separates answerable from unanswerable questions."""
    if not answerable_sims or not unanswerable_sims:
        return None
    best = None
    for t in sorted(set(answerable_sims + unanswerable_sims)):
        found = sum(s >= t for s in answerable_sims) / len(answerable_sims)
        rejected = sum(s < t for s in unanswerable_sims) / len(unanswerable_sims)
        balanced = (found + rejected) / 2
        if best is None or balanced > best[0] + 1e-9:
            best = (balanced, t, found, rejected)
    return best


def cmd_eval(hybrid, k):
    questions = [json.loads(line) for line in QUESTIONS_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    conn = connect()
    qvecs = embed([q["question"] for q in questions])

    results = []
    for q, vec in zip(questions, qvecs):
        chunks = search(conn, q["question"], vec, k=k, hybrid=hybrid)
        pages = rank_pages(chunks)
        correct = set(q["correct_pages"])
        top_sim = max((c["sim"] for c in chunks), default=0.0)
        r = {
            "id": q["id"],
            "type": q["type"],
            "question": q["question"],
            "correct_pages": q["correct_pages"],
            "got_pages": pages[:5],
            "top_sim": round(top_sim, 4),
            "answerable": bool(correct),
        }
        if correct:
            r["hit1"] = bool(pages) and pages[0] in correct
            r["hit3"] = any(p in correct for p in pages[:3])
            r["rr"] = next((1 / (i + 1) for i, p in enumerate(pages[:5]) if p in correct), 0.0)
        results.append(r)

    answerable = [r for r in results if r["answerable"]]
    unanswerable = [r for r in results if not r["answerable"]]
    mode = "hybrid (vector + keyword)" if hybrid else "vector only"
    label = "FAKE embedder (plumbing test, ignore the scores)" if USE_FAKE else MODEL

    print(f"\nModel: {label}   Mode: {mode}   Questions: {len(results)}")
    print("=" * 64)
    n = len(answerable)
    h1 = sum(r["hit1"] for r in answerable)
    h3 = sum(r["hit3"] for r in answerable)
    mrr = sum(r["rr"] for r in answerable) / n if n else 0
    print(f"Answerable questions ({n})")
    print(f"  Right page first (hit@1):     {h1}/{n}  ({h1 / n:.0%})")
    print(f"  Right page in top 3 (hit@3):  {h3}/{n}  ({h3 / n:.0%})")
    print(f"  Mean reciprocal rank:         {mrr:.2f}")

    print("\nBy question type (hit@3):")
    by_type = defaultdict(list)
    for r in answerable:
        by_type[r["type"]].append(r["hit3"])
    for t, hits in by_type.items():
        print(f"  {t:<12} {sum(hits)}/{len(hits)}")

    ans_sims = [r["top_sim"] for r in answerable]
    un_sims = [r["top_sim"] for r in unanswerable]
    print(f"\nUnanswerable questions ({len(unanswerable)}): top similarity")
    if un_sims:
        print(f"  unanswerable: min {min(un_sims):.2f}  max {max(un_sims):.2f}")
    if ans_sims:
        print(f"  answerable:   min {min(ans_sims):.2f}  max {max(ans_sims):.2f}")
    bt = best_threshold(ans_sims, un_sims)
    if bt:
        _, t, found, rejected = bt
        print(f"  Suggested 'not found' cut-off: {t:.2f}")
        print(f"    would still answer {found:.0%} of answerable questions")
        print(f"    would correctly say 'not found' for {rejected:.0%} of unanswerable ones")

    failures = [r for r in answerable if not r["hit3"]]
    weak = [r for r in answerable if r["hit3"] and not r["hit1"]]
    if failures:
        print("\nMISSED (right page not in top 3):")
        for r in failures:
            print(f"  {r['id']} [{r['type']}] {r['question']}")
            print(f"      expected: {r['correct_pages']}   got: {r['got_pages'][:3]}   top sim {r['top_sim']}")
    if weak:
        print("\nFOUND BUT NOT FIRST:")
        for r in weak:
            print(f"  {r['id']} [{r['type']}] {r['question']}   expected {r['correct_pages']}   got {r['got_pages'][:3]}")

    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = f"{'fake' if USE_FAKE else MODEL}_{'hybrid' if hybrid else 'vector'}"
    out = RESULTS_DIR / f"results_{stamp}.json"
    out.write_text(json.dumps({"model": label, "mode": mode, "results": results}, indent=2), encoding="utf-8")
    print(f"\nFull results saved to {out}")


def cmd_ask(question, hybrid, k):
    conn = connect()
    vec = embed([question])[0]
    for i, c in enumerate(search(conn, question, vec, k=k, hybrid=hybrid), 1):
        print(f"{i}. [{c['sim']:.2f}] {c['title']} > {c['section']}  ({c['slug']})")
        print("   " + c["text"].replace("\n", " ")[:160] + "...")


# --------------------------------------------------------------------------- main
def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ingest")
    p_eval = sub.add_parser("eval")
    p_eval.add_argument("--hybrid", action="store_true")
    p_eval.add_argument("--k", type=int, default=5)
    p_ask = sub.add_parser("ask")
    p_ask.add_argument("question")
    p_ask.add_argument("--hybrid", action="store_true")
    p_ask.add_argument("--k", type=int, default=5)
    args = parser.parse_args()

    if args.command == "ingest":
        cmd_ingest()
    elif args.command == "eval":
        cmd_eval(args.hybrid, args.k)
    else:
        cmd_ask(args.question, args.hybrid, args.k)


if __name__ == "__main__":
    main()