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

data_dir=${OPENIQ_DATA_DIR:-/data}
bot_pid=
scheduler_pid=
if [ "${RUN_DISCORD_BOT:-0}" = "1" ]; then
    case ",${REQUIRED_PROCESSES:-}," in *,bot,*) ;; *) export REQUIRED_PROCESSES="${REQUIRED_PROCESSES:+${REQUIRED_PROCESSES},}bot";; esac
fi
if [ "${RUN_SCHEDULER:-0}" = "1" ]; then
    case ",${REQUIRED_PROCESSES:-}," in *,scheduler,*) ;; *) export REQUIRED_PROCESSES="${REQUIRED_PROCESSES:+${REQUIRED_PROCESSES},}scheduler";; esac
fi
restore_source=${BACKUP_RESTORE_SOURCE:-}
if [ -n "$restore_source" ] && [ ! -e "$data_dir/db.sqlite3" ]; then
    snapshot=$(find "$restore_source" -maxdepth 1 -type d -name 'openiq-backup-*' -print 2>/dev/null | sort | tail -n 1)
    if [ -n "$snapshot" ]; then
        restore_temporary=$(mktemp -d)
        restore_output="$restore_temporary/data"
        restore_context="$restore_temporary/context"
        OPENIQ_DATA_DIR="$restore_context" DATABASE_PATH="$restore_context/db.sqlite3" \
            DATABASE_BACKEND=sqlite SECRET_KEY= python manage.py restore "$snapshot" --output "$restore_output"
        mkdir -p "$data_dir"
        mv "$restore_output/db.sqlite3" "$data_dir/db.sqlite3"
        mv "$restore_output/.secret-key" "$data_dir/.secret-key"
        chmod 600 "$data_dir/db.sqlite3" "$data_dir/.secret-key"
        rm -rf "$restore_temporary"
        echo "Restored local OpenIQ data from $snapshot." >&2
    fi
fi

python manage.py validate_environment
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
    python manage.py migrate --noinput
fi
if [ "${SEED_DEMO:-0}" = "1" ]; then
    python manage.py seed_demo
fi
if [ "${RUN_DISCORD_BOT:-0}" = "1" ]; then
    python manage.py runbot &
    bot_pid=$!
fi
if [ "${RUN_SCHEDULER:-0}" = "1" ]; then
    python manage.py scheduler --interval "${SCHEDULER_INTERVAL:-30}" &
    scheduler_pid=$!
fi
if [ "${RUN_BACKEND_ADMIN_SETUP:-0}" = "1" ]; then
    python manage.py bootstrap_admin
fi

backup_pid=
backup_output=${BACKUP_OUTPUT:-/backups}
backup_now() {
    if [ -d "$backup_output" ]; then
        python manage.py backup --output "$backup_output" --keep "${BACKUP_KEEP:-7}" \
            --timeout "${BACKUP_TIMEOUT:-120}" || \
            echo "Final backup failed; inspect storage and database configuration." >&2
    fi
}

if [ -d "$backup_output" ]; then
    python manage.py backup_scheduler --output "$backup_output" \
        --interval "${BACKUP_INTERVAL:-14400}" --keep "${BACKUP_KEEP:-7}" \
        --timeout "${BACKUP_TIMEOUT:-120}" &
    backup_pid=$!
else
    echo "Backup output $backup_output is not mounted; scheduled backups are disabled." >&2
fi

"$@" &
app_pid=$!

stop() {
    kill -TERM "$app_pid" 2>/dev/null || true
    wait "$app_pid" 2>/dev/null || true
    if [ -n "$backup_pid" ]; then
        kill -TERM "$backup_pid" 2>/dev/null || true
        wait "$backup_pid" 2>/dev/null || true
    fi
    if [ -n "$bot_pid" ]; then
        kill -TERM "$bot_pid" 2>/dev/null || true
        wait "$bot_pid" 2>/dev/null || true
    fi
    if [ -n "$scheduler_pid" ]; then
        kill -TERM "$scheduler_pid" 2>/dev/null || true
        wait "$scheduler_pid" 2>/dev/null || true
    fi
    backup_now
}
trap 'stop; exit 0' INT TERM

app_status=0
while kill -0 "$app_pid" 2>/dev/null; do
    if [ -n "$bot_pid" ] && ! kill -0 "$bot_pid" 2>/dev/null; then
        wait "$bot_pid" || true
        echo "Discord bot exited unexpectedly; stopping web process for restart." >&2
        kill -TERM "$app_pid" 2>/dev/null || true
        break
    fi
    if [ -n "$scheduler_pid" ] && ! kill -0 "$scheduler_pid" 2>/dev/null; then
        wait "$scheduler_pid" || true
        echo "Scheduler exited unexpectedly; stopping web process for restart." >&2
        kill -TERM "$app_pid" 2>/dev/null || true
        break
    fi
    sleep 1
done
wait "$app_pid" || app_status=$?
if [ -n "$backup_pid" ]; then
    kill -TERM "$backup_pid" 2>/dev/null || true
    wait "$backup_pid" || true
fi
if [ -n "$bot_pid" ]; then
    kill -TERM "$bot_pid" 2>/dev/null || true
    wait "$bot_pid" || true
fi
if [ -n "$scheduler_pid" ]; then
    kill -TERM "$scheduler_pid" 2>/dev/null || true
    wait "$scheduler_pid" || true
fi
backup_now
exit "$app_status"
