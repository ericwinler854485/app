# shopline_web.py
from flask import Flask, render_template, request, redirect, url_for, send_file, flash
import os
import threading
import time
import json
import pandas as pd
import requests
from datetime import datetime

# Core processing logic adapted from ShoplineBulkOrderCreator
class ShoplineBulkOrderCreator:
    def __init__(self, access_token: str, store_domain: str, api_version: str = "v20251201"):
        self.access_token = access_token
        self.store_domain = store_domain.replace('https://', '').replace('http://', '')
        self.api_version = api_version
        self.base_url = f"https://{self.store_domain}/admin/openapi/{self.api_version}"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            "User-Agent": "ShoplineWeb/1.0"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def create_order(self, row):
        def safe_str(v, d=''):
            if v is None: return d
            s = str(v).strip()
            return d if s.lower() in ['nan','null',''] else s

        # Build payload
        customer = {
            'email': safe_str(row.get('customer_email')),
            'first_name': safe_str(row.get('customer_first_name')),
            'last_name': safe_str(row.get('customer_last_name'))
        }
        shipping = {
            'address1': safe_str(row.get('shipping_address1')),
            'city': safe_str(row.get('shipping_city')),
            'province': safe_str(row.get('shipping_state')),
            'country': safe_str(row.get('shipping_country'), 'United States'),
            'zip': safe_str(row.get('shipping_zip'))
        }
        items = []
        for i in range(1, 6):
            name = safe_str(row.get(f'product_{i}_name'))
            price = safe_str(row.get(f'product_{i}_price'))
            qty = safe_str(row.get(f'product_{i}_quantity'), '1')
            if name and price:
                items.append({
                    'title': name,
                    'price': price,
                    'quantity': int(qty),
                    'requires_shipping': True,
                    'taxable': True
                })
        pm = safe_str(row.get('payment_method'), 'COD').upper()
        status = {'COD': 'unpaid', 'PAID': 'paid'}.get(pm, 'unpaid')
        payload = {
            'order': {
                'customer': customer,
                'shipping_address': shipping,
                'line_items': items,
                'financial_status': status,
                'fulfillment_status': 'unshipped',
                'send_receipt': True
            }
        }
        try:
            r = self.session.post(f"{self.base_url}/orders.json", json=payload, timeout=30)
            if r.status_code in (200, 201):
                o = r.json().get('order', {})
                return f"Order {o.get('name', o.get('id'))} created"
            return f"Error {r.status_code}: {r.text}"
        except Exception as e:
            return str(e)

    def process_csv(self, path, log):
        try:
            df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding='utf-8-sig')
        except UnicodeDecodeError:
            df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding='latin-1')
        for idx, row in df.iterrows():
            msg = self.create_order(row.to_dict())
            log.append(msg)
            time.sleep(0.2)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        out = f'results_{ts}.json'
        with open(out, 'w') as f:
            json.dump({'logs': log}, f, indent=2)
        return out

# -- Flask App: shopline_web.py --
app = Flask(__name__)
app.secret_key = os.urandom(24)

tasks = {}

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        token = request.form['access_token']
        domain = request.form['store_domain']
        file = request.files.get('csv_file')
        if not (token and domain and file):
            flash('All fields are required', 'danger')
            return redirect(url_for('index'))
        filepath = os.path.join('uploads', file.filename)
        os.makedirs('uploads', exist_ok=True)
        file.save(filepath)
        task_id = str(len(tasks) + 1)
        tasks[task_id] = {'status': 'Processing', 'logs': [], 'result_file': None}
        def run():
            creator = ShoplineBulkOrderCreator(token, domain)
            result_file = creator.process_csv(filepath, tasks[task_id]['logs'])
            tasks[task_id]['status'] = 'Completed'
            tasks[task_id]['result_file'] = result_file
        threading.Thread(target=run, daemon=True).start()
        return redirect(url_for('status', task_id=task_id))
    return render_template('index.html')

@app.route('/status/<task_id>')
def status(task_id):
    task = tasks.get(task_id)
    if not task:
        return 'Invalid task ID', 404
    return render_template('status.html', task_id=task_id, task=task)

@app.route('/download/<task_id>')
def download(task_id):
    task = tasks.get(task_id)
    if not task or not task['result_file']:
        return 'Not ready', 404
    return send_file(task['result_file'], as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)

# -- templates/index.html --
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Shopline Bulk Order</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css">
</head>
<body class="p-5">
  <div class="container">
    <h1 class="mb-4">Shopline Bulk Order Creator</h1>
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, msg in messages %}
          <div class="alert alert-{{ category }}">{{ msg }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}
    <form method="post" enctype="multipart/form-data">
      <div class="mb-3">
        <label class="form-label">Access Token</label>
        <input type="text" name="access_token" class="form-control" required>
      </div>
      <div class="mb-3">
        <label class="form-label">Store Domain (e.g., example.shoplineapp.com)</label>
        <input type="text" name="store_domain" class="form-control" required>
      </div>
      <div class="mb-3">
        <label class="form-label">CSV File</label>
        <input type="file" name="csv_file" accept=".csv" class="form-control" required>
      </div>
      <button type="submit" class="btn btn-primary">Start Processing</button>
    </form>
  </div>
</body>
</html>

# -- templates/status.html --
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Task Status</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css">
  <meta http-equiv="refresh" content="5">
</head>
<body class="p-5">
  <div class="container">
    <h1>Status for Task {{ task_id }}</h1>
    <p><strong>Current status:</strong> {{ task.status }}</p>
    <h5>Logs:</h5>
    <pre style="background:#f8f9fa; padding:1rem; height:300px; overflow:auto;">{{ task.logs | join("\n") }}</pre>
    {% if task.status == 'Completed' %}
      <a href="{{ url_for('download', task_id=task_id) }}" class="btn btn-success">Download Results</a>
    {% endif %}
  </div>
</body>
</html>
