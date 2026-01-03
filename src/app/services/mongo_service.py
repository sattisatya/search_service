import os
from pymongo import MongoClient
from typing import Tuple, Optional
from dotenv import load_dotenv
load_dotenv()

def connect_to_mongodb(collection_name: str) -> Tuple[Optional[MongoClient], Optional[object]]:
    try:
        mongo_uri = os.getenv('mongo_connection_string')
        # Add tls=True and tlsAllowInvalidCertificates=True for debugging if needed, 
        # but usually just dnspython + correct URI is enough.
        client = MongoClient(mongo_uri)
        # Force a connection check
        client.admin.command('ping')
        
        db = client[os.getenv('db_name', 'crda')]
        collection = db[collection_name]
        return client, collection
    except Exception as e:
        print(f"MongoDB Connection Error: {e}")
        return None, None
    

