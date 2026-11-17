"""Checks every part the document processing needs, one step at a time, and says what to fix.

Run from the project folder with the virtual environment active:
    python check_setup.py
It makes two tiny OpenAI calls (well under one cent). Your API key is never printed.
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

results: list[tuple[str, bool, str]] = []


def run(name: str, func, timeout: int = 90, fix: str = ""):
    """Runs one check in a thread so a hang is reported instead of freezing the script."""
    print(f"\n[{len(results) + 1}] {name} ...", flush=True)
    box: dict = {}

    def target():
        try:
            box["value"] = func()
        except BaseException as exc:  # report everything
            box["error"] = exc
            box["trace"] = traceback.format_exc(limit=3)

    started = time.perf_counter()
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout)
    seconds = time.perf_counter() - started
    if thread.is_alive():
        msg = f"did not finish within {timeout} seconds (it is hanging)"
        print(f"    FAIL: {msg}\n    Fix: {fix}" if fix else f"    FAIL: {msg}")
        results.append((name, False, msg))
        return None
    if "error" in box:
        exc = box["error"]
        msg = f"{exc.__class__.__name__}: {str(exc)[:400]}"
        print(f"    FAIL ({seconds:.1f}s): {msg}")
        if fix:
            print(f"    Fix: {fix}")
        results.append((name, False, msg))
        return None
    detail = box.get("value") or ""
    print(f"    OK ({seconds:.1f}s) {detail}")
    results.append((name, True, str(detail)))
    return box.get("value", True)


# ------------------------------------------------------------------ 1. Python
def check_python():
    v = sys.version_info
    if (v.major, v.minor) != (3, 11):
        raise RuntimeError(f"Python {v.major}.{v.minor} is running; this project needs 3.11")
    if ".venv" not in sys.executable:
        return f"{sys.version.split()[0]} (warning: not running from .venv: {sys.executable})"
    return f"{sys.version.split()[0]} from .venv"


run("Python version", check_python, fix="Activate the project environment: .venv\\Scripts\\Activate.ps1")


# ------------------------------------------------------------------ 2. packages
def check_packages():
    import importlib.metadata as md
    missing, found = [], []
    for pkg in ["fastapi", "sqlalchemy", "openai", "pypdf", "python-docx", "python-pptx", "openpyxl", "chromadb"]:
        try:
            found.append(f"{pkg} {md.version(pkg)}")
        except md.PackageNotFoundError:
            missing.append(pkg)
    if missing:
        raise RuntimeError("missing: " + ", ".join(missing))
    return "; ".join(found)


run("Required packages installed", check_packages, fix="python -m pip install -r requirements.txt")


# ------------------------------------------------------------------ 3. settings
def check_settings():
    from app.config import get_settings
    s = get_settings()
    key = s.openai_api_key.strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is empty in .env")
    if not key.startswith("sk-"):
        raise RuntimeError("OPENAI_API_KEY does not start with 'sk-'; check for quotes or spaces in .env")
    data = Path(s.data_dir).resolve()
    data.mkdir(parents=True, exist_ok=True)
    probe = data / ".write_test"
    probe.write_text("ok")
    probe.unlink()
    proxy = "yes" if (os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")) else "no"
    return (f"key set ({len(key)} chars), chat model {s.openai_chat_model}, embeddings {s.openai_embedding_model}, "
            f"vector store {s.vector_store}, data folder {data} (writable), proxy variable set: {proxy}")


run(".env settings", check_settings, timeout=30, fix="Open .env, set OPENAI_API_KEY=sk-... with no quotes, save")


# ------------------------------------------------------------------ 4. document reading
def check_parsing():
    from app.rag.chunking import chunk_sections
    from app.rag.parsing import parse_document
    sample = ROOT / "sample_docs" / "TBG_Design_Overview.docx"
    sections = parse_document(sample)
    chunks = chunk_sections(sections, sample.name)
    return f"{sample.name}: {len(sections)} sections, {len(chunks)} chunks"


run("Reading a Word document", check_parsing, timeout=60)


# ------------------------------------------------------------------ 5-6. OpenAI
def check_embeddings():
    from openai import OpenAI
    from app.config import get_settings
    s = get_settings()
    client = OpenAI(api_key=s.openai_api_key, timeout=30, max_retries=0)
    r = client.embeddings.create(model=s.openai_embedding_model, input=["TBG batch jobs"])
    return f"embedding of {len(r.data[0].embedding)} numbers received"


OPENAI_FIX = ("AuthenticationError = wrong key. RateLimitError/insufficient_quota = add billing credit at "
              "platform.openai.com. APIConnectionError or a hang = the network blocks api.openai.com; try another "
              "network (e.g. mobile hotspot) or ask IT to allow it. NotFoundError = model name not available.")
run("OpenAI embeddings", check_embeddings, timeout=60, fix=OPENAI_FIX)


def check_chat():
    from openai import OpenAI
    from app.config import get_settings
    s = get_settings()
    client = OpenAI(api_key=s.openai_api_key, timeout=30, max_retries=0)
    r = client.chat.completions.create(model=s.openai_chat_model, max_completion_tokens=5,
                                       messages=[{"role": "user", "content": "Reply with OK"}])
    return f"reply: {r.choices[0].message.content!r}"


run("OpenAI chat model", check_chat, timeout=60, fix=OPENAI_FIX)


# ------------------------------------------------------------------ 7. vector store
def check_store():
    from app.config import get_settings
    from app.rag.store import ChromaVectorStore, LocalVectorStore
    kind = get_settings().vector_store.strip().lower()
    tmp = tempfile.mkdtemp(prefix="kt_store_check_")
    if kind == "local":
        store = LocalVectorStore(str(Path(tmp) / "vectors.db"))
    else:
        store = ChromaVectorStore(tmp)
    store.upsert(["t:0"], [[0.1, 0.2, 0.3]], [{"app_id": "TBG", "doc_id": 0}], ["test"])
    hits = store.query("TBG", [0.1, 0.2, 0.3], 1)
    if not hits or hits[0][0] != "t:0":
        raise RuntimeError("store did not return the test vector")
    return f"{kind} store works (similarity {hits[0][1]:.2f})"


run("Vector store", check_store, timeout=180,
    fix="If Chroma fails or hangs, set VECTOR_STORE=local in .env (built-in store), restart the app and Re-index.")


# ------------------------------------------------------------------ 8. database
def check_database():
    from sqlalchemy import func, select
    from app.db import SessionLocal
    from app.models import Document
    with SessionLocal() as db:
        rows = db.execute(select(Document.status, func.count()).group_by(Document.status)).all()
    return "documents by status: " + (", ".join(f"{s}={n}" for s, n in rows) or "none yet")


run("Database", check_database, timeout=30, fix="python -m alembic upgrade head")

# ------------------------------------------------------------------ summary
print("\n" + "=" * 60)
failed = [r for r in results if not r[1]]
if failed:
    print(f"{len(failed)} check(s) failed:")
    for name, _, msg in failed:
        print(f"  - {name}: {msg}")
    print("\nFix the first failure above, then run: python check_setup.py again.")
else:
    print("All checks passed. Restart the app, then Re-index any Failed or stuck documents.")
print("=" * 60)
sys.stdout.flush()
os._exit(1 if failed else 0)  # exit even if a hanging check is still running
