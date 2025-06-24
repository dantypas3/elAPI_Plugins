#!/usr/bin/env python3
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from flask import Flask, render_template_string, request, send_file
import threading
import time
import webbrowser

from exports_resources import export_category_to_xlsx
from utils import resource_utils

app = Flask(__name__)

FORM_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Export Resources</title>
  <!-- Google Font -->
  <link href="https://fonts.googleapis.com/css2?family=Roboto&display=swap" rel="stylesheet">
  <style>
    body {
      font-family: 'Roboto', sans-serif;
      background: #f4f7f8;
      color: #333;
      margin: 0;             /* remove default margins */
      padding: 2rem;
      padding-bottom: 4rem;  /* space for the fixed footer */
    }
    .container {
      background: white;
      max-width: 500px;
      margin: 0 auto;
      padding: 1.5rem;
      border-radius: 8px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    h1 {
      font-size: 1.8rem;
      margin-bottom: 1rem;
      color: #0066cc;
      text-align: center;    /* ← centered */
    }
    label {
      display: block;
      margin-top: 1rem;
      font-weight: bold;
    }
    select, input[type="text"] {
      width: 100%;
      padding: 0.5rem;
      margin-top: 0.3rem;
      border: 1px solid #ccc;
      border-radius: 4px;
    }
    button {
      margin-top: 1.2rem;
      padding: 0.6rem 1.2rem;
      background: #28a745;
      color: white;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-size: 1rem;
    }
    button:hover {
      background: #218838;
    }

    /* ---- FOOTER STYLES ---- */
    .site-footer {
      position: fixed;
      bottom: 0;
      left: 0;
      width: 100%;
      background: #f1f1f1;
      padding: 0.5rem 1rem;
      font-size: 0.85rem;
      color: #666;
      text-align: left;
      box-shadow: 0 -1px 4px rgba(0,0,0,0.1);
    }
    .site-footer p {
      margin: 0.2rem 0;
    }
    .site-footer a {
      color: #0066cc;
      text-decoration: none;
    }
    .site-footer a:hover {
      text-decoration: underline;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>Export Elab Resources to XLSX</h1>
    <form method="post">
      <label for="category">Category:</label>
        <select name="category" id="category">
          {# sort by the 'title' attribute #}
          {% for cat in categories|sort(attribute='title') %}
            <option value="{{ cat['id'] }}">{{ cat['title'] }}</option>
          {% endfor %}
        </select>

      <label for="filename">File name (optional):</label>
      <input type="text" id="filename" name="filename">

      <button type="submit">Export</button>
    </form>
  </div>

  <footer class="site-footer">
    <p>
      Created for:
      <a href="https://bzh.db-engine.de/" target="_blank">
        Heidelberg University, Biochemistry Center
      </a>, SFB 1638
    </p>
    <p>
      Built by:
      <a href="https://github.com/dantypas3" target="_blank">D. Antypas</a>
    </p>
  </footer>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    categories = resource_utils.FixedCategoryEndpoint().get().json()
    categories = sorted(categories, key=lambda c: c.get('title', '').lower())
    if request.method == 'POST':
        category_id = int(request.form['category'])
        filename = request.form.get('filename') or None
        out_path = export_category_to_xlsx(category_id, filename)
        return send_file(out_path, as_attachment=True)
    return render_template_string(FORM_TEMPLATE, categories=categories)

def _open_browser():
    """Wait a second for the server to start, then open the browser."""
    time.sleep(1)
    webbrowser.open('http://127.0.0.1:5000/')

if __name__ == '__main__':
    threading.Thread(target=_open_browser, daemon=True).start()
    app.run(debug=True, use_reloader=False)
