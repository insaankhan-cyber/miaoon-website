"""SQLite storage: messages, conversations, handoffs. Stdlib only."""
import os, sqlite3, threading, time

DB = os.getenv("DB_PATH") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "agent.db")
os.makedirs(os.path.dirname(DB), exist_ok=True)
_c = sqlite3.connect(DB, check_same_thread=False)
_c.row_factory = sqlite3.Row
_l = threading.RLock()
_c.executescript("""
create table if not exists msgs(id integer primary key, sid text, role text, text text, ts real);
create index if not exists msgs_sid on msgs(sid, id);
create table if not exists convs(sid text primary key, status text default 'bot', contact text default '', lowconf integer default 0, created real);
create table if not exists handoffs(id integer primary key, sid text, kind text, reason text, summary text, contact text default '', status text default 'open', ts real);
""")


def _run(sql, args=(), fetch=None):
    with _l:
        cur = _c.execute(sql, args)
        if fetch == "one":
            return cur.fetchone()
        if fetch == "all":
            return cur.fetchall()
        _c.commit()
        return cur.lastrowid


def conv(sid):
    r = _run("select * from convs where sid=?", (sid,), "one")
    if not r:
        _run("insert into convs(sid,created) values(?,?)", (sid, time.time()))
        r = _run("select * from convs where sid=?", (sid,), "one")
    return r


def set_conv(sid, **kw):
    conv(sid)
    for k, v in kw.items():
        assert k in ("status", "contact", "lowconf")
        _run(f"update convs set {k}=? where sid=?", (v, sid))


def add_msg(sid, role, text):
    return _run("insert into msgs(sid,role,text,ts) values(?,?,?,?)", (sid, role, text, time.time()))


def history(sid, limit=12):
    rows = _run("select role,text from msgs where sid=? order by id desc limit ?", (sid, limit), "all")
    return [(r["role"], r["text"]) for r in reversed(rows)]


def messages(sid, after=0, roles=None):
    rows = _run("select id,role,text,ts from msgs where sid=? and id>? order by id", (sid, after), "all")
    return [dict(r) for r in rows if not roles or r["role"] in roles]


def last_id(sid):
    r = _run("select max(id) m from msgs where sid=?", (sid,), "one")
    return r["m"] or 0


def add_handoff(sid, kind, reason, summary, contact):
    return _run("insert into handoffs(sid,kind,reason,summary,contact,ts) values(?,?,?,?,?,?)",
                (sid, kind, reason, summary, contact, time.time()))


def set_handoff_contact(sid, contact):
    _run("update handoffs set contact=? where sid=? and status='open'", (contact, sid))


def close_handoffs(sid):
    _run("update handoffs set status='closed' where sid=?", (sid,))
    set_conv(sid, status="bot", lowconf=0)


def handoffs(status=None):
    if status:
        rows = _run("select * from handoffs where status=? order by id desc limit 200", (status,), "all")
    else:
        rows = _run("select * from handoffs order by id desc limit 200", (), "all")
    return [dict(r) for r in rows]
