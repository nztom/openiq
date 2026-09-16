#!/bin/sh
set -eu

for secret_name in SECRET_KEY DATABASE_PASSWORD DISCORD_CLIENT_SECRET DISCORD_BOT_TOKEN TWITCH_ACCESS_TOKEN; do
    secret_file=$(printenv "${secret_name}_FILE" || true)
    if [ -n "$secret_file" ]; then
        if [ ! -r "$secret_file" ]; then
            echo "${secret_name}_FILE is not readable." >&2
            exit 1
        fi
        secret_value=$(cat "$secret_file")
        export "${secret_name}=${secret_value}"
    fi
done

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

backup_pid=
if [ -d "${BACKUP_OUTPUT:-/backups}" ]; then
    python manage.py backup_scheduler --output "${BACKUP_OUTPUT:-/backups}" \
        --interval "${BACKUP_INTERVAL:-14400}" --keep "${BACKUP_KEEP:-7}" \
        --timeout "${BACKUP_TIMEOUT:-120}" &
    backup_pid=$!
else
    echo "Backup output ${BACKUP_OUTPUT:-/backups} is not mounted; scheduled backups are disabled." >&2
fi

"$@" &
app_pid=$!

stop() {
    kill -TERM "$app_pid" 2>/dev/null || true
    if [ -n "$backup_pid" ]; then
        kill -TERM "$backup_pid" 2>/dev/null || true
    fi
}
trap 'stop; wait "$app_pid"; exit 0' INT TERM

wait "$app_pid"
app_status=$?
if [ -n "$backup_pid" ]; then
    kill -TERM "$backup_pid" 2>/dev/null || true
    wait "$backup_pid" || true
fi
exit "$app_status"
