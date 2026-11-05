"""손으로 쓴 뉴스 해석(scripts/news/<industry>_*.py의 NEWS·VAL)을 reviews.json·config/valuation.json에 반영한다.
URL은 자동 수집 파일(news.json)에서 같은 제목을 찾아 실제 링크로 채운다(못 찾으면 손으로 적은 링크 사용 안 함)."""
import json, os, re, sys, importlib
sys.path.insert(0, os.path.dirname(__file__))
ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
mod = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else "cosmetics_1105")
P = lambda *a: os.path.join(ROOT, *a)
auto = json.load(open(P("docs", "data", "news.json"), encoding="utf-8"))["companies"]
norm = lambda s: re.sub(r"\W", "", s)[:18]
rv = json.load(open(P("docs", "data", "reviews.json"), encoding="utf-8"))
miss = []
for code, items in mod.NEWS.items():
    pool = [n for v in auto.values() for n in v]
    out = []
    for d, src, title, url, imp, read, val in items:
        hit = next((n for n in pool if norm(n["title"]) == norm(title)), None) or \
              next((n for n in pool if norm(title)[:12] in norm(n["title"])), None)
        if hit:
            url = hit["url"]
        else:
            miss.append((code, title))
            url = ""
        out.append({"date": d, "src": src, "title": title, "url": url, "impact": imp, "read": read, "val": val})
    # 이전 해석은 남기고(같은 제목은 새 해석으로 교체) 최신순으로 해석 8개 + 링크만 있는 기사 4개까지 보관
    prev = [n for n in rv["companies"].get(code, {}).get("news", [])
            if not any(norm(n["title"]) == norm(o["title"]) for o in out)]
    allr = sorted(out + [n for n in prev if n.get("read")], key=lambda n: n["date"], reverse=True)[:8]
    plain = [n for n in prev if not n.get("read")][:4]
    rv["companies"].setdefault(code, {})["news"] = allr + plain
rv["news_asof"] = mod.ASOF
json.dump(rv, open(P("docs", "data", "reviews.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
cfg = json.load(open(P("config", "valuation.json"), encoding="utf-8"))
for code, ch in mod.VAL.items():
    a = cfg["companies"][code]
    if "E1" in ch: a["E1"] = ch["E1"]
    if "g" in ch: a["g"] = ch["g"]
    if "shares" in ch: a["snapshot"]["shares"] = ch["shares"]
    if ch.get("note+") and ch["note+"] not in a.get("note", ""):
        a["note"] = (a.get("note", "") + " · " + ch["note+"]).strip(" ·")
cfg["asof"] = mod.ASOF
json.dump(cfg, open(P("config", "valuation.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("반영:", len(mod.NEWS), "개사 / 링크 못 찾음:", miss)
