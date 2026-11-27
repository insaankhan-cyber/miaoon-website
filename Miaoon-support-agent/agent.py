"""Miaoon Customer Support Agent: a real Claude-powered conversational agent. Stdlib only.
Claude reads the company profile (data/knowledge.md) and the brand voice (voice.md), holds the conversation,
and calls the hand_off_to_team tool when a person is needed."""
import os, re, json, time, urllib.error, urllib.request, hashlib
import store, notify

BASE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
KNOWLEDGE = open(os.path.join(BASE, "data", "knowledge.md"), encoding="utf-8").read()
VOICE = open(os.path.join(BASE, "voice.md"), encoding="utf-8").read()
SYSTEM = VOICE + "\n\n# Miaoon knowledge base\n" + KNOWLEDGE

TOOLS = [{
    "name": "hand_off_to_team",
    "description": "Pass this conversation to the Miaoon team (a human) with full context. Use for leads, complaints, urgent issues, or questions that need a person.",
    "input_schema": {"type": "object", "properties": {
        "kind": {"type": "string", "enum": ["lead", "complaint", "urgent", "support"]},
        "reason": {"type": "string", "description": "Short reason for the handoff"},
        "summary": {"type": "string", "description": "2-3 line summary for the team: what the visitor wants, what was already said, anything urgent"}},
        "required": ["kind", "reason", "summary"]}}]

# Hard safety net: these always reach a human, even if the model were to miss them.
HUMAN = re.compile(r"\b(human|real person|live agent|representative|speak (to|with)|talk (to|with) (a |an |the )?(person|someone|team|agent|human|somebody)|call me|callback|call back)\b", re.I)
COMPLAINT = re.compile(r"\b(refund|complain\w*|unhappy|disappointed|terrible|worst|scam|fraud|cheat\w*|angry|furious|legal|lawyer|sue|court|chargeback|not happy|waste of (my )?money|unacceptable)\b", re.I)
URGENT = re.compile(r"\b(urgent|urgently|asap|emergency)\b", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?<!\d)(\+?\d[\d\s\-]{8,14}\d)(?!\d)")


def trigger(text):
    for kind, rx in (("complaint", COMPLAINT), ("urgent", URGENT), ("support", HUMAN)):
        if rx.search(text):
            return kind
    return None


def find_contact(text):
    m = EMAIL.search(text) or PHONE.search(text)
    return m.group(0).strip() if m else ""


PRESETS = {  # all except anthropic speak the OpenAI-compatible chat API
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY", "gemini-flash-latest"),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", "openai/gpt-oss-20b"),
    "ollama": ("http://localhost:11434/v1", None, "llama3.1"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "meta-llama/llama-3.3-70b-instruct:free"),
}


def provider():
    p = os.getenv("LLM_PROVIDER", "").lower()
    if p in PRESETS or p == "anthropic":
        return p
    return "anthropic"


def _key():
    p = provider()
    if p == "anthropic":
        return os.getenv("ANTHROPIC_API_KEY")
    env = PRESETS[p][1]
    return os.getenv("LLM_API_KEY") or (os.getenv(env) if env else "ollama")


def llm_configured():
    return bool(_key())


def model_name():
    p = provider()
    return os.getenv("LLM_MODEL") or (MODEL if p == "anthropic" else PRESETS[p][2])


def _post(url, headers, body, waits=(2, 4)):
    """POST JSON. Free tiers often answer 429/503 under load, so retry a couple of times with a short wait."""
    # Ensure a custom User-Agent is sent to bypass Cloudflare 1010 block signatures
    headers = dict(headers)
    if "User-Agent" not in headers:
        headers["User-Agent"] = "MiaoonSupportAgent/1.0"

    for i in range(len(waits) + 1):
        try:
            req = urllib.request.Request(url, json.dumps(body).encode(), headers)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            detail = e.read()[:200]
            if e.code in (429, 500, 502, 503, 504) and i < len(waits):
                print(f"LLM busy ({e.code}), retrying in {waits[i]}s")
                time.sleep(waits[i])
                continue
            print("LLM HTTP error:", e.code, detail)
            return None
        except Exception as e:
            print("LLM error:", e)
            return None


def fallback_models():
    env = os.getenv("LLM_FALLBACK_MODELS")
    if env is not None:
        return [m.strip() for m in env.split(",") if m.strip()]
    return ["gemini-flash-lite-latest"] if provider() == "gemini" else []


def _api(system, messages, max_tokens=600, tools=None):
    """Returns Anthropic-style content blocks [{type:text|tool_use,...}] or None on failure."""
    key = _key()
    if not key:
        return None
    if provider() == "anthropic":
        body = {"model": model_name(), "max_tokens": max_tokens, "system": system, "messages": messages}
        if tools:
            body["tools"] = tools
        d = _post("https://api.anthropic.com/v1/messages",
                  {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}, body)
        return None if d is None else d.get("content", [])
    base = os.getenv("LLM_BASE_URL") or PRESETS[provider()][0]
    msgs = [{"role": "system", "content": system}] + messages
    d = None
    for mdl in [model_name()] + fallback_models():  # if the main model is overloaded, try the backup
        body = {"model": mdl, "max_tokens": max(max_tokens, 1500), "messages": msgs}
        if tools:
            body["tools"] = [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}} for t in tools]
        d = _post(base.rstrip("/") + "/chat/completions", {"Authorization": "Bearer " + key, "Content-Type": "application/json"}, body)
        if d is not None:
            break
        print("Model", mdl, "failed; trying next" if mdl != fallback_models()[-1:] and fallback_models() else "failed")
    try:
        m = d["choices"][0]["message"]
    except Exception:
        return None
    blocks = []
    if m.get("content"):
        blocks.append({"type": "text", "text": m["content"]})
    for tc in m.get("tool_calls") or []:
        try:
            args = json.loads(tc["function"].get("arguments") or "{}")
        except Exception:
            args = {}
        blocks.append({"type": "tool_use", "id": tc.get("id", "t"), "name": tc["function"]["name"], "input": args})
    return blocks


def _chat_messages(sid):
    msgs = []
    for role, text in store.history(sid, 20):
        r = "user" if role == "user" else "assistant"
        if msgs and msgs[-1]["role"] == r:
            msgs[-1]["content"] += "\n" + text
        else:
            msgs.append({"role": r, "content": text})
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    return msgs


def call_llm(sid):
    msgs = _chat_messages(sid)
    if not msgs or msgs[-1]["role"] != "user":
        return None
    blocks = _api(SYSTEM, msgs, 600, TOOLS)
    if blocks is None:
        return None
    text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
    tool = next((b.get("input") or {} for b in blocks if b.get("type") == "tool_use" and b.get("name") == "hand_off_to_team"), None)
    return {"reply": text, "handoff": tool}


def summarize(sid):
    hist = store.history(sid, 14)
    blocks = _api("Summarise this customer chat for a support teammate in 2-3 plain lines: what they want, what was already answered, anything urgent. No preamble.",
                  [{"role": "user", "content": "\n".join(f"{r}: {t}" for r, t in hist)}], 200)
    txt = "".join(b.get("text", "") for b in (blocks or []) if b.get("type") == "text").strip()
    return txt or "Customer said: " + " | ".join(t for r, t in hist if r == "user")[-500:]


MSG = {
    "lead": "Good, I'll pass this to the Miaoon team so they can come back with the right next step.",
    "complaint": "I've passed this to the team right away, along with our full chat, so you won't need to explain it again.",
    "urgent": "Understood. I've flagged this as urgent for the team, with our full chat attached.",
    "support": "That one needs a person. I've shared our chat with the team so you won't have to repeat yourself.",
}


def _reply(sid, text):
    store.add_msg(sid, "bot", text)
    return {"reply": text, "status": store.conv(sid)["status"], "last_id": store.last_id(sid)}


# CRM pilot: explicit visitor permission, sales handoffs only.
def crm_enabled():
    return os.getenv("CHATBOT_CAPTURE_ENABLED", "").lower() == "true" and len(os.getenv("LEAD_CAPTURE_API_KEY", "").strip()) >= 32


def crm_sales_contact(sid):
    if not crm_enabled():
        return ""
    row = store._run("select contact from handoffs where sid=? and status='open' and kind='lead' order by id desc limit 1", (sid,), "one")
    return (row["contact"] or "").strip() if row else ""


def crm_prompt(sid):
    if not crm_sales_contact(sid):
        return ""
    return " To save your contact details in our sales CRM for this enquiry, reply YES CRM. Privacy policy: https://www.miaoon.in/privacy-policy.html. This is optional."


def crm_capture(sid):
    contact = crm_sales_contact(sid)
    if not contact:
        return None
    email = contact.lower() if EMAIL.fullmatch(contact) else ""
    phone = re.sub(r"[ ()-]", "", contact) if not email else ""
    if not email and not re.fullmatch(r"\+?[0-9]{7,15}", phone):
        return "I couldn't validate your contact details for CRM submission. Our support team still has your enquiry."
    payload = {"event_id": "chatbot-" + hashlib.sha256(sid.encode()).hexdigest(),
               "source": "chatbot", "full_name": "Chatbot enquiry",
               "email": email or None, "phone": phone or None,
               "message": "Visitor requested sales follow-up via Miaoon chatbot.",
               "privacy_acknowledged": True}
    req = urllib.request.Request("https://miaoon-voice-agent.onrender.com/api/leads/capture",
        data=json.dumps(payload).encode(), headers={"Authorization": "Bearer " + os.getenv("LEAD_CAPTURE_API_KEY", "").strip(),
        "Content-Type": "application/json", "User-Agent": "MiaoonSupportAgent/1.0"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.load(response)
        if result.get("status") not in ("created", "duplicate") or not result.get("lead_id"):
            raise ValueError("Unconfirmed capture")
        return "Thank you. Your sales enquiry is saved in our CRM for the team to follow up."
    except Exception as exc:
        print("Chatbot CRM capture unconfirmed:", type(exc).__name__)
        return "CRM submission could not be confirmed. Your support enquiry is still saved. Reply YES CRM again to retry."


def escalate(sid, kind, reason, summary=None, lead_in=""):
    kind = kind if kind in MSG else "support"
    c = store.conv(sid)
    hid = store.add_handoff(sid, kind, reason, summary or summarize(sid), c["contact"])
    store.set_conv(sid, status="human")
    h = next(x for x in store.handoffs() if x["id"] == hid)
    notify.handoff(h, store.history(sid, 20))
    tail = f" They'll reach you on {c['contact']}." if c["contact"] else " What's the best email or WhatsApp number to reach you on?"
    return _reply(sid, (lead_in or MSG[kind]) + tail + (crm_prompt(sid) if kind == "lead" else ""))


def respond(sid, text):
    text = re.sub(r"[\x00-\x08\x0b-\x1f]", "", text).strip()[:1000]
    c = store.conv(sid)
    store.add_msg(sid, "user", text)
    if text.casefold() == "yes crm" and any(role == "bot" and "reply YES CRM" in msg for role, msg in store.history(sid, 20)):
        result = crm_capture(sid)
        if result is not None:
            return _reply(sid, result)
    contact = find_contact(text)
    if contact and not c["contact"]:
        store.set_conv(sid, contact=contact)
        store.set_handoff_contact(sid, contact)
        if c["status"] == "human":
            notify.contact_update(sid, contact)
            return _reply(sid, f"Thanks. I've passed {contact} to the team and they'll reach out there." + crm_prompt(sid))
    if c["status"] == "human":
        return _reply(sid, "Noted. I've added that to your case for the team.")
    kind = trigger(text)
    if kind:
        return escalate(sid, kind, f"Matched {kind} keywords")
    out = call_llm(sid)
    if out is None:
        return escalate(sid, "support", "AI service unavailable (check API key or rate limit)",
                        lead_in="I'm having trouble answering right now, so I've passed this to the team.")
    if out["handoff"]:
        h = out["handoff"]
        return escalate(sid, h.get("kind", "support"), h.get("reason") or "Agent chose to hand off", h.get("summary"), out["reply"])
    return _reply(sid, out["reply"] or "Could you tell me a bit more about what you need?")