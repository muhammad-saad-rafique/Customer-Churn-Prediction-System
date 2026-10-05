import os
import subprocess
import sys
import threading

import joblib
import pandas as pd
import sqlite3
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "customer_churn.db")
MODEL_FILE = os.path.join(BASE_DIR, "random_forest_model.pkl")

FEATURE_COLUMNS = [
    "Age",
    "Gender",
    "Tenure",
    "Usage Frequency",
    "Support Calls",
    "Payment Delay",
    "Total Spend",
    "Last Interaction",
    "Subscription Type_Basic",
    "Subscription Type_Premium",
    "Subscription Type_Standard",
    "Contract Length_Annual",
    "Contract Length_Monthly",
    "Contract Length_Quarterly",
]

app = Flask(__name__)
CORS(app)

process_lock = threading.Lock()
managed_processes = {
    "database": None,
    "prediction": None,
}

model = None


def get_model():
    global model

    if model is None:
        if not os.path.exists(MODEL_FILE):
            raise FileNotFoundError(f"{MODEL_FILE} was not found.")
        model = joblib.load(MODEL_FILE)

    return model


def get_connection():
    connection = sqlite3.connect(DATABASE, timeout=30)
    connection.row_factory = sqlite3.Row
    return connection


def table_exists(cursor, table_name):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def has_column(cursor, table_name, column_name):
    if not table_exists(cursor, table_name):
        return False

    cursor.execute(f"PRAGMA table_info({table_name})")
    return column_name in [column[1] for column in cursor.fetchall()]


def process_running(process):
    return process is not None and process.poll() is None


def get_process_status():
    with process_lock:
        return {
            name: {
                "running": process_running(process),
                "pid": process.pid if process_running(process) else None,
            }
            for name, process in managed_processes.items()
        }


def start_process(name):
    scripts = {
        "database": "database.py",
        "prediction": "predictions.py",
    }

    if name not in scripts:
        return {"error": "Unknown process"}, 404

    with process_lock:
        current_process = managed_processes[name]
        if process_running(current_process):
            return {
                "name": name,
                "running": True,
                "pid": current_process.pid,
                "message": f"{name} is already running.",
            }, 200

        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

        process = subprocess.Popen(
            [sys.executable, "-u", scripts[name]],
            cwd=BASE_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        managed_processes[name] = process

        return {
            "name": name,
            "running": True,
            "pid": process.pid,
            "message": f"{name} started.",
        }, 200


def stop_process(name):
    if name not in managed_processes:
        return {"error": "Unknown process"}, 404

    with process_lock:
        process = managed_processes[name]
        if not process_running(process):
            managed_processes[name] = None
            return {
                "name": name,
                "running": False,
                "pid": None,
                "message": f"{name} is already stopped.",
            }, 200

        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

        managed_processes[name] = None

    return {
        "name": name,
        "running": False,
        "pid": None,
        "message": f"{name} stopped.",
    }, 200


def count_rows(cursor, table_name):
    if not table_exists(cursor, table_name):
        return 0

    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    return int(cursor.fetchone()[0])


@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


@app.route("/api/processes", methods=["GET"])
def api_processes():
    return jsonify(get_process_status())


@app.route("/api/process/<name>/start", methods=["POST"])
def api_start_process(name):
    response, status_code = start_process(name)
    return jsonify(response), status_code


@app.route("/api/process/<name>/stop", methods=["POST"])
def api_stop_process(name):
    response, status_code = stop_process(name)
    return jsonify(response), status_code


@app.route("/api/process/<name>/toggle", methods=["POST"])
def api_toggle_process(name):
    current = get_process_status().get(name)
    if current is None:
        return jsonify({"error": "Unknown process"}), 404

    if current["running"]:
        response, status_code = stop_process(name)
    else:
        response, status_code = start_process(name)

    return jsonify(response), status_code


@app.route("/customers", methods=["GET"])
def get_customers():
    connection = get_connection()
    cursor = connection.cursor()
    limit = request.args.get("limit", 20, type=int)

    if not table_exists(cursor, "Customers"):
        connection.close()
        return jsonify([])

    cursor.execute("SELECT * FROM Customers ORDER BY CustomerID DESC LIMIT ?", (limit,))
    customers = [dict(row) for row in cursor.fetchall()]
    connection.close()
    return jsonify(customers)


@app.route("/predictions", methods=["GET"])
def get_predictions():
    connection = get_connection()
    cursor = connection.cursor()
    limit = request.args.get("limit", 20, type=int)

    if not table_exists(cursor, "Predictions"):
        connection.close()
        return jsonify([])

    if has_column(cursor, "Predictions", "Actual_Churn") and has_column(cursor, "Predictions", "Is_Correct"):
        cursor.execute("""
            SELECT
                PredictionID,
                CustomerID,
                Prediction,
                Probability,
                Prediction_time,
                Actual_Churn,
                Is_Correct
            FROM Predictions
            ORDER BY PredictionID DESC
            LIMIT ?
        """, (limit,))
    else:
        cursor.execute("""
            SELECT
                PredictionID,
                CustomerID,
                Prediction,
                Probability,
                Prediction_time,
                NULL AS Actual_Churn,
                NULL AS Is_Correct
            FROM Predictions
            ORDER BY PredictionID DESC
            LIMIT ?
        """, (limit,))

    predictions = [dict(row) for row in cursor.fetchall()]
    connection.close()
    return jsonify(predictions)


@app.route("/statistics", methods=["GET"])
def get_statistics():
    connection = get_connection()
    cursor = connection.cursor()

    total_customers = count_rows(cursor, "Customers")
    total_predictions = count_rows(cursor, "Predictions")
    churned = 0
    not_churned = 0
    actual_labels = 0
    correct_predictions = 0

    if table_exists(cursor, "Predictions"):
        cursor.execute("SELECT COUNT(*) FROM Predictions WHERE Prediction = 1")
        churned = int(cursor.fetchone()[0])

        cursor.execute("SELECT COUNT(*) FROM Predictions WHERE Prediction = 0")
        not_churned = int(cursor.fetchone()[0])

        if has_column(cursor, "Predictions", "Is_Correct"):
            cursor.execute("SELECT COUNT(*) FROM Predictions WHERE Is_Correct IS NOT NULL")
            actual_labels = int(cursor.fetchone()[0])

            cursor.execute("SELECT COUNT(*) FROM Predictions WHERE Is_Correct = 1")
            correct_predictions = int(cursor.fetchone()[0])

    connection.close()

    churn_rate = (churned / total_predictions) * 100 if total_predictions > 0 else 0
    accuracy = (correct_predictions / actual_labels) * 100 if actual_labels > 0 else None

    return jsonify({
        "total_customers": total_customers,
        "total_predictions": total_predictions,
        "prediction_churn": churned,
        "predicted_not_churn": not_churned,
        "churn_rate": round(churn_rate, 2),
        "actual_labels": actual_labels,
        "correct_predictions": correct_predictions,
        "accuracy": round(accuracy, 2) if accuracy is not None else None,
        "processes": get_process_status(),
    })


@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Customer data is required"}), 400

    required_fields = [
        "Age",
        "Gender",
        "Tenure",
        "Usage Frequency",
        "Support Calls",
        "Payment Delay",
        "Subscription Type",
        "Contract Length",
        "Total Spend",
        "Last Interaction",
    ]

    missing_fields = [field for field in required_fields if field not in data]

    if missing_fields:
        return jsonify({
            "error": "Missing required fields",
            "fields": missing_fields,
        }), 400

    df = pd.DataFrame([data])

    df["Gender"] = df["Gender"].map({
        "Male": 1,
        "Female": 0,
    })

    if df["Gender"].isnull().any():
        return jsonify({"error": "Gender must be Male or Female"}), 400

    df = pd.get_dummies(
        df,
        columns=["Subscription Type", "Contract Length"],
        dtype=int,
    )

    df = df.reindex(
        columns=FEATURE_COLUMNS,
        fill_value=0,
    )

    current_model = get_model()
    prediction = current_model.predict(df)[0]
    probabilities = current_model.predict_proba(df)[0]
    churn_probability = probabilities[1]

    return jsonify({
        "prediction": int(prediction),
        "prediction_label": "Churn" if prediction == 1 else "Not Churn",
        "churn_probability": round(float(churn_probability), 4),
        "churn_percentage": round(float(churn_probability) * 100, 2),
    })


if __name__ == "__main__":
    app.run(
        debug=True,
        port=5000,
        use_reloader=False,
    )
