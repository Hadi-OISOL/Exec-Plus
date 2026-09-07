# Use case: Packages the ExecPlus API for reproducible container deployments.
# What it does: Builds a non-root Python runtime containing the application and its production dependencies.

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY apps/api/src ./apps/api/src

RUN pip install --no-cache-dir .
RUN useradd --create-home --uid 10001 execplus

USER execplus

EXPOSE 8000

CMD ["uvicorn", "execplus.main:app", "--no-access-log", "--host", "0.0.0.0", "--port", "8000"]

