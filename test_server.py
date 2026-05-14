#!/usr/bin/env python3
"""Simple test server to verify Railway deployment."""

from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route('/api/status')
def status():
    return jsonify({
        'status': 'ok',
        'test': True,
        'cwd': os.getcwd(),
        'files': os.listdir('.')
    })

@app.route('/api/health')
def health():
    return jsonify({'health': 'ok'})

if __name__ == '__main__':
    print(f"Starting in {os.getcwd()}")
    print(f"Files: {os.listdir('.')}")
    app.run(host='0.0.0.0', port=3001, debug=False, threaded=True)