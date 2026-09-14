"""Declarative forms keep independent modules accessible without a frontend build."""
def f(name,label,kind='text',options=None,default=None): return {'name':name,'label':label,'type':kind,'options':options,'default':default}
def a(module,action,label,fields,role='admin'): return {'module':module,'action':action,'label':label,'fields':fields,'role':role}
MEM=f('member','Member','member'); EVENT=f('event','Event','event'); WAR=f('war','War','war'); SESSION=f('session','Session','session')
ACTIONS=[
 a('roster','save','Add member',[f('name','Family name'),f('character','Character'),f('class','Class',default='Unknown'),f('joined','Joined','date'),f('group','Group',default='Unassigned')]),
 a('roster','class','Set class',[MEM,f('class','Class'),f('spec','Specialization','select',['Succession','Awakening','Ascension']),f('backfill','Update past wars','checkbox')],'member'),
 a('roster','link','Link account',[MEM,f('user_id','Local account ID'),f('discord_id','Discord user ID')]),
 a('roster','vacation','Add vacation',[MEM,f('start','From','date'),f('end','Through','date')]),
 a('roster','note','Add private note',[MEM,f('text','Note','textarea')]),
 a('roster','group','Create group',[f('name','Group name'),f('color','Color','color',default='#63d9c5')]),
 a('roster','sync','Sync reviewed roster',[f('names','Family names, one per line','lines')]),
 a('roster','merge','Merge renamed member',[f('source','Old member','member'),f('target','Keep member','member')]),
 a('roster','remove','Mark inactive',[MEM]),
 a('wars','review','Review scores',[f('csv','Scores (CSV: name,kills,deaths)','textarea',default='name,kills,deaths\n')]),
 a('wars','save','Record war',[f('date','War date','date'),f('type','Type','select',['Node','Siege']),f('result','Result','select',['Win','Loss','Draw']),f('location','Node / castle'),f('opponents','Opposing guilds'),f('capped','Capped','checkbox'),f('cap','Cap details'),f('participants','Participants','participants'),f('note','Note','textarea')]),
 a('wars','delete','Delete war',[WAR]),
 a('wars','export','Export war package',[WAR]),
 a('events','save','Create event',[f('title','Title'),f('type','Type','select',['Node','Siege','Practice','Custom']),f('at','Start','datetime-local'),f('timezone','Timezone',default='Pacific/Auckland'),f('teams','Teams (name,capacity,optional group per line)','teams',default='Frontline,20\nFlex,10\nBackline,20'),f('recurrence_days','Repeat every N days (0 = once)','number',default=0),f('image','Card image URL (optional)','url'),f('accent','Accent color (optional)',default='')]),
 a('events','signup','Sign up / move team',[EVENT,MEM,f('team','Team name (empty to withdraw)')],'member'),
 a('events','template','Save event preset',[EVENT,f('name','Preset name')]),
 a('events','from_template','Use event preset',[f('template','Preset','template'),f('at','Start','datetime-local')]),
 a('events','next','Create next occurrence',[EVENT]),
 a('gear','save','Update gear',[MEM,f('ap','AP','number'),f('aap','Awakening AP','number'),f('dp','DP','number')],'member'),
 a('gear','delete','Remove current gear',[MEM],'member'),
 a('coaching','settings','Performance thresholds',[f('enabled','Enabled','checkbox',default=True),f('kdr','Minimum KDR','number',default=.5),f('attendance','Minimum attendance %','number',default=50),f('no_show','No-show threshold %','number',default=50),f('last_wars','KDR window (wars)','number',default=7),f('min_events','Minimum no-show events','number',default=3),f('miss_streak','Consecutive misses','number',default=3),f('grace_days','New-member grace (days)','number',default=7),f('cooldown_days','Resolution cooldown (days)','number',default=7)],'owner'),
 a('coaching','lead','Add lead',[f('name','Lead / role name'),f('capacity','Capacity','number',default=3)],'owner'),
 a('coaching','assign','Assign mentor',[MEM,f('lead','Lead','lead'),f('notes','Notes','textarea')],'owner'),
 a('coaching','resolve','Resolve assignment',[f('assignment','Assignment','assignment'),f('outcome','Outcome','textarea')]),
 a('coaching','link_event','Reconcile event attendance',[EVENT,WAR]),
 a('alliances','create','Invite allied guilds',[f('name','Alliance name'),f('partners','Partner guilds','guilds')],'owner'),
 a('alliances','respond','Respond to invitation',[f('alliance','Alliance','alliance'),f('response','Response','select',['accepted','declined'])],'owner'),
 a('alliances','leave','Leave alliance',[f('alliance','Alliance','alliance')],'owner'),
 a('live','start','Start live session',[f('title','Session title')]),
 a('live','stop','Save and stop',[SESSION]),
 a('live','link','Link session to war',[SESSION,WAR]),
 a('live','share','Public recap',[SESSION,f('public','Enable public link','checkbox')]),
 a('community','reminder','Set reminder',[f('text','Reminder','textarea'),f('at','Due','datetime-local')],'member'),
 a('community','cancel_reminder','Cancel reminder',[f('reminder','Reminder','reminder')],'member'),
 a('community','ticket','Open ticket',[f('category','Category',default='General'),f('subject','Subject'),f('text','Message','textarea')],'member'),
 a('community','reply','Reply to ticket',[f('ticket','Ticket','ticket'),f('text','Reply','textarea')],'member'),
 a('community','close_ticket','Close ticket',[f('ticket','Ticket','ticket')]),
 a('community','reopen_ticket','Reopen ticket',[f('ticket','Ticket','ticket')]),
 a('community','ticket_preview','Preview Discord ticket channel',[f('ticket','Ticket','ticket')]),
 a('community','apply','Submit application',[f('family','Family name'),f('answers','Tell us about your class, gear and availability','textarea')],'member'),
 a('community','review_application','Review application',[f('application','Application','application'),f('status','Decision','select',['accepted','rejected']),f('review','Review notes','textarea')]),
 a('community','roll','Roll 1–100',[],'member'),a('community','tap','Try enhancement',[],'member'),
 a('community','summary_text','Summarize discussion',[f('text','Discussion','textarea')],'member'),a('community','roast','Friendly roast',[MEM],'member'),
 a('community','welcome','Preview welcome',[MEM,f('message','Welcome message','textarea')]),
 a('community','weekly','Preview weekly summary',[]),a('community','post_event','Preview event card',[EVENT]),a('community','ping_missing','Preview missing responses',[EVENT]),a('community','run_due','Process due reminders / milestones',[]),
 a('integrations','twitch_link','Link Twitch',[MEM,f('handle','Twitch handle (empty to unlink)')],'member'),
 a('integrations','roster_preview','Read roster HTML',[f('html','Official guild page HTML','textarea')]),
 a('integrations','streams_refresh','Refresh from Twitch',[]),
 a('admin','access','Set account role',[f('username','Username'),f('role','Role','select',['owner','admin','member'])],'owner'),
 a('admin','adoption_key','Generate adoption key',[],'owner'),a('admin','adopt','Move Discord server',[f('key','Adoption key'),f('server_id','New Discord server ID')],'owner'),
 a('admin','purge','Purge war statistics',[f('confirmation','Type the guild name to confirm')],'owner'),
]
ACTIONS += [
 a('operations','schedule','Configure schedule',[f('kind','Job','select',['weekly','sync']),f('enabled','Enabled','checkbox',default=True),f('weekday','Weekday (Monday = 0)','number',default=0),f('hour','Hour','number',default=20),f('timezone','Timezone',default='Pacific/Auckland'),f('channel','Notification channel',default='preview')],'owner'),
 a('operations','tick','Run scheduled jobs',[]),a('operations','catchup','Catch up scheduled jobs',[f('days','Lookback days','number',default=14)]),
 a('operations','recruitment_form','Create application form',[f('title','Form title'),f('questions','Questions, one per line','lines'),f('channel','Channel',default='preview')],'owner'),
 a('operations','ticket_category','Create ticket category',[f('name','Category'),f('staff_role','Staff role')],'owner'),
 a('operations','welcome_role','Choose welcome role',[MEM,f('role','Role',default='Raider')],'member'),
 a('operations','challenge','Challenge roll',[f('opponent','Opponent','member')]),
 a('intelligence','character','Identify enemy character',[f('character','Character'),f('family','Family name'),f('class','Class'),f('guild','Enemy guild')]),
 a('intelligence','lookup_backoff','Simulate lookup rate limit',[f('until','Resume at','datetime-local')]),
]

ACTIONS += [a('live','import_log','Import IKUSA text log',[SESSION,f('date','Log date','date'),f('offset','Recorded timezone offset',default='+00:00'),f('text','Combat log text','textarea')])]

ACTIONS += [a('gear','rival','Record rival gear snapshot',[f('name','Rival guild'),f('average_score','Average gear score','number'),f('members','Members sampled','number')])]
ACTIONS += [a('events','share','Share event with alliance',[EVENT,f('enabled','Allies may view','checkbox',default=True)])]

for action in ACTIONS:
    if action['module']=='coaching' and action['action']=='settings':
        for kind in ['kdr','attendance','no_show']:
            action['fields'].extend([f(kind+'_mode',kind.replace('_',' ').title()+' window','select',['wars','days','month','all']),f(kind+'_size','Window size (wars/days)','number',default=7)])

for action in ACTIONS:
    if action['module']=='community' and action['action'] in ['roast','summary_text']:
        action['module']='ai'
        if action['action']=='summary_text':action['action']='summary'

ACTIONS += [
 a('integrations','roster_fetch','Fetch official roster preview',[f('url','Official BDO guild page URL')]),
 a('integrations','roster_source','Configure automatic roster source',[f('url','Verified official BDO guild page URL')],'owner'),
 a('intelligence','queue_lookup','Queue class lookup',[f('character','Character name')]),
 a('intelligence','resolve_queue','Process class lookups',[]),
]

ACTIONS += [a('admin','disband','Disband guild permanently',[f('confirmation','Type the guild name to confirm')],'owner')]

ACTIONS += [a('operations','accept_challenge','Accept roll challenge',[f('challenge','Challenge','challenge')],'member')]
for action in ACTIONS:
    if action['module']=='operations' and action['action']=='challenge':action['role']='member'

ACTIONS += [a('coaching','notify','Preview lead notification',[f('assignment','Assignment','assignment')])]
ACTIONS += [a('privacy','export','Export member data',[MEM],'member'),a('privacy','unlink','Unlink member identity',[MEM],'member'),
            a('privacy','anonymize','Anonymize member',[MEM,f('confirmation','Type the member name')],'member'),
            a('privacy','delete','Delete membership and identifying data',[MEM,f('confirmation','Type the member name')],'member')]
