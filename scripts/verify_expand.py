#!/usr/bin/env python3
"""Verify 16-call matrix integrity for expand data (agnes-3.0-flash, agnes-2.5-flash)."""
import json, collections

EXPECTED = ({(0, 'g')}
            | {(0, str(s)) for s in range(1, 7)}
            | {(p, str(s)) for p in (1, 2, 3) for s in (1, 2)}
            | {(p, '1') for p in (4, 5, 6)})

for m in ['agnes-3.0-flash', 'agnes-2.5-flash']:
    cells = collections.defaultdict(set)
    unans = 0
    total = 0
    failed = 0
    for line in open(f'results/expand/{m}.jsonl'):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get('FAILED'):
            failed += 1
            continue
        cells[r['qid']].add((r['para'], str(r['sample'])))
        total += 1
        if r.get('answer') is None:
            unans += 1
    bad = {q: c for q, c in cells.items() if c != EXPECTED}
    print(f'{m}: questions={len(cells)}, rows={total}, FAILED_rows={failed}, '
          f'unextracted={unans} ({100 * unans / max(1, total):.2f}%)')
    if bad:
        for q, c in list(bad.items())[:8]:
            print(f'  {q}: missing {sorted(EXPECTED - c)}')
    # dataset distribution
    ds = collections.Counter()
    for line in open(f'results/expand/{m}.jsonl'):
        try:
            r = json.loads(line)
            ds[(r['qid'], r.get('dataset'))] += 1
        except Exception:
            pass
    dcount = collections.Counter(d for (_, d) in ds.keys())
    print(f'  dataset distribution: {dict(dcount)}')
    print()
