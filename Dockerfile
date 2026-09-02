# Sales Insight — application image
FROM python:3.11-slim

# Keep Python output unbuffered and skip .pyc files.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first (better layer caching).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code.
COPY . .

EXPOSE 8000

# Bind to the platform-provided $PORT when set (e.g. Render), else 8000.
CMD ["sh", "-c", "uvicorn src:app --host 0.0.0.0 --port ${PORT:-8000}"]
