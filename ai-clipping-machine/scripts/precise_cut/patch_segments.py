"""Step 5b: force cut points cut_plan_lf.py cannot see (a breath, or a bad take whisper skipped, inside a kept voiced run).
Times = SOURCE seconds (words_raw / cut_plan 'src0'/'src1'). Ops:
  [t, "start"]        the segment containing t now STARTS at t (audio before t in that segment is dropped)
  [t, "end"]          the segment containing t now ENDS at t
  [t0, "drop", t1]    every segment lying inside [t0, t1] is removed
Words whose audio the ops removed are dropped from the plan (printed). Re-computes the cut timeline (out0 + the words'
cut times) the same way cut_plan_lf.py does. Run check_leftovers.py + render_cut.py after it.
usage: python -I patch_segments.py <project>/work '[[16.88, "start"], [24.45, "end"], [30.1, "drop", 31.0]]'"""
import json, sys
if len(sys.argv) < 3: raise SystemExit(__doc__)
W, ops = sys.argv[1], json.loads(sys.argv[2])
plan = json.load(open(f'{W}/cut_plan.json', encoding='utf-8'))
segs = plan['segments']
def inside(t): return any(m['src0'] - 1e-6 <= t <= m['src1'] + 1e-6 for m in segs)
was_in = [inside((w['s'] + w['e']) / 2) for w in plan['words']]
for op in ops:
    if op[1] == 'drop':
        before = len(segs); segs[:] = [m for m in segs if not (op[0] - 1e-6 <= m['src0'] and m['src1'] <= op[2] + 1e-6)]
        print(f'  drop {op[0]}-{op[2]}: removed {before - len(segs)} segment(s)'); continue
    t, kind = op[0], op[1]
    for m in segs:
        if m['src0'] < t < m['src1']:
            if kind == 'start': m['src0'] = round(t, 4)
            else: m['src1'] = round(t, 4)
            print(f'  {kind} @ {t}: segment now {m["src0"]}-{m["src1"]}')
            break
    else:
        print(f'  WARN no segment contains {t}')
keep = []
for w, was in zip(plan['words'], was_in):
    if was and not inside((w['s'] + w['e']) / 2): print(f"  word removed with its audio: {w['w']} @ {w['s']:.2f}"); continue
    keep.append(w)
plan['words'] = keep
# rebuild the cut timeline
acc = 0.0
for m in segs:
    m['out0'] = round(acc, 4); acc += m['src1'] - m['src0']
def to_cut(t):
    for m in segs:
        if m['src0'] - 1e-6 <= t <= m['src1'] + 1e-6: return m['out0'] + (t - m['src0'])
    # outside every segment: snap to the nearest boundary
    best = min(segs, key=lambda m: min(abs(t - m['src0']), abs(t - m['src1'])))
    return best['out0'] if abs(t - best['src0']) < abs(t - best['src1']) else best['out0'] + best['src1'] - best['src0']
for w in plan['words']:
    w['cs'] = round(to_cut(w['s']), 4); w['ce'] = round(to_cut(w['e']), 4)
plan['duration'] = round(acc, 4)
json.dump(plan, open(f'{W}/cut_plan.json', 'w', encoding='utf-8'), indent=1)
print(f'{len(segs)} segments -> {acc:.3f}s')
