import logging
from typing import Optional
from pymongo import MongoClient
import mongomock
from app.config import settings

logger = logging.getLogger("nettrace.mongo")

class MongoManager:
    _instance: Optional["MongoManager"] = None

    def __init__(self):
        self.client = None
        self.db = None
        self.is_atlas = False
        self._initialize_connection()

    def _initialize_connection(self):
        uri = settings.MONGODB_URI.strip() if settings.MONGODB_URI else ""
        if uri:
            try:
                logger.info("Attempting connection to MongoDB Atlas...")
                self.client = MongoClient(uri, serverSelectionTimeoutMS=4000)
                # Verify connection with ping
                self.client.admin.command('ping')
                self.db = self.client[settings.MONGODB_DB_NAME]
                self.is_atlas = True
                logger.info(f"Connected successfully to MongoDB Atlas! DB: {settings.MONGODB_DB_NAME}")
            except Exception as e:
                logger.warning(f"Could not connect to MongoDB Atlas ({e}). Falling back to Embedded In-Memory Engine.")
                self.client = mongomock.MongoClient()
                self.db = self.client[settings.MONGODB_DB_NAME]
                self.is_atlas = False
        else:
            logger.info("No MONGODB_URI specified. Using High-Performance Embedded In-Memory MongoDB Engine.")
            self.client = mongomock.MongoClient()
            self.db = self.client[settings.MONGODB_DB_NAME]
            self.is_atlas = False

    @classmethod
    def get_instance(cls) -> "MongoManager":
        if cls._instance is None:
            cls._instance = MongoManager()
        return cls._instance

    @property
    def policies(self):
        return self.db["policies"]

    @property
    def pull_requests(self):
        return self.db["pull_requests"]

    @property
    def deployments(self):
        return self.db["deployments"]

    @property
    def attestations(self):
        return self.db["attestations"]

    @property
    def agent_memory(self):
        return self.db["agent_memory"]

    @property
    def network_telemetry(self):
        return self.db["network_telemetry"]

    @property
    def drifts(self):
        return self.db["drifts"]

    @property
    def audit_logs(self):
        return self.db["audit_logs"]

def get_db():
    return MongoManager.get_instance()
