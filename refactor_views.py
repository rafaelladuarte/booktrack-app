import re

with open('books_ui/views.py', 'r') as f:
    content = f.read()

# Add import
if 'from .api_client import api_request' not in content:
    content = content.replace('import json', 'import json\nfrom .api_client import api_request')

# Update login_view to save refresh token
if "request.session['refresh_token'] = token_data.get('refresh_token')" not in content:
    content = content.replace(
        "request.session['access_token'] = token_data.get('access_token')",
        "request.session['access_token'] = token_data.get('access_token')\n                request.session['refresh_token'] = token_data.get('refresh_token')"
    )

# Fix 401 manual flushes
content = content.replace("""        if response.status_code == 401:
            request.session.flush()
            return redirect('login')""", """        if response.status_code == 401:
            return redirect('login')""")

content = content.replace("""        if response.status_code == 401:
            request.session.flush()
            return redirect('login')""", """        if response.status_code == 401:
            return redirect('login')""")

# regex replacement for httpx calls:
# we want to change: httpx.get(f"{API_URL}/endpoint", headers=headers, params=params)
# to: api_request(request, 'GET', f"/endpoint", params=params)

def replacer(match):
    method_str = match.group(1).upper()
    url_inner = match.group(2) # what's inside f"{API_URL}..."
    rest = match.group(3) # kwargs
    
    # remove headers=headers or headers=get_headers(request)
    rest = re.sub(r',\s*headers=get_headers\(request\)', '', rest)
    rest = re.sub(r'headers=get_headers\(request\),\s*', '', rest)
    rest = re.sub(r'headers=get_headers\(request\)', '', rest)
    
    rest = re.sub(r',\s*headers=headers', '', rest)
    rest = re.sub(r'headers=headers,\s*', '', rest)
    rest = re.sub(r'headers=headers', '', rest)
    
    # clean up any trailing comma or spaces if rest is just empty or whitespace
    rest = rest.strip()
    if rest.startswith(','):
        rest = rest[1:].strip()

    # reconstruct
    if rest:
        return f"api_request(request, '{method_str}', f\"{url_inner}\", {rest})"
    else:
        return f"api_request(request, '{method_str}', f\"{url_inner}\")"

# Pattern explanation:
# httpx\.(get|post|put|delete)\(f"\{API_URL\}(.*?)"(.*)\)
pattern = re.compile(r'httpx\.(get|post|put|delete)\(f"\{API_URL\}([^"]*)"(.*?)\)')
content = pattern.sub(replacer, content)

with open('books_ui/views.py', 'w') as f:
    f.write(content)

print("Refactoring complete.")
