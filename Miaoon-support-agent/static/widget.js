/* Miaoon support chat widget. Embed: <script src="https://YOUR-DOMAIN/widget.js" defer></script> */
(function () {
  var me = document.currentScript, API = me && me.src ? new URL(me.src).origin : "";
  var sid = null;
  try { sid = localStorage.getItem("mq_sid"); } catch (e) {}
  if (!sid) { sid = "s" + Math.random().toString(36).slice(2) + Date.now().toString(36); try { localStorage.setItem("mq_sid", sid); } catch (e) {} }
  var last = 0, human = false, busy = false, loaded = false;
  var host = document.createElement("div"), root = host.attachShadow({ mode: "open" });
  root.innerHTML = '<style>' +
    ':host{all:initial}*{box-sizing:border-box;font-family:system-ui,-apple-system,"Segoe UI",sans-serif}' +
    '.fab{position:fixed;right:20px;bottom:20px;width:56px;height:56px;border-radius:50%;border:1px solid #2a2a2a;background:#0a0a0a;color:#e7d9bd;cursor:pointer;display:grid;place-items:center;z-index:2147483000}' +
    '.fab:focus-visible,button:focus-visible,input:focus-visible{outline:2px solid #e7d9bd;outline-offset:2px}' +
    '.box{position:fixed;right:20px;bottom:90px;width:min(380px,calc(100vw - 24px));height:min(560px,calc(100vh - 110px));background:#0a0a0a;color:#f2efe9;border:1px solid #2a2a2a;border-radius:14px;display:none;flex-direction:column;overflow:hidden;z-index:2147483000;box-shadow:0 12px 40px rgba(0,0,0,.45)}' +
    '.box.on{display:flex}' +
    '.hd{padding:14px 16px;border-bottom:1px solid #2a2a2a;display:flex;justify-content:space-between;align-items:center}.hd b{font-size:15px}.hd small{color:#9a968e;display:block;font-size:12px;margin-top:2px}' +
    '.hd-actions{display:flex;gap:10px;align-items:center}' +
    '.restart{background:none;border:1px solid #2a2a2a;color:#9a968e;font-size:12px;padding:3px 7px;border-radius:6px;cursor:pointer}' +
    '.restart:hover{color:#f2efe9;border-color:#e7d9bd}' +
    '.x{background:none;border:0;color:#9a968e;font-size:22px;cursor:pointer;line-height:1}' +
    '.log{flex:1;overflow:auto;padding:14px;display:flex;flex-direction:column;gap:10px}' +
    '.m{max-width:86%;padding:9px 12px;border-radius:12px;font-size:14px;line-height:1.5;white-space:pre-wrap;word-wrap:break-word}' +
    '.bot{background:#161616;border:1px solid #2a2a2a;align-self:flex-start}.user{background:#e7d9bd;color:#0a0a0a;align-self:flex-end}' +
    '.team{background:#161616;border:1px solid #e7d9bd;align-self:flex-start}.team i{display:block;font-size:11px;color:#e7d9bd;font-style:normal;margin-bottom:2px}' +
    '.chips{display:flex;flex-wrap:wrap;gap:6px}.chip{background:none;border:1px solid #2a2a2a;color:#f2efe9;border-radius:999px;padding:6px 11px;font-size:13px;cursor:pointer}.chip:hover{border-color:#e7d9bd}' +
    '.dots{color:#9a968e;font-size:13px;align-self:flex-start}' +
    '.ft{border-top:1px solid #2a2a2a;padding:10px;display:flex;gap:8px}.ft input{flex:1;background:#161616;border:1px solid #2a2a2a;border-radius:9px;color:#f2efe9;padding:10px 12px;font-size:14px}' +
    '.ft button{background:#e7d9bd;color:#0a0a0a;border:0;border-radius:9px;padding:0 14px;font-weight:600;cursor:pointer}' +
    '.note{color:#6f6b64;font-size:11px;text-align:center;padding:0 10px 8px}' +
    '@media (prefers-reduced-motion:no-preference){.box.on{animation:up .18s ease-out}@keyframes up{from{transform:translateY(8px);opacity:0}}}' +
    '</style>' +
    '<button class="fab" aria-label="Open Miaoon chat"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/></svg></button>' +
    '<section class="box" role="dialog" aria-label="Miaoon support chat"><div class="hd"><div><b>Miaoon</b><small>AI assistant. Complex questions go to our team.</small></div><div class="hd-actions"><button class="restart" title="Restart Chat">Restart</button><button class="x" aria-label="Close chat">&times;</button></div></div>' +
    '<div class="log" role="log" aria-live="polite"></div>' +
    '<form class="ft"><input maxlength="1000" placeholder="Type your question" aria-label="Your message" autocomplete="off"><button>Send</button></form>' +
    '<div class="note">Chats are saved so our team can follow up.</div></section>';
  document.body.appendChild(host);
  var $ = function (s) { return root.querySelector(s); };
  var box = $(".box"), log = $(".log"), input = $("input");

  function add(role, text) {
    var d = document.createElement("div"); d.className = "m " + role;
    if (role === "team") { var l = document.createElement("i"); l.textContent = "Miaoon team"; d.appendChild(l); }
    d.appendChild(document.createTextNode(text)); log.appendChild(d); log.scrollTop = log.scrollHeight;
  }
  function chips() {
    var w = document.createElement("div"); w.className = "chips";
    ["What do you do?", "Tell me about AI agents", "Talk to the team"].forEach(function (t) {
      var b = document.createElement("button"); b.type = "button"; b.className = "chip"; b.textContent = t;
      b.onclick = function () { w.remove(); send(t); }; w.appendChild(b);
    }); log.appendChild(w);
  }
  function loadChat() {
    log.innerHTML = ""; last = 0; human = false;
    fetch(API + "/api/history?sid=" + sid).then(function (r) { return r.json(); }).then(function (d) {
      if (d.messages && d.messages.length) {
        d.messages.forEach(function (m) { add(m.role === "user" ? "user" : m.role === "human" ? "team" : "bot", m.text); last = Math.max(last, m.id); });
        human = d.status === "human";
      } else { add("bot", "Hi, I'm Miaoon's AI assistant. Ask me about our services, AI agents or past work, or ask for the team any time."); chips(); }
    }).catch(function () { add("bot", "Hi, I'm Miaoon's AI assistant. How can I help?"); chips(); });
  }
  function open() {
    box.classList.add("on"); input.focus();
    if (loaded) return; loaded = true;
    loadChat();
  }
  function restartChat() {
    sid = "s" + Math.random().toString(36).slice(2) + Date.now().toString(36);
    try { localStorage.setItem("mq_sid", sid); } catch (e) {}
    loadChat();
  }
  function send(text) {
    text = (text || "").trim(); if (!text || busy) return;
    busy = true; add("user", text); input.value = "";
    var t = document.createElement("div"); t.className = "dots"; t.textContent = "Typing…"; log.appendChild(t); log.scrollTop = log.scrollHeight;
    fetch(API + "/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sid: sid, message: text }) })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (x) {
        t.remove();
        if (!x.ok) { add("bot", x.d.error || "Something went wrong. You can also email hello@miaoon.in."); return; }
        add("bot", x.d.reply); last = Math.max(last, x.d.last_id || 0); human = x.d.status === "human";
      })
      .catch(function () { t.remove(); add("bot", "I can't reach the assistant right now. Please email hello@miaoon.in."); })
      .then(function () { busy = false; });
  }
  setInterval(function () {
    if (!human || !loaded) return;
    fetch(API + "/api/poll?sid=" + sid + "&after=" + last).then(function (r) { return r.json(); }).then(function (d) {
      (d.messages || []).forEach(function (m) { add("team", m.text); last = Math.max(last, m.id); });
      if (d.status !== "human") human = false;
    }).catch(function () {});
  }, 5000);
  $(".fab").onclick = function () { box.classList.contains("on") ? box.classList.remove("on") : open(); };
  $(".x").onclick = function () { box.classList.remove("on"); };
  $(".restart").onclick = function () { restartChat(); };
  $(".ft").onsubmit = function (e) { e.preventDefault(); send(input.value); };
})();