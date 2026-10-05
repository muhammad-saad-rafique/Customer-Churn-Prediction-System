import os

import numpy as np
import pandas as pd


TEST_DATASET = "customer_churn_dataset-testing-master.csv"
_dataset_cache = None


def _load_dataset():
    global _dataset_cache

    if _dataset_cache is None and os.path.exists(TEST_DATASET):
        _dataset_cache = pd.read_csv(TEST_DATASET)

    return _dataset_cache


def Generate_Values(CustomerID):
    dataset = _load_dataset()
    CustomerID += 1

    if dataset is not None and not dataset.empty:
        sample = dataset.sample(1).iloc[0]
        return (
            CustomerID,
            int(sample["Age"]),
            str(sample["Gender"]),
            int(sample["Tenure"]),
            int(sample["Usage Frequency"]),
            int(sample["Support Calls"]),
            int(sample["Payment Delay"]),
            str(sample["Subscription Type"]),
            str(sample["Contract Length"]),
            int(sample["Total Spend"]),
            int(sample["Last Interaction"]),
            int(sample["Churn"]),
        )

    Values_Gender = ["Male", "Female"]
    Values_Subcription = ["Basic", "Standard", "Premium"]
    Values_Contract = ["Monthly", "Annual", "Quarterly"]

    row = (
        CustomerID,
        int(np.random.randint(18, 65)),
        str(np.random.choice(Values_Gender)),
        int(np.random.randint(1, 61)),
        int(np.random.randint(2, 31)),
        int(np.random.randint(0, 10)),
        int(np.random.randint(0, 30)),
        str(np.random.choice(Values_Subcription)),
        str(np.random.choice(Values_Contract)),
        int(np.random.randint(100, 1000)),
        int(np.random.randint(1, 30)),
        None,
    )

    return row
