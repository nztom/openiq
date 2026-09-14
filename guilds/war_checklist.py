"""Officer-only, derived operational status; never infer capture success from startup."""
from .models import Record,Outbox


def checklist(guild):
    grouped={kind:{} for kind in ('event','session','war','import')}
    for record in Record.objects.filter(guild=guild,kind__in=grouped):grouped[record.kind][record.key]=record
    output=[];seen_wars=set();seen_sessions=set()
    def append(event=None,war=None,session=None,draft=None):
        if war:seen_wars.add(war.key)
        if session:seen_sessions.add(session.key)
        drafts=[draft] if draft else [d for d in grouped['import'].values() if war and d.data.get('war')==war.key]
        pending=[d for d in drafts if d.data.get('status')=='review']
        corrections=sum(sum(not row.get('member') for row in d.data.get('rows',[])) for d in pending)
        message=Outbox.objects.filter(guild=guild,key=f'{guild.pk}:event:{event.key}').first() if event else None
        signup=event.data.get('signups',[]) if event else []
        output.append({'title':event.data['title'] if event else session.data['title'] if session else war.data['date'] if war else 'Unlinked score review',
                       'event':event.key if event else None,'war':war.key if war else None,'session':session.key if session else None,
                       'signup':{'status':('archived' if event.data.get('archived') else 'locked' if event.data.get('locked') else 'open') if event else 'not linked',
                                 'confirmed':sum(not s.get('waitlisted') for s in signup),'waitlisted':sum(bool(s.get('waitlisted')) for s in signup)},
                       'capture':{'status':session.data['status'] if session else 'not linked','events':len(session.data.get('events',[])) if session else 0,
                                  'last_seen':session.data.get('capture_last_seen') if session else None},
                       'review':'corrections required' if corrections else 'awaiting finalization' if pending else 'finalized' if war else 'not imported',
                       'corrections':corrections,'result':war.data['result'] if war else None,
                       'discord':message.status if message else 'not queued'})
    for event in grouped['event'].values():
        war=grouped['war'].get(event.data.get('war'))
        session=grouped['session'].get(war.data.get('session')) if war else None
        append(event,war,session)
    for war in grouped['war'].values():
        if war.key not in seen_wars:append(war=war,session=grouped['session'].get(war.data.get('session')))
    for session in grouped['session'].values():
        if session.key not in seen_sessions:append(session=session)
    for draft in grouped['import'].values():
        if draft.data.get('status')=='review':append(draft=draft)
    return output
