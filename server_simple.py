#!/usr/bin/env python3
"""Minimal PolyNews Flask server — no threading, no subprocess."""

from flask import Flask, jsonify, send_from_directory

app = Flask(__name__, static_folder='dist', static_url_path='')

@app.route('/_health')
def health():
    return jsonify({'status': 'ok'})

@app.route('/api/status')
def status():
    return jsonify({'status': 'ok', 'lines_cached': 0, 'sources': []})

@app.route('/api/news')
def news():
    return jsonify({'lines': [], 'count': 0})

@app.route('/')
def index():
    return send_from_directory('dist', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('dist', path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3001, debug=False, threaded=False)