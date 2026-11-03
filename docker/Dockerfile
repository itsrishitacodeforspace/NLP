FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps for pdf/docx/ocr
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        tesseract-ocr \
        poppler-utils \
        curl \
    && rm -rf /var/lib/apt/lists/*

# NOTE: the repo root intentionally carries byte-level duplicate packages
# (clause_classification/, ner/, obligation_extraction/, risk_scoring/,
# context/, datasets/, evaluation/, taxonomy.py, provenance.py) that mirror
# nlp/*. They are dead code for the Python process — every import goes through
# nlp.* / app.* — but they are load-bearing HERE, because pyproject.toml only
# packages ["app", "nlp", "streamlit_app"], so `pip install .` would not ship
# them. `COPY . .` ships them into the image and PYTHONPATH=/app makes them
# importable at the top level. They are SUPERSEDED by nlp/*: never edit a
# root copy directly, edit nlp/ and re-sync (cp). Do not delete them without
# fixing the build that relies on them (see DEEP_AUDIT_20261103.md C10).
COPY . .
RUN pip install --upgrade pip && pip install .

EXPOSE 8000 8501

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
