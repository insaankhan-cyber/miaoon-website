(()=>{
  'use strict';
  if(document.getElementById('miaoon-launcher'))return;
  const API=new URL(document.currentScript?.src||'https://miaoon-support-agent.onrender.com/widget.js').origin;
  const sessionKey='miaoon-support-sid';
  let sid;
  try{sid=sessionStorage.getItem(sessionKey);if(!/^[A-Za-z0-9_-]{8,64}$/.test(sid||'')){sid='miaoon_'+crypto.randomUUID().replaceAll('-','');sessionStorage.setItem(sessionKey,sid)}}catch{sid='miaoon_'+Math.random().toString(36).slice(2,14)}
  const css=document.createElement('style');css.textContent=`
    #miaoon-launcher{position:fixed;bottom:22px;right:22px;width:62px;height:62px;border-radius:50%;border:0;z-index:2147483645;background:#181818;color:#fff;font-size:27px;box-shadow:0 8px 30px #0004;cursor:pointer}
    #miaoon-chat{position:fixed;bottom:98px;right:22px;width:min(380px,calc(100vw - 24px));height:min(550px,calc(100dvh - 120px));display:none;flex-direction:column;overflow:hidden;border-radius:18px;z-index:2147483645;background:#fff;color:#222;box-shadow:0 10px 40px #0003;font:14px/1.5 Arial,Helvetica,sans-serif}
    #miaoon-chat *{box-sizing:border-box}#miaoon-head{background:#181818;color:white;padding:16px 18px;font-weight:bold;font-size:17px;display:flex;align-items:center;justify-content:space-between}#miaoon-close{background:none;border:0;color:white;font-size:22px;cursor:pointer}
    #miaoon-messages{flex:1;min-height:0;overflow-y:auto;padding:15px;display:flex;flex-direction:column;gap:10px}.miaoon-msg{max-width:88%;padding:10px 13px;white-space:pre-wrap;overflow-wrap:anywhere;border-radius:13px}.miaoon-msg.user{align-self:flex-end;background:#191919;color:white}.miaoon-msg.bot,.miaoon-msg.human{align-self:flex-start;background:#f2f1f0}.miaoon-msg.human{border-left:3px solid #e96855}
    #miaoon-form{display:flex;gap:8px;border-top:1px solid #eee;padding:12px}#miaoon-input{flex:1;min-width:0;border:1px solid #ddd;border-radius:9px;padding:10px 12px;font:inherit}#miaoon-send{border:0;border-radius:9px;padding:10px 14px;color:white;background:#e96855;font:inherit;cursor:pointer}#miaoon-send:disabled{opacity:.5}#miaoon-foot{font-size:10px;color:#777;text-align:center;padding:0 0 8px}`;document.head.append(css);
  const launch=document.createElement('button');launch.id='miaoon-launcher';launch.type='button';launch.textContent='✦';launch.setAttribute('aria-label','Open Miaoon support chat');
  const chat=document.createElement('section');chat.id='miaoon-chat';chat.setAttribute('aria-label','Miaoon support chat');chat.innerHTML='<div id="miaoon-head"><span>✦ Miaoon AI & Live Support</span><button id="miaoon-close" type="button" aria-label="Close chat">×</button></div><div id="miaoon-messages" aria-live="polite"></div><form id="miaoon-form"><input id="miaoon-input" aria-label="Your message" maxlength="1000" placeholder="How can we help?" required><button id="miaoon-send" type="submit">Send</button></form><div id="miaoon-foot">AI assistant · Live team when available</div>';
  document.body.append(launch,chat);
  const $=s=>chat.querySelector(s),messages=$('#miaoon-messages');let open=false,last=0,busy=false;
  function add(text,role){const d=document.createElement('div');d.className='miaoon-msg '+role;d.textContent=text;messages.append(d);messages.scrollTop=messages.scrollHeight;return d}
  function toggle(v){open=v;chat.style.display=v?'flex':'none';launch.textContent=v?'×':'✦';launch.setAttribute('aria-label',v?'Close Miaoon support chat':'Open Miaoon support chat');if(v)$('#miaoon-input').focus()}
  launch.onclick=()=>toggle(!open);$('#miaoon-close').onclick=()=>toggle(false);
  function record(m){if(!m||!m.id||m.id<=last)return;last=m.id;add(m.text,m.role==='user'?'user':m.role==='human'?'human':'bot')}
  async function history(){try{const r=await fetch(`${API}/api/history?sid=${encodeURIComponent(sid)}`,{cache:'no-store'});if(!r.ok)return;const d=await r.json();for(const m of d.messages||[])record(m)}catch{}}
  async function poll(){try{const r=await fetch(`${API}/api/poll?sid=${encodeURIComponent(sid)}&after=${last}`,{cache:'no-store'});if(!r.ok)return;const d=await r.json();for(const m of d.messages||[])record(m)}catch{}}
  $('#miaoon-form').onsubmit=async e=>{e.preventDefault();if(busy)return;const input=$('#miaoon-input'),msg=input.value.trim();if(!msg)return;busy=true;$('#miaoon-send').disabled=true;input.value='';const before=last;add(msg,'user');let pending=add('Thinking…','bot');try{const r=await fetch(`${API}/api/chat`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sid,message:msg})});if(!r.ok)throw Error('HTTP '+r.status);const d=await r.json();pending.textContent=d.reply||'Your message has been received.'; // Refresh IDs to prevent duplicate bot messages.
    const h=await fetch(`${API}/api/history?sid=${encodeURIComponent(sid)}`,{cache:'no-store'});if(h.ok){const x=await h.json();last=Math.max(last,...(x.messages||[]).map(m=>m.id||0));}
  }catch{pending.textContent='Unable to connect. Please email hello@miaoon.in.'}finally{busy=false;$('#miaoon-send').disabled=false;messages.scrollTop=messages.scrollHeight}};
  add('Hi! I’m Miaoon’s assistant. Ask me anything, or type “human” to speak with our team.','bot');
  history().then(()=>{});setInterval(()=>{if(open&&!busy)poll()},4500);
})();
