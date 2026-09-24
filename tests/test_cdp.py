import requests

base = "http://127.0.0.1:5000/api"

print("R1 CDP:")
res = requests.post(f"{base}/show", json={"device_id": "R1", "command": "show cdp neighbors"})
print(res.text)

print("Topology:")
res = requests.get(f"{base}/topology/json")
print(res.text)
