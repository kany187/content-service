FROM python:3.12-slim

# Prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY Pipfile Pipfile.lock ./
RUN pip install --no-cache-dir pipenv \
    && pipenv install --system --deploy --ignore-pipfile \
    && pip uninstall -y pipenv

# Copy application code
COPY app ./app

# Cloud Run expects the container to listen on PORT (default 8080)
ENV PORT=8080
ENV PYTHONPATH=/app
EXPOSE 8080

# Non-root user for security
RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app
USER appuser

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
