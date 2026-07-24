FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements-production.txt .
RUN pip install --no-cache-dir -r requirements-production.txt

# Copy app
COPY . .

# Expose port
EXPOSE 8765

# Run web UI
CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8765"]
