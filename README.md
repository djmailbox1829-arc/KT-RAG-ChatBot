# KT Knowledge Assistant — Phase 3

Knowledge-transfer chatbot for new joiners on **TBG** (Third Party Billing Generation), **MOD** (CBs Modernization),
**eBill** (Electronic Billing System) and **Premium Billing** (Premium Billing System).

| Phase | What it adds | Status |
| --- | --- | --- |
| 1 | Admin sign-in, user access by email, email one-time-code sign-in, app picker | Done |
| 2 | Guardrails: PHI, sensitive topics, prompt injection and off-topic questions blocked before OpenAI | Done |
| 3 | Documents → answers: upload, PHI scan, hybrid search (Chroma + keywords), OpenAI answers with sources | **This version** |
| 4 | Multi-application polish and per-app tuning | Next |
| 5 | Images and flowcharts | Later |
| 6 | Evaluation, caching, dashboards | Later |

## Upgrading from Phase 2

Stop the server (Ctrl+C), copy these files over your project folder (keep `.env`, `kt_rag.db` and `.venv`), then:

```powershell
cd "F:\GenAI Program\KT-RAG-ChatBot"
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt      # adds OpenAI, Chroma and document readers (a few minutes)
python -m alembic upgrade head                 # adds the documents, chunks and chat tables
python -m uvicorn app.main:app --reload --port 8001
```

In `.env`, make sure `OPENAI_API_KEY=` has your key. The other new settings are optional (see `.env.example`).

## Try it with the sample documents

The `sample_docs` folder has **fictional** documents written for testing (not real system documentation):

| File | Application | Shows |
| --- | --- | --- |
| TBG_Design_Overview.docx | TBG | Headings, bullet lists and tables (batch jobs, data model, interfaces) |
| TBG_Production_Runbook.pdf | TBG | PDF with page numbers in the sources |
| TBG_Escalation_Contacts.md | TBG | **Contains a phone number and email on purpose**: it is quarantined, then you can redact and index it |
| MOD_Target_Architecture.pptx | MOD | Slides, a table on a slide and speaker notes |
| eBill_User_Guide.md | eBill | Markdown headings |
| Premium_Billing_Business_Rules.xlsx | Premium Billing | Two sheets of rules and batch jobs |

1. Admin → **Documents**: choose the application, select the matching file(s), **Upload and process**. The page refreshes
   until each file shows **Ready**.
2. Make sure your test user has access to those applications (Admin → Users).
3. As the user, open an application and ask, for example:
   - TBG: *Which batch job generates the invoices and when does it run?* · *What is stored in TBG_ERR_LOG?* ·
     *What is the restart order when a job fails?*
   - MOD: *What are the waves of the data migration?* · *How does eBill integrate with MOD?*
   - eBill: *What happens when the notification email fails?* · then the follow-up *and after the third failure?*
   - Premium Billing: *What is the grace period for APTC members?* · *How are retro terminations billed?*
   - Something the documents don't cover, e.g. TBG: *What is the TBG disaster recovery plan?* → "not found",
     and it appears under Admin → **Insights → Unanswered questions**.
4. Click a source to open the original document (PDFs open at the cited page).

## How a question is answered

1. **Guardrails** (Phase 2) on this server. Blocked questions stop here: not stored, not sent to OpenAI.
2. **Follow-ups** ("and after that?") are rewritten into a full question using the last 3 answers.
3. **Hybrid search, only in the selected application's documents**: meaning-based search in Chroma (OpenAI embeddings)
   plus keyword search (exact table, job and error names), merged by rank.
4. **Confidence gate**: if nothing in the documents is close enough (`MIN_RELEVANCE`), the user gets "not found" and
   **OpenAI is not asked**, so it can't make something up.
5. **Answer** from the 5 best excerpts only, with numbered citations. Temperature 0.1.
6. **Output checks**: personal data in the answer is replaced with [REDACTED]; citations must point at real excerpts;
   an answer without any valid citation is replaced with "not found".

Documents are scanned for personal data **before** anything is sent to OpenAI. A file with possible PHI is
**quarantined**: the admin sees which kinds of data were found and where (never the values), and chooses
**Redact and index** or **Delete**.

## If documents stay on Processing or show Failed

1. The Documents page shows the current step under each file (for example "creating embeddings with OpenAI").
   A file still processing after 10 minutes is marked **Stuck at: …** and can be re-indexed or deleted.
2. Run the setup check (with `.venv` active, in a second terminal):
   ```powershell
   python check_setup.py
   ```
   It tests Python, packages, `.env`, document reading, OpenAI and the vector store one by one and says what to fix.
3. If the **Vector store** check fails or hangs, set `VECTOR_STORE=local` in `.env` (built-in store, no extra
   packages), restart the app and click **Re-index** on each file.
4. Click inside the server terminal and press **Enter** if it looks frozen: on Windows, selecting text there pauses
   the app.

## Admin pages

| Page | What it does |
| --- | --- |
| Users | Grant, edit, revoke access by email and application |
| Documents | Upload, status (Ready, Processing, Quarantined, Failed), re-index, redact and index, delete, download |
| Insights | Questions asked, % answered, unanswered questions, answers marked not helpful with comments |
| Guardrails | Block counts, recent blocks, test box, your own rules |
| Audit log | Logins, access changes, uploads, deletions, rule changes |

## Tuning

| Setting (`.env`) | Default | When to change |
| --- | --- | --- |
| `OPENAI_CHAT_MODEL` | gpt-4o-mini | Use a stronger model (e.g. gpt-4o) if answers are too shallow |
| `MIN_RELEVANCE` | 0.30 | Lower (0.25) if good questions get "not found"; raise (0.35) if weak matches get answered |
| `CONTEXT_CHUNKS` | 5 | More excerpts for broad questions (costs more per answer) |
| `CHUNK_TOKENS` | 600 | Re-index after changing |
| `RERANKER` | none | `cross-encoder` for better ranking (needs `pip install sentence-transformers`, large download) |
| `CHAT_RETENTION_DAYS` | 90 | How long questions and answers are kept |

Uploaded files and the Chroma vector store live in `DATA_DIR` (default `.\data`). Back it up together with `kt_rag.db`.

## Requirements

- **Python 3.11** only
- An OpenAI API key with access to the chat and embedding models
- SQLite (built in). PostgreSQL works too: set `DATABASE_URL` and run `alembic upgrade head`.

## First-time setup (new machine)

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env      # then set SECRET_KEY, ADMIN_PASSWORD and OPENAI_API_KEY
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --port 8001
```

- Admin: http://127.0.0.1:8001/admin/login · Users: http://127.0.0.1:8001/login
- With `EMAIL_MODE=console` the sign-in code is printed in the terminal. For real emails see `.env.example` (Gmail app password).
- Always activate `.venv` first (the prompt shows `(.venv)`).

## Tests

```powershell
python -m pytest
```

Tests use a fake model and an in-memory store: they make **no OpenAI calls** and cost nothing.

## Project layout

```
app/
  main.py              start-up, security headers, error pages
  config.py            settings from .env
  db.py, models.py     database and tables
  security.py          passwords, one-time codes, CSRF, email checks
  guardrails/          PHI detection, topic and injection rules, engine, admin rules
  rag/                 parsing, chunking, keyword search, vector store, retrieval, prompts, citations,
                       answer pipeline (pure Python) and service.py (database + OpenAI)
  routers/admin.py     users, guardrails, audit, account
  routers/documents.py documents and insights
  routers/user.py      sign-in, app picker, chat, chat API, feedback, source downloads
  templates/, static/
migrations/            database migrations (run: python -m alembic upgrade head)
sample_docs/           fictional test documents
tests/                 pytest suite
```
