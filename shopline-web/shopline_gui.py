# /root/shopline-web/shopline_gui.py
import csv
import requests

class ShoplineBulkOrderCreator:
    def __init__(self, access_token: str, store_domain: str):
        self.token = access_token
        self.domain = store_domain.rstrip('/')

    def process_csv_file(self, csv_path: str, log_cb=None) -> dict:
        results = {}
        with open(csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                email = row.get('customer_email', f"row{len(results)+1}")
                data = {k: v for k, v in row.items() if k != 'customer_email'}
                api_url = f"https://{self.domain}/api/orders"
                headers = {
                    'Authorization': f"Bearer {self.token}",
                    'Content-Type': 'application/json'
                }
                try:
                    resp = requests.post(api_url, json=data, headers=headers, timeout=30)
                    status = resp.status_code
                    try:
                        body = resp.json()
                    except ValueError:
                        body = resp.text
                except Exception as e:
                    status, body = 0, str(e)
                results[email] = {'status': status, 'response': body}
                if log_cb:
                    log_cb(f"Processed {email}: {status}")
        return results
