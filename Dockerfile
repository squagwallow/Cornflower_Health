FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY src/ ./src/
COPY samples/ ./samples/

# Create logs directory
RUN mkdir -p logs

# Run from src/ so imports resolve correctly
WORKDIR /app/src

EXPOSE 8000

CMD ["uvicorn", "webhook:app", "--host", "0.0.0.0", "--port", "8000"]
