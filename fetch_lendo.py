import httpx
import json

headers = {} # No auth needed if we fetch properties
try:
    resp = httpx.get("http://localhost:8000/api/reading_status")
    lendo_id = next(s['id'] for s in resp.json()['data'] if s['name'].lower() == 'lendo')
    
    # We need auth for books
    # Let's just login
    login_resp = httpx.post("http://localhost:8000/api/auth/login", data={"username": "testuser", "password": "password"})
    if login_resp.status_code == 200:
        headers["Authorization"] = f"Bearer {login_resp.json()['access_token']}"
        books_resp = httpx.get(f"http://localhost:8000/api/books?status_id={lendo_id}", headers=headers)
        print(json.dumps(books_resp.json()['data'], indent=2))
except Exception as e:
    print(e)
