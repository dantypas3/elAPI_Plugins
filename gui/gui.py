import os
import sys
import threading
import time
import webbrowser
import math
from typing import Tuple, Union
import tempfile

from flask import Flask, flash, redirect, render_template, request, send_file, url_for
from httpx import ReadTimeout, ConnectTimeout
from werkzeug.serving import make_server
from werkzeug.utils import secure_filename
from werkzeug.wrappers.response import Response as WerkzeugResponse

from src.factories import ExporterFactory, ImporterFactory
from src.utils import endpoints

# Extend PATH for Finder-launched app so external tools can be found
if getattr(sys, 'frozen', False):
    os.environ['PATH'] = os.pathsep.join([os.environ.get('PATH', ''), '/usr/local/bin', '/opt/homebrew/bin'])
    try:
        os.chdir(os.path.expanduser('~'))
    except Exception:
        pass


def resource_path(rel_path: str) -> str:
    """
    Resolve a path to a resource bundled with PyInstaller.  When frozen,
    sys._MEIPASS points to the temporary extraction directory; otherwise
    the file’s directory is used.
    """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, rel_path)

# Ensure local modules can be imported
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# Configure Flask to look up templates and static files in the bundled locations
app = Flask(
    __name__,
    template_folder=resource_path("templates"),
    static_folder=resource_path("static"),
)
app.secret_key = os.urandom(24)

# Use a writable directory for uploads (outside the application bundle)
APP_NAME = "elAPI_Plugins"
UPLOAD_DIR = os.path.join(tempfile.gettempdir(), APP_NAME, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR

server = None

@app.route("/", methods=["GET", "POST"])
def index() -> Union[str, WerkzeugResponse]:
    endpoint = endpoints.get_fixed("categories")
    offset = 0
    page_size = 30
    max_retries = 3
    categories: list[dict] = []

    # Fetch all categories from the API with simple retry logic
    while True:
        attempt = 0
        current_limit = page_size
        while True:
            try:
                response = endpoint.get(query={"limit": current_limit, "offset": offset})
                response.raise_for_status()
                data = response.json()
                page = data["data"] if isinstance(data, dict) and "data" in data else data
                break
            except (ReadTimeout, ConnectTimeout):
                if attempt >= max_retries:
                    print(f"Timeout on offset {offset}. Skipping after {max_retries} retries.")
                    page = []
                    break
                attempt += 1
                sleep_s = 1.5 * attempt
                current_limit = max(5, math.ceil(current_limit / 2))
                print(
                    f"Timeout on offset {offset}. Retry {attempt}/{max_retries} after {sleep_s:.1f}s"
                    f" with limit={current_limit}…"
                )
                time.sleep(sleep_s)

        if not page:
            if attempt >= max_retries:
                offset += current_limit
                continue
            break

        categories.extend(page)
        print(f"Fetched {len(page)} categories (total: {len(categories)})")

        if len(page) < current_limit:
            break
        offset += current_limit

    categories = sorted(categories, key=lambda c: c.get("title", "").lower())

    if request.method == "POST":
        action = request.form.get("export_type")
        if action == "resources":
            cid = int(request.form["category"])
            fname = request.form.get("filename") or None
            exporter = ExporterFactory.get_exporter("resources", cid)
            path = exporter.xlsx_export(fname)
            return send_file(path, as_attachment=True)

        elif action == "experiments":
            fname = request.form.get("exp_filename") or None
            exporter = ExporterFactory.get_exporter("experiments")
            path = exporter.xlsx_export(fname)
            return send_file(path, as_attachment=True)

        elif action == "imports":
            cid = int(request.form["category"])
            import_path = request.form.get("import_path", "").strip()
            import_target = (request.form.get("import_target") or "resources").strip().lower()

            if import_path:
                full_path = os.path.abspath(import_path)
                if not os.path.isfile(full_path):
                    flash(f"No file found at {full_path}", "error")
                    return redirect(url_for("index"))
                source = full_path
            else:
                uploaded = request.files.get("import_file")
                if not uploaded or not uploaded.filename:
                    flash("No file selected and no path provided", "error")
                    return redirect(url_for("index"))
                filename = secure_filename(uploaded.filename)
                full_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                uploaded.save(full_path)
                source = full_path

            try:
                if import_target == "resources":
                    importer = ImporterFactory.get_importer("resources", csv_path=full_path, template=cid)
                    ids = importer.create_all_from_csv()
                    count = len(ids)
                    flash(f"Imported {count} resources from {source}", "success")
                else:
                    flash(f"Unknown import target: {import_target}", "error")
                    return redirect(url_for("index"))

                flash(f"Imported {count} {import_target} from {source}", "success")
            except Exception as e:
                flash(f"Import failed: {e}", "error")

            return redirect(url_for("index"))

    return render_template("index.html", categories=categories)

@app.route("/shutdown", methods=["POST"])
def shutdown() -> Tuple[str, int]:
    global server
    if server:
        threading.Thread(target=server.shutdown).start()
    return "Shutting down", 200

def _open_browser() -> None:
    # Open the web interface in the default browser after the server starts
    time.sleep(1)
    webbrowser.open("http://127.0.0.1:1991")

if __name__ == "__main__":
    server = make_server("127.0.0.1", 1991, app)
    threading.Thread(target=_open_browser, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
