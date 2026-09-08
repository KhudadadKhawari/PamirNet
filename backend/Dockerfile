FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends freeradius-utils curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 pamirnet \
    && useradd --system --uid 10001 --gid pamirnet --home /app pamirnet

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/staticfiles /var/lib/pamirnet/freeradius \
    && chown -R pamirnet:pamirnet /app /var/lib/pamirnet

EXPOSE 8000

FROM base AS development
RUN pip install --no-cache-dir -r requirements-dev.txt
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

FROM base AS production
RUN python manage.py collectstatic --noinput
USER pamirnet
CMD ["gunicorn", "pamirnet.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--threads", "2", "--timeout", "60", "--graceful-timeout", "30", "--access-logfile", "-", "--error-logfile", "-"]
