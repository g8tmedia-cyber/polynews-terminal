#!/bin/bash
set -e

echo "=== Railway deployment starting ==="
echo "Files: $(ls -la /app/)"

# Simple inline Flask server - no threading, no subprocess at startup
python3 -u -c "
import os
from flask import Flask, jsonify, send_from_directory
from collections import deque

app = Flask(__name__, static_folder='dist', static_url_path='')
raw_lines = deque(maxlen=200)

@app.route('/_health')
def health():
    return 'OK', 200

@app.route('/api/status')
def status():
    return jsonify({'status': 'ok', 'lines_cached': len(raw_lines)})

@app.route('/api/news')
def news():
    return jsonify({'lines': list(raw_lines), 'count': len(raw_lines)})

@app.route('/')
def index():
    return send_from_directory('dist', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('dist', path)

print('Starting Flask on port 3001...')
app.run(host='0.0.0.0', port=3001, debug=False, threaded=False, use_reloader=False)
"