from pathlib import Path
import py_compile
import shutil

target = Path(__file__).resolve().parent / "app.py"
if not target.exists():
    raise SystemExit("app.py was not found in this folder. Put this script beside app.py.")

code = target.read_text(encoding="utf-8")
if '@app.route("/mongo-data")' in code:
    print("The MongoDB Documents route is already present. No changes made.")
    raise SystemExit(0)

required = ["def page(", "MongoClient", "MONGO_URI", "MONGO_DB_NAME", '@app.route("/health")']
missing = [item for item in required if item not in code]
if missing:
    raise SystemExit("This app.py is a different version. Missing: " + ", ".join(missing) + ". No changes made.")

backup = target.with_name("app_before_mongo_documents_backup.py")
if not backup.exists():
    shutil.copy2(target, backup)
    print("Backup created:", backup.name)

if "import json" not in code:
    code = code.replace("from flask import Flask, request, render_template_string",
                        "from flask import Flask, request, render_template_string\nimport json\nfrom html import escape as html_escape", 1)

needle = '        ("mongodb", "MongoDB Sharding", "/mongodb"),'
if needle in code:
    code = code.replace(needle, needle + '\n        ("mongo-data", "MongoDB Documents", "/mongo-data"),', 1)

route = r'''
@app.route("/mongo-data")
def mongo_data_page():
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
        client = get_mongo_client()
        client.admin.command("ping")
        db = client[MONGO_DB_NAME]
        collection = db[collection_name]
        if search:
            matches = []
            for doc in collection.find({}).limit(5000):
                text_doc = json.dumps(doc, default=str, ensure_ascii=False)
                if search.casefold() in text_doc.casefold():
                    matches.append(doc)
            total = len(matches)
            start = (page_no - 1) * page_size
            docs = matches[start:start + page_size]
            note = "Search checks at most the first 5,000 documents."
        else:
            total = collection.estimated_document_count()
            docs = list(collection.find({}).sort("_id", 1).skip((page_no - 1) * page_size).limit(page_size))
            note = "Real documents fetched from MongoDB through mongos. This page is read-only."

        counts = {name: db[name].estimated_document_count() for name in sorted(allowed)}
        content += "<section class='panel'><h3>Explore MongoDB collections</h3>"
        content += "<p class='sub'>Database: " + html_escape(MONGO_DB_NAME) + " · Choose a collection.</p>"
        content += "<form method='get' class='table-tools' style='display:flex;gap:8px;flex-wrap:wrap'>"
        content += "<select class='search' name='collection'>"
        for name in ("nodes", "replication_logs", "failover_events"):
            selected = " selected" if name == collection_name else ""
            content += "<option value='" + name + "'" + selected + ">" + name + " (" + format(counts[name], ",") + ")</option>"
        content += "</select>"
        content += "<input class='search' name='q' value='" + html_escape(search, quote=True) + "' placeholder='Search document contents…'>"
        content += "<button class='btn primary' type='submit'>View documents</button></form>"
        content += "<p class='muted'>" + html_escape(note) + "</p></section>"
        content += "<section class='panel'><h3>Documents: " + html_escape(collection_name) + "</h3>"
        content += "<p class='sub'>" + format(total, ",") + " total or matching documents · " + str(page_size) + " per page</p>"
        if docs:
            for index, doc in enumerate(docs, start=(page_no - 1) * page_size + 1):
                pretty = json.dumps(doc, default=str, ensure_ascii=False, indent=2)
                doc_id = html_escape(str(doc.get("_id", "No _id"))[:100])
                content += "<details class='panel' style='margin:12px 0;background:#0d1728'><summary style='cursor:pointer;color:#9edfff;font-weight:bold'>Document " + str(index) + " · " + doc_id + "</summary>"
                content += "<pre style='white-space:pre-wrap;overflow-wrap:anywhere;color:#cfe0f8;font:12px/1.6 Consolas,monospace'>" + html_escape(pretty) + "</pre></details>"
        else:
            content += "<p class='muted'>No documents matched. Try another search or collection.</p>"
        previous = "/mongo-data?collection=" + collection_name + "&page=" + str(page_no - 1) if page_no > 1 else "#"
        next_link = "/mongo-data?collection=" + collection_name + "&page=" + str(page_no + 1) if page_no * page_size < total else "#"
        content += "<p><a class='btn' href='" + previous + "'>← Previous</a> <a class='btn' href='" + next_link + "'>Next →</a></p></section>"
    except Exception as exc:
        content += "<section class='panel'><h3>MongoDB Documents</h3><p class='muted'>Could not load documents: " + html_escape(str(exc)) + "</p></section>"
    finally:
        if client is not None:
            client.close()
    return page("MongoDB Documents", content, "mongo-data")


'''
marker = '@app.route("/health")'
if marker not in code:
    raise SystemExit('Could not find @app.route("/health"). No changes made.')
code = code.replace(marker, route + marker, 1)
target.write_text(code, encoding="utf-8")
try:
    py_compile.compile(str(target), doraise=True)
except Exception as exc:
    shutil.copy2(backup, target)
    raise SystemExit("Syntax check failed; restored backup. Error: " + str(exc))
print("SUCCESS: MongoDB Documents page added and Python syntax checked.")
print("Backup file:", backup.name)
print("Restart Flask with: python app.py")
print("Open: http://127.0.0.1:5000/mongo-data")
