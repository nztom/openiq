# Guild data and member controls

OpenIQ stores Discord account/server identifiers, guild access roles, game family
and character names, roster/class information, war scores, signups, gear, tickets,
applications and reminders. Officer notes/coaching and review imports are private.
OAuth access/refresh tokens live in server-side sessions; capture credentials are
stored as hashes. Uploaded OCR images are processed temporarily; extracted rows
remain until import retention removes them. See SECURITY.md for session expiry
and README.md for retention settings.

In **My Stats**, a linked member can export their own data or unlink their account
and Twitch/Discord identifiers. An officer can select a member on their behalf
through the same scoped API. Exports include that member's scores and owned
records; member exports omit private officer notes and coaching assignments.
Ask the guild operator to review any additional private records for an export.

Anonymization requires typing the member's current name. It replaces identifying
roster fields with an inactive anonymous entry, removes owned tickets,
applications, reminders, gear/coaching and capture credentials, and scrubs known
names/identifiers from retained guild records and audit text. Finalized scores
keep their anonymous member reference so guild totals remain consistent.
**Delete membership and identifying data** also removes local access to this
guild. It does not delete the account's membership in another guild or remove
the Discord account itself. The last guild owner must transfer ownership first.

These controls cover data held by this application. Operators must separately
review unrelated free-form text, local capture files, external Discord messages,
downloaded exports and backups. Known-name scrubbing cannot identify every piece
of personal information in arbitrary prose. Expire private backups according to
the guild's policy; restoring an older backup can reintroduce removed information,
so record removal requests outside the restored dataset and reapply them.
Discord OAuth may grant access again if the member still holds a configured
Discord role; remove that authority separately when access must stay revoked.
