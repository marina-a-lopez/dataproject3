import requests
try:
    res = requests.get("http://127.0.0.1:8000/api/profile/00000000-0000-0000-0000-000000000000")
    print(res.status_code, res.text)
except Exception as e:
    print(str(e))
