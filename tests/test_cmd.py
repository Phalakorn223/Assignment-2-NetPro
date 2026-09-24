from connection_manager import ConnectionManager

conn_mgr = ConnectionManager()
conn_mgr.connect("R1", {"ip": "192.168.74.131", "port": 32769, "connection_type": "TELNET"})

res = conn_mgr.send_command("R1", "show ip interface brief", use_textfsm=True)
print("Type:", type(res.get("output")))
print("Value:", res.get("output"))
