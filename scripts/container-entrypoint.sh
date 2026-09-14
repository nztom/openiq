#!/bin/sh
set -eu
python manage.py validate_environment
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
    python manage.py migrate --noinput
fi
if [ "${SEED_DEMO:-0}" = "1" ]; then
    python manage.py seed_demo
fi
if [ "${RUN_BACKEND_ADMIN_SETUP:-0}" = "1" ]; then
    python manage.py bootstrap_admin
fi
exec "$@"
