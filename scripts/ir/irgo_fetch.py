"""IRGO(m.irgo.co.kr) 회사별 IR 자료 목록을 받아 raw/<업종>/irgo/<코드>.html로 저장한다(GitHub Actions에서 실행).
1단계: HTML 저장만. 링크 구조 확인 후 PDF 다운로드를 붙인다."""
import json, os, sys, time, argparse, urllib.request
ap = argparse.ArgumentParser(); ap.add_argument("--industry", default=""); ap.add_argument("--codes", default="")
a = ap.parse_args()
cfg = f"config/{a.industry}/companies.json" if a.industry else "config/companies.json"
cj = json.load(open(cfg, encoding="utf-8")); L = cj if isinstance(cj, list) else cj.get("companies", cj)
codes = a.codes.split(",") if a.codes else [c["code"] for c in L]
out = f"raw/{a.industry}/irgo" if a.industry else "raw/irgo"; os.makedirs(out, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"}
for c in codes:
    for host in ("https://m.irgo.co.kr/IR-COMP/", "https://www.irgo.co.kr/IR-COMP/"):
        try:
            h = urllib.request.urlopen(urllib.request.Request(host + c, headers=UA), timeout=30).read()
            open(f"{out}/{c}{'' if 'm.' in host else '_www'}.html", "wb").write(h); print(c, host, len(h))
        except Exception as e:
            print(c, host, "ERR", e)
        time.sleep(1)
