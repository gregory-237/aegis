# Образ веб-панели (Django + DRF под gunicorn). Контекст сборки — корень репозитория.
FROM python:3.12-slim

WORKDIR /app

COPY server/web/requirements.txt ./req.txt
RUN pip install --no-cache-dir -r req.txt gunicorn whitenoise

COPY server/web ./server/web
COPY deploy/web-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /app/server/web
ENV PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings \
    AEGIS_WEB_DEBUG=0

# Собрать статику (БД не требуется).
RUN python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["/entrypoint.sh"]
