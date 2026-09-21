# Guild data portability

Guild owners can move supported operational data between OpenIQ instances from
the dashboard **Settings** page. Choose **Export guild** on the source, then
**Import guild** on an existing destination guild. Import always shows a
preview and requires the destination guild name before it writes anything.

## Format and limits

The download is a UTF-8 JSON envelope with format `openiq-guild-v1`. Its
`payload` contains source guild metadata, portable configuration, and records;
`digest` is the SHA-256 of the canonical payload and detects a changed or
damaged file. The digest is an integrity check, not proof of who created the
file. Imports are limited to 4 MiB, 50,000 records, bounded nesting and text
values, known record types, unique record keys, and the exact supported schema
version.

Portable records are roster members and groups, wars and their attendance
scores, signup events and templates, gear snapshots, roster-retention history,
and coaching leads and assignments. Configuration includes performance,
retention, capture, integration feature switches, milestones, schedules,
welcome behavior, and command-access rules.

## Redaction and conflicts

Exports omit account links, Discord and Twitch identifiers, server/channel/
role/message IDs, share tokens, integration URLs, credentials, queued delivery
state, support tickets, applications, reminders, and live capture sessions.
Exports are generated directly into the response and are not retained by the
server. Uploaded JSON is validated within its preview or confirmation request
and is not stored between requests.

The destination preserves record keys so relationships remain stable. A
missing record or configuration section is reported as **create**, identical
data as **skip**, and different data under the same key as **reject**. Any
rejection blocks the entire atomic import; existing data is never overwritten.
After transfer, owners must reconnect accounts and reconfigure Discord,
Twitch, integration URLs, and credentials manually.
