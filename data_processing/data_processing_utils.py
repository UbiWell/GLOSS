"""
Utility functions for data processing with MongoDB.
"""
from pymongo import MongoClient
from datetime import datetime
from data_processing import db_config
from agents.config import USE_CSV
import pymongo
from typing import List, Dict, Any
import os
import pandas as pd


def fetch_documents_between_timestamps(uid: str, start_timestamp: int, end_timestamp: int,
                                       collection_name: str) -> List[Dict[str, Any]]:
    """
    Fetch documents from a MongoDB collection or CSV file between two timestamps.

    Parameters:
    - uid (str): User identifier to filter documents.
    - start_timestamp (datetime): The start timestamp (inclusive).
    - end_timestamp (datetime): The end timestamp (exclusive).
    - collection_name (str): The name of the collection/CSV file to query.
    - USE_CSV (bool): Whether to read from CSV instead of MongoDB.

    Returns:
    - list: A list of documents that match the query, sorted by timestamp.
    """

    if USE_CSV:
        try:
            # Read CSV file from sample_data folder
            if os.getenv("RUNNING_IN_DOCKER") == "true":
                csv_filename = f"/workspace/sample_data/{collection_name}.csv"
            else:
                csv_filename = f"../sample_data/{collection_name}.csv"
            df = pd.read_csv(csv_filename)

            # Filter by uid
            df = df[df['uid'] == uid]

            # Determine timestamp column name based on collection
            timestamp_col = 'start_timestamp' if collection_name == 'ios_steps' else 'timestamp'

            # Convert timestamp column to datetime if it's not already
            if timestamp_col in df.columns:

                # print(start_timestamp, end_timestamp)
                # print(df[timestamp_col])

                # Filter by timestamp range
                mask = (df[timestamp_col] >= start_timestamp) & (df[timestamp_col] < end_timestamp)
                df_filtered = df[mask]

                # Sort by timestamp
                df_filtered = df_filtered.sort_values(by=timestamp_col)

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

    else:
        try:
            # MongoDB implementation
            db = db_config.DbConfig().getDb()
            collection = db[collection_name]

            # Build query based on collection type
            if collection_name == 'ios_steps':
                query = {
                    'uid': uid,
                    'start_timestamp': {
                        '$gte': start_timestamp,
                        '$lte': end_timestamp  # Changed to $lte for consistency
                    }
                }
                sort_field = 'start_timestamp'
            else:
                query = {
                    'uid': uid,
                    'timestamp': {
                        '$gte': start_timestamp,
                        '$lte': end_timestamp  # Changed to $lte for consistency
                    }
                }
                sort_field = 'timestamp'

            # Execute query with proper sorting
            results = collection.find(query).sort(sort_field, pymongo.ASCENDING)
            documents = list(results)

        except Exception as e:
            print(f"Error querying MongoDB: {e}")
            documents = []

    return documents


def fetch_first_and_last_document(uid, collection_name):
    """
    Fetch the first and last documents for a specific uid from a MongoDB collection.

    Parameters:
    - uid (str): The user ID to filter the documents.
    - collection_name (str): The name of the collection to query.

    Returns:
    - tuple: A tuple containing the first and last documents for the specified uid.
    """
    db = db_config.DbConfig().getDb()
    collection = db[collection_name]

    # Fetch all documents for the specified uid, sorted by timestamp
    results = collection.find({'uid': uid}).sort('timestamp', pymongo.ASCENDING)
    documents = list(results)

    # Return the first and last documents
    if documents:
        first_document = documents[0]
        last_document = documents[-1]
        return first_document, last_document
    else:
        return None, None  # Return None if no documents are found

def fetch_first_and_last_document(uid, collection_name):
    """
    Fetch the first and last documents for a specific uid from a MongoDB collection.

    Parameters:
    - uid (str): The user ID to filter the documents.
    - collection_name (str): The name of the collection to query.

    Returns:
    - tuple: A tuple containing the first and last documents for the specified uid.
    """
    db = db_config.DbConfig().getDb()
    collection = db[collection_name]

    # Fetch all documents for the specified uid, sorted by timestamp
    results = collection.find({'uid': uid}).sort('timestamp', pymongo.ASCENDING)
    documents = list(results)

    # Return the first and last documents
    if documents:
        first_document = documents[0]
        last_document = documents[-1]
        return first_document, last_document
    else:
        return None, None  # Return None if no documents are found


# Example usage
if __name__ == "__main__":
    start_datetime = datetime(2025, 8, 28, 0, 0, 0)
    end_datetime = datetime(2025, 8, 28, 23, 59, 59)

    start_timestamp = start_datetime.timestamp()
    end_timestamp = end_datetime.timestamp()

    collection_name = 'ios_steps'

    documents = fetch_documents_between_timestamps("test004", start_timestamp, end_timestamp, collection_name)

    for doc in documents:
        print(doc)

    print("total entries:", len(documents))
