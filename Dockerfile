FROM python:3.12-slim

WORKDIR /app

# Install Playwright deps + browser
RUN apt-get update && apt-get install -y \
    wget gnupg curl git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install playwright \
    && playwright install chromium --with-deps

# Copy app
COPY polynews.py server.py ./
COPY dist/ ./dist/

ENV PORT=3001
EXPOSE 3001

CMD ["python3", "server.py"]
