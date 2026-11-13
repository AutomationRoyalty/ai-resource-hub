#!/usr/bin/env python3
"""Serve the kit folder on http://127.0.0.1:8765 so the review page can play its reels.

Why: opening review.html straight from Finder (file://) fails when the kit lives in a protected
folder like Desktop or Documents. macOS gives the browser that one HTML file, not the mp4s next to
it. Over localhost everything loads, and this server supports byte ranges so scrubbing works.

usage: python3 scripts/review_server.py [videos/<slug>]   (opens that video's review page)"""
import http.server, os, re, sys, webbrowser

PORT = 8765
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=ROOT, **k)

    def log_message(self, *a): pass

    def end_headers(self):
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def send_head(self):
        rng = self.headers.get('Range')
        path = self.translate_path(self.path)
        if not rng or not os.path.isfile(path): return super().send_head()
        m = re.match(r'bytes=(\d*)-(\d*)', rng)
        size = os.path.getsize(path)
        if not m: return super().send_head()
        a = int(m.group(1)) if m.group(1) else max(0, size - int(m.group(2) or 0))
        b = int(m.group(2)) if m.group(1) and m.group(2) else size - 1
        if a >= size: self.send_error(416); return None
        b = min(b, size - 1)
        f = open(path, 'rb'); f.seek(a)
        self.send_response(206)
        self.send_header('Content-Type', self.guess_type(path))
        self.send_header('Content-Range', f'bytes {a}-{b}/{size}')
        self.send_header('Content-Length', str(b - a + 1))
        self.end_headers()
        self._left = b - a + 1
        return f

    def copyfile(self, src, dst):
        left = getattr(self, '_left', None)
        if left is None: return super().copyfile(src, dst)
        while left > 0:
            chunk = src.read(min(65536, left))
            if not chunk: break
            try: dst.write(chunk)
            except (BrokenPipeError, ConnectionResetError): break
            left -= len(chunk)


if __name__ == '__main__':
    page = f'http://127.0.0.1:{PORT}/'
    if len(sys.argv) > 1: page += sys.argv[1].strip('/') + '/review.html'
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    print(f'Review server running. Open: {page}\n(keep this running while you review; Ctrl+C to stop)', flush=True)
    if '--no-open' not in sys.argv: webbrowser.open(page)
    srv.serve_forever()
