#!/usr/bin/env bash
# Старт веб-панели: миграции, роли/пользователи, затем gunicorn.
set -e

echo ">> применяю миграции"
python manage.py migrate --noinput

echo ">> создаю роли и стартовых пользователей"
python manage.py bootstrap_rbac

echo ">> запускаю gunicorn на :8000"
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 60
