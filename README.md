# BrandLess (team CLARION)
Evidence-led brand review with human approval. Problem statement: Inkloom AI brand-governance platform.

## What it does
Approved sources (guidelines, terminology, facts, evidence, brand palette) -> draft review (text, PDF, DOCX, image) -> explained findings with the cited source -> creator accepts / disputes / rejects -> new tracked version (word diff) -> separate reviewer approves ONE version -> downloadable approval record -> insights on repeated and disputed rules.

## Checks
terminology, approved facts (conflicting sources escalate), promotional claims (not verifiable / check scope), brand-palette colours, missing alt text, colour contrast, non-descriptive link text, optional AI tone check (output verified against real guideline text).

## Run
    pip install -r requirements.txt
    uvicorn main:app --reload
Deploy (Render): build `pip install -r requirements.txt`, start `uvicorn main:app --host 0.0.0.0 --port $PORT`.
Optional env: ANTHROPIC_API_KEY (AI layer), MODEL.

## Responsible design
AI is optional and disclosed in the footer; emails and phone numbers are masked before any AI call; AI findings are dropped unless their quote exists in the source; no suggestion is applied automatically; self-approval is blocked; all actions are audit-logged.

## Known limitations
Demo users have no passwords; scanned PDFs / OCR not supported; image check uses dominant colours only; SQLite resets on free hosting restarts.

## Disclosure
Code written with AI assistance (Claude). Libraries: FastAPI, Uvicorn, pypdf, Pillow.
