# Use official Python runtime as base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=5000


# Install system dependencies and Chrome/ChromeDriver dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    wget \
    unzip \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    # libgdk-pixbuf2.0-0 removed (not available in slim) \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxshmfence1 \
    libgbm1 \
    xdg-utils \
    curl \
    --no-install-recommends && rm -rf /var/lib/apt/lists/*

# Install Google Chrome (modern key method)
RUN wget -O /usr/share/keyrings/google-chrome.gpg https://dl.google.com/linux/linux_signing_key.pub && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*



# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py linkedin_functions.py .env ./


# Create non-root user for security and ensure Chrome profile dir exists and is owned by appuser
RUN useradd -m -u 1000 appuser \
    && mkdir -p /home/appuser/SeleniumProfile \
    && chown -R appuser:appuser /app /home/appuser/SeleniumProfile

USER appuser

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/health')"

# Run the application with uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000"]
