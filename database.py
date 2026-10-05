import sqlite3
import time

from Data_Generator import Generate_Values


DATABASE = "customer_churn.db"


def ensure_column(cursor, table_name, column_name, column_definition):
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [column[1] for column in cursor.fetchall()]

    if column_name not in columns:
        cursor.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )


connection = sqlite3.connect(DATABASE, timeout=30)
cursor = connection.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS Customers(
    CustomerID INTEGER,
    Age INTEGER,
    Gender TEXT,
    Tenure INTEGER,
    Usage_Frequency INTEGER,
    Support_Calls INTEGER,
    Payment_Delay INTEGER,
    Subscription_Type TEXT,
    Contract_Length TEXT,
    Total_Spend INTEGER,
    Last_Interaction INTEGER,
    Actual_Churn INTEGER
)
""")

ensure_column(cursor, "Customers", "Actual_Churn", "INTEGER")
connection.commit()

try:
    while True:
        cursor.execute("SELECT MAX(CustomerID) FROM Customers")
        last_id = cursor.fetchone()[0]

        if last_id is None:
            last_id = 0

        customers = Generate_Values(last_id)
        cursor.execute("""
        INSERT INTO Customers (
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
            Actual_Churn
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, customers)

        connection.commit()
        time.sleep(2)
except KeyboardInterrupt:
    pass
finally:
    connection.close()
