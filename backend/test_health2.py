import urllib.request, json

req = urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5)
data = json.loads(req.read().decode())
print(json.dumps(data, indent=2))