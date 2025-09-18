FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git openssh-client ca-certificates curl gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    corepack enable && \
    npm i -g @google/gemini-cli && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create and use a virtual environment to satisfy PEP 668
ENV VENV_PATH=/opt/venv
RUN python -m venv "$VENV_PATH"
ENV PATH="$VENV_PATH/bin:$PATH" \
    PYTHONUNBUFFERED=1

COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

CMD ["python", "-m", "src.main"]

