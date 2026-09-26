import requests
import json

data = {
    "email": "teststaff123123@foodpilot.local",
    "password": "Password123!",
    "full_name": "Test Staff",
    "phone": "9999999999",
    "outlet_id": 1,
    "role": "staff",
    "pin": "1234"
}

# Need to login to get token first
login_data = {
    "email": "admin@example.com",
    "password": "admin"
}

res = requests.post("http://localhost:5000/api/auth/login", json=login_data)
if res.status_code == 200:
    token = res.json()["access_token"]
    print("Got token")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    create_res = requests.post("http://localhost:5000/api/admin/staff", json=data, headers=headers)
    print(create_res.status_code)
    print(create_res.text)
else:
    print("Login failed")
    print(res.text)
