import requests

base = "http://127.0.0.1:5000/api"

for port, dev in [(32769, "R1"), (32770, "R2"), (32771, "R3")]:
    res = requests.post(f"{base}/connect/{dev}", json={
        "ip": "192.168.74.131",
        "port": port,
        "connection_type": "TELNET"
    })
    print(dev, res.json())

# Test interface R1
res = requests.get(f"{base}/devices/R1/interfaces")
print("R1 interfaces:", res.json())
