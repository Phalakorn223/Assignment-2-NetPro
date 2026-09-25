"""
test_all_features.py — Automated End-to-End Test Suite for NetConfig Tracer Studio
"""
import requests
import json
import time

BASE = "http://127.0.0.1:5000/api"
passed = 0
failed = 0
results = []

def test(name, fn):
    global passed, failed
    print(f"\n[TEST] {name}...", end=" ", flush=True)
    try:
        ok, msg = fn()
        if ok:
            print("PASS")
            passed += 1
            results.append((name, "PASS", msg))
        else:
            print("FAIL:", msg)
            failed += 1
            results.append((name, "FAIL", msg))
    except Exception as e:
        print("EXCEPTION:", e)
        failed += 1
        results.append((name, "EXCEPTION", str(e)))

# 1. Inventory
def test_inventory():
    r = requests.get(f"{BASE}/inventory")
    if r.status_code != 200:
        return False, f"Status code {r.status_code}"
    data = r.json()
    devices = data.get("devices", data if isinstance(data, list) else [])
    ids = [d["id"] for d in devices]
    if "R1" not in ids or "R2" not in ids or "R3" not in ids:
        return False, f"Missing R1, R2 or R3 in inventory: {ids}"
    return True, f"Found {len(devices)} devices: {ids}"

# 2. Add and Remove Inventory Device
def test_add_remove_inventory():
    new_dev = {
        "id": "TEST_SW",
        "name": "TEST_SW",
        "device_type_label": "switch",
        "connection_type": "TELNET",
        "ip": "192.168.74.131",
        "port": 32999
    }
    r = requests.post(f"{BASE}/inventory", json=new_dev)
    if r.status_code != 200:
        return False, f"Add failed: {r.text}"
    # Delete it
    r_del = requests.delete(f"{BASE}/inventory/TEST_SW")
    if r_del.status_code != 200:
        return False, f"Delete failed: {r_del.text}"
    return True, "Add and Delete worked"

# 3. Connection Manager
def test_connect_devices():
    for dev in ["R1", "R2", "R3"]:
        r = requests.post(f"{BASE}/connect/{dev}")
        if r.status_code != 200:
            return False, f"Failed connecting {dev}: {r.text}"
        data = r.json()
        if not data.get("success"):
            return False, f"Connect error on {dev}: {data.get('message')}"
    return True, "All 3 devices connected"

# 4. Active Connections
def test_connections_list():
    r = requests.get(f"{BASE}/connections")
    data = r.json()
    connected_ids = [d["id"] for d in data.get("connected", [])]
    if set(["R1", "R2", "R3"]).issubset(set(connected_ids)):
        return True, f"Active: {connected_ids}"
    return False, f"Not all connected: {connected_ids}"

# 5. Interface list
def test_interfaces_list():
    for dev in ["R1", "R2", "R3"]:
        r = requests.get(f"{BASE}/devices/{dev}/interfaces")
        if r.status_code != 200:
            return False, f"Failed {dev}: {r.text}"
        ifaces = r.json().get("interfaces", [])
        if not ifaces:
            return False, f"No interfaces returned for {dev}"
    return True, "All devices returned interface list"

# 6. Interface configure (toggle up/down or configure description/IP)
def test_interface_configure():
    # Test setting description on R1 Ethernet0/3 (unused port)
    payload = {
        "interface": "Ethernet0/3",
        "status": "down"
    }
    r = requests.post(f"{BASE}/devices/R1/interfaces/configure", json=payload)
    if r.status_code != 200:
        return False, f"Config failed: {r.text}"
    data = r.json()
    if not data.get("success"):
        return False, f"Apply error: {data.get('message')}"
    return True, "Configured Ethernet0/3"

# 7. Routing Preview: Static Route
def test_routing_preview_static():
    payload = {
        "device_id": "R1",
        "routing_type": "static",
        "networks": [
            {"network": "10.0.0.0", "mask": "255.255.255.0", "next_hop": "192.168.75.2"}
        ]
    }
    r = requests.post(f"{BASE}/routing/preview", json=payload)
    if r.status_code != 200:
        return False, f"Status {r.status_code}: {r.text}"
    cmds = r.json().get("commands", [])
    expected = "ip route 10.0.0.0 255.255.255.0 192.168.75.2"
    if any(expected in c for c in cmds):
        return True, f"Generated: {cmds}"
    return False, f"Unexpected commands: {cmds}"

# 8. Routing Preview: OSPF
def test_routing_preview_ospf():
    payload = {
        "device_id": "R1",
        "routing_type": "ospf",
        "process_id": "1",
        "router_id": "1.1.1.1",
        "networks": [
            {"network": "192.168.75.0", "wildcard": "0.0.0.255", "area": "0"}
        ]
    }
    r = requests.post(f"{BASE}/routing/preview", json=payload)
    if r.status_code != 200:
        return False, f"Status {r.status_code}: {r.text}"
    cmds = r.json().get("commands", [])
    if any("router ospf 1" in c for c in cmds) and any("network 192.168.75.0 0.0.0.255 area 0" in c for c in cmds):
        return True, f"Generated: {cmds}"
    return False, f"Unexpected commands: {cmds}"

# 9. Routing Preview: RIP
def test_routing_preview_rip():
    payload = {
        "device_id": "R1",
        "routing_type": "rip",
        "version": "2",
        "networks": [
            {"network": "192.168.75.0"}
        ]
    }
    r = requests.post(f"{BASE}/routing/preview", json=payload)
    if r.status_code != 200:
        return False, f"Status {r.status_code}: {r.text}"
    cmds = r.json().get("commands", [])
    if any("router rip" in c for c in cmds) and any("version 2" in c for c in cmds):
        return True, f"Generated: {cmds}"
    return False, f"Unexpected commands: {cmds}"

# 10. Routing Preview: EIGRP
def test_routing_preview_eigrp():
    payload = {
        "device_id": "R1",
        "routing_type": "eigrp",
        "as_number": "100",
        "networks": [
            {"network": "192.168.75.0", "wildcard": "0.0.0.255"}
        ]
    }
    r = requests.post(f"{BASE}/routing/preview", json=payload)
    if r.status_code != 200:
        return False, f"Status {r.status_code}: {r.text}"
    cmds = r.json().get("commands", [])
    if any("router eigrp 100" in c for c in cmds):
        return True, f"Generated: {cmds}"
    return False, f"Unexpected commands: {cmds}"

# 11. Routing Preview: BGP
def test_routing_preview_bgp():
    payload = {
        "device_id": "R1",
        "routing_type": "bgp",
        "as_number": "65001",
        "router_id": "1.1.1.1",
        "neighbors": [
            {"ip": "192.168.75.2", "remote_as": "65002"}
        ],
        "networks": [
            {"network": "192.168.75.0", "mask": "255.255.255.0"}
        ]
    }
    r = requests.post(f"{BASE}/routing/preview", json=payload)
    if r.status_code != 200:
        return False, f"Status {r.status_code}: {r.text}"
    cmds = r.json().get("commands", [])
    if any("router bgp 65001" in c for c in cmds) and any("neighbor 192.168.75.2 remote-as 65002" in c for c in cmds):
        return True, f"Generated: {cmds}"
    return False, f"Unexpected commands: {cmds}"

# 12. Routing Apply (Live on Router R1)
def test_routing_apply():
    payload = {
        "device_id": "R1",
        "commands": [
            "ip route 172.16.99.0 255.255.255.0 192.168.75.2",
            "no ip route 172.16.99.0 255.255.255.0 192.168.75.2"
        ]
    }
    r = requests.post(f"{BASE}/routing/apply", json=payload)
    if r.status_code != 200:
        return False, f"Apply failed: {r.text}"
    data = r.json()
    if not data.get("success"):
        return False, f"Error: {data.get('message')}"
    return True, "Applied and cleaned up route on R1"

# 13. Show Commands
def test_show_commands():
    payload = {
        "device_id": "R1",
        "command": "show ip route"
    }
    r = requests.post(f"{BASE}/show", json=payload)
    if r.status_code != 200:
        return False, f"Show failed: {r.text}"
    output = r.json().get("output", "")
    if "Gateway of last resort" in output or "Codes:" in output:
        return True, "show ip route succeeded"
    return False, f"Unexpected output: {output[:100]}"

# 14. CLI Free-form execution
def test_cli_execute():
    payload = {
        "device_id": "R1",
        "command": "show clock"
    }
    r = requests.post(f"{BASE}/cli/execute", json=payload)
    if r.status_code != 200:
        return False, f"CLI failed: {r.text}"
    out = r.json().get("output", "")
    if "UTC" in out or ":" in out:
        return True, f"Output: {out.strip()}"
    return False, f"Unexpected output: {out}"

# 15. Topology Auto-Discovery API
def test_topology():
    r = requests.get(f"{BASE}/topology/json")
    if r.status_code != 200:
        return False, f"Topology API failed: {r.text}"
    data = r.json()
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    node_ids = [n["id"] for n in nodes]
    if "R1" not in node_ids or "R2" not in node_ids or "R3" not in node_ids:
        return False, f"Missing routers in topology: {node_ids}"
    if not any(e["from"] == "R1" and e["to"] == "R2" or e["from"] == "R2" and e["to"] == "R1" for e in edges):
        return False, f"Missing R1 <-> R2 link in edges: {edges}"
    return True, f"Discovered {len(nodes)} nodes, {len(edges)} edges"

# 16. Front Panel Ports Modal
def test_ports_modal():
    for dev in ["R1", "R2", "R3"]:
        r = requests.get(f"{BASE}/ports/{dev}")
        if r.status_code != 200 or not r.json().get("success"):
            return False, f"Ports for {dev} failed"
    return True, "All ports returned"

# 17. Autocomplete / Suggestions
def test_suggestions():
    r = requests.get(f"{BASE}/suggestions?q=sh+ip")
    if r.status_code != 200:
        return False, f"Status {r.status_code}"
    suggs = r.json().get("suggestions", [])
    if any("show ip interface brief" in s or "show ip route" in s for s in suggs):
        return True, f"Found {len(suggs)} suggestions"
    return False, f"Suggestions unexpected: {suggs}"

# 18. Command Normalization via CLI
def test_command_normalization():
    payload = {
        "device_id": "R1",
        "command": "sh ip int br"
    }
    r = requests.post(f"{BASE}/cli/execute", json=payload)
    if r.status_code != 200:
        return False, f"Status {r.status_code}"
    normalized = r.json().get("command", "")
    if normalized == "show ip interface brief":
        return True, f"Normalized to: {normalized}"
    return False, f"Was not normalized: {normalized}"

# 19. Virtual PC Config
def test_virtual_pc_config():
    pc = {
        "id": "PC_TEST",
        "name": "PC_TEST",
        "device_type_label": "pc",
        "connection_type": "PC",
        "ip": "10.10.10.50",
        "mask": "255.255.255.0",
        "gateway": "10.10.10.1"
    }
    # Add PC to inventory
    r_add = requests.post(f"{BASE}/inventory", json=pc)
    if r_add.status_code != 200:
        return False, f"Failed adding PC: {r_add.text}"
    
    # Configure PC
    cfg = {"ip": "10.10.10.55", "mask": "255.255.255.0", "gateway": "10.10.10.1"}
    r_cfg = requests.post(f"{BASE}/pc/PC_TEST/config", json=cfg)
    if r_cfg.status_code != 200 or not r_cfg.json().get("success"):
        requests.delete(f"{BASE}/inventory/PC_TEST")
        return False, f"Config PC failed: {r_cfg.text}"
    
    # Delete PC
    requests.delete(f"{BASE}/inventory/PC_TEST")
    return True, "PC created, configured, and deleted successfully"

# 20. Virtual PC Ping via Router Gateway Proxy
def test_virtual_pc_ping():
    pc = {
        "id": "PC_PROXY_TEST",
        "name": "PC_PROXY_TEST",
        "device_type_label": "pc",
        "connection_type": "PC",
        "ip": "192.168.74.200",
        "mask": "255.255.255.0",
        "gateway": "192.168.74.133",
        "gateway_router": "R1"
    }
    requests.post(f"{BASE}/inventory", json=pc)
    
    ping_payload = {
        "target": "192.168.74.101",
        "via_device_id": "R1"
    }
    r = requests.post(f"{BASE}/pc/PC_PROXY_TEST/ping", json=ping_payload)
    requests.delete(f"{BASE}/inventory/PC_PROXY_TEST")
    
    if r.status_code != 200:
        return False, f"Ping failed: {r.text}"
    data = r.json()
    if data.get("reachable"):
        return True, "Ping via router proxy succeeded"
    return False, f"Ping unreachable: {data}"

# 21. Ping endpoint reachability
def test_ping_endpoint():
    r = requests.post(f"{BASE}/ping", json={"ip": "127.0.0.1"})
    if r.status_code != 200:
        return False, f"Status {r.status_code}"
    return True, f"Reachable: {r.json().get('reachable')}"

# 22. Interface State Toggle Endpoint
def test_interface_state_endpoint():
    payload = {
        "device_id": "R1",
        "interface": "Ethernet0/3",
        "state": "down"
    }
    r = requests.post(f"{BASE}/config/interface/state", json=payload)
    if r.status_code != 200:
        return False, f"Status {r.status_code}: {r.text}"
    return True, "Interface state successfully set"

# 23. Interface Configure Direct Endpoint
def test_interface_config_direct():
    payload = {
        "device_id": "R1",
        "interface": "Ethernet0/3",
        "ip": "",
        "mask": "255.255.255.0",
        "state": "down",
        "description": "NetConfig-Tracer-Test"
    }
    r = requests.post(f"{BASE}/config/interface", json=payload)
    if r.status_code != 200:
        return False, f"Status {r.status_code}: {r.text}"
    return True, "Direct interface config endpoint verified"

# 24. Routing Config with Redistribution & Default-Originate
def test_routing_redistribute_config():
    payload = {
        "device_id": "R1",
        "route_type": "ospf",
        "process_id": 1,
        "router_id": "1.1.1.1",
        "networks": [
            {"network": "192.168.75.0", "wildcard": "0.0.0.255", "area": 0}
        ],
        "redistribute": [
            {"source": "connected", "subnets": True}
        ],
        "default_originate": {
            "enabled": True,
            "always": True
        }
    }
    r = requests.post(f"{BASE}/routing/preview", json=payload)
    if r.status_code != 200:
        return False, f"Status {r.status_code}: {r.text}"
    cmds = r.json().get("commands", [])
    has_redist = any("redistribute connected subnets" in c for c in cmds)
    has_orig = any("default-information originate always" in c for c in cmds)
    if has_redist and has_orig:
        return True, "Redistribution and default-originate commands generated successfully"
    return False, f"Missing commands in: {cmds}"

# 25. Topology Interface Diagnostics
def test_topology_diagnostics():
    r = requests.get(f"{BASE}/topology/interfaces")
    if r.status_code != 200:
        return False, f"Status {r.status_code}: {r.text}"
    dev_ifaces = r.json().get("device_interfaces", {})
    if "R1" in dev_ifaces and "R2" in dev_ifaces:
        return True, f"Found diagnostics for {list(dev_ifaces.keys())}"
    return False, f"Unexpected diagnostics: {dev_ifaces}"

# 26. EVE-NG Direct Import
def test_eveng_import():
    payload = {
        "host": "http://192.168.74.131/api",
        "lab_path": "Test.unl",
        "username": "admin",
        "password": "eve"
    }
    r = requests.post(f"{BASE}/eveng/import", json=payload)
    if r.status_code != 200:
        return False, f"Status {r.status_code}: {r.text}"
    data = r.json()
    if data.get("success"):
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        return True, f"Imported {len(nodes)} nodes, {len(edges)} edges from EVE-NG"
    return False, f"Import error: {data.get('message')}"

# 27. Interface DHCP Configuration
def test_interface_dhcp_config():
    payload = {
        "device_id": "R1",
        "interface": "Ethernet0/3",
        "ip": "dhcp",
        "mask": "",
        "state": "down",
        "description": "DHCP-Test-Port"
    }
    r = requests.post(f"{BASE}/config/interface", json=payload)
    if r.status_code != 200:
        return False, f"Status {r.status_code}: {r.text}"
    cmds = r.json().get("commands", [])
    if any("ip address dhcp" in c for c in cmds):
        return True, "Generated 'ip address dhcp' successfully"
    return False, f"Unexpected commands: {cmds}"

# 28. Interface No IP Address Configuration
def test_interface_no_ip_config():
    payload = {
        "device_id": "R1",
        "interface": "Ethernet0/3",
        "ip": "no ip address",
        "mask": "",
        "state": "down",
        "description": "No-IP-Test-Port"
    }
    r = requests.post(f"{BASE}/config/interface", json=payload)
    if r.status_code != 200:
        return False, f"Status {r.status_code}: {r.text}"
    cmds = r.json().get("commands", [])
    if any("no ip address" in c for c in cmds):
        return True, "Generated 'no ip address' successfully"
    return False, f"Unexpected commands: {cmds}"

# Run all tests
test("1. Inventory List", test_inventory)
test("2. Add/Remove Inventory", test_add_remove_inventory)
test("3. Connect Devices (R1, R2, R3)", test_connect_devices)
test("4. Active Connections Pool", test_connections_list)
test("5. Interfaces List", test_interfaces_list)
test("6. Interface Configure", test_interface_configure)
test("7. Routing Preview: Static", test_routing_preview_static)
test("8. Routing Preview: OSPF", test_routing_preview_ospf)
test("9. Routing Preview: RIP", test_routing_preview_rip)
test("10. Routing Preview: EIGRP", test_routing_preview_eigrp)
test("11. Routing Preview: BGP", test_routing_preview_bgp)
test("12. Routing Apply (Live Config)", test_routing_apply)
test("13. Show Command Execution", test_show_commands)
test("14. CLI Freeform Execution", test_cli_execute)
test("15. Topology Auto-Discovery", test_topology)
test("16. Front Panel Ports", test_ports_modal)
test("17. Command Suggestions", test_suggestions)
test("18. Command Normalization", test_command_normalization)
test("19. Virtual PC Config", test_virtual_pc_config)
test("20. Virtual PC Ping via Proxy", test_virtual_pc_ping)
test("21. Ping Endpoint", test_ping_endpoint)
test("22. Interface State Toggle", test_interface_state_endpoint)
test("23. Direct Interface Config", test_interface_config_direct)
test("24. Routing Redistribution Preview", test_routing_redistribute_config)
test("25. Topology Interfaces Diagnostics", test_topology_diagnostics)
test("26. EVE-NG Direct Import", test_eveng_import)
test("27. Interface DHCP Configuration", test_interface_dhcp_config)
test("28. Interface No IP Configuration", test_interface_no_ip_config)

print("\n" + "="*50)
print(f"RESULTS: {passed} PASSED, {failed} FAILED out of {passed+failed} tests")
print("="*50)

