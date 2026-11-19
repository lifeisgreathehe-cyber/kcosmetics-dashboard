"""철강 대시보드 첫 실적 시드 (2026-11-14, 한 번만 실행)

DART는 해외 IP를 막아 클라우드에서 못 받는다. 그래서 같은 사용자의 공개 저장소
'실적 랭킹'(lifeisgreathehe-cyber/earnings-dashboard, data/co/<코드>.json — DART 연결재무 기준)에 있는
26개사의 10년 연간·최근 분기·TTM을 우리 형식(백만원)으로 옮겨 둔다. 2차전지 대시보드의 TCC스틸은 그대로 복사.
국내 PC에서 `python scripts\\update.py --industry steel --only dart`를 돌리면 전부 DART 원자료로 바뀐다.

사용: python scripts/steel/seed_ed.py <earnings-dashboard co json 폴더>
"""
import json, os, sys, glob, datetime
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
src = sys.argv[1]
cfg = json.load(open(os.path.join(ROOT, "config/steel/companies.json"), encoding="utf-8"))
bat = {c["code"]: c for c in json.load(open(os.path.join(ROOT, "docs/battery/data/companies.json"), encoding="utf-8"))["companies"]}
m = lambda v: None if v is None else round(v * 100)  # 억원 → 백만원
out = []
for c in cfg:
    rec = {k: c[k] for k in ("code", "name", "group", "market")}
    p = os.path.join(src, c["code"] + ".json")
    if c["code"] in bat:
        b = bat[c["code"]]
        rec.update({k: b[k] for k in ("annual", "quarterly", "bs", "shares", "source") if k in b})
    elif os.path.exists(p) and open(p, encoding="utf-8").read(1) == "{":
        d = json.load(open(p, encoding="utf-8"))
        A = {str(a["year"]): {"rev": m(a["sales"]), "gp": m(a.get("gp")), "op": m(a["op"]), "ni": m(a["ni_ctrl"])}
             for a in d["annual"] if a.get("sales")}
        Q = {q["q"]: {"rev": m(q["sales"]), "gp": m(q.get("gp")), "op": m(q["op"]), "ni": m(q["ni_ctrl"])}
             for q in d["quarters"] if q.get("sales") is not None}
        # TTM 차이로 이전 분기 되살리기: q[t-4] = q[t] − (TTM[t] − TTM[t-1])
        T = {t["q"]: t for t in d.get("ttm", [])}
        tk = sorted(T)
        prevq = lambda q: f"{int(q[:4]) - (q[-1] == '1')}Q{4 if q[-1] == '1' else int(q[-1]) - 1}"
        back = lambda q: f"{int(q[:4]) - 1}Q{q[-1]}"
        for _ in range(8):
            for t in sorted(tk, reverse=True):
                pq, bq = prevq(t), back(t)
                if t in Q and pq in T and bq not in Q:
                    Q[bq] = {f: (None if Q[t].get(f) is None or T[t].get(g) is None or T[pq].get(g) is None
                                 else round(Q[t][f] - (T[t][g] - T[pq][g]) * 100))
                             for f, g in (("rev", "sales"), ("op", "op"), ("ni", "ni_ctrl"))}
                    Q[bq]["gp"] = None
        # 연간 합계와 맞지 않는 되살린 분기는 버림(연결 범위 변경 등)
        for y in {k[:4] for k in Q}:
            ks = [f"{y}Q{i}" for i in range(1, 5)]
            if all(k in Q for k in ks) and y in A and A[y]["rev"]:
                s = sum(Q[k]["rev"] or 0 for k in ks)
                if abs(s / A[y]["rev"] - 1) > 0.03:
                    for k in ks[:-1]:
                        if k < min(q["q"] for q in d["quarters"]):
                            Q.pop(k, None)
        Q = {k: v for k, v in Q.items() if v.get("rev")}
        mt = d.get("metrics") or {}
        eq = next((a.get("equity_ctrl") for a in reversed(d["annual"]) if a.get("equity_ctrl")), None)
        nc = mt.get("net_cash")
        rec.update(annual=dict(sorted(A.items())), quarterly=dict(sorted(Q.items())),
                   bs={"period": mt.get("last_q") or "", "equity": m(eq), "cash": m(max(nc or 0, 0)), "st_fin": 0, "debt": m(max(-(nc or 0), 0))} if eq else {},
                   shares={"period": d.get("asof"), "common": round(d["mcap"] * 1e8 / d["px"])} if d.get("mcap") and d.get("px") else {},
                   source="earnings-dashboard")
    else:
        rec.update(annual={}, quarterly={}, source="pending")
    out.append(rec)
json.dump({"updated": datetime.date.today().isoformat(), "companies": out},
          open(os.path.join(ROOT, "docs/steel/data/companies.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("seeded", sum(1 for r in out if r.get("annual")), "of", len(out))
