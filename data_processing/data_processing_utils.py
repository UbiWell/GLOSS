"""
Utility functions for reading passive sensing data from the sample CSVs.

The MongoDB path this module used to carry was dropped along with db_config /
mongo_config: this deployment reads CSVs only and there is no database to talk
to. Restore those modules from version control if a database-backed deployment
is ever needed again.
"""
from typing import List, Dict, Any
import os
import pandas as pd


def fetch_documents_between_timestamps(uid: str, start_timestamp: int, end_timestamp: int,
                                       collection_name: str) -> List[Dict[str, Any]]:
    """
    Fetch documents for one user from a sample CSV, between two timestamps.

    Parameters:
    - uid (str): User identifier to filter documents.
    - start_timestamp (int): The start timestamp (inclusive).
    - end_timestamp (int): The end timestamp (exclusive).
    - collection_name (str): The name of the CSV file (without .csv) to query.

    Returns:
    - list: A list of documents that match the query, sorted by timestamp.
    """
    csv_filename = None
    try:
        # Read CSV file from sample_data folder
        if os.getenv("RUNNING_IN_DOCKER") == "true":
            csv_filename = f"/workspace/sample_data/{collection_name}.csv"
        else:
            # Resolved from this file rather than the working directory, so
            # it does not matter where the process was started from.
            repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            csv_filename = os.path.join(repo_root, "sample_data", f"{collection_name}.csv")
        df = pd.read_csv(csv_filename)

        # Filter by uid
        df = df[df['uid'] == uid]

        # Determine timestamp column name based on collection
        timestamp_col = 'start_timestamp' if collection_name == 'ios_steps' else 'timestamp'

        if timestamp_col in df.columns:
            # Filter by timestamp range, then sort
            mask = (df[timestamp_col] >= start_timestamp) & (df[timestamp_col] < end_timestamp)
            df_filtered = df[mask].sort_values(by=timestamp_col)

            # Convert back to list of dictionaries
            documents = df_filtered.to_dict('records')
        else:
            print(f"Warning: '{timestamp_col}' column not found in CSV")
            documents = []

    except FileNotFoundError:
        print(f"Error: CSV file '{csv_filename}' not found")
        documents = []
    except Exception as e:
        print(f"Error reading CSV: {e}")
        documents = []

    return documents
