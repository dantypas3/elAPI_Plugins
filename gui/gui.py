#!/usr/bin/env python3
import os
import sys
import threading
import time
import webbrowser

from flask import Flask, render_template, request, send_file
from werkzeug.serving import make_server

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from plugins.resources.export import export_resources_to_xlsx
from plugins.experiments.export import export_experiments_to_xlsx

from utils import endpoints

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    categories = endpoints.FixedCategoryEndpoint().get().json()
    categories = sorted(categories, key=lambda c: c.get('title', '').lower())

    if request.method == 'POST':

        export_type = request.form.get('export_type')

        if export_type == 'category':
            category_id = int(request.form['category'])
            filename = request.form.get('filename') or None
            out_path = export_resources_to_xlsx(category_id, filename)
            return send_file(out_path, as_attachment=True)
        elif export_type == 'experiments':
            filename = request.form.get('exp_filename') or None
            out_path  = export_experiments_to_xlsx(filename)
        else:
            return "Unknown export type", 400

        return send_file(out_path, as_attachment=True)

    return render_template('index.html', categories=categories)

http_server = None

@app.route('/shutdown', methods=['POST'])
def shutdown():
    global http_server
    if http_server is None:
        return 'Server not found', 500
    threading.Thread(target=http_server.shutdown).start()
    return 'Shutting down', 200

def _open_browser():
    """Give the server a moment, then open the default browser."""
    time.sleep(1)
    webbrowser.open('http://127.0.0.1:5000/')

if __name__ == '__main__':
    http_server = make_server('127.0.0.1', 5000, app)
    server_thread = threading.Thread(target=http_server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    print("Serving on http://127.0.0.1:5000")

    threading.Thread(target=_open_browser, daemon=True).start()

    server_thread.join()
    print("Server has shut down. Exiting.")