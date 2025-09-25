import os
from pymongo import MongoClient
from typing import Tuple, Optional
from dotenv import load_dotenv
load_dotenv()

def connect_to_mongodb(collection_name: str) -> Tuple[Optional[MongoClient], Optional[object]]:
    try:
        mongo_uri = os.getenv('mongo_connection_string')
        client = MongoClient(mongo_uri)
        db = client[os.getenv('db_name', 'crda')]
        collection = db[collection_name]
        return client, collection
    except Exception:
        return None, None
    
