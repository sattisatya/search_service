import sys
sys.path.append("/var/task/src/app")

from fastapi import Request
from mangum import Mangum
from src.app.main import app

handler = Mangum(app)

def lambda_handler(event, context):
    """
    AWS Lambda entrypoint for FastAPI app using Mangum adapter.
    """
    return handler(event, context)
