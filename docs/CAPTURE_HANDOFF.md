# Authenticated capture forwarding

Start a live session in the dashboard. On the server, issue its credential as an
officer (use the actual guild, session and username):

```sh
umask 077
python manage.py pair_capture --guild 1 --session SESSION --user OFFICER > .capture-token
```

Transfer that private file to the capture machine through a secure channel.
It grants event ingestion for this session only, expires after 24 hours, and
requires the issuing account to retain officer access. Pairing again immediately
replaces the old credential. Keep the file outside shared folders and Git.

```sh
python scripts/forward_capture.py events.jsonl \
  --endpoint https://YOUR_HOST/capture/1/SESSION/ --token-file .capture-token
```

The forwarder reads normalized newline-terminated JSON events with stable `id`
fields. It retains each batch until acknowledged, retries connection failures
with backoff, and replays the retained source file after restart. The server
deduplicates IDs, applies each batch atomically and rejects stopped sessions.
Keep source logs until the dashboard confirms all events. Do not rotate away
unacknowledged source files. `--once` drains the available complete lines and exits.
Credentials require HTTPS except when forwarding to loopback.

The History war checklist shows capture last-seen time and event count. Session
records retain at most 50 batch diagnostics containing timestamp and counts.
The credential hash is excluded from dashboard state. To revoke:

```sh
python manage.py pair_capture --guild 1 --session SESSION --user OFFICER --revoke
```

The transport is tested with synthetic events. It does not validate BDO decoding
or replace the separately developed desktop capture companion.
