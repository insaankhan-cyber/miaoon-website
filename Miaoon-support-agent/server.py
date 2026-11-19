"""Miaoon support agent server. Stdlib only: `python server.py`"""
import os, re, json, time, hmac
from collections import defaultdict, deque
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

BASE = os.path.dirname(os.path.abspath(__file__))


def load_env(path=os.path.join(BASE, ".env")):
    if os.path.exists(path):
        for ln in open(path, encoding="utf-8"):
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()
import agent, store  # noqa: E402  (after env is loaded)

ALLOWED = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "https://miaoon.in,https://www.miaoon.in,http://localhost:8000").split(",") if o.strip()]
RATE = int(os.getenv("RATE_PER_MIN", "20"))
_hits = defaultdict(deque)
SID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
STATIC = {"/": ("index.html", "text/html"), "/widget.js": ("widget.js", "application/javascript"), "/admin": ("admin.html", "text/html")}


def limited(ip):
    q, now = _hits[ip], time.time()
    while q and now - q[0] > 60:
        q.popleft()
    q.append(now)
    return len(q) > RATE


class H(BaseHTTPRequestHandler):
    server_version = "MiaoonAgent"

    def log_message(self, *a):
        pass

    def _cors(self):
        o = self.headers.get("Origin")
        if o and ("*" in ALLOWED or o in ALLOWED):
            self.send_header("Access-Control-Allow-Origin", o)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Admin-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def _ip(self):
        if os.getenv("TRUST_PROXY") == "1":
            return (self.headers.get("X-Forwarded-For") or "").split(",")[0].strip() or self.client_address[0]
        return self.client_address[0]

    def _admin(self):
        tok = os.getenv("ADMIN_TOKEN", "")
        if not tok:
            self._send(503, {"error": "Set ADMIN_TOKEN to enable the dashboard"})
            return False
        if not hmac.compare_digest(self.headers.get("X-Admin-Token", ""), tok):
            self._send(401, {"error": "Wrong token"})
            return False
        return True

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 20000:
            raise ValueError("too large")
        return json.loads(self.rfile.read(n) or b"{}")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path in STATIC:
            f, ct = STATIC[u.path]
            with open(os.path.join(BASE, "static", f), "rb") as fh:
                return self._send(200, fh.read(), ct)
        if u.path == "/health":
            return self._send(200, {"ok": True, "llm": agent.llm_configured(), "provider": agent.provider(), "model": agent.model_name()})
        if u.path in ("/api/history", "/api/poll"):
            sid = q.get("sid", "")
            if not SID.match(sid):
                return self._send(400, {"error": "bad sid"})
            if u.path == "/api/history":
                return self._send(200, {"status": store.conv(sid)["status"],
                                        "messages": store.messages(sid, 0)})
            return self._send(200, {"status": store.conv(sid)["status"],
                                    "messages": store.messages(sid, int(q.get("after", 0) or 0), ("human",))})
        if u.path.startswith("/api/admin/"):
            if not self._admin():
                return
            if u.path == "/api/admin/handoffs":
                return self._send(200, {"handoffs": store.handoffs(q.get("status"))})
            if u.path == "/api/admin/conv" and SID.match(q.get("sid", "")):
                return self._send(200, {"messages": store.messages(q["sid"], 0), "contact": store.conv(q["sid"])["contact"]})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        u = urlparse(self.path)
        try:
            b = self._body()
        except Exception:
            return self._send(400, {"error": "bad request"})
        sid = str(b.get("sid") or b.get("session_id") or "")
        if u.path == "/api/chat":
            msg = str(b.get("message", "")).strip()
            if not SID.match(sid) or not msg:
                return self._send(400, {"error": "sid and message required"})
            if limited(self._ip()):
                return self._send(429, {"error": "Slow down a little and try again in a minute."})
            return self._send(200, agent.respond(sid, msg))
        if u.path in ("/api/admin/reply", "/api/admin/close"):
            if not self._admin():
                return
            if not SID.match(sid):
                return self._send(400, {"error": "bad sid"})
            if u.path == "/api/admin/reply":
                text = str(b.get("text", "")).strip()[:2000]
                if not text:
                    return self._send(400, {"error": "empty"})
                store.add_msg(sid, "human", text)
                return self._send(200, {"ok": True})
            store.close_handoffs(sid)
            return self._send(200, {"ok": True})
        self._send(404, {"error": "not found"})


def make_server(port=None):
    return ThreadingHTTPServer(("0.0.0.0", port if port is not None else int(os.getenv("PORT", "8000"))), H)


if __name__ == "__main__":
    s = make_server()
    mode = f"{agent.provider()} / {agent.model_name()}" if agent.llm_configured() else "NO API KEY: set one in .env or every chat will be handed to the team"
    print(f"Miaoon support agent on :{s.server_address[1]} | {mode}")
    print("Demo page: /   Team dashboard: /admin" + ("" if os.getenv("ADMIN_TOKEN") else "  (set ADMIN_TOKEN first)"))
    s.serve_forever()
