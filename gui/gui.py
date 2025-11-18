import os
import sys
import threading
import time
import webbrowser
from typing import Tuple, Union

from flask import Flask, flash, redirect, render_template, request, send_file, url_for
from werkzeug.serving import make_server
from werkzeug.utils import secure_filename
from werkzeug.wrappers.response import Response as WerkzeugResponse

from src.factories import ExporterFactory, ImporterFactory
from src.utils import endpoints
from src.utils.logging_config import setup_logging

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(SCRIPT_DIR, "templates")
if SCRIPT_DIR not in sys.path:
  sys.path.insert(0, SCRIPT_DIR)

setup_logging()

app = Flask(__name__, template_folder=TEMPLATE_DIR)
app.secret_key = os.urandom(24)

UPLOAD_DIR = os.path.join(SCRIPT_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR

# ── NEW: inactivity tracking & server handle ───────────────────────────────
LAST_ACTIVITY = time.monotonic()
SERVER = None  # will be assigned in __main__

INACTIVITY_TIMEOUT_SEC = 5 * 60  # 5 minutes
CHECK_INTERVAL_SEC = 5  # how often the watchdog checks


@app.before_request
def _touch_activity():
  global LAST_ACTIVITY
  LAST_ACTIVITY = time.monotonic()


def _inactivity_watchdog(timeout: int = INACTIVITY_TIMEOUT_SEC, poll: int = CHECK_INTERVAL_SEC) -> None:
  """Shut the server down if no requests arrive for `timeout` seconds."""
  while True:
    time.sleep(poll)
    if time.monotonic() - LAST_ACTIVITY > timeout:
      # Gracefully stop the server loop
      if SERVER is not None:
        try:
          SERVER.shutdown()
        except Exception:
          pass
      # No busy loop; allow serve_forever() to return
      break


# ── routes ─────────────────────────────────────────────────────────────────
@app.route("/", methods=["GET", "POST"])
def index() -> Union[str, WerkzeugResponse]:
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


def shutdown_server() -> None:
  if SERVER:
    try:
      SERVER.shutdown()
    except Exception:
      pass  # or log the error


@app.route("/shutdown", methods=["POST"])
def shutdown() -> tuple[str, int]:
  threading.Thread(target=shutdown_server, daemon=True).start()
  return "OK", 200


# ── helpers ────────────────────────────────────────────────────────────────
def _open_browser() -> None:
  time.sleep(1)
  webbrowser.open("http://127.0.0.1:5000")


# ── main ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
  SERVER = make_server("127.0.0.1", 5000, app)

  # Start browser and inactivity watchdog
  threading.Thread(target=_open_browser, daemon=True).start()
  threading.Thread(target=_inactivity_watchdog, daemon=True).start()

  try:
    # Serve in the main thread; returns when shutdown() is called
    SERVER.serve_forever()
  finally:
    try:
      SERVER.server_close()
    except Exception:
      pass
