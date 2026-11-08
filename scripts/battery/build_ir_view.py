# scripts/battery/ir_view_*.py 의 IR(dict) → docs/battery/data/ir_view.json
import glob, importlib.util, json, os, datetime
IR, basis = {}, {}
for f in sorted(glob.glob(os.path.join(os.path.dirname(__file__), "ir_view_*.py"))):
    sp = importlib.util.spec_from_file_location(os.path.basename(f)[:-3], f); m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    IR.update(m.IR)
def S(t): return [{"date": a, "title": b, "url": c, "kind": d} for a, b, c, d in t]
out = {"updated": datetime.date.today().isoformat(), "companies": {}}
for code, v in IR.items():
    out["companies"][code] = {
        "basis": v.get("basis", ""), "tone": v.get("tone", "neu"), "verdict_label": v.get("label", "종합"), "verdict": v.get("verdict", ""),
        "summary": v.get("summary", ""),
        "strategy": [{"item": a, "target": b, "check": c, "grade": d} for a, b, c, d in v.get("strategy", [])],
        "changes": [{"topic": a, "before": b, "now": c, "read": d} for a, b, c, d in v.get("changes", [])],
        "cross": [{"who": a, "role": b, "says": c, "verdict": d} for a, b, c, d in v.get("cross", [])],
        "sources": S(v.get("sources", [])),
    }
p = os.path.join("docs", "battery", "data", "ir_view.json")
json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("ir_view.json", len(out["companies"]), "개사")
