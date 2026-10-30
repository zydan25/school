FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/base.txt /app/requirements/base.txt
RUN python -m pip install --no-cache-dir -r /app/requirements/base.txt

COPY . /app
RUN mkdir -p /app/staticfiles /app/media \
    && addgroup --system school \
    && adduser --system --ingroup school --home /app school \
    && chown -R school:school /app

USER school
EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60"]
