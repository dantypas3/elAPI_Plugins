import os
import sys
import threading
import time
import webbrowser
from typing import Tuple, Union

from flask import Flask, flash, redirect, render_template, request, send_file, \
    url_for
from werkzeug.serving import make_server
from werkzeug.utils import secure_filename
from werkzeug.wrappers.response import Response as WerkzeugResponse

from src.elabftw_client.factories import ExporterFactory, ImporterFactory
from src.elabftw_client.utils import endpoints

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(SCRIPT_DIR, "templates")
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

app = Flask(__name__, template_folder=TEMPLATE_DIR)
app.secret_key = os.urandom(24)

UPLOAD_DIR = os.path.join(SCRIPT_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR


@app.route("/", methods=["GET", "POST"])
def index () -> Union[str, WerkzeugResponse]:
    categories = endpoints.get_fixed("categories").get().json()
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
                importer = ImporterFactory.get_importer("resources")
                count = importer.create_new(csv_path=full_path,
                                            category_id=cid)
                flash(f"Imported {count} resources from {source}", "success")
            except Exception as e:
                flash(f"Import failed: {e}", "error")

            return redirect(url_for("index"))

        else:
            flash("Unknown action", "error")
            return redirect(url_for("index"))

    return render_template("index.html", categories=categories)


@app.route("/shutdown", methods=["POST"])
def shutdown () -> Tuple[str, int]:
    return "OK", 200


def _open_browser () -> None:
    time.sleep(1)
    webbrowser.open("http://127.0.0.1:5000")


if __name__ == "__main__":
    server = make_server("127.0.0.1", 5000, app)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    threading.Thread(target=_open_browser, daemon=True).start()
    server.serve_forever()
