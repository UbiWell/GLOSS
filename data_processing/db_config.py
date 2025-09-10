"""
File to access MongoDB
"""
import urllib.parse

from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from data_processing import mongo_config as definitions
import os


class DbConfig:
    '''
    load config
    '''

    def __init__(self):
        self.db_host = definitions.host
        self.db_port = int(definitions.port)
        self.database = definitions.database
        self.db_user = definitions.username
        if definitions.password:
            self.db_pwd = urllib.parse.quote(definitions.password)
        if self.db_user and self.db_pwd:
            self.db_uri = os.getenv("MONGO_URI",
                                    "mongodb://{}:{}@{}:{}/{}".format(self.db_user, self.db_pwd, self.db_host,
                                                                      self.db_port,
                                                                      self.database))
        else:
            self.db_uri = os.getenv("MONGO_URI", f"mongodb://{self.db_host}:{self.db_port}/{self.database}")

    def getDb(self):
        client = MongoClient(self.db_uri)
        return client[self.database]

    def getTempClient(self):
        return MongoClient(self.db_uri)

    def getTempClientPool(self):
        return MongoClient(self.db_uri, maxPoolSize=100)


if __name__ == "__main__":
    DbConfig().getDb()
