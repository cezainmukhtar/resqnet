import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import urlopen

from flask import Flask, jsonify, request
from flask_cors import CORS

from alerts import describe_rules, evaluate_alerts, overall_risk, summarize_forecast

app = Flask(__name__)
CORS(app)

# Database file always lives next to app.py, whatever folder you run it from
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resqnet.db")

EMERGENCY_TYPES = ["Flood", "Landslide", "Fire", "Earthquake", "Medical", "Other"]

# Alerts look this many hours ahead; forecasts are cached to spare Open-Meteo
WINDOW_HOURS = 24
FORECAST_TTL_SECONDS = 600
FORECAST_CACHE = {}


def utc_now_text():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def parse_coordinates(raw_latitude, raw_longitude):
    """Return (latitude, longitude) as floats, or None if missing or out of range."""
    try:
        latitude = float(raw_latitude)
        longitude = float(raw_longitude)
    except (TypeError, ValueError):
        return None

    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None

    return latitude, longitude


# DATABASE CONNECTION
def get_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


# CREATE / UPGRADE DATABASE TABLE
def initialize_database():
    connection = get_db()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            emergency_type TEXT NOT NULL,
            description TEXT NOT NULL,
            location TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            created_at TEXT NOT NULL
        )
    """)

    # Older databases were created without coordinates: add the columns in place
    existing = {row["name"] for row in connection.execute("PRAGMA table_info(reports)")}
    if "latitude" not in existing:
        connection.execute("ALTER TABLE reports ADD COLUMN latitude REAL")
    if "longitude" not in existing:
        connection.execute("ALTER TABLE reports ADD COLUMN longitude REAL")

    connection.commit()
    connection.close()


initialize_database()


# HOME ROUTE
@app.route("/")
def home():
    return jsonify({
        "message": "ResQnet Backend is running!",
        "status": "Online"
    })


# WEATHER API
@app.route("/weather")
def weather():
    try:
        latitude = request.args.get("latitude")
        longitude = request.args.get("longitude")

        if not latitude or not longitude:
            return jsonify({
                "error": "Latitude and longitude are required"
            }), 400

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m"
        }

        url = "https://api.open-meteo.com/v1/forecast?" + urlencode(params)

        with urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())

        return jsonify({
            "status": "success",
            "weather": data["current"]
        })

    except Exception:
        app.logger.exception("Weather request failed")
        return jsonify({
            "status": "error",
            "message": "Weather service unavailable"
        }), 500


def fetch_forecast(latitude, longitude):
    """Hourly forecast for the next WINDOW_HOURS, cached. Returns (data, fetched_at)."""
    key = (round(latitude, 2), round(longitude, 2))
    cached = FORECAST_CACHE.get(key)

    if cached and time.time() - cached["time"] < FORECAST_TTL_SECONDS:
        return cached["data"], cached["fetched_at"]

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "precipitation,wind_gusts_10m,temperature_2m",
        "forecast_hours": WINDOW_HOURS,
        "timezone": "UTC",
    }
    url = "https://api.open-meteo.com/v1/forecast?" + urlencode(params)

    with urlopen(url, timeout=10) as response:
        data = json.loads(response.read().decode())

    fetched_at = utc_now_text()
    FORECAST_CACHE[key] = {"time": time.time(), "data": data, "fetched_at": fetched_at}
    return data, fetched_at


# WEATHER-BASED ALERTS (rule-based, generated from the live forecast)
@app.route("/alerts")
def get_alerts():
    coordinates = parse_coordinates(
        request.args.get("latitude"), request.args.get("longitude")
    )

    if coordinates is None:
        return jsonify({
            "error": "Valid latitude (-90 to 90) and longitude (-180 to 180) are required"
        }), 400

    latitude, longitude = coordinates

    try:
        data, fetched_at = fetch_forecast(latitude, longitude)
        summary = summarize_forecast(data.get("hourly", {}), WINDOW_HOURS)
    except Exception:
        app.logger.exception("Forecast request failed")
        return jsonify({
            "status": "error",
            "message": "Forecast service unavailable"
        }), 502

    if summary is None:
        return jsonify({
            "status": "error",
            "message": "Forecast data incomplete"
        }), 502

    alerts = evaluate_alerts(summary)

    return jsonify({
        "status": "success",
        "location": {"latitude": latitude, "longitude": longitude},
        "window_hours": WINDOW_HOURS,
        "generated_at": utc_now_text(),
        "forecast_fetched_at": fetched_at,
        "summary": summary,
        "risk_level": overall_risk(alerts),
        "alerts": alerts,
        "rules": describe_rules(),
    })


# SUBMIT EMERGENCY REPORT
@app.route("/reports", methods=["POST"])
def create_report():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Invalid request"}), 400

    name = str(data.get("name", "")).strip()
    emergency_type = str(data.get("emergency_type", "")).strip()
    description = str(data.get("description", "")).strip()
    location = str(data.get("location", "")).strip()

    if not all([name, emergency_type, description, location]):
        return jsonify({"error": "All fields are required"}), 400

    if emergency_type not in EMERGENCY_TYPES:
        return jsonify({
            "error": "emergency_type must be one of: " + ", ".join(EMERGENCY_TYPES)
        }), 400

    if len(name) > 100 or len(location) > 200 or len(description) > 1000:
        return jsonify({"error": "One of the fields is too long"}), 400

    coordinates = parse_coordinates(data.get("latitude"), data.get("longitude"))

    if coordinates is None:
        return jsonify({
            "error": "Valid latitude (-90 to 90) and longitude (-180 to 180) are required"
        }), 400

    latitude, longitude = coordinates

    connection = get_db()

    cursor = connection.execute("""
        INSERT INTO reports
        (name, emergency_type, description, location, latitude, longitude, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        name,
        emergency_type,
        description,
        location,
        latitude,
        longitude,
        utc_now_text()
    ))

    connection.commit()
    report_id = cursor.lastrowid
    connection.close()

    return jsonify({
        "status": "success",
        "message": "Emergency report submitted",
        "report_id": report_id
    }), 201


# GET ALL EMERGENCY REPORTS
@app.route("/reports", methods=["GET"])
def get_reports():
    connection = get_db()

    reports = connection.execute(
        "SELECT * FROM reports ORDER BY id DESC"
    ).fetchall()

    connection.close()

    return jsonify([dict(report) for report in reports])


# RUN SERVER
if __name__ == "__main__":
    app.run(debug=True, port=5000)
