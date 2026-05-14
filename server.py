#!/usr/bin/env python3
"""PolyNews Terminal — Flask server: REST polling."""

import subprocess, sys, os, threading, json, time
from collections import deque
from flask import Flask, Response, jsonify, send_from_directory

app = Flask(__name__, static_folder='dist', static_url_path='')
MAX_LINES = 200
raw_lines = deque(maxlen=MAX_LINES)
lines_lock = threading.Lock()
POLL_INTERVAL = 120

def run_polynews():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    polynews_path = os.path.join(script_dir, 'polynews.py')
    proc = subprocess.Popen(
        ['python3', polynews_path, '--live', '--interval', str(POLL_INTERVAL)],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        cwd=script_dir,
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

poly_t = threading.Thread(target=run_polynews, daemon=True)
poly_t.start()

@app.route('/api/status')
def status():
    with lines_lock:
        lines = list(raw_lines)
    sources = []
    for line in reversed(lines):
        if 'Reddit' in line and ':' in line: sources.append('reddit')
        elif 'Hacker News' in line: sources.append('hn')
        elif 'BBC' in line: sources.append('bbc')
        elif 'Yahoo' in line: sources.append('yahoo')
        elif 'CoinDesk' in line: sources.append('coindesk')
        elif 'The Block' in line: sources.append('block')
        elif 'Polymarket' in line: sources.append('polymarket')
        elif 'Google News' in line: sources.append('google')
        elif 'Twitter' in line: sources.append('twitter')
    sources = list(dict.fromkeys(reversed(sources)))
    return jsonify({"status": "ok", "lines_cached": len(lines), "sources": sources})

@app.route('/api/news')
def news():
    with lines_lock:
        return jsonify({"lines": list(raw_lines), "count": len(raw_lines)})

@app.route('/api/news/stream')
def stream():
    def generate():
        last_idx = 0
        while True:
            time.sleep(2)
            with lines_lock:
                lines = list(raw_lines)
            if len(lines) > last_idx:
                for l in lines[last_idx:]:
                    yield f"data: {json.dumps({'line': l})}\n\n"
                last_idx = len(lines)
    return Response(generate(), mimetype='text/event-stream')

@app.route('/')
def index():
    return send_from_directory('dist', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('dist', path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 3001)), debug=False, threaded=True)