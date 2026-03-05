#!/bin/sh

if [ "$DATABASE" = "postgres" ]
then
    echo "Waiting for postgres..."

    while ! nc -z "$SQL_HOST" "$SQL_PORT"; do
      sleep 0.1
    done

    echo "PostgreSQL started"
fi

python manage.py migrate
python manage.py collectstatic --no-input

# Workers: (2 × CPU cores) + 1, overridable via GUNICORN_WORKERS.
# Threads per worker: 4 by default, overridable via GUNICORN_THREADS.
# gthread worker class allows each worker to serve multiple requests
# concurrently, avoiding blocking on I/O (DB queries, network, etc.).
WORKERS=${GUNICORN_WORKERS:-$(( 2 * $(nproc) + 1 ))}
THREADS=${GUNICORN_THREADS:-4}

if [ "$#" -eq 0 ]; then
    exec gunicorn \
        --bind 0.0.0.0:8000 \
        --workers "$WORKERS" \
        --worker-class gthread \
        --threads "$THREADS" \
        --timeout 60 \
        --graceful-timeout 60 \
        config.wsgi:application
else
    exec "$@"
fi
