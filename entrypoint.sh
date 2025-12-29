#!/bin/sh

if [ "$DATABASE" = "postgres" ]
then
    echo "Waiting for postgres..."

    while ! nc -z "$SQL_HOST" "$SQL_PORT"; do
      sleep 0.1
    done

    echo "PostgreSQL started"
fi

python manage.py collectstatic --no-input
python manage.py flush --no-input
python manage.py migrate

# Set default workers if GUNICORN_WORKERS is not set
WORKERS=${GUNICORN_WORKERS:-3}

if [ "$#" -eq 0 ]; then
    exec gunicorn --bind 0.0.0.0:8000 --workers "$WORKERS" --timeout 60 --graceful-timeout 60 config.wsgi:application
else
    exec "$@"
fi
