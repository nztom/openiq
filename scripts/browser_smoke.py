"""Exercise real browser workflows in an isolated, disposable local guild."""
import os,uuid
from pathlib import Path
from playwright.sync_api import sync_playwright
base=os.getenv('OPENIQ_URL','http://127.0.0.1:8765')
artifacts=Path(os.getenv('OPENIQ_BROWSER_ARTIFACTS','docs'));artifacts.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(base+'/')
    page.get_by_label('Username:').fill('demo');page.get_by_label('Password:').fill(os.getenv('DEMO_PASSWORD','prototype-local-2026'));page.get_by_role('button',name='Sign in',exact=True).click()
    page.wait_for_selector('.card')
    for name in ['Members','History','Analytics','My Stats','Performance','Signups','Gear','Live War','Alliance','Streams','Community','Settings']:
        page.locator('nav').get_by_role('button',name=name,exact=True).click()
        assert page.locator('#title').inner_text()==name
        assert not page.locator('#error').is_visible()
    page.locator('nav').get_by_role('button',name='Members',exact=True).click()
    assert page.title()=='OpenIQ'
    page.screenshot(path=str(artifacts/'dashboard.png'),full_page=True)
    page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(artifacts/'mobile.png'),full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),'Mobile overflow'
    page.set_viewport_size({'width':1440,'height':1000})
    test_guild='UITest-'+uuid.uuid4().hex[:8]
    created=page.evaluate('''async name => {
      const r=await fetch('/onboard/',{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:JSON.stringify({name,names:['TestAlpha','TestBeta']})});
      if(!r.ok)throw Error(await r.text());return await r.json();
    }''',test_guild)
    try:
        page.reload();page.wait_for_selector('#guild');page.locator('#guild').select_option(str(created['id']))
        page.wait_for_function('state && state.guild.id===Number(document.querySelector("#guild").value)')
        page.get_by_role('button',name='Add member',exact=True).click();page.get_by_label('Family name',exact=True).fill('TestGamma');page.get_by_role('button',name='Save',exact=True).click();page.wait_for_function('!document.querySelector("#dialog").open || document.querySelector("#form-error").textContent');assert not page.locator('#dialog').is_visible(), page.locator('#form-error').inner_text()
        page.get_by_placeholder('Search family name…').fill('TestGamma');assert page.locator('#panel').get_by_role('heading',name='TestGamma').count()==1
        page.get_by_placeholder('Search family name…').fill('')
        page.locator('nav').get_by_role('button',name='History',exact=True).click()
        page.locator('.actions-menu').select_option(label='Record war')
        page.get_by_label('Node / castle',exact=True).fill('Calpheon Castle');page.get_by_label('Opposing guilds',exact=True).fill('Iron Vow');page.get_by_label('Capped',exact=True).check();page.get_by_label('Cap details',exact=True).fill('Tier 2 · 550 GS')
        page.get_by_label('Kills',exact=True).fill('20');page.get_by_label('Deaths',exact=True).fill('4');page.get_by_label('War class',exact=True).fill('Warrior')
        page.get_by_role('button',name='Save',exact=True).click();page.wait_for_function('!document.querySelector("#dialog").open || document.querySelector("#form-error").textContent');assert not page.locator('#dialog').is_visible(), page.locator('#form-error').inner_text()
        assert page.locator('#panel td').filter(has_text='20').count()>0
        assert page.locator('#panel').get_by_text('Calpheon Castle',exact=False).count()>0
        page.get_by_role('button',name='Details',exact=True).click()
        page.locator('[data-detail-kills]').fill('24');page.get_by_role('button',name='Save row',exact=True).click()
        page.wait_for_function("state.records.war[0].participants[0].kills===24")
        assert page.locator('[data-detail-kills]').input_value()=='24'
        page.get_by_label('Sort players',exact=True).select_option('name')
        page.get_by_role('button',name='Close',exact=True).click()
        page.get_by_role('button',name='Review scores',exact=True).click()
        page.get_by_label('Scores (CSV: name,kills,deaths)',exact=True).fill('name,kills,deaths\nTestGamma,8,2\nNoRosterMatch,3,1')
        page.get_by_role('button',name='Save',exact=True).click();page.wait_for_function('!document.querySelector("#dialog").open')
        page.get_by_role('button',name='Finalize score review',exact=True).click()
        unmatched=page.get_by_label('Match extracted name NoRosterMatch',exact=True)
        assert unmatched.input_value()=='' and unmatched.get_attribute('required') is not None
        unmatched.select_option(label='TestBeta')
        page.get_by_role('button',name='Save',exact=True).click();page.wait_for_function('!document.querySelector("#dialog").open || document.querySelector("#form-error").textContent')
        assert not page.locator('#dialog').is_visible(),page.locator('#form-error').inner_text()
        assert page.evaluate("state.records.war.length===2 && state.records.import[0].status==='finalized'")
        page.get_by_role('button',name='Read screenshots',exact=True).click()
        page.locator('#images').set_input_files(['fixtures/ocr/war-names.png','fixtures/ocr/war-scores.png'])
        page.get_by_role('button',name='Read images',exact=True).click();page.get_by_role('button',name='Verify scores',exact=True).wait_for()
        page.get_by_role('button',name='Verify scores',exact=True).click();page.get_by_role('button',name='Save',exact=True).click()
        page.wait_for_function("state.records.war.length===3 && state.records.import.filter(i=>i.status==='finalized').length===2")
        page.locator('nav').get_by_role('button',name='Analytics',exact=True).click()
        assert page.get_by_role('img',name='K/D across recorded wars',exact=True).count()==1
        assert page.locator('#class-bubbles [data-bubble]').count()>0
        page.locator('[data-priority-toggle]').first.uncheck()
        assert page.locator('[data-priority-line]').first.evaluate("node=>node.style.display")=='none'
        page.locator('nav').get_by_role('button',name='Signups',exact=True).click();page.get_by_role('button',name='Create event',exact=True).click();page.get_by_label('Title',exact=True).fill('UI test event');page.get_by_role('button',name='Save',exact=True).click();page.wait_for_function('!document.querySelector("#dialog").open || document.querySelector("#form-error").textContent');assert not page.locator('#dialog').is_visible(), page.locator('#form-error').inner_text()
        assert page.get_by_role('heading',name='UI test event',exact=True).count()==1
        page.locator('nav').get_by_role('button',name='Gear',exact=True).click();page.get_by_role('button',name='Update gear',exact=True).click()
        for label,value in [('AP','300'),('Awakening AP','302'),('DP','400')]:page.get_by_label(label,exact=True).fill(value)
        page.get_by_role('button',name='Save',exact=True).click();page.wait_for_function('!document.querySelector("#dialog").open || document.querySelector("#form-error").textContent');assert not page.locator('#dialog').is_visible(), page.locator('#form-error').inner_text();assert page.locator('#panel strong').filter(has_text='702').count()==1
        session=page.evaluate("async()=>await call('live','start',{title:'UI test fight'})")
        page.evaluate("""async session=>await call('live','ingest',{session:session.id,events:[
          {id:'ui-live-1',at:'2026-09-11T06:00:00Z',kind:'kill',player:'TestAlpha',target:'EnemyOne',guild:'Iron Vow',class:'Warrior',family:'EnemyFamily'},
          {id:'ui-live-2',at:'2026-09-11T06:00:20Z',kind:'death',player:'EnemyTwo',target:'TestBeta',guild:'Moonfall',class:'Shai',family:'OtherFamily'}
        ]})""",session)
        page.locator('nav').get_by_role('button',name='Live War',exact=True).click()
        assert page.locator('#live-totals').inner_text().startswith('1 kills · 1 deaths')
        page.get_by_label('Enemy guild',exact=True).select_option('Iron Vow')
        assert page.locator('#live-totals').inner_text().startswith('1 kills · 0 deaths')
        assert page.locator('#feed .feed').count()==1
        page.locator('#replay').fill('0')
        assert page.locator('#live-totals').inner_text().startswith('0 kills · 0 deaths')
        assert page.locator('#feed .feed').count()==0
        page.locator('nav').get_by_role('button',name='History',exact=True).click()
        page.get_by_role('button',name='Link signup event',exact=True).first.click()
        page.locator('#dialog [data-field="event"]').select_option(label='UI test event')
        page.get_by_role('button',name='Save',exact=True).click();page.wait_for_function('!document.querySelector("#dialog").open')
        page.get_by_role('button',name='Link live session',exact=True).first.click()
        page.locator('#dialog [data-field="session"]').select_option(label='UI test fight')
        page.get_by_role('button',name='Save',exact=True).click();page.wait_for_function('!document.querySelector("#dialog").open')
        assert page.locator('#panel').get_by_text('UI test event',exact=False).count()>0
        assert page.locator('#panel').get_by_text('UI test fight (live)',exact=False).count()>0
        page.evaluate("""async()=>await call('integrations','streams_fixture',{streams:[
          {handle:'alpha_stream',title:'Node war',viewers:50,category:'Black Desert',partner:true},
          {handle:'beta_stream',title:'Variety night',viewers:10,category:'Variety',partner:false}
        ]})""")
        page.locator('nav').get_by_role('button',name='Streams',exact=True).click()
        page.get_by_label('Stream category',exact=True).select_option('Black Desert')
        assert page.locator('#stream-grid [data-stream]').count()==1
        page.get_by_role('button',name='Watch here',exact=True).click()
        assert 'channel=alpha_stream' in page.locator('.stream-player iframe').get_attribute('src')
        page.get_by_role('button',name='Close player',exact=True).click()
        assert page.get_by_label('Stream category',exact=True).count()==1
        lifecycle=page.evaluate("""async()=>{
          const alpha=records('member').find(m=>m.name==='TestAlpha'),beta=records('member').find(m=>m.name==='TestBeta');
          const event=await call('events','save',{title:'Lifecycle war',type:'Node',at:'2026-09-12T08:00:00Z',timezone:'Pacific/Auckland',teams:[{name:'Main',capacity:10}]});
          await call('events','signup',{event:event.id,member:alpha.id,team:'Main'});
          const session=await call('live','start',{title:'Lifecycle capture'});
          await call('live','ingest',{session:session.id,events:[{id:'lifecycle-kill',at:'2026-09-12T08:10:00Z',kind:'kill',player:'TestAlpha',target:'Enemy',guild:'Rival',class:'Warrior'}]});
          const draft=await call('wars','review',{rows:[{name:'TestAlpha',kills:12,deaths:2},{name:'TestBeta',kills:4,deaths:3}]});
          const war=await call('wars','finalize',{import:draft.id,date:'2026-09-12',type:'Node',result:'Win',location:'Lifecycle Node',participants:[{member:alpha.id,kills:12,deaths:2},{member:beta.id,kills:4,deaths:3}]});
          await call('coaching','link_event',{event:event.id,war:war.id});await call('live','link',{session:session.id,war:war.id});
          return {event:event.id,session:session.id,war:war.id,alpha:alpha.id};
        }""")
        assert page.evaluate("""flow=>{
          const event=records('event').find(e=>e.id===flow.event),session=records('session').find(s=>s.id===flow.session),war=records('war').find(w=>w.id===flow.war),member=state.analytics.members.find(m=>m.id===flow.alpha);
          return event.war===flow.war&&session.war===flow.war&&war.session===flow.session&&member.calendar.some(day=>day.war===flow.war&&day.present)&&state.analytics.timeline.some(day=>day.war===flow.war&&day.kills===16);
        }""",lifecycle)
        page.locator('nav').get_by_role('button',name='Analytics',exact=True).click();assert page.get_by_role('img',name='K/D across recorded wars',exact=True).count()==1
        page.evaluate("async()=>await call('admin','settings',{config:{channels:{events:'789'},weekly:{weekday:2,hour:18,timezone:'UTC'}}})")
        page.locator('nav').get_by_role('button',name='Settings',exact=True).click()
        page.get_by_role('button',name='Configure guild',exact=True).click();page.get_by_label('Bot channel',exact=True).fill('123')
        page.get_by_role('button',name='Save',exact=True).click();page.wait_for_function('!document.querySelector("#dialog").open')
        assert page.evaluate("state.guild.config.channels.events==='789' && state.guild.config.weekly.hour===18")
        page.get_by_role('button',name='Configure tickets',exact=True).click()
        for label,value in [('Bot user ID','200'),('Ticket staff role ID','300'),('Parent category ID (optional)','400')]:page.get_by_label(label,exact=True).fill(value)
        page.get_by_role('button',name='Save',exact=True).click();page.wait_for_function('!document.querySelector("#dialog").open')
        assert page.evaluate("state.guild.config.tickets.staff_role==='300'")
        page.get_by_role('button',name='Configure welcome',exact=True).click();page.get_by_label('Role label,Discord role ID per line',exact=True).fill('Raider,500')
        page.get_by_role('button',name='Save',exact=True).click();page.wait_for_function('!document.querySelector("#dialog").open')
        assert page.evaluate("state.guild.config.welcome.role_ids.Raider==='500'")
        page.get_by_role('button',name='Configure roles',exact=True).click();page.get_by_label('admin role IDs, one per line',exact=True).fill('600')
        page.get_by_role('button',name='Save',exact=True).click();page.wait_for_function('!document.querySelector("#dialog").open')
        assert page.evaluate("state.guild.config.roles.admin[0]==='600'")
        parsed=page.evaluate("async()=>await parseIkusaText('[23:59:58] Alpha has killed Enemy from Rival\\n[00:00:02] Alpha died to Enemy from Rival','2026-09-11','+12:00')")
        assert len(parsed)==2 and parsed[1]['player']=='Enemy'
        assert not errors,errors
        print('Browser passed: OpenIQ branding, 12 tabs, mobile layout, member search/create, war entry/inline edit, CSV and real-OCR score finalization, direct war/event/session linking, complete signup/capture/review/reconciliation/analytics lifecycle, analytics overlays, event creation, gear update, scoped live replay/debrief, stream filtering/player, settings preservation, ticket/welcome/access role configuration, browser IKUSA parsing, no JavaScript errors.')
    except Exception:
        print('FORM ERROR:',page.locator('#form-error').inner_text())
        print('INVALID:',page.evaluate('Array.from(document.querySelectorAll("#action-form :invalid")).map(e=>({tag:e.tagName,type:e.type,value:e.value,message:e.validationMessage}))'))
        print('JS ERRORS:',errors)
        raise
    finally:
        page.evaluate('''async ({id,name})=>{const r=await fetch(`/api/${id}/admin/disband/`,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:JSON.stringify({confirmation:name})});if(!r.ok)throw Error(await r.text());}''',{'id':created['id'],'name':test_guild})
        browser.close()
