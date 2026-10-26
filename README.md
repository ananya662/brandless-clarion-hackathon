# BrandLess (team CLARION)

Run locally:

    pip install -r requirements.txt
    uvicorn main:app --reload

Deploy (Render): Build `pip install -r requirements.txt`, Start `uvicorn main:app --host 0.0.0.0 --port $PORT`.
Optional env: ANTHROPIC_API_KEY (enables AI tone layer), MODEL.

Demo users (no passwords; demo only): asha=creator, manoj=manager, rina=reviewer.
AI assistance was used to draft this code; disclosed per event rules.
