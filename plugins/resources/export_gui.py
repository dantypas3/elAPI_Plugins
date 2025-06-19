from flask import Flask, render_template_string, request, send_file
from pathlib import Path
from .exports_resources import export_category_to_xlsx
from utils import resource_utils

app = Flask(__name__)

FORM_TEMPLATE = """
<!doctype html>
<title>Export Resources</title>
<h1>Export Resources to XLSX</h1>
<form method="post">
  <label for="category">Category:</label>
  <select name="category" id="category">
  {% for cat in categories %}
    <option value="{{ cat['id'] }}">{{ cat['title'] }}</option>
  {% endfor %}
  </select>
  <br>
  <label for="filename">File name (optional):</label>
  <input type="text" id="filename" name="filename">
  <button type="submit">Export</button>
</form>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    categories = resource_utils.FixedCategoryEndpoint().get().json()
    if request.method == 'POST':
        category_id = int(request.form.get('category'))
        filename = request.form.get('filename') or None
        out_path = export_category_to_xlsx(category_id, filename)
        return send_file(out_path, as_attachment=True)
    return render_template_string(FORM_TEMPLATE, categories=categories)

if __name__ == '__main__':
    app.run(debug=True)
