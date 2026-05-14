#!/bin/bash
set -e
cd /app
echo "=== Railway deployment starting ==="
echo "Python: $(python3 --version)"
echo "Files in /app: $(ls -la)"
exec python3 -u server.py