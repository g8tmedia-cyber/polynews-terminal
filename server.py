#!/usr/bin/env python3
"""PolyNews Terminal — Flask server: REST polling + SSE fallback."""

import subprocess
import sys
import os
import threading
import json
import time
import re
from collections import deque
from flask import Flask, Response, jsonify, send_from_directory

app = Flask(__name__, static_folder='dist', static_url_path='')

MAX_LINES = 200
raw_lines = deque(maxlen=MAX_LINES)
lines_lock = threading.Lock()

POLL_INTERVAL = 120  # seconds between polynews refreshes

# ── Background poller ─────────────────────────────────────────────────────────
def run_polynews():
    proc = subprocess.Popen(
        [sys.executable, '/home/pc/polynews.py', '--live', '--interval', str(POLL_INTERVAL)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        cwd='/home/pc',
        env={**os.environ, 'TERM': 'xterm-256color'}
    )
    try:
        for line in iter(proc.stdout.readline, b''):
            if line:
                decoded = line.decode('utf-8', errors='replace')
                with lines_lock:
                    raw_lines.append(decoded.rstrip())
    finally:
        proc.terminate()
        proc.wait()

# Start background poller
poly_t = threading.Thread(target=run_polynews, daemon=True)
poly_t.start()

# ── SSE (works locally, good for same-network browsers) ───────────────────────
@app.route('/stream')
def stream():
    def generate():
        last_idx = 0
        while True:
            time.sleep(2)
            with lines_lock:
                lines = list(raw_lines)
            if len(lines) > last_idx:
                for l in lines[last_idx:]:
                    yield f"data: {l}\n\n"
                last_idx = len(lines)
            yield f"data: heartbeat\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )

# ── REST polling endpoint (reliable over Cloudflare) ─────────────────────────
@app.route('/api/news')
def get_news():
    """Return latest raw lines as JSON array."""
    with lines_lock:
        lines = list(raw_lines)
    return jsonify({
        'status': 'ok',
        'timestamp': time.time(),
        'count': len(lines),
        'lines': lines
    })

@app.route('/api/status')
def status():
    return jsonify({
        'status': 'ok',
        'sources': ['hn','bbc','yahoo','coindesk','block','polymarket','reddit','google'],
        'lines_cached': len(raw_lines)
    })

# ── Static SPA ─────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    dist = os.path.join(os.path.dirname(__file__), 'dist')
    index_path = os.path.join(dist, 'index.html')
    if os.path.exists(index_path):
        return send_from_directory(dist, 'index.html')
    return "Run `npm run build` first.", 503

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=3000)
    args = parser.parse_args()
    print(f"🚀 PolyNews Terminal → http://0.0.0.0:{args.port}")
    app.run(host='0.0.0.0', port=args.port, threaded=True, debug=False)