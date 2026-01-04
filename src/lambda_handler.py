import sys
import json
sys.path.append("/var/task/src/app")

from fastapi import Request
from mangum import Mangum
from src.app.main import app

handler = Mangum(app)

def lambda_handler(event, context):
    """
    AWS Lambda entrypoint for FastAPI app using Mangum adapter.
    """
    # CORS headers
    cors_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
    }

    # Handle OPTIONS preflight request
    # Check for method in requestContext (API Gateway v2 / Function URL) or httpMethod (API Gateway v1)
    method = event.get('requestContext', {}).get('http', {}).get('method') or event.get('httpMethod')
    
    if method == 'OPTIONS':
        return {
            "statusCode": 200,
            "headers": cors_headers,
            "body": ""
        }

    # Process the request
    response = handler(event, context)
    
    # Ensure headers exist in response
    if 'headers' not in response:
        response['headers'] = {}
        
    # Add CORS headers to the response
    response['headers'].update(cors_headers)
    
    return response
