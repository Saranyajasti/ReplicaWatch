from flask import Flask, request, render_template_string, jsonify
import psycopg
from psycopg.rows import dict_row
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from datetime import datetime, date
from decimal import Decimal
import json
import os
import re
from urllib.parse import urlencode

app = Flask(__name__)

# Keep these settings aligned with your existing Docker containers.
PG = {
    "host": os.getenv("PGHOST", "localhost"),
    "port": int(os.getenv("PGPORT", "55432")),
    "dbname": os.getenv("PGDATABASE", "project_copy"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", "rwpass123"),
    "connect_timeout": 3,
}
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27020")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "replicationDB")
REFRESH_SECONDS = 15

STYLE = """
:root{--bg:#0a1020;--panel:#121d31;--panel2:#17253c;--line:#293a56;--text:#eaf1ff;--muted:#91a3bf;--cyan:#38c6f4;--green:#43d9a3;--red:#ff7185;--amber:#f8c66b}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at top,#13213a 0,#0a1020 55%);color:var(--text);font-family:Inter,Segoe UI,Arial,sans-serif;font-size:14px}
a{color:inherit;text-decoration:none}.shell{display:grid;grid-template-columns:235px minmax(0,1fr);min-height:100vh}
.sidebar{background:#0c1425;border-right:1px solid var(--line);padding:24px 14px;position:sticky;top:0;height:100vh}
.brand{padding:0 12px 24px;border-bottom:1px solid var(--line);margin-bottom:22px}.brand h1{font-size:25px;letter-spacing:-.7px;margin:0;color:var(--cyan)}.brand p{color:var(--muted);font-size:12px;line-height:1.5}
.nav-label{color:#667c9e;text-transform:uppercase;font-size:10px;letter-spacing:1.5px;padding:0 12px;margin:22px 0 8px}
nav a{display:flex;align-items:center;gap:11px;padding:12px;border-radius:10px;color:#b9c8df;margin:4px 0;font-weight:600}nav a:hover,nav a.active{background:#173c53;color:#fff}nav .ico{width:20px;text-align:center;color:var(--cyan)}
main{min-width:0;padding:26px clamp(16px,3vw,42px) 50px}.topbar{display:flex;justify-content:space-between;gap:16px;align-items:center;margin-bottom:24px;flex-wrap:wrap}.eyebrow{color:var(--cyan);font-size:11px;font-weight:800;letter-spacing:1.6px;text-transform:uppercase}.topbar h2{font-size:28px;margin:6px 0 0;letter-spacing:-.7px}.top-actions{display:flex;gap:9px;align-items:center;flex-wrap:wrap}.pill,.btn{border:1px solid var(--line);background:#142138;border-radius:9px;padding:9px 12px;color:var(--text);font-size:12px}.btn{cursor:pointer;font-weight:700}.btn:hover{border-color:var(--cyan)}.btn.primary{background:#16445a;border-color:#216b86}.muted{color:var(--muted)}.grid{display:grid;gap:15px}.metrics{grid-template-columns:repeat(4,minmax(0,1fr));margin-bottom:16px}.two{grid-template-columns:repeat(2,minmax(0,1fr))}.three{grid-template-columns:repeat(3,minmax(0,1fr))}.panel,.metric{background:linear-gradient(145deg,#17253b,#111c2f);border:1px solid var(--line);border-radius:15px;padding:20px;min-width:0;box-shadow:0 8px 26px #00000012}.metric-top{display:flex;justify-content:space-between;align-items:center;color:#aabbd4;font-size:12px;font-weight:700}.metric-icon{display:grid;place-items:center;width:34px;height:34px;border-radius:10px;background:#18374b;color:var(--cyan);font-size:17px}.metric-value{font-size:30px;font-weight:800;letter-spacing:-1px;margin:15px 0 4px}.metric-note{font-size:12px;color:var(--muted)}.cyan{color:var(--cyan)}.green{color:var(--green)}.red{color:var(--red)}.amber{color:var(--amber)}
.panel-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:16px;flex-wrap:wrap}.panel h3{margin:0;font-size:16px}.panel p.sub{margin:7px 0 0;color:var(--muted);font-size:12px}.status{display:inline-flex;align-items:center;gap:6px;border-radius:30px;padding:5px 9px;font-size:11px;font-weight:800;background:#123d31;color:var(--green)}.status.down{background:#4a202d;color:var(--red)}.status.warn{background:#47351a;color:var(--amber)}.dot{width:6px;height:6px;border-radius:50%;background:currentColor}.server-list{display:grid;gap:10px}.server{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:13px;border:1px solid var(--line);border-radius:11px;background:#0f192b}.server strong{display:block;font-size:13px}.server small{display:block;color:var(--muted);margin-top:5px;overflow-wrap:anywhere}.chart-wrap{height:260px;position:relative}.chart-wrap.short{height:210px}.table-tools{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}.search{min-width:180px;flex:1;background:#0c1526;border:1px solid var(--line);border-radius:9px;padding:10px 12px;color:var(--text);outline:none}.search:focus{border-color:var(--cyan)}select.search{flex:0 1 180px}.table-wrap{width:100%;overflow:auto;border:1px solid var(--line);border-radius:10px}table{border-collapse:collapse;width:100%;min-width:600px;font-size:12px}th{background:#1b2b43;color:#9edfff;text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.6px;position:sticky;top:0}th,td{padding:12px 13px;border-bottom:1px solid #263650;white-space:nowrap}td{color:#d6e0f0}tbody tr:hover{background:#1b2c43}tbody tr:last-child td{border-bottom:0}.pagination{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:13px;color:var(--muted);font-size:12px}.empty,.error{padding:14px;border-radius:10px;background:#101b2d;color:var(--muted)}.error{border:1px solid #633445;color:#ffb0bc}.info{padding:12px 14px;border:1px solid var(--line);background:#101a2c;border-radius:10px;color:var(--muted);line-height:1.6;font-size:12px}.footer{color:#6f83a2;font-size:11px;margin-top:24px}.table-title{font-size:16px;font-weight:800}.mini{font-size:11px;color:var(--muted)}
@media(max-width:1050px){.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.three{grid-template-columns:1fr}.shell{grid-template-columns:190px minmax(0,1fr)}}
@media(max-width:700px){.shell{display:block}.sidebar{position:relative;height:auto;padding:14px}.brand{padding-bottom:10px;margin-bottom:10px}.brand p,.nav-label{display:none}nav{display:flex;overflow:auto;gap:5px}nav a{white-space:nowrap;padding:9px;font-size:12px}.nav-label{display:none}main{padding:18px 12px}.metrics,.two{grid-template-columns:1fr}.topbar h2{font-size:23px}.metric-value{font-size:26px}}
"""

BASE = r"""
<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="{{ refresh }}">
<title>{{ title }} · Replica Watch</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>{{ style|safe }}</style></head><body>
<div class="shell"><aside class="sidebar"><div class="brand"><h1>Replica Watch</h1><p>DATABASE RELIABILITY PLATFORM<br>PostgreSQL · MongoDB</p></div>
<div class="nav-label">Workspace</div><nav>
{% for key,label,url,ico in links %}<a class="{{ 'active' if active==key else '' }}" href="{{url}}"><span class="ico">{{ico}}</span>{{label}}</a>{% endfor %}
</nav><div class="nav-label">System</div><div class="info">Auto-refresh every {{ refresh }} seconds.<br>Values are read from your running databases.</div></aside>
<main><div class="topbar"><div><div class="eyebrow">Replica Watch / {{ section }}</div><h2>{{ title }}</h2></div><div class="top-actions"><span class="pill">● Monitoring</span><button class="btn" onclick="location.reload()">↻ Refresh now</button><span class="pill" id="clock">Loading time…</span></div></div>
{{ content|safe }}<div class="footer">Replica Watch · Read-only monitoring dashboard · Refreshes every {{refresh}} seconds</div></main></div>
<script>
function tick(){const e=document.getElementById('clock');if(e)e.textContent=new Date().toLocaleTimeString();}tick();setInterval(tick,1000);
document.querySelectorAll('[data-filter-table]').forEach(function(input){input.addEventListener('input',function(){const table=document.getElementById(input.dataset.filterTable);if(!table)return;const q=input.value.toLowerCase();table.querySelectorAll('tbody tr').forEach(tr=>tr.style.display=tr.innerText.toLowerCase().includes(q)?'':'none');});});
</script></body></html>
"""

LINKS = [
    ("overview", "Overview", "/", "▦"),
    ("postgres", "PostgreSQL", "/postgres", "◈"),
    ("nodes", "Nodes", "/nodes", "▤"),
    ("logs", "Replication Logs", "/logs", "≋"),
    ("events", "Failover Events", "/events", "⚡"),
    ("mongodb", "MongoDB Shards", "/mongodb", "◉"),
    ("mongo-data", "MongoDB Documents", "/mongo-data", "▤"),
    ("health", "System Health", "/health", "♥"),
]

def render_page(title, content, active="overview", section="Overview"):
    return render_template_string(BASE, title=title, content=content, active=active,
        section=section, links=LINKS, style=STYLE, refresh=REFRESH_SECONDS)

def pg_connect():
    return psycopg.connect(**PG, row_factory=dict_row)

def json_safe(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ", timespec="seconds") if isinstance(value, datetime) else value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)

def safe_table(table):
    if table not in {"nodes", "replication_logs", "failover_events"}:
        raise ValueError("Unsupported table")
    return table

def pg_rows(sql, params=()):
    with pg_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()] if cur.description else []

def pg_scalar(sql, params=()):
    rows = pg_rows(sql, params)
    if not rows:
        return 0
    return next(iter(rows[0].values()))

def pg_status():
    info = {"ok": False, "error": None, "replicas": [], "counts": {}, "node_status": {}}
    try:
        with pg_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version() AS version, pg_is_in_recovery() AS in_recovery, current_database() AS db")
                row = cur.fetchone()
                info.update(ok=True, version=row["version"].split(",")[0], in_recovery=row["in_recovery"], db=row["db"])
                cur.execute("""SELECT client_addr::text AS client_addr, application_name, state, sync_state,
                    sent_lsn::text AS sent_lsn, write_lsn::text AS write_lsn, flush_lsn::text AS flush_lsn,
                    replay_lsn::text AS replay_lsn,
                    CASE WHEN write_lag IS NULL THEN NULL ELSE round((extract(epoch from write_lag)*1000)::numeric,2) END AS write_lag_ms,
                    CASE WHEN replay_lag IS NULL THEN NULL ELSE round((extract(epoch from replay_lag)*1000)::numeric,2) END AS replay_lag_ms
                    FROM pg_stat_replication ORDER BY client_addr""")
                info["replicas"] = [dict(r) for r in cur.fetchall()]
                for table in ("nodes", "replication_logs", "failover_events"):
                    try:
                        cur.execute(f'SELECT COUNT(*) AS n FROM "{table}"')
                        info["counts"][table] = cur.fetchone()["n"]
                    except Exception:
                        conn.rollback()
                        info["counts"][table] = None
                try:
                    cur.execute("SELECT lower(status) AS status, count(*) AS n FROM nodes GROUP BY lower(status)")
                    info["node_status"] = {r["status"]: r["n"] for r in cur.fetchall()}
                except Exception:
                    conn.rollback()
    except Exception as exc:
        info["error"] = str(exc).splitlines()[0]
    return info

def mongo_status():
    out = {"ok": False, "error": None, "counts": {}, "shards": [], "collections": [], "chunk_counts": {}}
    client = None
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2500, connectTimeoutMS=2500)
        client.admin.command("ping")
        db = client[MONGO_DB_NAME]
        out["ok"] = True
        for name in ("nodes", "replication_logs", "failover_events"):
            out["counts"][name] = db[name].estimated_document_count()
            out["collections"].append(name)
        out["shards"] = client.admin.command("listShards").get("shards", [])
        # Chunk counts are routing metadata, not document counts; label them clearly.
        try:
            chunks = client["config"]["chunks"]
            pipeline = [{"$group": {"_id": {"ns": "$ns", "shard": "$shard"}, "chunks": {"$sum": 1}}}]
            for item in chunks.aggregate(pipeline):
                out["chunk_counts"].setdefault(item["_id"]["ns"], []).append(
                    {"shard": item["_id"]["shard"], "chunks": item["chunks"]})
        except Exception:
            pass
        # Read-only status checks against each shard's advertised replica-set address.
        for shard in out["shards"]:
            shard["health"] = "Registered"
    except Exception as exc:
        out["error"] = str(exc).splitlines()[0]
    finally:
        if client:
            client.close()
    return out

def esc(value):
    s = "" if value is None else str(value)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def table_html(rows, columns=None, table_id="data-table"):
    if not rows:
        return "<div class='empty'>No records found for this query.</div>"
    if columns is None:
        columns = list(rows[0].keys())
    head = "".join(f"<th>{esc(c.replace('_',' '))}</th>" for c in columns)
    body = ""
    for row in rows:
        body += "<tr>" + "".join(f"<td>{esc(row.get(c))}</td>" for c in columns) + "</tr>"
    return f"<div class='table-wrap'><table id='{table_id}'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"

def metric(label, value, note, icon, color="cyan"):
    return f"""<div class='metric'><div class='metric-top'><span>{label}</span><span class='metric-icon'>{icon}</span></div>
    <div class='metric-value {color}'>{esc(value)}</div><div class='metric-note'>{note}</div></div>"""

def status_badge(ok, label=None):
    return f"<span class='status {' ' if ok else ' down'}'><span class='dot'></span>{esc(label or ('Online' if ok else 'Offline'))}</span>"

def error_panel(message):
    return f"<div class='error'><b>Connection/problem:</b> {esc(message)}<br><span class='mini'>Check that the relevant Docker container is running and the connection settings at the top of app.py are correct.</span></div>"

def format_rows(rows):
    return [{k: json_safe(v) for k, v in r.items()} for r in rows]

@app.route("/")
def overview():
    pg = pg_status()
    mo = mongo_status()
    pg_counts = pg.get("counts", {})
    mo_counts = mo.get("counts", {})
    total_replicas = len(pg.get("replicas", []))
    content = "<div class='grid metrics'>"
    content += metric("POSTGRESQL", "ONLINE" if pg["ok"] else "OFFLINE", pg.get("db", "Connection unavailable"), "◈", "green" if pg["ok"] else "red")
    content += metric("STREAMING REPLICAS", total_replicas, "Connected standbys reported by primary", "⇄", "green" if total_replicas else "amber")
    content += metric("MONGODB ROUTER", "ONLINE" if mo["ok"] else "OFFLINE", "mongos · localhost:27020", "◉", "green" if mo["ok"] else "red")
    content += metric("REGISTERED SHARDS", len(mo.get("shards", [])), "Shards registered with mongos", "▦")
    content += "</div><div class='grid two'>"
    content += "<section class='panel'><div class='panel-head'><div><h3>PostgreSQL · Cluster status</h3><p class='sub'>Live values from the primary server</p></div>" + status_badge(pg["ok"]) + "</div>"
    if pg["ok"]:
        content += f"<div class='info'>Database: <b>{esc(pg.get('db'))}</b><br>Server: <b>{esc(pg.get('version'))}</b><br>Primary recovery mode: <b>{esc(pg.get('in_recovery'))}</b></div><div class='server-list' style='margin-top:12px'>"
        if pg["replicas"]:
            for r in pg["replicas"]:
                content += f"<div class='server'><div><strong>{esc(r.get('application_name') or r.get('client_addr') or 'Standby')}</strong><small>{esc(r.get('client_addr'))} · {esc(r.get('sync_state'))}</small></div>{status_badge(r.get('state')=='streaming',r.get('state','Unknown'))}</div>"
        else:
            content += "<div class='empty'>No standbys currently reported by pg_stat_replication.</div>"
        content += "</div>"
    else: content += error_panel(pg.get("error") or "PostgreSQL unavailable")
    content += "</section><section class='panel'><div class='panel-head'><div><h3>MongoDB · Sharding</h3><p class='sub'>Router and shard registration status</p></div>" + status_badge(mo["ok"]) + "</div>"
    if mo["ok"]:
        for s in mo["shards"]:
            content += f"<div class='server'><div><strong>{esc(s.get('_id'))}</strong><small>{esc(s.get('host'))}</small></div>{status_badge(True,'Registered')}</div>"
        if not mo["shards"]: content += "<div class='empty'>No shards are registered.</div>"
    else: content += error_panel(mo.get("error") or "MongoDB unavailable")
    content += "</section></div><div class='grid two'>"
    content += "<section class='panel'><div class='panel-head'><div><h3>PostgreSQL node status</h3><p class='sub'>Counts grouped by the actual nodes.status values</p></div></div>"
    if pg["ok"] and pg.get("node_status"):
        labels = json.dumps(list(pg["node_status"].keys()))
        values = json.dumps([int(v) for v in pg["node_status"].values()])
        node_colors = {"active": "#ff5f87", "inactive": "#38a9ef", "failed": "#f8c66b"}
        colors = json.dumps([node_colors.get(label.lower(), "#9aa9c2") for label in pg["node_status"].keys()])
        content += f"<div class='chart-wrap short'><canvas id='pgNodesChart'></canvas></div><script>new Chart(document.getElementById('pgNodesChart'),{{type:'doughnut',data:{{labels:{labels},datasets:[{{data:{values},backgroundColor:{colors},borderColor:'#f4f7ff',borderWidth:2,hoverOffset:5}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{position:'bottom',labels:{{color:'#b8c8df',padding:14}}}}}}}}}});</script>"
        content += "<div class='info'>Status colours: active = pink, inactive = blue, failed = yellow. Counts come directly from PostgreSQL.</div>"
    else: content += "<div class='empty'>Node status chart is unavailable.</div>"
    content += "</section><section class='panel'><div class='panel-head'><div><h3>MongoDB document counts</h3><p class='sub'>Collection totals through mongos</p></div></div>"
    if mo["ok"]:
        labels = json.dumps(list(mo["counts"].keys()))
        values = json.dumps([int(v) for v in mo["counts"].values()])
        content += f"<div class='chart-wrap short'><canvas id='mongoChart'></canvas></div><script>new Chart(document.getElementById('mongoChart'),{{type:'bar',data:{{labels:{labels},datasets:[{{label:'Documents',data:{values},borderWidth:1}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},scales:{{x:{{ticks:{{color:'#b8c8df'}},grid:{{color:'#293a56'}}}},y:{{beginAtZero:true,ticks:{{color:'#b8c8df'}},grid:{{color:'#293a56'}}}}}}}}}});</script>"
    else: content += "<div class='empty'>MongoDB counts are unavailable.</div>"
    content += "</section></div><div class='info'>Charts use live database query results at page load. The MongoDB shard status here means registered in mongos metadata; it is not a full replica-member election or latency probe.</div>"
    return render_page("System Overview", content, "overview", "Overview")

@app.route("/postgres")
def postgres_page():
    pg = pg_status()
    content = "<div class='grid metrics'>"
    content += metric("PRIMARY CONNECTION", "UP" if pg["ok"] else "DOWN", "PostgreSQL endpoint", "◈", "green" if pg["ok"] else "red")
    content += metric("CONNECTED STANDBYS", len(pg["replicas"]), "Rows from pg_stat_replication", "⇄", "green" if pg["replicas"] else "amber")
    content += metric("NODES TABLE", pg.get("counts", {}).get("nodes", "—"), "PostgreSQL rows", "▤")
    content += metric("REPLICATION LOGS", pg.get("counts", {}).get("replication_logs", "—"), "PostgreSQL rows", "≋")
    content += "</div>"
    if not pg["ok"]:
        content += error_panel(pg.get("error") or "PostgreSQL connection failed")
    else:
        content += "<section class='panel'><div class='panel-head'><div><h3>Streaming replication details</h3><p class='sub'>Live rows from pg_stat_replication on the primary</p></div></div>"
        rows = format_rows(pg["replicas"])
        content += table_html(rows, table_id="replicas-table") if rows else "<div class='empty'>No active standby connections reported by PostgreSQL.</div>"
        content += "</section><section class='panel'><h3>Node state distribution</h3><p class='sub'>Based on actual node status values</p>"
        if pg.get("node_status"):
            content += table_html([{"status":k,"count":v} for k,v in pg["node_status"].items()])
        else: content += "<div class='empty'>No node status data found.</div>"
        content += "</section>"
    return render_page("PostgreSQL Monitor", content, "postgres", "PostgreSQL")

@app.route("/mongodb")
def mongodb_page():
    mo = mongo_status()
    content = "<div class='grid metrics'>"
    content += metric("MONGOS ROUTER", "ONLINE" if mo["ok"] else "OFFLINE", MONGO_URI, "◉", "green" if mo["ok"] else "red")
    content += metric("REGISTERED SHARDS", len(mo["shards"]), "Registered in config metadata", "▦")
    content += metric("TOTAL DOCUMENTS", sum(mo["counts"].values()) if mo["ok"] else "—", "Across three project collections", "▤")
    content += metric("SHARDED COLLECTIONS", 3 if mo["ok"] else "—", "Project collections configured in this setup", "⇄")
    content += "</div>"
    if not mo["ok"]:
        content += error_panel(mo.get("error") or "MongoDB connection failed")
    else:
        content += "<section class='panel'><div class='panel-head'><div><h3>Registered shards</h3><p class='sub'>Shard routing metadata returned by mongos listShards</p></div>" + status_badge(True, "Router connected") + "</div>"
        shard_rows = [{"replica_set":s.get("_id"),"host":s.get("host"),"state":"Registered"} for s in mo["shards"]]
        content += table_html(shard_rows, table_id="shards-table") if shard_rows else "<div class='empty'>No registered shards.</div>"
        content += "</section><section class='panel'><div class='panel-head'><div><h3>Collection statistics</h3><p class='sub'>Document counts queried through mongos</p></div></div>"
        rows = []
        for name, count in mo["counts"].items():
            rows.append({"collection":MONGO_DB_NAME+"."+name,"documents":count})
        content += table_html(rows, table_id="mongo-collections")
        content += "<div class='chart-wrap'><canvas id='mongoDist'></canvas></div>"
        labels = json.dumps(list(mo["counts"].keys()))
        values = json.dumps([int(v) for v in mo["counts"].values()])
        content += f"<script>new Chart(document.getElementById('mongoDist'),{{type:'bar',data:{{labels:{labels},datasets:[{{label:'Documents',data:{values},borderWidth:1}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},scales:{{x:{{ticks:{{color:'#b8c8df'}},grid:{{color:'#293a56'}}}},y:{{beginAtZero:true,ticks:{{color:'#b8c8df'}},grid:{{color:'#293a56'}}}}}}}}}});</script>"
        content += "</section><section class='panel'><div class='panel-head'><div><h3>Chunk distribution</h3><p class='sub'>Chunk counts are routing metadata; they are not document counts.</p></div></div>"
        chunk_rows = []
        for ns, items in mo["chunk_counts"].items():
            for item in items:
                chunk_rows.append({"namespace":ns,"shard":item["shard"],"chunks":item["chunks"]})
        content += table_html(chunk_rows, table_id="chunks-table") if chunk_rows else "<div class='empty'>Chunk metadata unavailable or no chunks recorded.</div>"
        content += "</section><div class='info'>The collection shard keys configured for this project are nodes hashed by _id, replication_logs hashed by node_id, and failover_events hashed by node_id. Chunk distribution is not the same as exact per-shard document distribution.</div>"
    return render_page("MongoDB Shard Monitor", content, "mongodb", "MongoDB")


@app.route("/mongo-data")
def mongo_data_page():
    """Browse actual MongoDB documents without modifying the collections."""
    allowed = {"nodes", "replication_logs", "failover_events"}
    collection_name = request.args.get("collection", "nodes")
    if collection_name not in allowed:
        collection_name = "nodes"
    search = request.args.get("q", "").strip()[:100]
    page_no = max(1, min(100000, request.args.get("page", 1, type=int)))
    page_size = 25
    client = None
    content = ""
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2500, connectTimeoutMS=2500)
        client.admin.command("ping")
        collection = client[MONGO_DB_NAME][collection_name]

        # Search safely across a bounded set of documents by their JSON text.
        # This avoids assuming a fixed schema for MongoDB's flexible documents.
        if search:
            scan_limit = 5000
            found = []
            cursor = collection.find({}).limit(scan_limit)
            for doc in cursor:
                rendered = json.dumps(doc, default=json_safe, ensure_ascii=False)
                if search.casefold() in rendered.casefold():
                    found.append(doc)
            total = len(found)
            start = (page_no - 1) * page_size
            docs = found[start:start + page_size]
            search_note = f"Search scans up to the first {scan_limit:,} documents in this collection."
        else:
            total = collection.estimated_document_count()
            docs = list(collection.find({}).sort("_id", 1).skip((page_no - 1) * page_size).limit(page_size))
            search_note = "Showing actual documents read from MongoDB through mongos."

        counts = {name: client[MONGO_DB_NAME][name].estimated_document_count() for name in sorted(allowed)}
        content += "<div class='grid metrics'>"
        content += metric("DATABASE", MONGO_DB_NAME, "Connected MongoDB database", "◉", "green")
        content += metric("CURRENT COLLECTION", collection_name, "Selected document collection", "▤")
        content += metric("MATCHING DOCUMENTS", f"{total:,}", "Count estimate unless searching", "⌕")
        content += metric("DOCUMENTS PER PAGE", page_size, "Readable JSON view", "≡")
        content += "</div>"

        content += "<section class='panel'><div class='panel-head'><div><h3>Explore MongoDB collections</h3><p class='sub'>Choose a collection to view its real stored documents</p></div></div>"
        content += "<div class='table-tools'><form method='get' style='display:flex;gap:8px;flex-wrap:wrap;width:100%'>"
        content += "<select class='search' name='collection' aria-label='MongoDB collection'>"
        for name in ("nodes", "replication_logs", "failover_events"):
            selected = " selected" if name == collection_name else ""
            content += f"<option value='{name}'{selected}>{name} ({counts[name]:,})</option>"
        content += "</select>"
        content += f"<input class='search' name='q' value='{esc(search)}' placeholder='Search document contents…'>"
        content += "<button class='btn primary' type='submit'>View documents</button>"
        content += "</form></div>"
        content += "<div class='info'>" + esc(search_note) + " This page is read-only; it does not insert, update, or delete documents.</div>"
        content += "</section>"

        content += "<section class='panel'><div class='panel-head'><div><h3>Documents · " + esc(collection_name) + "</h3><p class='sub'>JSON-style view of the BSON documents returned by MongoDB</p></div><span class='pill'>Read only</span></div>"
        if docs:
            content += "<div class='doc-list' style='display:grid;gap:12px'>"
            for idx, doc in enumerate(docs, start=(page_no - 1) * page_size + 1):
                pretty = json.dumps(doc, default=json_safe, ensure_ascii=False, indent=2)
                content += "<details class='panel' style='padding:0;margin:0;background:#0d1728'><summary style='cursor:pointer;padding:14px 16px;color:#9edfff;font-weight:700'>Document " + str(idx) + " · " + esc(str(doc.get("_id", "No _id"))[:90]) + "</summary>"
                content += "<pre style='margin:0;padding:16px;white-space:pre-wrap;overflow-wrap:anywhere;overflow-x:auto;color:#cfe0f8;font:12px/1.65 Consolas,monospace;border-top:1px solid #293a56'>" + esc(pretty) + "</pre></details>"
            content += "</div>"
        else:
            content += "<div class='empty'>No documents matched. Try a different search term or select another collection.</div>"

        prev_url = f"/mongo-data?collection={collection_name}&page={page_no-1}&q={esc(search)}" if page_no > 1 else "#"
        next_url = f"/mongo-data?collection={collection_name}&page={page_no+1}&q={esc(search)}" if (page_no * page_size < total) else "#"
        content += f"<div class='pagination'><span>Page {page_no} · {total:,} {'matches' if search else 'estimated documents'}</span><div><a class='btn' href='{prev_url}'>← Previous</a> <a class='btn' href='{next_url}'>Next →</a></div></div></section>"
    except Exception as exc:
        content += error_panel(str(exc))
    finally:
        if client:
            client.close()
    return render_page("MongoDB Documents", content, "mongo-data", "Document Explorer")


@app.route("/health")
def health_page():
    pg, mo = pg_status(), mongo_status()
    content = "<div class='grid two'>"
    content += "<section class='panel'><div class='panel-head'><div><h3>PostgreSQL service</h3><p class='sub'>Connection and streaming replication</p></div>"+status_badge(pg["ok"])+( "</div>")
    if pg["ok"]:
        content += f"<div class='info'>Database: {esc(pg.get('db'))}<br>Server: {esc(pg.get('version'))}<br>In recovery: {esc(pg.get('in_recovery'))}<br>Streaming standbys: {len(pg['replicas'])}</div>"
    else: content += error_panel(pg.get("error") or "Unavailable")
    content += "</section><section class='panel'><div class='panel-head'><div><h3>MongoDB service</h3><p class='sub'>mongos and registered shards</p></div>"+status_badge(mo["ok"])+( "</div>")
    if mo["ok"]:
        content += f"<div class='info'>Router: {esc(MONGO_URI)}<br>Database: {esc(MONGO_DB_NAME)}<br>Registered shards: {len(mo['shards'])}</div>"
    else: content += error_panel(mo.get("error") or "Unavailable")
    content += "</section></div>"

    # Live health checks for PostgreSQL and MongoDB services.
    health_labels = ["PostgreSQL primary"]
    health_values = [1 if pg["ok"] else 0]
    health_colors = ["#43d9a3" if pg["ok"] else "#ff7185"]
    if pg["ok"]:
        for index, replica in enumerate(pg.get("replicas", []), start=1):
            is_streaming = replica.get("state") == "streaming"
            health_labels.append(f"PostgreSQL standby {index}")
            health_values.append(1 if is_streaming else 0)
            health_colors.append("#43d9a3" if is_streaming else "#ff7185")
    health_labels.append("MongoDB router")
    health_values.append(1 if mo["ok"] else 0)
    health_colors.append("#43d9a3" if mo["ok"] else "#ff7185")
    # Registered shards are labelled separately; registration alone is not a replica health probe.
    if mo["ok"]:
        for shard in mo.get("shards", []):
            health_labels.append(f"Shard {shard.get('_id', 'unknown')} (registered)")
            health_values.append(1)
            health_colors.append("#f8c66b")

    chart_labels = json.dumps(health_labels)
    chart_values = json.dumps(health_values)
    chart_colors = json.dumps(health_colors)
    content += "<section class='panel' style='margin-top:15px'><div class='panel-head'><div><h3>System Health Status</h3><p class='sub'>Live connection and streaming checks; yellow means shard registration metadata only</p></div></div>"
    content += "<div class='chart-wrap'><canvas id='systemHealthChart'></canvas></div>"
    content += f"<script>new Chart(document.getElementById('systemHealthChart'),{{type:'bar',data:{{labels:{chart_labels},datasets:[{{label:'Status',data:{chart_values},backgroundColor:{chart_colors},borderRadius:6}}]}},options:{{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:function(ctx){{const v=ctx.raw;const label=ctx.label||'';return label.includes('(registered)')?'Registered in mongos metadata':(v===1?'Online / streaming':'Offline / not streaming');}}}}}}}},scales:{{x:{{min:0,max:1,ticks:{{stepSize:1,color:'#b8c8df',callback:function(v){{return v===1?'Online':'Offline';}}}},grid:{{color:'#293a56'}}}},y:{{ticks:{{color:'#b8c8df'}},grid:{{display:false}}}}}}}}}});</script>"
    content += "<div class='info'>Green = connected/streaming. Red = connection or streaming check failed. Yellow = shard is registered with mongos; this dashboard does not claim that registration alone proves every shard replica member is healthy.</div></section>"
    return render_page("Service Health", content, "health", "Health")

@app.route("/nodes")
def nodes_page():
    return data_page("Nodes", "nodes", "nodes")

@app.route("/logs")
def logs_page():
    return data_page("Replication Logs", "replication_logs", "logs")

@app.route("/events")
def events_page():
    return data_page("Failover Events", "failover_events", "events")

def data_page(title, table, active):
    page_no = max(1, min(1000000, request.args.get("page", 1, type=int)))
    page_size = 50
    search = request.args.get("q", "").strip()[:100]
    status_filter = request.args.get("status", "all").strip().lower()
    if status_filter not in ("all", "active", "inactive", "failed"):
        status_filter = "all"
    try:
        safe_table(table)
        # Introspect column names, so tables with slightly different schemas still render.
        with pg_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT column_name FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s ORDER BY ordinal_position""", (table,))
                columns = [r["column_name"] for r in cur.fetchall()]
                if not columns:
                    raise RuntimeError(f"Table '{table}' was not found in the public schema.")
                where_parts = []
                params = []
                status_counts = {"all": 0, "active": 0, "inactive": 0, "failed": 0}
                if table == "nodes" and "status" in columns:
                    cur.execute('SELECT COUNT(*) AS n FROM "nodes"')
                    status_counts["all"] = cur.fetchone()["n"]
                    cur.execute('SELECT LOWER(CAST("status" AS TEXT)) AS node_status, COUNT(*) AS n FROM "nodes" GROUP BY LOWER(CAST("status" AS TEXT))')
                    for count_row in cur.fetchall():
                        key = str(count_row["node_status"] or "").lower()
                        if key in ("active", "inactive", "failed"):
                            status_counts[key] = count_row["n"]
                    if status_filter != "all":
                        where_parts.append('LOWER(CAST("status" AS TEXT)) = %s')
                        params.append(status_filter)
                if search:
                    where_parts.append("(" + " OR ".join(f'CAST("{c}" AS TEXT) ILIKE %s' for c in columns) + ")")
                    params.extend([f"%{search}%"] * len(columns))
                where = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""
                cur.execute(f'SELECT COUNT(*) AS n FROM "{table}"' + where, params)
                total = cur.fetchone()["n"]
                offset = (page_no - 1) * page_size
                cur.execute(f'SELECT * FROM "{table}"' + where + f' ORDER BY 1 DESC LIMIT %s OFFSET %s',
                            params + [page_size, offset])
                rows = format_rows([dict(r) for r in cur.fetchall()])
        content = f"<section class='panel'><div class='panel-head'><div><h3>{title} · live records</h3><p class='sub'>{total:,} matching records · showing up to {page_size} per page</p></div><span class='pill'>PostgreSQL</span></div>"
        if table == "nodes" and "status" in columns:
            content += "<div style='display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 4px'>"
            for key, label in (("all", "All"), ("active", "Active"), ("inactive", "Inactive"), ("failed", "Failed")):
                selected_style = "border-color:#65b9ff;background:#1b3551;color:#9edfff;" if status_filter == key else ""
                query = {"status": key}
                if search:
                    query["q"] = search
                href = "/nodes?" + urlencode(query) if key != "all" or search else "/nodes"
                content += f"<a class='btn' style='{selected_style}' href='{href}'>{label} <strong style='margin-left:5px'>{status_counts[key]:,}</strong></a>"
            content += "</div>"
        content += f"""<form class='table-tools' method='get'><input type='hidden' name='status' value='{esc(status_filter)}'><input class='search' name='q' value='{esc(search)}' placeholder='Search across all columns…'><button class='btn primary' type='submit'>Search</button><a class='btn' href='/{'logs' if table=='replication_logs' else 'events' if table=='failover_events' else 'nodes'}'>Clear</a></form>"""
        content += table_html(rows, columns if rows else None, "records-table")
        page_query = {"page": page_no - 1, "q": search}
        if table == "nodes" and status_filter != "all": page_query["status"] = status_filter
        prev_url = "?" + urlencode(page_query) if page_no > 1 else "#"
        page_query["page"] = page_no + 1
        next_url = "?" + urlencode(page_query) if offset + len(rows) < total else "#"
        content += f"<div class='pagination'><span>Page {page_no} · {total:,} results</span><div><a class='btn' href='{prev_url}'>← Previous</a> <a class='btn' href='{next_url}'>Next →</a></div></div></section>"
    except Exception as exc:
        content = error_panel(str(exc))
    return render_page(title, content, active, "Data Explorer")

@app.route("/api/status")
def api_status():
    return jsonify({"timestamp":datetime.now().isoformat(timespec="seconds"),"postgresql":pg_status(),"mongodb":mongo_status()})

@app.route("/api/records/<table>")
def api_records(table):
    try:
        safe_table(table)
        limit = max(1, min(200, request.args.get("limit", 50, type=int)))
        offset = max(0, request.args.get("offset", 0, type=int))
        rows = format_rows(pg_rows(f'SELECT * FROM "{table}" ORDER BY 1 DESC LIMIT %s OFFSET %s', (limit, offset)))
        return jsonify({"table":table,"limit":limit,"offset":offset,"records":rows})
    except Exception as exc:
        return jsonify({"error":str(exc)}), 400

if __name__ == "__main__":
    print("Replica Watch dashboard: http://127.0.0.1:5000")
    print("Read-only dashboard. Database rows are not modified.")
    app.run(host="0.0.0.0", port=5000, debug=False)