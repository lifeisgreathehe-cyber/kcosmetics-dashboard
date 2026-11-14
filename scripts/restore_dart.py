#!/usr/bin/env python3
"""PC에서 받은 DART 데이터를 백업 폴더에서 되살린다.

git이 꼬여서(merge 중단 등) 저장소를 최신 main으로 되돌려야 할 때, 미리 복사해 둔
docs\\ 와 raw\\ 폴더(백업)에서 DART 실적·사업보고서만 골라 다시 넣고
PER·적정주가·리뷰를 다시 계산한다. 다른 파일(뉴스·리뷰 해석 등)은 최신 main 그대로 둔다.

사용법:  python scripts\\restore_dart.py C:\\Users\\ceter\\Desktop\\dart_backup
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDUSTRIES = ["cosmetics", "semi", "chem", "battery", "apparel", "food", "logistics", "auto", "steel"]


def paths(base: Path, ind: str):
    if ind == "cosmetics":
        return base / "docs" / "data", base / "raw"
    return base / "docs" / ind / "data", base / "raw" / ind


def load(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except Exception:  # noqa: BLE001
        return None


def last_q(c):
    q = c.get("quarterly") or {}
    return max(q) if q else ""


def merge_companies(cur: dict, bak: dict) -> int:
    """회사별로 백업 쪽 DART 실적이 더 최신이거나 현재에 없으면 백업 값을 쓴다."""
    bmap = {c["code"]: c for c in bak.get("companies", [])}
    n = 0
    out = []
    for c in cur.get("companies", []):
        b = bmap.get(c["code"])
        if b and b.get("source") == "dart" and b.get("quarterly") and (
                c.get("source") != "dart" or not c.get("quarterly")
                or last_q(b) > last_q(c) or len(b["quarterly"]) > len(c["quarterly"])):
            # 설정 쪽 필드(이름·그룹 등)는 최신 main 값을 유지하고 실적만 바꾼다
            nc = {**c}
            for k in ("annual", "quarterly", "bs", "shares", "source", "fin_ccy_converted"):
                if k in b:
                    nc[k] = b[k]
            out.append(nc)
            n += 1
        else:
            out.append(c)
    cur["companies"] = out
    if n and bak.get("updated", "") > cur.get("updated", ""):
        cur["updated"] = bak["updated"]
    return n


def run_module(path: Path, *args):
    spec = importlib.util.spec_from_file_location(f"m_{abs(hash(str(path)))}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(mod)
        mod.main(*args)
    finally:
        sys.path.remove(str(path.parent))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    backup = Path(sys.argv[1])
    if not backup.exists():
        print("백업 폴더가 없어요:", backup)
        return 1
    changed = []
    for ind in INDUSTRIES:
        cur_data, cur_raw = paths(ROOT, ind)
        bak_data, bak_raw = paths(backup, ind)
        cur, bak = load(cur_data / "companies.json"), load(bak_data / "companies.json")
        n = merge_companies(cur, bak) if cur and bak else 0
        if n:
            (cur_data / "companies.json").write_text(json.dumps(cur, ensure_ascii=False, indent=0), "utf-8")
        docs = 0
        if (bak_raw / "dart_docs").exists():
            (cur_raw / "dart_docs").mkdir(parents=True, exist_ok=True)
            for f in (bak_raw / "dart_docs").glob("*.json"):
                t = cur_raw / "dart_docs" / f.name
                old, new = load(t) or {}, load(f) or {}
                if new.get("reports") and new.get("fetched", "") >= old.get("fetched", "") and new != old:
                    shutil.copyfile(f, t)
                    docs += 1
        print(f"[{ind}] 실적 되살림 {n}개사, 사업보고서 {docs}개")
        if n or docs:
            changed.append(ind)
    for ind in changed:
        try:
            run_module(ROOT / "scripts" / "build_valuation.py", ind)
        except Exception as e:  # noqa: BLE001
            print(f"[{ind}] 밸류에이션 계산 실패:", e)
        rv = ROOT / "scripts" / ind / "build_reviews.py"
        if rv.exists():
            try:
                run_module(rv)
            except Exception as e:  # noqa: BLE001
                print(f"[{ind}] 리뷰 정리 실패:", e)
    print("끝. 바뀐 업종:", changed or "없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
