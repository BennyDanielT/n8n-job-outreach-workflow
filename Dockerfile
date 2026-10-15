FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CHROME_BINARY=/usr/bin/chromium

# Chromium + driver for the LinkedIn scraper (Debian packages: work on amd64 and arm64).
RUN apt-get update \
 && apt-get install -y --no-install-recommends chromium chromium-driver fonts-liberation ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY data/master_resume.yaml ./data/master_resume.yaml

RUN useradd --create-home --uid 10001 appuser \
 && mkdir -p /app/data /home/appuser/chrome-profile \
 && chown -R appuser:appuser /app/data /home/appuser
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
