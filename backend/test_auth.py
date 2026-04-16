import urllib.request, json, sys

BASE = "http://127.0.0.1:8000"

def post(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=body, headers={"Content-Type": "application/json"}, method="POST")
    r = urllib.request.urlopen(req)
    return json.loads(r.read().decode())

def get(path, token=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE}{path}", headers=headers)
    r = urllib.request.urlopen(req)
    return json.loads(r.read().decode())

# 1. Health (public)
h = get("/")
print("1. Health:", h["status"], "| tools:", h["tools"])

# 2. Protected without token -> 401
try:
    get("/api/tools")
    print("2. ERROR: should have been 401!")
    sys.exit(1)
except urllib.error.HTTPError as e:
    print(f"2. Tools (no auth): {e.code} {e.reason} OK")

# 3. Register
reg = post("/api/auth/register", {"username": "testuser", "email": "test@example.com", "password": "pass123"})
print("3. Register:", reg["user"], "OK")
token = reg["access_token"]

# 4. Protected with token -> 200
tools = get("/api/tools", token)
print("4. Tools (authed):", [t["name"] for t in tools], "OK")

# 5. Login
login = post("/api/auth/login", {"username": "testuser", "password": "pass123"})
print("5. Login:", login["user"], "OK")

# 6. Profile - no PII
me = get("/api/auth/me", login["access_token"])
print("6. Profile:", me, "OK")
assert "email" not in me, "PII LEAK: email in /me response!"
print("   -> No email in profile response (PII safe) OK")

# 7. Duplicate register -> 409
try:
    post("/api/auth/register", {"username": "testuser", "email": "x@x.com", "password": "pass123"})
    print("7. ERROR: should have been 409!")
    sys.exit(1)
except urllib.error.HTTPError as e:
    print(f"7. Duplicate register: {e.code} OK")

# 8. Bad password -> 401
try:
    post("/api/auth/login", {"username": "testuser", "password": "wrongpass"})
    print("8. ERROR: should have been 401!")
    sys.exit(1)
except urllib.error.HTTPError as e:
    print(f"8. Bad login: {e.code} OK")

# 9. Refresh token
refresh = post("/api/auth/refresh", {"refresh_token": reg["refresh_token"]})
print("9. Refresh: new access token obtained OK")

# 10. New token works
tools2 = get("/api/tools", refresh["access_token"])
print("10. Refreshed token works:", len(tools2), "tools OK")

print("")
print("=== ALL AUTH TESTS PASSED ===")
