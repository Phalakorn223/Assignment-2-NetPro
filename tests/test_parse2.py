from connection_manager import ConnectionManager, parse_ip_interface_brief

conn_mgr = ConnectionManager()
conn_mgr.connect("R1", {"ip": "192.168.74.131", "port": 32769, "connection_type": "TELNET"})

res = conn_mgr.send_command("R1", "show ip interface brief", use_textfsm=True)
out = res.get("output")
print("parse_ip_interface_brief returns:")
print(parse_ip_interface_brief(out))
