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


def test_eval_suite_still_passes(c):
    e = c.get("/api/eval", headers=A).json()
    assert e["correct"] == len(e["cases"]) and e["precision"] == 1.0 and e["recall"] == 1.0


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
