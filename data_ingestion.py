import json
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import pprint
import pandas as pd

def load_json_data(file_path):
    """Load and return data from a JSON file."""
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
            return data
    except FileNotFoundError:
        print(f"The file '{file_path}' was not found.")
        return None
    except json.JSONDecodeError:
        print("There was an error decoding the JSON.")
        return None

def load_excel_data(file_path):
    """Load and return data from an Excel file."""
    try:
        # Read the Excel file
        df = pd.read_excel(file_path, sheet_name=0)  # sheet_name=0 means first sheet
        
        # Convert DataFrame to list of dictionaries
        data = df.to_dict('records')
        return data
    except FileNotFoundError:
        print(f"The file '{file_path}' was not found.")
        return None
    except Exception as e:
        print(f"Error reading Excel file: {str(e)}")
        return None

def save_to_mongodb(transformed_data):
    """Save transformed data to MongoDB."""
    try:
        # Get MongoDB connection string from environment variable
        mongo_uri = os.getenv('mongo_connection_string')
        
        # Create MongoDB client
        client = MongoClient(mongo_uri)
        
        # Access the crda database
        db = client['crda']
        
        # Access the insights collection
        collection = db['insights']
        
        # Insert the transformed data
        if isinstance(transformed_data, list):
            result = collection.insert_many(transformed_data)
            print(f"Successfully inserted {len(result.inserted_ids)} documents")
        else:
            result = collection.insert_one(transformed_data)
            print(f"Successfully inserted document with id: {result.inserted_id}")
            
        client.close()
        return True
        
    except Exception as e:
        print(f"Error saving to MongoDB: {str(e)}")
        return False

def main():
    """Main function to orchestrate the data processing pipeline."""
    # Load environment variables
    load_dotenv()
    
    # Load Excel data
    data = load_excel_data('insights.xlsx')
    if not data:
        return
    
    # Print data for verification (first 2 entries)
    print("Data to be inserted:")
    pprint.pprint(data[:2])  

    # Save to MongoDB
    if data:
        success = save_to_mongodb(data)
        if success:
            print("Data successfully saved to MongoDB insights collection")
        else:
            print("Failed to save data to MongoDB")

if __name__ == "__main__":
    main()