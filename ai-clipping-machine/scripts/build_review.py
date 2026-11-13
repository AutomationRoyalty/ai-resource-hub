#!/usr/bin/env python3
"""Build (or refresh) the reel review page for one video: videos/<slug>/review.html

usage: python3 scripts/build_review.py videos/<slug>

Reads videos/<slug>/reels.json (headlines), working/<id>/build.json (duration, captions),
clips.tsv (source IN/OUT) and the finished <slug>-<id>.mp4 files. Each reel's version is the
mp4's modified time, so after a re-render the page flags that reel as "Updated" and keeps your
previous note for reference. Feedback is saved in the browser (localStorage) and exported with
the "Copy feedback" button as plain text to paste into Claude."""
import json, os, sys, html, datetime

V = os.path.abspath(sys.argv[1]); slug = os.path.basename(V)
cfg = json.load(open(os.path.join(V, 'reels.json')))
src = {}
if os.path.exists(os.path.join(V, 'clips.tsv')):
    for line in open(os.path.join(V, 'clips.tsv')):
        p = line.split()
        if len(p) == 3: src[p[0]] = (float(p[1]), float(p[2]))
title = slug.replace('-', ' ').title()
ideas = os.path.join(V, 'ideas.md')
if os.path.exists(ideas):
    first = open(ideas).readline().strip().lstrip('# ')
    if first: title = first.split(':', 1)[-1].strip().strip('"')

def mmss(s): return f"{int(s // 60)}:{int(s % 60):02d}"
reels = []
for cid in cfg:
    mp4 = f'{slug}-{cid}.mp4'
    if not os.path.exists(os.path.join(V, mp4)): continue
    b = json.load(open(os.path.join(V, 'working', cid, 'build.json')))
    ver = int(os.path.getmtime(os.path.join(V, mp4)))
    reels.append({'id': cid, 'n': len(reels) + 1, 'file': mp4, 'ver': ver, 'headline': b['headline'],
                  'duration': b['duration'], 'caption': b['caption'],
                  'src': f"{mmss(src[cid][0])} to {mmss(src[cid][1])}" if cid in src else '',
                  'poster': f'review/{cid}.jpg' if os.path.exists(os.path.join(V, 'review', f'{cid}.jpg')) else ''})
data = {'slug': slug, 'title': title, 'built': datetime.datetime.now().strftime('%-d %b %Y, %H:%M'), 'reels': reels}

TEMPLATE = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'review_template.html')).read()
out = TEMPLATE.replace('/*__DATA__*/null', json.dumps(data)).replace('__TITLE__', html.escape(title))
open(os.path.join(V, 'review.html'), 'w').write(out)
print(f'wrote {os.path.join(V, "review.html")} ({len(reels)} reels)')
