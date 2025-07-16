# /root/shopline-web/app.py
from flask import Flask, request, render_template, send_file
import os, json
from shopline_gui import ShoplineBulkOrderCreator

app = Flask(__name__)

UPLOAD_DIR = "/tmp/shopline_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        csv_file = request.files.get("csv_file")
        token = request.form.get("access_token", "").strip()
        domain = request.form.get("store_domain", "").strip()
        if not (csv_file and token and domain):
            return render_template("index.html", error="All fields are required.")

        csv_path = os.path.join(UPLOAD_DIR, csv_file.filename)
        csv_file.save(csv_path)

        creator = ShoplineBulkOrderCreator(token, domain)
        results = creator.process_csv_file(csv_path, log_cb=lambda m: None)

        result_path = os.path.join(UPLOAD_DIR, "results.json")
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        return send_file(result_path, as_attachment=True, download_name="results.json")

    return render_template("index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
