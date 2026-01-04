import json
import urllib.request
import urllib.error
import sys

# Uncomment the one you want to use
# Local RIE (Docker):
# BASE_URL = "http://localhost:9000/2015-03-31/functions/function/invocations"
# Remote Function URL:
BASE_URL = "https://g6lc3gscrfrxnh4prft5skcn3y0joluc.lambda-url.ap-south-1.on.aws"

def invoke_lambda(method, path, body=None, query_params=None):
    """
    Invokes the Lambda function.
    - If BASE_URL is the local RIE, it wraps the request in an API Gateway v2.0 event.
    - If BASE_URL is a real Function URL, it sends a standard HTTP request.
    """
    
    print(f"--- Invoking {method} {path} ---")

    if "localhost" in BASE_URL and "invocations" in BASE_URL:
        # --- LOCAL RIE MODE (Wrap in JSON Event) ---
        
        # Construct the API Gateway v2.0 event structure
        event = {
            "version": "2.0",
            "routeKey": f"{method} {path}",
            "rawPath": path,
            "rawQueryString": "",
            "headers": {
                "content-type": "application/json" if body else ""
            },
            "requestContext": {
                "http": {
                    "method": method,
                    "path": path,
                    "protocol": "HTTP/1.1",
                    "sourceIp": "127.0.0.1",
                    "userAgent": "test-script"
                }
            },
            "body": json.dumps(body) if body else None,
            "isBase64Encoded": False
        }

        if query_params:
            q_str = "&".join([f"{k}={v}" for k, v in query_params.items()])
            event["rawQueryString"] = q_str
            event["queryStringParameters"] = query_params

        req = urllib.request.Request(
            BASE_URL,
            data=json.dumps(event).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )

        try:
            with urllib.request.urlopen(req) as response:
                resp_data = response.read().decode('utf-8')
                lambda_resp = json.loads(resp_data)
                
                print(f"Status Code: {lambda_resp.get('statusCode')}")
                body_content = lambda_resp.get('body')
                try:
                    parsed_body = json.loads(body_content)
                    print("Body:")
                    print(json.dumps(parsed_body, indent=2))
                except (TypeError, json.JSONDecodeError):
                    print(f"Body: {body_content}")
                    
        except urllib.error.URLError as e:
            print(f"Error invoking Lambda: {e}")

    else:
        # --- REMOTE FUNCTION URL MODE (Standard HTTP) ---
        
        # Construct full URL
        # Remove trailing slash from BASE_URL if present
        base = BASE_URL.rstrip('/')
        # Ensure path starts with /
        if not path.startswith('/'):
            path = '/' + path
            
        full_url = base + path

        if query_params:
            q_str = "&".join([f"{k}={v}" for k, v in query_params.items()])
            full_url += "?" + q_str

        headers = {}
        data = None
        if body:
            headers['Content-Type'] = 'application/json'
            data = json.dumps(body).encode('utf-8')

        req = urllib.request.Request(
            full_url,
            data=data,
            headers=headers,
            method=method
        )

        try:
            with urllib.request.urlopen(req) as response:
                print(f"Status Code: {response.getcode()}")
                resp_data = response.read().decode('utf-8')
                try:
                    parsed_body = json.loads(resp_data)
                    print("Body:")
                    print(json.dumps(parsed_body, indent=2))
                except json.JSONDecodeError:
                    print(f"Body: {resp_data}")
        except urllib.error.HTTPError as e:
             print(f"HTTP Error: {e.code} {e.reason}")
             print(e.read().decode('utf-8'))
        except urllib.error.URLError as e:
            print(f"Error invoking URL: {e}")

    print("\n")

if __name__ == "__main__":
    # 1. Test Health Check
    invoke_lambda("GET", "/health")

    # 2. Test Get Insights
    invoke_lambda("GET", "/api/insights/")

    # 3. Test Search (POST)
    invoke_lambda("POST", "/api/search", body={
        "question": "What is the capital of France?",
        "chat_type": "question",
        
    })

    # 4. Test Get Chat History (assuming a chat_id exists or just testing 404/empty)
    # You would typically use a real chat_id from a previous search response
    invoke_lambda("GET", "/api/chats/test-chat-id", query_params={"chat_type": "question"})
