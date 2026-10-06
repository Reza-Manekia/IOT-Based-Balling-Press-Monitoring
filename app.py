"""
Baling Press Monitoring Dashboard
----------------------------------
Firebase Realtime Database se bale weight readings fetch karta hai,
web dashboard mein table + statistics dikhata hai, aur Excel download
ka option deta hai.

Run karne ka tareeqa:
    pip install -r requirements.txt
    python app.py

Phir browser mein: http://localhost:5000

AAPKO SIRF NEECHE DIYE GAYE 2 VALUES BHARNI HAIN (Firebase config).
Baaki sab kaam khud hota hai.
"""

from flask import Flask, render_template, send_file
import requests
from datetime import datetime
from collections import defaultdict
import io
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# =========================================================
# FIREBASE CONFIG - YAHAN APNI VALUES DAALEIN
# =========================================================
DATABASE_URL = os.getenv("DARABASE_URL")
LEGACY_TOKEN = os.getenv("LEGACY_TOKEN")
# =========================================================


def fetch_readings():
    """
    Firebase se /readings node ka saara data fetch karta hai.
    Har reading Firebase mein is tarah save hai:
        readings/2026-09-03_15-43-57 -> {id, pH, weight, time}

    Return: list of dicts, sorted by time (oldest to newest)
    """
    url = f"{DATABASE_URL}/readings.json?auth={LEGACY_TOKEN}"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()

    if not data:
        return []

    rows = []
    for key, val in data.items():
        if not val:
            continue
        time_str = val.get("time", "")
        weight = val.get("weight", 0)
        rows.append({
            "time_str": time_str,
            "weight": weight,
        })

    # Time string se actual datetime object banayein sorting ke liye
    def parse_dt(row):
        try:
            return datetime.strptime(row["time_str"], "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return datetime.min

    rows.sort(key=parse_dt)
    return rows


def build_table_and_stats(rows):
    """
    Raw readings se:
    1. Table rows banata hai (S.No, Time, Day, Weight)
    2. Per-day aur per-hour average bale count nikalta hai
    """
    table = []
    day_counts = defaultdict(int)      # e.g. {"2026-09-03": 12}
    hour_counts = defaultdict(int)     # e.g. {"2026-09-03 15": 3}

    for idx, row in enumerate(rows, start=1):
        try:
            dt = datetime.strptime(row["time_str"], "%Y-%m-%d %H:%M:%S")
            display_time = dt.strftime("%I:%M %p")   # e.g. 03:43 PM
            display_day = dt.strftime("%A")           # e.g. Wednesday
            date_key = dt.strftime("%Y-%m-%d")
            hour_key = dt.strftime("%Y-%m-%d %H")
        except (ValueError, TypeError):
            display_time = row["time_str"] or "N/A"
            display_day = "N/A"
            date_key = "unknown"
            hour_key = "unknown"

        table.append({
            "sno": idx,
            "time": display_time,
            "day": display_day,
            "weight": row["weight"],
        })

        day_counts[date_key] += 1
        hour_counts[hour_key] += 1

    total_bales = len(rows)
    num_days = len(day_counts) if day_counts else 1
    num_active_hours = len(hour_counts) if hour_counts else 1

    avg_per_day = round(total_bales / num_days, 1)
    avg_per_hour = round(total_bales / num_active_hours, 1)

    stats = {
        "total_bales": total_bales,
        "avg_per_day": avg_per_day,
        "avg_per_hour": avg_per_hour,
        "num_days": num_days,
    }

    return table, stats


@app.route("/")
def dashboard():
    rows = fetch_readings()
    table, stats = build_table_and_stats(rows)
    # Sabse recent reading upar dikhane ke liye table reverse kar dein (optional)
    table_display = list(reversed(table))
    return render_template("index.html", table=table_display, stats=stats)


@app.route("/download-excel")
def download_excel():
    rows = fetch_readings()
    table, _ = build_table_and_stats(rows)

    df = pd.DataFrame(table)
    df.columns = ["S.No", "Time", "Day", "Weight"]

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Bale Readings")

    output.seek(0)
    filename = f"baling_press_readings_{datetime.now().strftime('%Y-%m-%d')}.xlsx"

    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)