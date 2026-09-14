'use strict';
const setup=document.querySelector('#setup-form');
if(setup){
 const invite=document.querySelector('#bot-invite');
 const updateInvite=()=>{if(invite){const query=new URLSearchParams({client_id:invite.dataset.client,scope:'bot applications.commands',permissions:String((1<<28)|(1<<16)|(1<<14)|(1<<11)|(1<<10)|(1<<4)),guild_id:setup.elements.server_id.value,disable_guild_select:'true'});invite.href='https://discord.com/oauth2/authorize?'+query;}};
 setup.elements.server_id.addEventListener('change',updateInvite);updateInvite();
 setup.addEventListener('submit',async event=>{
  event.preventDefault();const submit=setup.querySelector('button');if(submit.disabled)return;
  const error=document.querySelector('#setup-error');error.textContent='';submit.disabled=true;submit.textContent='Creating…';setup.setAttribute('aria-busy','true');
  try{const response=await fetch('/onboard/',{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':setup.elements.csrfmiddlewaretoken.value},body:JSON.stringify({name:setup.elements.name.value,region:setup.elements.region.value,server_id:setup.elements.server_id.value})});const result=await response.json();if(!response.ok)throw Error(result.error||'Guild setup failed. Refresh Discord access and retry.');location.assign('/');}
  catch(failure){error.textContent=failure.message;error.focus();submit.disabled=false;submit.textContent='Create guild workspace';setup.removeAttribute('aria-busy');}
 });
}
