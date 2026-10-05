# Use case: Packages the ExecPlus API for reproducible container deployments.
# What it does: Builds a non-root Python runtime containing the application and its production dependencies.

ARG PYTHON_IMAGE=python:3.12-slim
FROM ${PYTHON_IMAGE} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY apps/api/src ./apps/api/src
COPY alembic.ini ./
COPY migrations ./migrations
COPY scripts ./scripts

RUN pip install --no-cache-dir .
RUN useradd --create-home --uid 10001 execplus && chmod -R a+rX /app

USER execplus

EXPOSE 8000

CMD ["uvicorn", "execplus.main:app", "--no-access-log", "--host", "0.0.0.0", "--port", "8000"]
