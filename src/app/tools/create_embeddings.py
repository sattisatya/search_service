from pymongo import MongoClient
from dotenv import load_dotenv
import os
from openai import OpenAI
import time

def connect_to_mongodb():
    """Connect to MongoDB and return database and collection objects"""
    try:
        mongo_uri = os.getenv('mongo_connection_string')
        client = MongoClient(mongo_uri)
        db = client['crda']
        collection = db['knowledge_bank']
        return client, collection
    except Exception as e:
        print(f"Error connecting to MongoDB: {str(e)}")
        return None, None

def get_embedding(text, model="text-embedding-ada-002", client=None):
    """Get embedding for a text using OpenAI API"""
    try:
        response = client.embeddings.create(
            model=model,
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error getting embedding: {str(e)}")
        return None

def process_questions_and_create_embeddings():
    """Process only main user questions and create embeddings"""
    # Load environment variables
    load_dotenv()
    
    # Initialize OpenAI client
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    # Connect to MongoDB
    mongo_client, collection = connect_to_mongodb()
    if mongo_client is None or collection is None:
        return
    
    try:
        # Get all documents from the collection
        documents = collection.find({})
        
        for doc in documents:
            # Generate embedding only for main question
            if 'user_question_short' in doc:
                main_q_embedding = get_embedding(doc['user_question_short'], client=openai_client)
                if main_q_embedding:
                    # Update document with only the main question embedding
                    collection.update_one(
                        {'_id': doc['_id']},
                        {'$set': {'question_embedding': main_q_embedding}}
                    )
                    print(f"Updated embedding for document {doc['_id']}")
            
            # Sleep briefly to respect API rate limits
            time.sleep(0.5)
        
        print("Completed processing all documents")
        
    except Exception as e:
        print(f"Error processing documents: {str(e)}")
    
    finally:
        if mongo_client is not None:
            mongo_client.close()

if __name__ == "__main__":
    process_questions_and_create_embeddings()