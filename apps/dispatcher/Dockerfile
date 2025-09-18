FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn[standard] httpx pydantic

COPY dispatcher.py ./

CMD ["uvicorn", "dispatcher:app", "--host", "0.0.0.0", "--port", "8099"]

