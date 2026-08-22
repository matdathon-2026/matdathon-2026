"""End-to-end golden path verification against a running server.

Usage:
    .\.venv\Scripts\python.exe spike\verify_goldenpath.py [base_url]
"""
import json
import sys
import time
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
FAIL = []


def call(method, path, body=None, timeout=180):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, method=method,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw[:600]


def step(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + ((" | " + detail) if detail else ""))
    if not ok:
        FAIL.append(name)


print("=== DidimHeart golden path @ %s ===" % BASE)

s, r = call("GET", "/status/ai")
step("status/ai", s == 200 and r.get("auth") == "configured", json.dumps(r, ensure_ascii=False))

s, sess = call("POST", "/api/v1/demo-sessions", {})
sid = sess.get("id") or sess.get("sessionId")
step("create demo session", s == 200 and bool(sid), str(sid))

profile = {
    "ageBand": "18_24",
    "region": "seoul",
    "selfRelianceStage": "within_1_year",
    "interests": ["housing", "finance"],
    "workStudyStatus": "job_seeking",
    "urgentNeed": "housing",
}
s, r = call("PUT", "/api/v1/demo-sessions/%s/profile" % sid, profile)
step("save profile", s == 200, json.dumps(r, ensure_ascii=False)[:160])

t0 = time.time()
s, rec = call("POST", "/api/v1/recommendations", {"sessionId": sid})
elapsed = time.time() - t0
recs = rec.get("recommendations", []) if isinstance(rec, dict) else []
step("recommendations (AI)", s == 200 and len(recs) >= 1,
     "%d recs in %.1fs" % (len(recs), elapsed))
if s != 200:
    print("    BODY:", json.dumps(rec, ensure_ascii=False)[:500])

for x in recs:
    has_src = bool(x.get("sourceUrl")) and bool(x.get("verifiedAt"))
    step("  rec %s has source+verifiedAt" % x.get("benefitId"), has_src,
         "fit=%s next=%s" % (x.get("fit"), str(x.get("nextAction"))[:50]))

if not recs:
    print("\n=== ABORTED: no recommendations ===")
    sys.exit(1)

bid = recs[0]["benefitId"]

s, draft = call("POST", "/api/v1/plans/draft", {"sessionId": sid, "benefitId": bid})
steps = draft.get("steps", []) if isinstance(draft, dict) else []
step("plan draft (AI)", s == 200 and len(steps) >= 1, "%d steps" % len(steps))
if s != 200:
    print("    BODY:", json.dumps(draft, ensure_ascii=False)[:500])
    sys.exit(1)

save_body = {
    "sessionId": sid,
    "benefitId": bid,
    "title": draft.get("title") or "plan",
    "deadline": draft.get("deadline"),
    "requiredDocuments": draft.get("requiredDocuments", []),
    "steps": [
        {
            "id": st.get("id") or ("step-%d" % i),
            "title": st.get("title", "step"),
            "description": st.get("description", ""),
            "estimatedMinutes": st.get("estimatedMinutes") or 10,
            "order": st.get("order") if st.get("order") is not None else i,
        }
        for i, st in enumerate(steps[:10])
    ],
    "uncertainties": draft.get("uncertainties", []),
    "sourceUrl": draft.get("sourceUrl", ""),
    "applyUrl": draft.get("applyUrl", ""),
}
s, plan = call("POST", "/api/v1/plans", save_body)
pid = plan.get("id") or plan.get("planId") if isinstance(plan, dict) else None
step("save plan", s == 200 and bool(pid), str(pid))
if not pid:
    print("    BODY:", json.dumps(plan, ensure_ascii=False)[:500])
    sys.exit(1)

step_id = save_body["steps"][0]["id"]
path = "/api/v1/plans/%s/steps/%s/complete" % (pid, step_id)
s1, c1 = call("POST", path, {"sessionId": sid})
s2, c2 = call("POST", path, {"sessionId": sid})
step("complete step", s1 == 200, json.dumps(c1, ensure_ascii=False)[:160])

s, led = call("GET", "/api/v1/hearts/ledger?sessionId=%s" % sid)
if s == 422:
    step("  ledger accepts camelCase sessionId", False, "API inconsistency: requires snake_case session_id")
    s, led = call("GET", "/api/v1/hearts/ledger?session_id=%s" % sid)
entries = led.get("entries", led.get("transactions", [])) if isinstance(led, dict) else []
earns = [e for e in entries if e.get("type") in ("earn", "EARN")]
bal = led.get("balance") if isinstance(led, dict) else None
step("hearts ledger", s == 200 and len(earns) == 1,
     "earn entries=%d balance=%s (idempotency: 2 completes -> 1 earn)" % (len(earns), bal))

s, imp = call("GET", "/api/v1/impact")
step("sponsor impact", s == 200, json.dumps(imp, ensure_ascii=False)[:200])

print("\n=== RESULT: %s ===" % ("ALL PASS" if not FAIL else "%d FAILED -> %s" % (len(FAIL), FAIL)))
sys.exit(1 if FAIL else 0)
