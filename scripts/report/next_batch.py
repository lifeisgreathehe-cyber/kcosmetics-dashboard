"""매일 원고 작성 루틴이 쓸 다음 회사 목록을 고른다.

우선순위
1) 원고가 있는데 그 뒤 새 분기 실적이 나온 회사(원고 basis < 최신 분기) → 다시 쓰기
2) 원고가 없는 회사, 시가총액 큰 순서
재무 자료(분기 실적)가 하나도 없는 회사는 뒤로 미룬다.

사용: python3 scripts/report/next_batch.py [-n 20] [--json]
"""
import argparse, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, 'docs', 'report', 'data')
CFG = os.path.join(ROOT, 'config', 'report')


def latest_q(code):
    p = os.path.join(DATA, 'c', f'{code}.json')
    try:
        d = json.load(open(p, encoding='utf-8'))
    except Exception:
        return None
    q = d.get('quarterly') or {}
    ks = sorted(k for k, v in q.items() if isinstance(v, dict) and v.get('rev'))
    return ks[-1] if ks else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-n', type=int, default=20)
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    L = json.load(open(os.path.join(DATA, 'list.json'), encoding='utf-8'))['companies']
    seen, redo, new, nodata = set(), [], [], []
    for c in sorted(L, key=lambda x: -(x.get('mcap') or 0)):
        code = c['code']
        if code in seen:
            continue
        seen.add(code)
        lq = latest_q(code)
        cfg = os.path.join(CFG, f'{code}.json')
        row = dict(code=code, name=c['name'], ind=c['ind'], group=c.get('group'), mcap=c.get('mcap'), latest_q=lq)
        if os.path.exists(cfg):
            try:
                basis = json.load(open(cfg, encoding='utf-8')).get('basis')
            except Exception:
                basis = None
            if lq and (not basis or basis < lq):
                row['why'] = f'새 실적 {lq} (원고 기준 {basis or "없음"})'
                redo.append(row)
        elif lq:
            row['why'] = '원고 없음'
            new.append(row)
        else:
            row['why'] = '원고 없음, 재무 자료 없음'
            nodata.append(row)
    pick = (redo + new + nodata)[:a.n]
    if a.json:
        print(json.dumps(pick, ensure_ascii=False, indent=1))
    else:
        print(f'다시 쓰기 {len(redo)} · 새로 쓰기 {len(new)} · 자료 없음 {len(nodata)} → 오늘 {len(pick)}개')
        for r in pick:
            print(r['code'], r['name'], r['ind'], r['group'], r['mcap'], r['why'])


if __name__ == '__main__':
    main()
