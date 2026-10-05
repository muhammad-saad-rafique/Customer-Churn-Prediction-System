import sqlite3
import time

import joblib
import pandas as pd


DATABASE = "customer_churn.db"
MODEL_FILE = "random_forest_model.pkl"


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


def ensure_column(cursor, table_name, column_name, column_definition):
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [column[1] for column in cursor.fetchall()]

    if column_name not in columns:
        cursor.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )


def has_column(cursor, table_name, column_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return column_name in [column[1] for column in cursor.fetchall()]


def table_exists(cursor, table_name):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cursor.fetchone() is not None


connection = sqlite3.connect(DATABASE, timeout=30)
cursor = connection.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS Predictions(
    PredictionID INTEGER PRIMARY KEY AUTOINCREMENT,
    CustomerID INTEGER,
    Prediction INTEGER,
    Probability FLOAT,
    Prediction_time TEXT,
    Actual_Churn INTEGER,
    Is_Correct INTEGER
)
""")

ensure_column(cursor, "Predictions", "Actual_Churn", "INTEGER")
ensure_column(cursor, "Predictions", "Is_Correct", "INTEGER")
connection.commit()

cursor.execute("SELECT MAX(CustomerID) FROM Predictions")
last_processed_id = cursor.fetchone()[0]

if last_processed_id is None:
    last_processed_id = 0

model = joblib.load(MODEL_FILE)

try:
    while True:
        if not table_exists(cursor, "Customers"):
            time.sleep(6)
            continue

        actual_expression = "Actual_Churn" if has_column(cursor, "Customers", "Actual_Churn") else "NULL AS Actual_Churn"
        df = pd.read_sql_query(
            f"""
            SELECT
                CustomerID,
                Age,
                Gender,
                Tenure,
                Usage_Frequency,
                Support_Calls,
                Payment_Delay,
                Subscription_Type,
                Contract_Length,
                Total_Spend,
                Last_Interaction,
                {actual_expression}
            FROM Customers
            WHERE CustomerID > ?
            ORDER BY CustomerID
            LIMIT 3
            """,
            connection,
            params=(last_processed_id,),
        )

        if df.empty:
            time.sleep(6)
            continue

        fill_values = {
            "Age": df["Age"].mean(),
            "Gender": df["Gender"].mode()[0] if not df["Gender"].mode().empty else "Male",
            "Tenure": df["Tenure"].mean(),
            "Usage_Frequency": df["Usage_Frequency"].mean(),
            "Support_Calls": df["Support_Calls"].mean(),
            "Payment_Delay": df["Payment_Delay"].mean(),
            "Subscription_Type": df["Subscription_Type"].mode()[0] if not df["Subscription_Type"].mode().empty else "Basic",
            "Contract_Length": df["Contract_Length"].mode()[0] if not df["Contract_Length"].mode().empty else "Monthly",
            "Total_Spend": df["Total_Spend"].mean(),
            "Last_Interaction": df["Last_Interaction"].mean(),
        }
        df = df.fillna(value=fill_values)

        df = df.rename(
            columns={
                "Usage_Frequency": "Usage Frequency",
                "Support_Calls": "Support Calls",
                "Payment_Delay": "Payment Delay",
                "Subscription_Type": "Subscription Type",
                "Contract_Length": "Contract Length",
                "Total_Spend": "Total Spend",
                "Last_Interaction": "Last Interaction",
            }
        )

        customer_ids = df["CustomerID"].copy()
        actual_churn = df["Actual_Churn"].copy()

        df["Gender"] = df["Gender"].map({
            "Male": 1,
            "Female": 0,
        })

        df = pd.get_dummies(
            df.drop(columns=["CustomerID", "Actual_Churn"]),
            columns=["Subscription Type", "Contract Length"],
            dtype=int,
        )

        X = df.reindex(columns=FEATURE_COLUMNS, fill_value=0)

        predictions = model.predict(X)
        churn_probability = model.predict_proba(X)[:, 1]

        prediction_records = []

        for index in range(len(customer_ids)):
            actual = actual_churn.iloc[index]
            actual_value = None if pd.isna(actual) else int(actual)
            predicted_value = int(predictions[index])
            is_correct = None

            if actual_value is not None:
                is_correct = int(predicted_value == actual_value)

            prediction_records.append(
                (
                    int(customer_ids.iloc[index]),
                    predicted_value,
                    float(churn_probability[index]),
                    time.strftime("%Y-%m-%d %H:%M:%S"),
                    actual_value,
                    is_correct,
                )
            )

        cursor.executemany("""
        INSERT INTO Predictions(
            CustomerID,
            Prediction,
            Probability,
            Prediction_time,
            Actual_Churn,
            Is_Correct
        )
        VALUES(?, ?, ?, ?, ?, ?)
        """, prediction_records)

        last_processed_id = int(customer_ids.max())
        connection.commit()
        time.sleep(6)
except KeyboardInterrupt:
    pass
finally:
    connection.close()
