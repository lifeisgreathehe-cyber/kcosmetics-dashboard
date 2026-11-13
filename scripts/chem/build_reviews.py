"""화학·정유 회사별 리뷰(reviews_src.py, 있으면) + 분기 실적 추세(companies.json) → docs/chem/data/reviews.json"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
try:
    from reviews_src import R, NEXT  # 회사별 해석 원고 (DART 수집 후 작성)
except ImportError:
    R, NEXT = {}, "3분기 보고서는 11월 14일 전후 공시돼요."
NEW = {}

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


def clean(Q):
    """비어 있는 항목(None)은 0으로 두고, 매출이 없는 분기는 뺀다."""
    return {k: {f: (v.get(f) or 0) for f in ("rev", "op", "ni")} for k, v in Q.items() if v.get("rev")}


def eok(v):
    v = round(v / 100)
    return f"{v/10000:,.1f}조" if abs(v) >= 10000 else f"{v:,}억"


def trend(co):
    Q = clean(co["quarterly"])
    ks = sorted(Q)[-4:]
    out, gs = [], []
    for k in ks:
        prev = f"{int(k[:4])-1}{k[4:]}"
        p = Q.get(prev, {}).get("rev")
        gs.append(f"{(Q[k]['rev']/p-1)*100:+.0f}%" if p else "-")
    out.append(f"매출 성장률(전년 같은 분기 대비)이 {' → '.join(gs)}였고, {ks[-1]} 매출은 {eok(Q[ks[-1]]['rev'])}원이었어요.")
    om = [Q[k]["op"] / Q[k]["rev"] * 100 for k in ks if Q[k]["rev"]]
    out.append(f"영업이익률은 {ks[0]} {om[0]:.1f}%에서 {ks[-1]} {om[-1]:.1f}%로 {'올랐어요' if om[-1] > om[0] + 0.5 else '내려왔어요' if om[-1] < om[0] - 0.5 else '비슷했어요'}.")
    ni = sum(Q[k]["ni"] for k in ks)
    out.append(f"최근 4개 분기 순이익 합계는 {eok(ni)}원이에요." if ni > 0 else f"최근 4개 분기 순이익 합계는 {eok(-ni)}원 적자예요.")
    return out


def auto(co):
    """해석 원고가 아직 없는 회사: 숫자만으로 만든 자동 리뷰."""
    Q = clean(co["quarterly"])
    ks = sorted(Q)[-4:]
    last = Q[ks[-1]]
    prev = Q.get(f"{int(ks[-1][:4])-1}{ks[-1][4:]}", {})
    g = (last["rev"] / prev["rev"] - 1) * 100 if prev.get("rev") else 0
    om = last["op"] / last["rev"] * 100 if last["rev"] else 0
    om0 = Q[ks[0]]["op"] / Q[ks[0]]["rev"] * 100 if Q[ks[0]]["rev"] else 0
    tone = "pos" if g > 5 and om >= om0 else "neg" if g < -5 and om < om0 or last["op"] < 0 else "neu"
    title = f"{ks[-1]} 매출 {g:+.0f}%, 영업이익률 {om:.1f}%" if last["rev"] else "실적 확인 중"
    return dict(tone=tone, title=title, auto=True,
                eval="아직 회사별 해석을 쓰지 않았어요. DART 실적 숫자만 자동으로 정리했어요.",
                watch=[], news=[], next=NEXT, mix_title="", mix=[],
                points=["사업보고서 핵심 내용은 다음 업데이트 때 정리할게요. 위 원문 링크에서 바로 볼 수 있어요."])


def main():
    cos = {c["code"]: c for c in json.load(open(os.path.join(ROOT, "docs/chem/data/companies.json")))["companies"]}
    import datetime
    out = {"updated": datetime.date.today().isoformat(),
           "period": "DART 확정 실적(2026년 2분기까지) + 2026-11-13까지 나온 3분기 잠정실적과 뉴스",
           "disclaimer": "공시 수치와 언론 보도를 바탕으로 정리한 참고용 해석이며 투자 권유가 아닙니다.",
           "companies": {}}
    deep = (json.load(open(os.path.join(ROOT, "docs/chem/data/deep.json"))).get("companies") or {})
    for code, co in cos.items():
        if len(clean(co.get("quarterly") or {})) < 4:
            continue
        r = R.get(code) or (dict(NEW[code]["review"], next=NEXT) if code in NEW else auto(co))
        r = dict(r, next=r.get("next") or NEXT)
        dp_ = deep.get(code) or {}
        ev = r["eval"]
        last_q = sorted(clean(co["quarterly"]))[-1]
        if r.get("basis") and last_q > r["basis"]:
            # 새 분기 확정 실적이 들어왔는데 해석은 이전 분기 기준: 숫자는 위 추세에 이미 반영, 해석 갱신 예정임을 알림
            ev = f"※ {last_q} 확정 실적이 새로 들어왔어요. 위 실적 동향 숫자는 {last_q} 기준이고, 아래 해석은 {r['basis']} 실적과 잠정실적 기사를 기준으로 쓴 것이라 곧 다시 써요. " + ev
        if (r.get("auto") or not r.get("points")) and dp_.get("explain"):
            # 사업 핵심: 심층분석 제품 해설(사람이 쓴 원고)의 항목별 첫 문장
            r["points"] = [f"{sec['h']} — {re.split(r'(?<=요\.)\s', sec['p'])[0]}"
                           for sec in dp_["explain"].get("sections", [])[:4]]
            r["mix_title"] = dp_["explain"].get("title", "")
        news = r.get("news") or []
        if not news and dp_.get("news"):
            news = [(n["date"], n["title"], n["url"], n.get("read", ""), n.get("impact", "")) for n in dp_["news"][:4]]
        dp = os.path.join(ROOT, f"raw/chem/dart_docs/{code}.json")
        docs = json.load(open(dp)) if os.path.exists(dp) else {}
        reps = docs.get("reports") or []
        rep = next((x for x in reps if "반기" in x["report_nm"]), None) or (reps[0] if reps else {})
        out["companies"][code] = {
            "tone": r["tone"], "title": r["title"],
            "trend": trend(co) + r.get("extra", []),
            "eval": ev, "watch": r["watch"], "basis": r.get("basis"),
            "news": [dict(zip(("date", "title", "url", "read", "impact"), n)) for n in news],
            "next": r["next"],
            "biz": {"report": rep.get("report_nm", ""), "url": rep.get("url", ""),
                    "mix_title": r.get("mix_title", ""),
                    "mix": [{"label": l, "pct": p} for l, p in r.get("mix", [])],
                    "points": r["points"]},
        }
    with open(os.path.join(ROOT, "docs/chem/data/reviews.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("reviews.json", len(out["companies"]))


if __name__ == "__main__":
    main()
