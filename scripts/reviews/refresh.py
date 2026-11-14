"""'최근 4개 분기 리뷰'를 새 실적 발표에 맞춰 다시 쓴다 (7개 대시보드 공용).

python scripts/reviews/refresh.py --industry all            # 저장된 데이터로만 다시 쓰기
python scripts/reviews/refresh.py --industry all --fetch    # 네이버 분기 실적도 받아서 (GitHub Actions 매일 루틴)

동작
 1. 회사마다 가장 최근 발표 분기를 찾는다: DART(companies.json) > 네이버 분기 실적(raw/earnings) > 잠정실적 기사(news.json).
 2. 리뷰 원고가 그 분기를 아직 반영하지 않았으면
    - 손으로 쓴 원고(scripts/reviews/manual_*.py, basis가 그 분기 이상)가 있으면 그걸 쓰고
    - 없으면 숫자·동종업체 비교·기사 키워드로 실적 동향/평가/체크 포인트/다음 발표를 자동으로 다시 쓴다.
 3. 원래 원고는 r['_base']에 보관해 몇 번을 돌려도 결과가 같다(멱등). 업종별 build_reviews.py가 원고를
    새로 만들면 그걸 새 기준으로 삼는다.
"""
import glob, importlib, json, os, re, statistics, sys
import datetime as dt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import earnings as E  # noqa: E402

ROOT = E.ROOT
INDUSTRIES = ["cosmetics", "semi", "chem", "battery", "apparel", "food", "logistics"]
FIELDS = ("tone", "title", "trend", "eval", "watch", "next")
TODAY = dt.datetime.now(E.KST).date().isoformat()
QNAME = lambda q: f"{q[:4]}년 {q[-1]}분기"


def eok(v):
    v = round(v / 100)
    return f"{v/10000:,.1f}조" if abs(v) >= 10000 else f"{v:,}억"


def pct(a, b):
    if a is None or b is None or b == 0:
        return None
    if b < 0 or a < 0:
        return None
    return (a / b - 1) * 100


def fpct(x):
    return "-" if x is None else f"{x:+.0f}%"


def comp_dir(ind):
    return os.path.join(E.data_dir(ind), "companies.json")


# ---------------------------------------------------------------- 원고가 이미 그 분기를 다뤘나
STALE = re.compile(r"(예정|전망|예상|추정|컨센서스|발표 전|나올|발표돼요|공시돼요|공시되면)")


def mentions_actual(text, q):
    qn = int(q[-1])
    qp = rf"({qn}\s*분기|{qn}Q|Q{qn})"
    for s in re.split(r"(?<=[.요다])\s+", text or ""):
        if re.search(qp, s) and re.search(r"\d[\d,.]*\s*(억|조)|흑자|적자|[+\-−]\d+%", s) and not STALE.search(s):
            return True
    return False


def drop_stale(sents, q):
    """'3분기는 11/9~13 발표 예정' 같은 지난 예고 문장을 뺀다."""
    qn = int(q[-1])
    qp = re.compile(rf"({qn}\s*분기|{qn}Q|Q{qn}|{q})")
    return [s for s in sents if not (qp.search(s) and STALE.search(s))]


AUTO_TREND = re.compile(r"^(매출 성장률\(전년 같은 분기 대비\)|영업이익률은 20\d\dQ|최근 4개 분기 순이익 합계)")


# ---------------------------------------------------------------- 기사 키워드 → 사이클/경쟁력 단서
CYC = [("환율", r"환율|원화 강세|원·달러|달러 약세|엔화"), ("유가·원재료", r"유가|원재료|원가 부담|원료 가격|곡물|원당|원맥|카카오"),
       ("업황(가격·스프레드)", r"스프레드|정제마진|메모리 가격|D램 가격|낸드 가격|업황|다운사이클|업사이클|운임|SCFI|BDI|판가"),
       ("수요 둔화", r"수요 둔화|소비 위축|내수 부진|소비 침체|경기 둔화|재고 조정|고객사 재고"),
       ("계절·일회성", r"일회성|계절|비수기|성수기|성과급|충당금|소송|손상|기저 효과|기저효과"),
       ("관세·정책", r"관세|보조금|AMPC|규제|정책")]
CMP = [("점유율·경쟁", r"점유율|경쟁 심화|경쟁 격화|가격 경쟁|출혈"), ("판매 부진", r"판매 부진|역성장|매출 감소|부진한 판매"),
       ("신제품·브랜드", r"신제품|신규 브랜드|브랜드력|히트|인기|품귀"), ("수주·고객 확대", r"수주|신규 고객|고객사 확대|납품 확대|공급 계약|인증"),
       ("해외 확장", r"해외 매출|수출 비중|해외 비중|글로벌|미국 진출|유럽|일본|중국 진출|입점"), ("증설·생산능력", r"증설|생산능력|캐파|CAPA|신공장")]


def tags(items, since):
    txt = " ".join((n.get("title", "") + " " + (n.get("summary") or n.get("read") or "")) for n in items if (n.get("date") or "") >= since)
    return [k for k, p in CYC if re.search(p, txt)], [k for k, p in CMP if re.search(p, txt)]


# ---------------------------------------------------------------- 자동 원고
def auto_review(name, q, cur, prv, series, peers, nums, src, cyc, cmp, base, val_note):
    rev, op = cur.get("rev"), cur.get("op")
    ry = nums.get("rev_yoy") if nums.get("rev_yoy") is not None else pct(rev, prv.get("rev"))
    oy = nums.get("op_yoy") if nums.get("op_yoy") is not None else pct(op, prv.get("op"))
    if op is not None and prv.get("op") is not None and (op < 0 or prv["op"] < 0):
        oy = None
    turn = (nums.get("turn") if prv.get("op") is None else None) or ("흑자 전환" if (op or 0) > 0 and (prv.get("op") or 0) < 0 else
                                "적자 전환" if (op or 0) < 0 and (prv.get("op") or 0) > 0 else
                                "적자 지속" if (op or 0) < 0 and (prv.get("op") or 0) < 0 else None)
    cons = nums.get("cons")
    opm = op / rev * 100 if rev and op is not None else None
    # 제목·톤
    if turn == "흑자 전환":
        title, tone = f"{q[-1]}분기 영업이익 흑자 전환", "pos"
    elif turn in ("적자 전환", "적자 지속"):
        title, tone = f"{q[-1]}분기 영업{'적자 전환' if turn == '적자 전환' else '적자 지속'}", "neg"
    elif oy is not None and oy >= 30:
        title, tone = f"{q[-1]}분기 영업이익 {oy:+.0f}%로 고성장", "pos"
    elif oy is not None and oy >= 10:
        title, tone = f"{q[-1]}분기 영업이익 {oy:+.0f}%로 개선", "pos"
    elif oy is not None and oy > -10:
        title, tone = f"{q[-1]}분기 이익은 작년과 비슷({oy:+.0f}%)", "neu"
    elif oy is not None:
        title, tone = f"{q[-1]}분기 영업이익 {oy:+.0f}%로 부진", "neg"
    elif ry is not None:
        title, tone = f"{q[-1]}분기 매출 {ry:+.0f}%", "pos" if ry >= 10 else "neg" if ry <= -10 else "neu"
    else:
        title, tone = f"{q[-1]}분기 실적 발표", "neu"
    if cons:
        title += f", 시장 기대 {cons}"

    # 실적 동향
    parts = []
    if rev:
        parts.append(f"매출 {eok(rev)}원" + (f"({ry:+.0f}%)" if ry is not None else ""))
    if op is not None:
        parts.append(f"영업{'손실' if op < 0 else '이익'} {eok(abs(op))}원" + (f"({oy:+.0f}%)" if oy is not None else f"({turn})" if turn else ""))
    s1 = f"{QNAME(q)} {'잠정 ' if src.get('kind') != 'dart' else ''}실적은 " + ", ".join(parts) + (
        f"로 영업이익률 {opm:.1f}%를 기록했어요." if opm is not None and op >= 0 else "를 기록했어요.")
    if cons:
        s1 += f" 시장 기대치(컨센서스)를 {cons}했어요." if cons != "부합" else " 시장 기대치(컨센서스)에 부합했어요."
    if src.get("label"):
        s1 += f" <span class=\"sub\">({src['label']})</span>"
    trend = [s1]
    ks = sorted(series)[-4:]
    if len(ks) >= 3 and q in series:
        gs = [fpct(pct(series[k].get("rev"), (series.get(E.yoy_key(k)) or {}).get("rev"))) for k in ks]
        om = [(series[k].get("op") or 0) / series[k]["rev"] * 100 for k in ks if series[k].get("rev")]
        line = f"최근 4개 분기({ks[0]}~{ks[-1]}) 매출 성장률은 {' → '.join(gs)}"
        if len(om) == len(ks):
            line += f", 영업이익률은 {' → '.join(f'{x:.1f}%' for x in om)}"
        trend.append(line + "였어요.")
    # 원고의 손글씨 문장은 살리되, 지난 예고·Q2 기준 자동 숫자 문장은 뺀다
    keep = [t for t in drop_stale(base.get("trend") or [], q) if not AUTO_TREND.search(t)]
    trend += keep[:2]

    # 평가: 사이클 vs 경쟁력
    pm = peers.get("op_med")
    pr = peers.get("rev_med")
    grp = peers.get("group") or "같은 업종"
    J = []
    weak = tone == "neg"
    strong = tone == "pos"
    pn = peers.get("n", 0)
    if pn >= 3 and pm is not None:
        peer_txt = f"{grp} {pn}개사의 {q[-1]}분기 영업이익 증감률 중앙값은 {pm:+.0f}%(매출 {fpct(pr)})예요."
    else:
        peer_txt = ""
    if weak:
        if pm is not None and pn >= 3 and pm <= -5:
            J.append(f"이익이 줄었지만 {peer_txt} 동종 업체도 함께 약해, 회사 고유의 경쟁력 문제보다 업황·사이클 영향이 큰 구간으로 봐요.")
        elif ry is not None and ry >= 0:
            J.append(f"매출은 {ry:+.0f}%로 지켰는데 이익이 줄어, 판매 경쟁력보다는 원가·판관비·믹스(비용) 쪽 문제예요. {peer_txt + ' ' if peer_txt else ''}"
                     "비용이 일회성인지(사이클), 가격 경쟁·마케팅비 증가처럼 계속되는 것인지(경쟁력)는 다음 분기 이익률로 판별해요.")
        elif pm is not None and pn >= 3 and pm > 0:
            J.append(f"{peer_txt} 동종 업체는 이익이 늘었는데 이 회사는 매출과 이익이 함께 줄어, 경쟁력(점유율·제품력) 약화 신호로 보고 점검해야 해요.")
        else:
            J.append(f"매출과 이익이 함께 줄었어요. {peer_txt + ' ' if peer_txt else ''}비교 대상이 적어 사이클인지 경쟁력 문제인지 단정하기 어렵고, 다음 분기 회복 여부로 판단해요.")
    elif strong:
        if pm is not None and pn >= 3 and pm >= 10:
            rel = ""
            if oy is not None and oy >= pm + 20:
                rel = f" 이 회사는 {oy:+.0f}%로 동종 중앙값보다 크게 앞서, 업황 위에 회사 고유의 경쟁력(제품·고객·점유율) 몫이 더해졌어요."
            elif oy is not None and oy <= pm - 20:
                rel = f" 이 회사는 {oy:+.0f}%로 동종 중앙값에 못 미쳐, 업황 순풍을 덜 받았거나 비용·제품 믹스에서 뒤처졌어요. 상대적으로는 경쟁력 점검이 필요해요."
            elif oy is not None:
                rel = f" 이 회사({oy:+.0f}%)는 동종과 비슷한 속도라 개선의 대부분을 업황 덕분으로 봐요."
            J.append(f"{peer_txt} 업종 전체가 함께 좋아진 구간이라 이번 개선에는 업황(사이클) 순풍이 크게 섞여 있어요.{rel}")
        elif pm is not None and pn >= 3:
            J.append(f"{peer_txt} 동종 업체보다 확실히 좋은 실적이라 업황보다는 회사 고유의 경쟁력(제품·고객·채널) 덕분으로 봐요.")
        else:
            J.append("이익이 늘어난 분기예요. 일회성 이익이 섞였는지, 다음 분기에도 이어지는지를 확인해야 해요.")
    else:
        J.append(f"이익은 작년과 큰 차이가 없어요. {peer_txt}".strip())
    if cyc or cmp:
        J.append("최근 기사에서 보이는 요인은 " + ", ".join([f"{k}(사이클·외부)" for k in cyc[:3]] + [f"{k}(회사 고유)" for k in cmp[:3]]) + "이에요.")
    J.append(val_note)
    be = " ".join(drop_stale(re.split(r"(?<=[.요])\s+", base.get("eval") or ""), q)).strip()
    if be:
        J.append(f"<br><span class=\"sub\">이전 분석({base.get('_asof', '')} 작성, {q} 발표 전 기준)</span> {be}")
    ev = " ".join(x for x in J if x)

    watch = list(drop_stale(base.get("watch") or [], q))
    if weak:
        watch.insert(0, "4분기에도 이익 감소가 이어지는지(사이클이면 업종과 함께 회복, 경쟁력 문제면 혼자 부진)")
    elif strong:
        watch.insert(0, "4분기에도 같은 이익률을 유지하는지(일회성·업황 순풍 여부)")
    return {"tone": tone, "title": title, "trend": trend, "eval": ev, "watch": watch[:4], "next": E.next_release(q)}


# ---------------------------------------------------------------- 업종 단위 실행
def load_manual(ind):
    out = {}
    for p in sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), f"manual_{ind}*.py"))):
        mod = importlib.import_module(os.path.basename(p)[:-3])
        out.update(getattr(mod, "REV", {}))
    return out


def clean_q(Q):
    return {k: {f: v.get(f) for f in ("rev", "op", "ni")} for k, v in (Q or {}).items() if v.get("rev")}


def refresh(ind, fetch=False):
    dd = E.data_dir(ind)
    rp = os.path.join(dd, "reviews.json")
    rv = E.load(rp)
    cj = E.load(comp_dir(ind), {"companies": []})
    if not rv:
        return
    cos = {c["code"]: c for c in cj.get("companies", [])}
    if fetch:
        live = E.fetch_naver(ind, [c for c in rv["companies"] if re.fullmatch(r"\d{6}|\d{5}[A-Z]", c)])
    else:
        live = E.load(os.path.join(ROOT, "raw", "earnings", f"{ind}.json"), {"companies": {}})
    news = (E.load(os.path.join(dd, "news.json"), {}) or {}).get("companies", {})
    manual = load_manual(ind)
    target = E.expected_quarter()
    allnames = [c.get("name", "") for c in cos.values()]

    # 1) 회사별 최신 분기 숫자
    info = {}
    for code, r in rv["companies"].items():
        co = cos.get(code, {})
        names = [co.get("name") or ""] + [k for k in (co.get("news_kw") or []) if len(k) >= 3]
        names = [n for n in names if n]
        series = clean_q(co.get("quarterly"))
        src = {}
        if series:
            src = {"kind": "dart", "label": "DART 분기 확정치"}
        lv = (live.get("companies") or {}).get(code) or {}
        for k, v in lv.items():
            if k not in series and v.get("rev"):
                series[k] = v
                src = {"kind": "naver", "label": f"네이버 금융 분기 실적 {live.get('fetched', '')[:10]}"}
        own = [dict(n, office=n.get("src"), own=True) for n in r.get("news") or []]
        evs = E.news_events((news.get(code) or []) + own, names, allnames)
        last = max(series) if series else None
        nums, srcs = {}, []
        if evs:
            eq = evs[0]["q"]
            if eq >= target:
                nums, srcs = E.merge_event(evs, eq)
                if not last or eq > last:
                    prv = series.get(E.yoy_key(eq), {})
                    rec = {}
                    # 기사 숫자가 별도·부문 기준이라 DART 연결 숫자와 범위가 다르면(직전 분기 대비 ±40% 넘게 차이) 증감률만 쓴다
                    pq = series.get(E.prev_q(eq)) or {}
                    scope = bool(nums.get("rev") and pq.get("rev") and not 0.6 < nums["rev"] / pq["rev"] < 1.6)
                    for f in ("rev", "op", "ni"):
                        if nums.get(f) is not None and not scope:
                            rec[f] = nums[f]
                        elif nums.get(f + "_yoy") is not None and prv.get(f) and prv[f] > 0:
                            rec[f] = prv[f] * (1 + nums[f + "_yoy"] / 100)
                    if scope:
                        nums = {k: v for k, v in nums.items() if k not in ("rev", "op", "ni")}
                    if rec.get("rev") or rec.get("op") is not None:
                        series[eq] = rec
                        last = eq
                        e0 = srcs[-1]
                        lk = f"<a href=\"{e0['url']}\" target=\"_blank\" rel=\"noopener\">{e0['src'] or '기사'} {e0['date'][5:]}</a>" if e0.get("url") else f"{e0['src']} {e0['date'][5:]}"
                        src = {"kind": "news", "label": f"잠정실적 기사: {lk}" + (" · 기사 숫자는 집계 범위가 달라 증감률만 DART 연결 기준에 적용" if scope else "")}
        info[code] = {"series": series, "last": last, "src": src, "nums": nums, "group": co.get("group") or "",
                      "name": co.get("name") or code, "names": names}

    # 2) 동종(그룹) 비교 통계
    def yo(i, f):
        s, q = i["series"], i["last"]
        if not q:
            return None
        if i["src"].get("kind") == "news" and i["nums"].get(f + "_yoy") is not None:
            return i["nums"][f + "_yoy"]
        return pct((s.get(q) or {}).get(f), (s.get(E.yoy_key(q)) or {}).get(f))
    grp = {}
    for code, i in info.items():
        if i["last"] and i["last"] >= target:
            grp.setdefault(i["group"], []).append(code)
    allc = [c for v in grp.values() for c in v]

    def peer_stats(code):
        g = info[code]["group"]
        pool = [c for c in grp.get(g, []) if c != code]
        label = g
        if len(pool) < 3:
            pool, label = [c for c in allc if c != code], "같은 대시보드"
        ops = [x for x in (yo(info[c], "op") for c in pool) if x is not None]
        rs = [x for x in (yo(info[c], "rev") for c in pool) if x is not None]
        return {"group": label, "n": len(ops), "op_med": statistics.median(ops) if ops else None,
                "rev_med": statistics.median(rs) if rs else None}

    # 3) 원고 다시 쓰기
    n_auto = n_manual = n_keep = n_wait = 0
    for code, r in rv["companies"].items():
        i = info[code]
        # 원래 원고 복원(이전 자동 결과면 _base 로 되돌림)
        a = r.get("_auto") or {}
        if r.get("_base") and all(r.get(f) == a.get(f) for f in FIELDS if f in a):
            base = dict(r["_base"])
        else:
            base = {f: r.get(f) for f in FIELDS}
            base["_asof"] = r.get("asof") or rv.get("updated", "")
        q = i["last"]
        m = manual.get(code)
        out = None
        if m and m.get("basis", "") >= (q or ""):
            out = {f: m[f] for f in FIELDS if f in m}
            out.setdefault("next", E.next_release(m["basis"]))
            r["basis"] = m["basis"]
            r["asof"] = m.get("asof", TODAY)
            r["how"] = "manual"
            n_manual += 1
        elif q and q >= target:
            # 업종별 build_reviews.py가 숫자로 만든 문장('…2026Q3 매출은 …')은 해석이 아니라서 빼고 본다
            btxt = " ".join([base.get("title") or ""] + [t for t in base.get("trend") or [] if not AUTO_TREND.search(t)] + [base.get("eval") or ""])
            if mentions_actual(btxt, q):
                # 원고가 이미 이 분기 실적을 다뤘으면 문장은 두고, 지난 예고만 정리
                out = {f: base.get(f) for f in FIELDS}
                out["trend"] = drop_stale(base.get("trend") or [], q)
                out["watch"] = drop_stale(base.get("watch") or [], q)
                out["next"] = E.next_release(q)
                r["how"] = "kept"
                n_keep += 1
            else:
                cur = i["series"].get(q, {})
                prv = i["series"].get(E.yoy_key(q), {})
                items = [n for n in (news.get(code) or []) + (r.get("news") or [])
                         if E.EARN.search(n.get("title", "")) and any(x in n.get("title", "") for x in i["names"] or [""])]
                cyc, cmp = tags(items, (dt.date.fromisoformat(TODAY) - dt.timedelta(days=45)).isoformat())
                vn = ("적정주가는 한 분기 숫자가 아니라 업황 사이클 평균의 정상화 이익으로 계산해서, 이번 실적만으로 바꾸지 않았어요. "
                      "같은 방향의 실적이 한 분기 더 이어지면 정상화 이익 가정을 다시 봐요.")
                out = auto_review(i["name"], q, cur, prv, i["series"], peer_stats(code), i["nums"], i["src"], cyc, cmp, base, vn)
                r["how"] = "auto"
                n_auto += 1
            r["basis"] = q
            r["asof"] = TODAY
        else:
            # 아직 이번 분기 숫자를 못 찾음: 지난 예고 문장만 정리
            out = {f: base.get(f) for f in FIELDS}
            nx = base.get("next") or ""
            if re.search(r"예정|전후|발표돼요|공시돼요|공시되면", nx) or not nx:
                out["next"] = (f"{QNAME(target)} 실적 숫자를 아직 확인하지 못했어요(분기보고서 마감 11월 14일). "
                               "잠정실적·분기보고서가 나오면 매일 루틴이 이 리뷰를 자동으로 다시 써요.")
            r["how"] = "waiting"
            n_wait += 1
        r["_base"] = base
        r["_auto"] = {f: out.get(f) for f in FIELDS}
        r.update({f: out.get(f) for f in FIELDS})
        if r.get("how") == "auto":
            r["note"] = f"{QNAME(q)} 실적 발표 후 자동으로 다시 쓴 리뷰예요({TODAY}). 동종 비교·기사 키워드로 판단했고, 손으로 쓴 해석은 아래 '이전 분석'과 뉴스 해석에 있어요."
        elif r.get("how") == "manual":
            r["note"] = ""
        else:
            r.pop("note", None)
    rv["updated"] = TODAY
    rv["period"] = f"최근 4개 분기 실적 + {TODAY}까지 발표된 {QNAME(target)} 실적(잠정실적·분기보고서)과 뉴스"
    rv["refresh"] = {"run": dt.datetime.now(E.KST).strftime("%Y-%m-%d %H:%M"), "target": target,
                     "manual": n_manual, "auto": n_auto, "kept": n_keep, "waiting": n_wait}
    with open(rp, "w", encoding="utf-8") as f:
        json.dump(rv, f, ensure_ascii=False, indent=1)
    print(f"[{ind}] 리뷰 갱신: 손글씨 {n_manual} · 자동 {n_auto} · 원고 유지 {n_keep} · 대기 {n_wait}")


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    ind = argv[argv.index("--industry") + 1] if "--industry" in argv else "all"
    fetch = "--fetch" in argv
    for i in (INDUSTRIES if ind == "all" else [ind]):
        try:
            refresh(i, fetch)
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            print(f"[{i}] 리뷰 갱신 실패: {e}")


if __name__ == "__main__":
    main()
