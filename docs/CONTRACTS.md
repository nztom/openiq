# Application contracts

Guild recovery requires a signed-in Discord user, an unexpired single-use adoption
key, and a fresh Discord API check confirming owner, Administrator, or Manage Guild
authority on the destination server. A failed authority check does not consume the
key. Recovery records the issuer, redeemer, and old/new server IDs in the audit
trail without storing the plaintext key. Production callers use POST `/recover/`
with `guild`, `server_id`, and `key` and the session's CSRF token. The older direct
`admin.adopt` action is restricted to explicit local development login mode.

## Calculations

- Guild K/D divides total included kills by total included deaths, never averages individual ratios. A positive kill count with zero deaths is represented by JSON `null` and displayed as infinity; 0/0 is displayed as 0.
- Member exception status removes that member from guild combat totals. Their personal totals remain available.
- War/row exclusions remove combat statistics, not attendance. Eligibility requires a war on/after the member's join date and outside recorded inclusive vacation intervals. The card uses the last seven eligible wars. Current inactive members retain their historical data.
- Win rate is wins divided by wins plus losses; draws are not in the denominator.
- Gear score is `max(AP, AAP) + DP`. This is an explicit prototype convention, not an assertion about an unpublished upstream formula.
- Improvement compares the last and first included single-war K/D using a denominator floor of one. Consistency uses the population standard deviation of those ratios. Award definitions differ from a possible upstream implementation.
- Event waitlists use signup time within the selected team. Withdrawing promotes the earliest remaining signup. Moves enter the target team's queue at the current time. Repeating a manually requested event preserves wall-clock time in its configured timezone.
- Archiving an event adds one pity point to each waitlisted member, once per event. Three points can be treated as a prototype token; automatic token-based prioritization is not implemented.
- Scheduled jobs write a unique job record per schedule/date. Notification output enters the outbox; enabled delivery drains it with durable claims, retries and remote-message reconciliation. The `scheduler` management command or optional Compose jobs profile runs jobs continuously; individual `tick` calls remain available.

## API

Browser mutations require an authenticated session and CSRF token. The capture handoff uses a separate session-scoped expiring bearer credential:

```text
GET  /api/<guild_id>/state/
POST /api/<guild_id>/<module>/<action>/
POST /ocr/<guild_id>/
GET  /onboard/
POST /onboard/
POST /capture/<guild_id>/<session_id>/  (scoped bearer credential, not a browser session)
```

JSON mutation responses contain `{ "ok": true, "result": ... }`. Domain validation returns HTTP 400; denied access returns HTTP 403. Modules validate cross-guild record references. The service wraps mutation, revision increment and audit entry in one database transaction.

External AI/Twitch/roster preparation runs before that transaction. The service
rechecks access, role, guild revision and configuration before accepting its
result; a concurrent change returns a retryable validation error rather than
overwriting newer state. Welcome-role HTTP calls also run outside the component
transaction. Successful member responses omit private `notes` fields even when
the underlying action returns a full member record. War saves/deletions generate
targeted correction history inside the mutation transaction; privacy scrubbing
does not recreate removed data in new history entries.

## Normalized event file

A JSON array or newline-delimited objects:

```json
{"id":"session-1-event-1","at":"2026-09-11T09:00:00Z","kind":"kill","player":"Aster","target":"Opponent","guild":"Moonfall","class":"Warrior","family":"EnemyFamily"}
```

`player` is the killer and `target` the victim, including death events. `kind` describes the local player's perspective. Stable event IDs support repeat ingestion. Timestamps require an offset. The JSONL tail adapter waits for a newline before parsing a partial record; truncated or rotated files reset its read position. Browser ingestion uploads parsed event objects; it does not capture network packets.

## IKUSA text contract

The publicly served IKUSA log-import frontend provided this interoperable text
shape:

```text
[23:59:58] LocalCharacter has killed EnemyCharacter from EnemyGuild (LocalFamily, EnemyFamily)
[00:00:02] LocalCharacter died to EnemyCharacter from EnemyGuild
```

The independently written parser takes an explicit date and timezone offset. It reverses actor/victim for `died to`, and recognizes a greater-than-12-hour backwards clock jump as midnight. Smaller out-of-order clock changes are rejected for review. IDs are derived from date, line position and text; importing arbitrary overlapping subsets is not guaranteed to deduplicate the same way as importing the complete same file.

Only the text format was used as compatibility evidence from the publicly served `ikusaParser` asset. No upstream implementation is bundled. Synthetic contract fixtures are provided; authentic game-log verification remains pending. See [IKUSA introduction](https://ikusa.site/docs/introduction) and [Source product documentation](https://critiq.one/docs/index.html).

## External adapters

Discord OAuth follows the [authorization code flow](https://docs.discord.com/developers/topics/oauth2). Tokens remain in the server-side session store. Guild roles are refreshed on requests after three minutes; an API failure invalidates the login rather than retaining unverified privilege.

Twitch uses its [streams API](https://dev.twitch.tv/docs/api/reference/#get-streams). Partner flags in fixture data are fixture metadata; the live adapter does not infer partner status.

Notification delivery is opt-in and separate from preview generation. Durable claims, message markers and pending remote-operation records reconcile retries after local persistence failure. Missing ambiguous remote outcomes fail closed for operator inspection; unconditional exactly-once delivery is not guaranteed. Live Discord behavior remains an installation acceptance check.


## Packet calibration and capture

`guilds/packets.py` assembles TCP bytes independently per source/destination address and port tuple. It trims retransmitted overlaps, buffers bounded out-of-order segments and searches for the configured record marker. Calibration defines record size, name fields, encoding, kill-flag nibble and allowed server networks. Invalid/truncated name records are rejected. Each event gets a stream-position-derived identifier.

`fixtures/calibration-historical.json` contains historical field positions and a documentation-only server CIDR. `fixtures/combat-synthetic.pcap` is generated from synthetic MAC/IP addresses and player names. The synthetic-PCAP test never sniffs live traffic. Scapy may require interface-enumeration access during import even for offline use.

Current-patch calibration, authenticated network traces, prolonged capture, TCP sequence wraparound, and exhaustive packet-loss recovery remain unverified. The decoder does not decrypt unknown payloads or bypass game protections.

## Compatibility sources

OpenIQ is an independent implementation. Public Critiq workflow documentation
and product demonstrations informed the feature design; upstream application
code and branding assets are not included. The [Critiq documentation](https://critiq.one/docs/index.html)
and [IKUSA introduction](https://ikusa.site/docs/introduction) provide context,
not a promise of feature parity or identical private formulas.

The historical packet calibration derives from public field-format information
in [sch-28/ikusa_logger](https://github.com/sch-28/ikusa_logger), dated 2023-04-19.
The decoder implementation is independent. Synthetic fixtures establish the
implemented contract; they do not establish current-patch compatibility.
Current validation boundaries live in [feature state](../tasks/FEATURE_STATE.md).
