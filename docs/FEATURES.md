# Feature status

Implemented means validated locally with synthetic data or controlled remote
responses. It does not mean a live Discord/BDO/Twitch installation has passed
acceptance. [RUNBOOK.md](RUNBOOK.md) is the operator entry point. The current
feature boundary and actionable backlog live in [the task register](../tasks/README.md);
this document remains the detailed capability matrix.

| Area | Implemented | Still requires external verification |
|---|---|---|
| Identity | Discord-only production login, verified first-run setup, role refresh, expiring recovery, session/rate-limit controls | Staging OAuth, role changes and bot install |
| Roster and guilds | Independent guild access, family links, groups, vacations, private notes, exceptions, merge, allied shared summaries | Representative regional roster imports and guild acceptance |
| Wars | CSV/OCR score review and correction, event/session relationships, operational checklist, export and correction history | Real screenshots and a complete officer/member war workflow |
| Capture | JSONL/IKUSA ingestion, calibrated synthetic PCAP, expiring scoped handoff, retained-log retry/deduplication and last-seen diagnostics | Current-patch calibration, real traffic and prolonged capture |
| Events and coaching | Capacity/waitlists, recurrence, signup cards, locks/archive, attendance reconciliation, private mentoring | Real Discord buttons, restarts and permission failures |
| Community and roles | Structured recruitment, private tickets with reopen/transcripts, welcome role hierarchy checks and optional selection replacement | Actual channel overwrites, ticket recovery and role hierarchy |
| Discord delivery | Native typed command catalog, persistent components, durable outbox claims, backoff and remote reconciliation | Staging acceptance; ambiguous outcomes require operator inspection |
| Settings and UX | Validated nested forms, integration/heartbeat status, all-section empty states, mobile/keyboard and automated accessibility checks | Spoken screen-reader review and user acceptance |
| Operations | SQLite/PostgreSQL snapshots, validated restore, backup scheduling, preflight, diagnostics, maintenance, retention and privacy controls | Target Linux shutdown/restart, TLS, off-host backup and restore rehearsal |
| Optional providers | Twitch adapter and configurable Ollama, with explicit per-guild switches | Real provider credentials/connectivity and output acceptance |

## Validation

The release gate runs Django checks/tests with the unchanged 100% statement and
branch coverage threshold, command registration, real Tesseract synthetic
fixtures, packet fixtures, JavaScript syntax, Compose configuration and Chromium
workflows. Test counts are emitted by the runner rather than copied as a stale
baseline here. PostgreSQL native restore/concurrency checks require a separate
test server. Coverage excludes test code and generated migrations, and does not
measure JavaScript or the desktop Tk interface.

Chromium checks cover 12 dashboard sections, first-run setup, every catalog action
dialog, failed-save recovery, keyboard focus and narrow layouts. Automated axe
checks inspect WCAG A/AA rules, including labels and contrast. Accessibility-tree
checks establish semantics, not the experience of a person using a screen reader.
The independent browser smoke script covers the complete war lifecycle.

All OCR/packet fixtures are synthetic. No live Discord, Twitch, BDO capture, real
war screenshot, target-host rehearsal or officer acceptance is claimed by these
offline tests. See the unchecked tasks for the exact remaining launch work.
