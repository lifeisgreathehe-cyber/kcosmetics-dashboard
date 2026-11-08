"""손으로 쓴 IR 해석(scripts/ir/<업종>_ir_*.py 의 IR dict)을 docs/<업종>/data/ir_analysis.json으로 합친다.
IR = {code: {"asof","sources":[...],"summary","strategy":[{h,claim,feas(높음|보통|낮음),why}],
             "changes":[{h,before,now,read}],"cross":[{claim,src,verdict(일치|부분 일치|불일치|확인 불가),read}],"val"}}
사용: python3 scripts/ir/build_ir.py [--industry X]"""
import json, os, sys, glob, importlib, argparse
ap = argparse.ArgumentParser(); ap.add_argument("--industry", default=""); a = ap.parse_args()
pre = (a.industry or "cosmetics") + "_ir_"
sys.path.insert(0, os.path.dirname(__file__))
out = {}
for f in sorted(glob.glob(os.path.join(os.path.dirname(__file__), pre + "*.py"))):
    out.update(importlib.import_module(os.path.basename(f)[:-3]).IR)
FE, VE = {"높음", "보통", "낮음"}, {"일치", "부분 일치", "불일치", "확인 불가"}
for c, x in out.items():
    for s in x.get("strategy", []): assert s["feas"] in FE, (c, s["h"])
    for s in x.get("cross", []): assert s["verdict"] in VE, (c, s["claim"])
dst = f"docs/{a.industry}/data/ir_analysis.json" if a.industry else "docs/data/ir_analysis.json"
updated = max([x.get("asof", "") for x in out.values()] or [""])
json.dump({"source": "회사 IR 자료(IRGO·KIND 원문) 해석, 손으로 작성", "updated": updated, "companies": out},
          open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(dst, len(out), "개사")
