# BrandLess (team CLARION)

**Keep the message. Check the promise.** A pre-publication brand-governance workspace: content is checked against approved guidelines, terms, facts, evidence and a brand palette; every finding is explained with the exact source it relies on; people (creator, manager, reviewer) decide.

- **Live demo:** https://brandless-clarion-hackathon.onrender.com (free host: the first load can take about 50 seconds)
- **Problem statement:** Inkloom AI brand-governance platform (We Code Coders, Codex 48)
- **Sign-in:** demo accounts are listed on the sign-in page (password `demo123`, fictional data only)

## Try it in two minutes
1. Sign in as `asha` (creator, NovaDesk workspace). New draft > **Load sample draft** > **Run review**.
2. Click **Apply suggestion to text** on the terminology and price findings, then **Dispute** the revenue claim (a reason is required).
3. **Save as new version and re-run review** (see "Changes since v1"), answer the remaining findings, **Submit for approval**.
4. Sign out, sign in as `rina` (reviewer), open the draft, add a note, **Approve this version**, then **Download approval record**.
5. Sign in as `manoj` (manager): **Sources** (add or import a guideline with **Load sample guideline** > **Analyse guideline**), **Insights**, **Evaluation** (30 labelled drafts).
6. Sign in as `acme_manager` to see a second, fully isolated workspace with different rules.

## Features
- **Access and isolation:** salted PBKDF2 passwords, server-side sessions, sign out, login throttling, creator/manager/reviewer roles checked on every endpoint, workspace isolation (other workspaces look like missing records).
- **Source library:** guidelines, preferred/banned terms, approved facts, evidence, brand palette; add, activate/deactivate (versioned), delete (blocked while cited by findings).
- **Guideline import:** upload PDF/DOCX/TXT; proposed rules with the source passage, warnings for vague, conflicting, duplicate or incomplete rules; nothing is active until a manager accepts it.
- **Review inputs:** pasted text, PDF, DOCX, PNG/JPG, TXT/MD with size and type checks.
- **Checks:** terminology, approved facts (conflicting sources are escalated, never guessed), promotional claims (`not verifiable` / `check scope`, never "proven false"), palette colours (text and uploaded images), missing alt text, colour contrast, non-descriptive link text, optional AI tone layer.
- **Evidence-support check:** each finding is tested against the cited passage (`verified` / `partial` / `unsupported`); unsupported findings are downgraded to suggestions and partial ones are marked NEEDS HUMAN CHECK (the reviewer must add a note to approve).
- **Human control:** apply suggestion (never automatic), accept / dispute / reject with reasons, unsaved edits preserved, immutable versions with word-level diff, submission blocked until every finding is answered, approval bound to one version, self-approval blocked, comments, downloadable approval record.
- **Insights and audit:** findings by rule, frequently disputed rules (possibly unclear guidelines), audit trail with JSON export.
- **Evaluation tab:** 30 labelled fictional drafts (10 clean, 10 seeded errors, 10 unsupported/ambiguous claims) with precision, recall, clean-draft false positives and the misses listed.
- **Robustness:** double-click protection, refresh restores tab and open draft, input limits, friendly errors, delete controls for drafts and sources.

## Run it locally
Requires Python 3.10-3.12.

```
git clone https://github.com/ananya662/brandless-clarion-hackathon.git
cd brandless-clarion-hackathon
pip install -r requirements.txt
uvicorn main:app --reload
```
Open http://127.0.0.1:8000. Data is stored in `brandless.db` (SQLite) unless `DATABASE_URL` is set.

| Variable | Purpose |
| `DATABASE_URL` | PostgreSQL connection string. If unset, or if the connection fails, the app uses SQLite. The page footer shows the active storage. |
| `ANTHROPIC_API_KEY` | Optional. Enables the AI tone layer (draft text with emails/phone numbers masked is sent to the Anthropic API). Off by default. |
| `MODEL` | Anthropic model name for the optional AI layer. |
| `DEMO_PASSWORD`, `SHOW_DEMO` | Demo accounts' password; set `SHOW_DEMO=0` to hide credentials on the sign-in page. |
| `DB` | SQLite file path (default `brandless.db`). |

## Deploy on Render
Web Service from this repo. Build: `pip install -r requirements.txt`. Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`. Optional: a Render PostgreSQL database and its Internal Database URL as `DATABASE_URL`; `PYTHON_VERSION=3.12.7`.

## Tests
```
pip install -r requirements-dev.txt
python -m pytest -q tests                     # 25 backend tests (SQLite)
DATABASE_URL=postgresql://user:pass@host/db python -m pytest -q tests   # same suite on PostgreSQL (empties the public schema)
```
UI tests (simulated browser, Node 18+): `npm install jsdom`, start the app with a throwaway database (`DB=ui_test.db uvicorn main:app --port 8011`), then `BASE=http://127.0.0.1:8011 node tests/ui_flow.js` (also `import_ui.js`, `eval_ui.js`, `polish_ui.js`, `login_ui.js`). Do not run them against a shared deployment: they create data.

## Architecture
```
Browser (single-page JS) > FastAPI (role + workspace checks) > extraction (pypdf, DOCX XML, Pillow)
  > exact checks + source retrieval (+ optional AI, masked, output-verified)
  > evidence-support check > findings > creator decisions > immutable versions > reviewer approval > audit
Storage: SQLite or PostgreSQL through one small adapter.
```
Everything is in `main.py` (API, rules engine, adapter and the embedded web interface) on purpose, so a judge can read and run it quickly.

## Security, privacy and accessibility
Passwords are salted PBKDF2-SHA256; session tokens are random and expire after 24 hours; all output is HTML-escaped; uploaded text is treated as data, never instructions; emails and phone numbers are masked before any AI call; AI use is disclosed in the page footer. Controls are native elements with text status labels (not colour alone). No formal accessibility audit has been done.

## Known limitations
- Demo accounts are public by design; use fictional data only. There is no self-registration, password reset or OAuth yet.
- Claim detection is keyword-based. The evaluation lists one real miss: paraphrased claims without trigger words ("Customers see twice the revenue").
- The evaluation set is small and written by the developer; it is a regression and reliability check, not real-world accuracy. No external user study was done.
- The AI tone layer is implemented but off in the live demo and was not tested with a live key.
- Scanned PDFs (OCR), logo and layout analysis are not supported; images are checked by dominant colours only.
- On Render's free tier the service sleeps when idle and the free PostgreSQL database expires after 30 days.

## Roadmap
**Next:** self-service workspace and user management, password reset and OAuth/SSO, email notifications for approvals, a formal WCAG audit, user testing with real content teams.
**Then:** semantic matching (embeddings or an LLM, with the same verification rule) for paraphrased claims, OCR for scanned documents, logo and layout checks, larger evaluation sets with external reviewers.
**Later:** CMS and design-tool integrations (browser extension, Google Docs, Figma), multilingual rules, on-premise deployment with local models.

## Disclosure
Built by one participant (Ananya, PSIT Kanpur) during the event windows. Code, tests and documents were written with AI assistance (Claude); every feature was run and tested before being listed. Libraries: FastAPI, Uvicorn, Pydantic, pypdf, Pillow, psycopg2; tests: pytest, httpx, jsdom.
