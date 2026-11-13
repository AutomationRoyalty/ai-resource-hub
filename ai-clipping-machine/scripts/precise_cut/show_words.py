"""Print words_raw.json phrase by phrase with word indices (to write retakes.json ranges straight from it).
A [time] marks the first word of a phrase and every word after a > 0.6 s pause.
usage: python -I show_words.py <project>/work [first phrase] [last phrase]"""
import json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if len(sys.argv) < 2: raise SystemExit(__doc__)
W = sys.argv[1]
d = json.load(open(f'{W}/words_raw.json', encoding='utf-8'))
p0 = int(sys.argv[2]) if len(sys.argv) > 2 else 0
p1 = int(sys.argv[3]) if len(sys.argv) > 3 else len(d['phrases']) - 1
for pi in range(p0, p1 + 1):
    s0, s1, _ = d['phrases'][pi]
    ws = [(i, w) for i, w in enumerate(d['words']) if w['phrase'] == pi]
    print(f'P{pi:03d} {s0:7.2f}-{s1:7.2f}: ' + ' '.join(f"{i}:{w['w']}" + (f"[{w['s']:.2f}]" if k == 0 or w['s'] - ws[k - 1][1]['e'] > 0.6 else '') for k, (i, w) in enumerate(ws)))
