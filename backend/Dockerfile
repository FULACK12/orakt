FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip \
    && python -m pip install \
      "alembic>=1.16,<2.0" \
      "baostock>=0.9.3,<1.0" \
      "fastapi>=0.116,<1.0" \
      "feedparser>=6.0.11,<7.0" \
      "fonttools>=4.59,<5.0" \
      "httpx>=0.28,<1.0" \
      "pypdf>=6,<7" \
      "psycopg[binary]>=3.2,<4.0" \
      "pydantic-settings>=2.10,<3.0" \
      "sqlalchemy>=2.0.41,<3.0" \
      "solders==0.29.0" \
      "uvicorn[standard]>=0.35,<1.0"

COPY app ./app
RUN python -m pip install --no-deps .

COPY alembic.ini ./
COPY alembic ./alembic
COPY config ./config

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
