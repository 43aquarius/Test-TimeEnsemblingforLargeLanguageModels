#!/usr/bin/env python3
"""Check every (qid, para, sample) cell has at least one row with answer != None."""
import json, collections

EXPECTED = ({(0, 'g')}
            | {(0, str(s)) for s in range(1, 7)}
            | {(p, str(s)) for p in (1, 2, 3) for s in (1, 2)}
            | {(p, '1') for p in (4, 5, 6)})

questions = json.load(open('/home/z/my-project/data/questions_expand.json'))
QIDS = [q['id'] for q in questions]

for m in ['agnes-3.0-flash', 'agnes-2.5-flash']:
    ok_cells = collections.defaultdict(set)   # cells with valid answer
    none_cells = collections.defaultdict(set)  # cells whose latest row is None
    for line in open(f'/home/z/my-project/results/expand/{m}.jsonl'):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get('FAILED'):
            continue
        cell = (r['qid'], r['para'], str(r['sample']))
        if r.get('answer') is None:
            none_cells[r['qid']].add((r['para'], str(r['sample'])))
        else:
            ok_cells[r['qid']].add((r['para'], str(r['sample'])))
    # a cell is bad only if it has NO valid-answer row across retries
    bad = []
    for qid in QIDS:
        for cell in EXPECTED:
            if cell not in ok_cells[qid]:
                bad.append((qid, cell))
    print(f'{m}: cells_with_answer={sum(len(v) for v in ok_cells.values())}/1904, '
          f'cells_missing_answer={len(bad)}')
    if bad:
        for qid, cell in bad[:10]:
            print(f'  MISSING: {qid} para={cell[0]} sample={cell[1]}')
    # per-dataset accuracy snapshot (greedy only, quick sanity)
    qs = {q['id']: q for q in questions}
    greedy_acc = collections.Counter()
    greedy_tot = collections.Counter()
    for line in open(f'/home/z/my-project/results/expand/{m}.jsonl'):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get('FAILED') or r.get('answer') is None:
            continue
        if r['para'] == 0 and str(r['sample']) == 'g':
            ds = r['dataset']
            greedy_tot[ds] += 1
            if r.get('correct'):
                greedy_acc[ds] += 1
    tot_all = sum(greedy_tot.values())
    acc_all = sum(greedy_acc.values())
    dist = ', '.join(f'{d}:{greedy_acc[d]}/{greedy_tot[d]}'
                     for d in sorted(greedy_tot, key=lambda x: -greedy_tot[x]))
    print(f'  greedy acc: {acc_all}/{tot_all} = {100 * acc_all / max(1, tot_all):.1f}%  ({dist})')
    print()
