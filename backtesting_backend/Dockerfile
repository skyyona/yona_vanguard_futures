FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install build deps for packages that may need compilation
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first for better caching
COPY backtesting_backend/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY backtesting_backend /app

# Default port used by Engine Host scaffold
ENV ENGINE_HOST_PORT=8203
EXPOSE 8203

# Use uvicorn module to run the ASGI app
CMD ["uvicorn", "backtesting_backend.engine_host.main:app", "--host", "0.0.0.0", "--port", "8203", "--log-level", "info"]
