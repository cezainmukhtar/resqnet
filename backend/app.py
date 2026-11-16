from flask import Flask, jsonify, request
from flask_cors import CORS
from urllib.request import urlopen
from urllib.parse import urlencode
import json
import sqlite3
from datetime import datetime

app = Flask(__name__)
CORS(app)

# DATABASE CONNECTION
def get_db():
    connection = sqlite3.connect("resqnet.db")
    connection.row_factory = sqlite3.Row
    return connection


# CREATE DATABASE TABLE
def initialize_database():
    connection = get_db()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            emergency_type TEXT NOT NULL,
            description TEXT NOT NULL,
            location TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

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

    except Exception as error:
        return jsonify({
            "status": "error",
            "message": str(error)
        }), 500


# SUBMIT EMERGENCY REPORT
@app.route("/reports", methods=["POST"])
def create_report():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid request"}), 400

    name = data.get("name", "").strip()
    emergency_type = data.get("emergency_type", "").strip()
    description = data.get("description", "").strip()
    location = data.get("location", "").strip()

    if not all([name, emergency_type, description, location]):
        return jsonify({
            "error": "All fields are required"
        }), 400

    connection = get_db()

    cursor = connection.execute("""
        INSERT INTO reports
        (name, emergency_type, description, location, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        name,
        emergency_type,
        description,
        location,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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