"""
Utility functions for data processing with MongoDB.
"""
from pymongo import MongoClient
from datetime import datetime
from data_processing import db_config
import pymongo


def fetch_documents_between_timestamps(uid, start_timestamp, end_timestamp, collection_name):
    """
    Fetch documents from a MongoDB collection between two timestamps.

    Parameters:
    - start_timestamp (datetime): The start timestamp.
    - end_timestamp (datetime): The end timestamp.
    - collection_name (str): The name of the collection to query.
    - db_name (str): The name of the database. Default is 'your_database_name'.

    Returns:
    - list: A list of documents that match the query.
    """
    db = db_config.DbConfig().getDb()
    collection = db[collection_name]
    if collection_name == 'ios_steps':
        query = {
            'uid': uid,
            'start_timestamp': {
                '$gte': start_timestamp,
                '$lt': end_timestamp
            }
        }
    else:
        query = {
            'uid': uid,
            'timestamp': {
                '$gte': start_timestamp,
                '$lt': end_timestamp
            }
        }

    results = collection.find(query, sort=[('timestamp', pymongo.ASCENDING)])
    documents = list(results)

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


# Example usage
if __name__ == "__main__":
    start_datetime = datetime(2024, 7, 1, 0, 0, 0)
    end_datetime = datetime(2024, 7, 12, 23, 59, 59)

    start_timestamp = start_datetime.timestamp()
    end_timestamp = end_datetime.timestamp()

    collection_name = 'ios_steps'

    documents = fetch_documents_between_timestamps("test004", start_timestamp, end_timestamp, collection_name)

    for doc in documents:
        print(doc)

    print("total entries:", len(documents))
