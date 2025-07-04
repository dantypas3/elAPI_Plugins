import os
import sys
import threading
import time
import webbrowser

from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from werkzeug.serving import make_server
from werkzeug.utils import secure_filename

import io

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

UPLOAD_FOLDER = os.path.join(SCRIPT_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

from plugins.resources.create import create_resources
from plugins.resources.export import export_resources_to_xlsx
from plugins.experiments.export import export_experiments_to_xlsx
from utils import endpoints

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/', methods=['GET', 'POST'])
def index():
    # Fetch and sort categories for dropdowns
    categories = endpoints.FixedCategoryEndpoint().get().json()
    categories = sorted(categories, key=lambda c: c.get('title', '').lower())

    if request.method == 'POST':
        action = request.form.get('export_type')

        if action == 'category':
            cid = int(request.form['category'])
            fname = request.form.get('filename') or None
            path = export_resources_to_xlsx(cid, fname)
            return send_file(path, as_attachment=True)

        elif action == 'experiments':
            fname = request.form.get('exp_filename') or None
            path = export_experiments_to_xlsx(fname)
            return send_file(path, as_attachment=True)

        elif action == 'imports':
            try:
                cid = int(request.form['category'])
            except (KeyError, ValueError):
                flash("Missing or invalid category for import", "error")
                return redirect(url_for('index'))

            import_path = request.form.get('import_path', '').strip()
            if import_path:
                full_path = os.path.abspath(import_path)
                if not os.path.isfile(full_path):
                    flash(f"No file found at {full_path}", "error")
                    return redirect(url_for('index'))
                source = full_path
            else:
                uploaded = request.files.get('import_file')
                if not uploaded or not uploaded.filename:
                    flash("No file selected and no path provided", "error")
                    return redirect(url_for('index'))
                filename = secure_filename(uploaded.filename)
                full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                uploaded.save(full_path)
                source = full_path

            try:
                count = create_resources(source, cid)
                flash(f"Imported {count} resources from {source}", "success")
            except Exception as e:
                flash(f"Import failed: {e}", "error")

            return redirect(url_for('index'))

        else:
            flash("Unknown action", "error")
            return redirect(url_for('index'))

    return render_template('index.html', categories=categories)

@app.route('/shutdown', methods=['POST'])
def shutdown():
    return 'OK', 200


def _open_browser():
    time.sleep(1)
    webbrowser.open('http://127.0.0.1:5000')

if __name__ == '__main__':
    http_server = make_server('127.0.0.1', 5000, app)
    server_thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    server_thread.start()

    print("Serving on http://127.0.0.1:5000")
    threading.Thread(target=_open_browser, daemon=True).start()
    server_thread.join()