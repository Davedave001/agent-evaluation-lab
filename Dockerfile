FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src:/app/axiom-runtime/src

RUN pip install --no-cache-dir fastapi uvicorn pydantic pytest

COPY axiom-runtime/src/ /app/axiom-runtime/src/
COPY agent-evaluation-lab/src/ /app/src/
COPY agent-evaluation-lab/server.py /app/server.py

EXPOSE 8003

CMD ["python", "server.py"]
