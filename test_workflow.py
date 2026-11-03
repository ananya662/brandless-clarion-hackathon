"""Regression tests for the suggestion/revision workflow. Run: pytest -q tests"""
import base64, json, os, shutil, subprocess, sys, textwrap
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi.testclient import TestClient
import main

A, M, R = {"X-Token": ""}, {"X-Token": ""}, {"X-Token": ""}
DRAFT1 = "NovaDesk starts at INR 299/month and guarantees 2x revenue in 7 days."


@pytest.fixture()
def c(tmp_path):
    main.DB = str(tmp_path / "t.db")
    if main.PG:  # real PostgreSQL run: start every test from an empty schema
        main.q("DROP SCHEMA public CASCADE", w=True); main.q("CREATE SCHEMA public", w=True)
    with TestClient(main.app) as cl:
        for h, u in ((A, "asha"), (M, "manoj"), (R, "rina")):
            h["X-Token"] = cl.post("/api/login", json={"username": u, "password": "demo123"}).json()["token"]
        yield cl


def new(c, text):
    return c.post("/api/contents", json={"title": "t", "text": text}, headers=A).json()["vid"]


def det(c, vid, h=A):
    return c.get(f"/api/versions/{vid}", headers=h).json()


def rules(d): return [(f["rule"], f["state"]) for f in d["findings"]]


def test_corrected_price_clears_mismatch_but_guarantee_remains(c):
    v1 = new(c, DRAFT1)
    assert ("fact", "contradicted") in rules(det(c, v1))
    v2 = c.post(f"/api/versions/{v1}/revise", json={"text": DRAFT1.replace("INR 299", "INR 499")}, headers=A).json()["vid"]
    d2 = det(c, v2)
    assert "INR 499/month" in d2["version"]["text"] and "INR 299" not in d2["version"]["text"]
    assert not [f for f in d2["findings"] if f["rule"] == "fact"]
    assert ("claim", "not_verifiable") in rules(d2)


def test_review_runs_on_exactly_the_saved_text(c):
    v1 = new(c, DRAFT1)
    text = "Pricing: INR 499/month. Contact sales."
    v2 = c.post(f"/api/versions/{v1}/revise", json={"text": text}, headers=A).json()["vid"]
    d = det(c, v2)
    assert d["version"]["text"] == text and d["findings"] == []


def test_removing_or_supporting_the_guarantee_clears_not_verifiable(c):
    v1 = new(c, DRAFT1)
    v2 = c.post(f"/api/versions/{v1}/revise", json={"text": "NovaDesk starts at INR 499/month."}, headers=A).json()["vid"]
    assert not [f for f in det(c, v2)["findings"] if f["rule"] == "claim"]
    c.post("/api/sources", json={"kind": "evidence", "title": "Guarantee terms", "body": "Approved guarantee terms for annual plans."}, headers=M)
    v3 = c.post(f"/api/versions/{v2}/revise", json={"text": "NovaDesk guarantees uptime at INR 499/month."}, headers=A).json()["vid"]
    claims = [f for f in det(c, v3)["findings"] if f["rule"] == "claim"]
    assert claims and all(f["state"] == "scope_check" for f in claims)  # supported by approved evidence, scope to be checked


def test_history_and_previous_findings_remain_accessible(c):
    v1 = new(c, DRAFT1)
    v2 = c.post(f"/api/versions/{v1}/revise", json={"text": DRAFT1.replace("INR 299", "INR 499")}, headers=A).json()["vid"]
    d2 = det(c, v2)
    assert [h["n"] for h in d2["history"]] == [1, 2] and d2["latest"] is True
    d1 = det(c, v1)
    assert d1["latest"] is False and "INR 299" in d1["version"]["text"] and ("fact", "contradicted") in rules(d1)
    assert c.get(f"/api/versions/{v2}/diff", headers=A).json()["ops"]


def test_stale_and_unchanged_saves_are_rejected(c):
    v1 = new(c, DRAFT1)
    assert c.post(f"/api/versions/{v1}/revise", json={"text": DRAFT1}, headers=A).status_code == 400  # unchanged
    v2 = c.post(f"/api/versions/{v1}/revise", json={"text": "NovaDesk at INR 499/month."}, headers=A).json()["vid"]
    assert c.post(f"/api/versions/{v1}/revise", json={"text": "other"}, headers=A).status_code == 409  # stale base
    fid = det(c, v1)["findings"][0]["id"]
    assert c.post(f"/api/findings/{fid}/decide", json={"decision": "accept"}, headers=A).status_code == 409
    assert c.post(f"/api/versions/{v1}/submit", headers=A).status_code == 409
    assert det(c, v2)["latest"] is True


def test_duplicate_terminology_grouped_but_separate_terms_kept(c):
    v = new(c, "Meet Nova Desk! Nova Desk is great. Also try Nova-Desk.")
    term = [f for f in det(c, v)["findings"] if f["rule"] == "terminology"]
    by = {f["span"]: f["occurrences"] for f in term}
    assert by == {"Nova Desk": 2, "Nova-Desk": 1}  # one card per distinct wording, occurrences counted, none hidden
    assert sum(by.values()) == 3


def test_evaluation_reports_30_labelled_drafts_honestly(c):
    e = c.get("/api/eval", headers=A).json()
    assert e["total"] == 30 and e["groups"] == {"clean": 10, "seeded error": 10, "unsupported/ambiguous claim": 10}
    assert e["clean_false_positives"] == 0 and e["precision"] == 1.0 and e["recall"] >= 0.95
    assert [x["text"] for x in e["cases"] if not x["ok"]] == ["Customers see twice the revenue."]   # documented limitation: paraphrased claim
    assert e["support_checked"] == e["support_correct"] == 4


def test_claim_matcher_handles_percent_and_best_practices(c):
    assert ("claim", "not_verifiable") in rules(det(c, new(c, "100% satisfaction, no questions asked.")))
    assert not rules(det(c, new(c, "Read our best practices guide.")))


def test_standard_findings_carry_verified_support(c):
    d = det(c, new(c, DRAFT1))
    by = {f["rule"]: f for f in d["findings"]}
    assert by["fact"]["support"] == "verified" and "499" in by["fact"]["support_note"]
    assert by["claim"]["support"] == "n/a" and not by["claim"]["needs_review"]


def test_unsupported_citation_is_downgraded_and_routed_to_a_human(c):
    c.post("/api/sources", json={"kind": "fact", "title": "Seat price", "body": "Pricing is under review.", "pattern": r"(?:USD)\s?([\d,]+)", "value": "20"}, headers=M)
    f = next(x for x in det(c, new(c, "Seats cost USD 30 each."))["findings"] if x["rule"] == "fact")
    assert f["support"] == "unsupported" and f["needs_review"] == 1
    assert f["state"] == "suggestion" and f["message"].startswith("Unverified")     # never shown as a violation


def test_partial_support_requires_a_reviewer_note(c):
    v = new(c, "Every customer will double revenue in 90 days.")
    f = det(c, v)["findings"][0]
    assert (f["state"], f["support"], f["needs_review"]) == ("scope_check", "partial", 1)
    c.post(f"/api/findings/{f['id']}/decide", json={"decision": "accept"}, headers=A)
    assert c.post(f"/api/versions/{v}/submit", headers=A).status_code == 200
    r = c.post(f"/api/versions/{v}/approve", json={"approve": True}, headers=R)
    assert r.status_code == 400 and "NEEDS HUMAN CHECK" in r.json()["detail"]
    assert c.post(f"/api/versions/{v}/approve", json={"approve": True, "note": "Checked the case study scope"}, headers=R).status_code == 200


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_apply_replacement_function_in_browser_code():
    line = next(l for l in main.HTML.splitlines() if l.startswith("function applyAll"))
    script = line + textwrap.dedent("""
        const t=(a,b,c,d)=>{const r=applyAll(a,b,c); if(r!==d){console.log('FAIL',JSON.stringify([a,r,d]));process.exit(1)}};
        t('at INR 299/month','INR 299','INR 499','at INR 499/month');
        t('INR 299 and INR 299','INR 299','INR 499','INR 499 and INR 499');
        t('INR 2990 stays','INR 299','INR 499','INR 2990 stays');
        t('Nova Desk, Nova Desk','Nova Desk','NovaDesk','NovaDesk, NovaDesk');
        t('a Nova Desks','Nova Desk','NovaDesk','a Nova Desks');
        t('price $1 here','price $1','cost $&','cost $& here');
        console.log('OK');""")
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert out.stdout.strip() == "OK", out.stdout + out.stderr


def test_evidence_dispute_and_human_approval_preserved(c):
    v1 = new(c, DRAFT1)
    d = det(c, v1)
    fact = next(f for f in d["findings"] if f["rule"] == "fact")
    assert fact["source_id"] and "499" in fact["quote"]                      # evidence-backed finding
    for f in d["findings"]:
        body = {"decision": "dispute", "reason": "see case study"} if f["rule"] == "claim" else {"decision": "accept"}
        assert c.post(f"/api/findings/{f['id']}/decide", json=body, headers=A).status_code == 200
    assert c.post(f"/api/findings/{fact['id']}/decide", json={"decision": "reject"}, headers=A).status_code == 400  # reason required
    assert c.post(f"/api/versions/{v1}/submit", headers=A).status_code == 200
    assert c.post(f"/api/versions/{v1}/approve", json={"approve": True, "note": "x"}, headers=A).status_code == 403   # no self-approval
    assert c.post(f"/api/versions/{v1}/approve", json={"approve": True}, headers=R).status_code == 400               # disputes need a note
    assert c.post(f"/api/versions/{v1}/approve", json={"approve": True, "note": "narrow evidence reviewed"}, headers=R).status_code == 200
    v2 = c.post(f"/api/versions/{v1}/revise", json={"text": "NovaDesk at INR 499/month."}, headers=A).json()["vid"]
    assert det(c, v2)["version"]["status"] == "draft" and det(c, v1)["version"]["status"] == "approved"  # approval is version-bound


def test_cannot_submit_with_unanswered_findings(c):
    v1 = new(c, DRAFT1)
    r = c.post(f"/api/versions/{v1}/submit", headers=A)
    assert r.status_code == 400 and "Respond to" in r.json()["detail"]
    assert det(c, v1)["version"]["status"] == "draft"          # not stuck in review
    for f in det(c, v1)["findings"]:
        c.post(f"/api/findings/{f['id']}/decide", json={"decision": "accept"}, headers=A)
    assert c.post(f"/api/versions/{v1}/submit", headers=A).status_code == 200


def test_auth_required_and_roles_enforced(c):
    assert c.get("/api/sources").status_code == 401
    assert c.get("/api/sources", headers={"X-Token": "bogus"}).status_code == 401
    assert c.post("/api/login", json={"username": "asha", "password": "wrong"}).status_code == 401
    assert c.post("/api/sources", json={"kind": "term", "title": "x", "body": "y", "value": "z"}, headers=A).status_code == 403
    assert c.post("/api/sources", json={"kind": "term", "title": "x", "body": "y", "value": "z"}, headers=M).status_code == 200
    assert c.get("/api/info").json()["demo"]  # demo credentials are published for judges


def test_login_throttle_and_logout(c):
    for _ in range(8): assert c.post("/api/login", json={"username": "rina", "password": "bad"}).status_code == 401
    assert c.post("/api/login", json={"username": "rina", "password": "demo123"}).status_code == 429
    c.post("/api/logout", headers=A)
    assert c.get("/api/me", headers=A).status_code == 401


def test_delete_controls_and_audit_export(c):
    v = new(c, DRAFT1); d = det(c, v); cid = d["version"]["content_id"]
    cited = d["findings"][0]["source_id"]
    assert c.delete(f"/api/sources/{cited}", headers=M).status_code == 409            # cited sources are protected
    sid = c.post("/api/sources", json={"kind": "evidence", "title": "e", "body": "b"}, headers=M).json()["id"]
    assert c.delete(f"/api/sources/{sid}", headers=A).status_code == 403
    assert c.delete(f"/api/sources/{sid}", headers=M).status_code == 200
    assert c.delete(f"/api/contents/{cid}", headers=R).status_code == 403            # not the author
    assert c.get("/api/audit/export", headers=A).status_code == 403
    assert c.delete(f"/api/contents/{cid}", headers=A).status_code == 200
    assert c.get(f"/api/versions/{v}", headers=A).status_code == 404
    assert "content_deleted" in [e["action"] for e in c.get("/api/audit/export", headers=M).json()["events"]]


GUIDE = """Brand voice: Use "NovaDesk" instead of "Nova Desk". Never use "Novadesk".
The starting price is INR 599 per month. Annual plans are INR 499 per month.
Our colours are #1F2A44, #2F6FED and #FFFFFF.
Always keep a professional and friendly tone.
You must not promise guaranteed results."""


def props(c): return c.get("/api/proposals", headers=M).json()


def test_guideline_import_proposes_flags_and_needs_manager_confirmation(c):
    assert c.post("/api/import", json={"text": GUIDE}, headers=A).status_code == 403
    assert c.post("/api/import", json={"text": "   "}, headers=M).status_code == 400
    before = len(c.get("/api/sources", headers=M).json())
    assert c.post("/api/import", json={"name": "guide.txt", "text": GUIDE}, headers=M).json()["created"] >= 6
    assert len(c.get("/api/sources", headers=M).json()) == before            # nothing is active until accepted
    p = props(c); kinds = [x["kind"] for x in p]
    assert kinds.count("term") == 2 and kinds.count("fact") == 2 and "asset" in kinds
    assert all(x["passage"] for x in p)                                         # every proposal cites its source passage
    bare = next(x for x in p if x["kind"] == "term" and not x["title"]); assert "preferred" in bare["flag"].lower()
    assert all("different INR amounts" in x["flag"] for x in p if x["kind"] == "fact")
    vague = next(x for x in p if x["kind"] == "guideline" and "professional" in x["body"]); assert "Vague" in vague["flag"]
    assert not next(x for x in p if x["kind"] == "guideline" and "guaranteed" in x["body"])["flag"]


def test_accepting_proposals_changes_reviews_and_validates_edits(c):
    c.post("/api/import", json={"name": "guide.txt", "text": GUIDE}, headers=M)
    p = props(c); bare = next(x for x in p if x["kind"] == "term" and not x["title"])
    assert c.post(f"/api/proposals/{bare['id']}/accept", json={"title": "", "body": bare["body"], "value": bare["value"]}, headers=M).status_code == 400
    assert c.post(f"/api/proposals/{bare['id']}/accept", json={"title": "NovaDesk", "body": bare["body"], "value": "Novadesk"}, headers=M).status_code == 200
    assert c.post(f"/api/proposals/{bare['id']}/accept", json={"title": "NovaDesk", "body": "x", "value": "y"}, headers=M).status_code == 409   # already handled
    v = new(c, "Try Novadesk today")
    assert ("terminology", "contradicted") in rules(det(c, v))
    fact = next(x for x in p if x["kind"] == "fact" and x["value"] == "599")
    assert c.post(f"/api/proposals/{fact['id']}/accept", json={"title": fact["title"], "body": fact["body"], "pattern": "(", "value": "599"}, headers=M).status_code == 400  # bad regex
    assert c.post(f"/api/proposals/{fact['id']}/accept", json={"title": fact["title"], "body": fact["body"], "pattern": fact["pattern"], "value": "599"}, headers=M).status_code == 200
    v2 = new(c, "Plans from INR 499 per month")
    assert ("fact", "conflict") in rules(det(c, v2))                            # two active sources disagree -> escalated, not guessed
    other = next(x for x in props(c) if x["kind"] == "fact")
    assert c.post(f"/api/proposals/{other['id']}/reject", headers=M).status_code == 200
    assert other["id"] not in [x["id"] for x in props(c)]


def test_accept_clean_only_activates_unflagged_complete_rules(c):
    c.post("/api/import", json={"name": "guide.txt", "text": GUIDE}, headers=M)
    n = c.post("/api/proposals/accept-clean", headers=M).json()["accepted"]
    assert n == 2                                                                # palette + the unflagged 'guaranteed' guideline
    left = props(c)
    assert left and all(x["flag"] for x in left)
    assert any(x["kind"] == "term" and x["title"] == "NovaDesk" and "already exists" in x["flag"] for x in left)  # duplicate stays for a human
    srcs = c.get("/api/sources", headers=M).json()
    assert any(s["origin"] == "guide.txt" and s["passage"] for s in srcs)       # provenance kept


def test_import_pattern_matches_seeded_price_pattern(c):
    seeded = next(s for s in c.get("/api/sources", headers=M).json() if s["kind"] == "fact")["pattern"]
    assert main.INR_PAT == seeded


def acme(c, u):
    return {"X-Token": c.post("/api/login", json={"username": u, "password": "demo123"}).json()["token"]}


def test_workspaces_are_isolated(c):
    AM, AC = acme(c, "acme_manager"), acme(c, "acme_creator")
    v = new(c, DRAFT1); d = det(c, v); cid = d["version"]["content_id"]; fid = d["findings"][0]["id"]; cited = d["findings"][0]["source_id"]
    c.post("/api/import", json={"name": "g.txt", "text": GUIDE}, headers=M)
    assert c.get("/api/contents", headers=AM).json() == [] and c.get("/api/contents", headers=AC).json() == []
    srcs = c.get("/api/sources", headers=AM).json()
    assert srcs and all(s["ws"] == 2 for s in srcs) and not any(s["title"] == "NovaDesk" for s in srcs)
    for r in (c.get(f"/api/versions/{v}", headers=AC), c.get(f"/api/versions/{v}/diff", headers=AC), c.get(f"/api/versions/{v}/record", headers=AC),
              c.post(f"/api/versions/{v}/comment", json={"text": "x"}, headers=AC), c.post(f"/api/versions/{v}/submit", headers=AC),
              c.post(f"/api/versions/{v}/revise", json={"text": "other"}, headers=AC), c.post(f"/api/findings/{fid}/decide", json={"decision": "accept"}, headers=AC),
              c.post(f"/api/sources/{cited}/toggle", headers=AM), c.delete(f"/api/sources/{cited}", headers=AM), c.delete(f"/api/contents/{cid}", headers=AM)):
        assert r.status_code == 404                                              # looks exactly like a missing record
    assert c.get("/api/proposals", headers=AM).json() == [] and props(c)
    pid = props(c)[0]["id"]
    assert c.post(f"/api/proposals/{pid}/accept", json={"title": "x", "body": "y", "value": "z"}, headers=AM).status_code == 404
    assert c.post(f"/api/proposals/{pid}/reject", headers=AM).status_code == 404
    assert c.post("/api/proposals/accept-clean", headers=AM).json()["accepted"] == 0
    assert c.get("/api/insights", headers=AM).json()["by_rule"] == []
    assert all(e["who"].startswith("acme") for e in c.get("/api/audit/export", headers=AM).json()["events"])
    assert any(e["who"] == "asha" for e in c.get("/api/audit/export", headers=M).json()["events"])


def test_each_workspace_applies_its_own_rules(c):
    AC = acme(c, "acme_creator"); text = "Try Zefyr at INR 499/month. Meet Nova Desk."
    ac = {(f["rule"], f["span"]) for f in det(c, c.post("/api/contents", json={"title": "t", "text": text}, headers=AC).json()["vid"], AC)["findings"]}
    nv = {(f["rule"], f["span"]) for f in det(c, new(c, text))["findings"]}
    assert ("terminology", "Zefyr") in ac and ("fact", "INR 499") in ac and ("terminology", "Nova Desk") not in ac
    assert ("terminology", "Nova Desk") in nv and ("terminology", "Zefyr") not in nv and not any(r == "fact" for r, _ in nv)
    assert c.get("/api/eval", headers=AC).json()["correct"] == c.get("/api/eval", headers=A).json()["correct"]   # evaluation is workspace-independent


def test_login_lists_both_demo_workspaces_and_me_reports_workspace(c):
    info = c.get("/api/info").json()
    assert {d["workspace"] for d in info["demo"]} == {"NovaDesk demo workspace", "Acme Studio demo workspace"} and info["db"] in ("sqlite", "postgresql")
    assert c.get("/api/me", headers=acme(c, "acme_manager")).json()["workspace"] == "Acme Studio demo workspace"


def test_input_limits_and_file_type_checks(c):
    assert c.post("/api/contents", json={"title": "t", "text": "x" * 50001}, headers=A).status_code == 400
    assert c.post("/api/contents", json={"title": "t" * 121, "text": "ok"}, headers=A).status_code == 400
    assert c.post("/api/contents", json={"title": "t", "text": "   "}, headers=A).status_code == 400
    v = new(c, "short draft")
    assert c.post(f"/api/versions/{v}/revise", json={"text": "y" * 50001}, headers=A).status_code == 400
    ex = lambda name, data="aGk=": c.post("/api/extract", json={"name": name, "data": data}, headers=A)
    assert ex("virus.exe").status_code == 400 and ex("notes.txt").status_code == 200
    assert ex("broken.pdf").status_code == 400 and ex("big.txt", "A" * 14_000_001).status_code == 413
    assert ex("empty.txt", "").status_code == 400                                  # nothing to extract
