with open('books_ui/views.py', 'r') as f:
    content = f.read()

content = content.replace("response = api_request(request, 'POST', f\"/auth/token\", data=data)", "response = httpx.post(f\"{API_URL}/auth/token\", data=data)")

with open('books_ui/views.py', 'w') as f:
    f.write(content)

