"""
app.py — NetConfig Tracer Studio Web Server
Flask backend ที่ใช้ ConnectionManager, command_builder, command_normalizer, topology_builder
Spec v3: เพิ่ม hardware_profiles, validators, config lifecycle, interface CRUD
"""

from flask import Flask, render_template, request, jsonify, Response

from connection_manager import (
    ConnectionManager, ip_is_valid, ping_check,
    load_inventory, save_inventory, add_device_to_inventory,
    remove_device_from_inventory, get_device_by_id
)
from command_builder import (
    build_ip_address_commands, build_interface_state_commands,
    build_interface_description, build_static_route, build_default_route,
    build_rip, build_eigrp, build_ospf, build_bgp, preview_commands
)
from command_normalizer import normalize, get_suggestions
from topology_builder import (
    build_topology_graph, graph_to_json, DEMO_GRAPH_JSON, NX_AVAILABLE
)
from hardware_profiles import (
    get_model_list, generate_interfaces, create_additional_interface,
    HARDWARE_PROFILES
)
from validators import (
    validate_ip, validate_subnet_mask, validate_wildcard_mask,
    validate_router_id, validate_as_number, validate_port,
    validate_interface_config
)

app = Flask(__name__)

# Global Connection Manager (session pool)
conn_mgr = ConnectionManager()

# Demo show-command simulation สำหรับอุปกรณ์ที่ยังไม่ได้ต่อจริง
DEMO_DEVICES = {
    "R1": {
        "name": "Router-R1", "model": "Cisco 4331", "type": "router",
        "ip": "192.168.1.116", "connection_type": "SSH",
        "interfaces": {
            "GigabitEthernet0/0/0": {"ip": "192.168.1.116", "mask": "255.255.255.0", "status": "up"},
            "GigabitEthernet0/0/1": {"ip": "10.1.1.1", "mask": "255.255.255.252", "status": "up"},
            "GigabitEthernet0/0/2": {"ip": "unassigned", "mask": "", "status": "down"},
            "Serial0/1/0": {"ip": "172.16.1.1", "mask": "255.255.255.252", "status": "up"},
            "Loopback0": {"ip": "1.1.1.1", "mask": "255.255.255.255", "status": "up"},
        },
        "routing": {
            "static": [{"network": "192.168.2.0", "mask": "255.255.255.0", "next_hop": "10.1.1.2"}],
            "default": {"next_hop": "192.168.1.1"},
        },
    },
    "R2": {
        "name": "Router-R2", "model": "Cisco 4331", "type": "router",
        "ip": "192.168.1.125", "connection_type": "TELNET",
        "interfaces": {
            "GigabitEthernet0/0/0": {"ip": "192.168.1.125", "mask": "255.255.255.0", "status": "up"},
            "GigabitEthernet0/0/1": {"ip": "10.1.1.2", "mask": "255.255.255.252", "status": "up"},
            "GigabitEthernet0/0/2": {"ip": "10.2.2.1", "mask": "255.255.255.0", "status": "up"},
            "Serial0/1/0": {"ip": "172.16.1.2", "mask": "255.255.255.252", "status": "up"},
            "Loopback0": {"ip": "2.2.2.2", "mask": "255.255.255.255", "status": "up"},
        },
        "routing": {"static": [], "default": {}},
    },
    "SW1": {
        "name": "Switch-SW1", "model": "Cisco Catalyst 2960", "type": "switch",
        "ip": "192.168.1.117", "connection_type": "SSH",
        "interfaces": {
            "FastEthernet0/1": {"ip": "unassigned", "mask": "", "status": "up"},
            "FastEthernet0/2": {"ip": "unassigned", "mask": "", "status": "up"},
            "FastEthernet0/3": {"ip": "unassigned", "mask": "", "status": "down"},
            "FastEthernet0/4": {"ip": "unassigned", "mask": "", "status": "down"},
            "GigabitEthernet0/1": {"ip": "unassigned", "mask": "", "status": "up"},
            "Vlan1": {"ip": "192.168.1.117", "mask": "255.255.255.0", "status": "up"},
        },
        "routing": {},
    },
}


# ===========================================================================
# Helpers
# ===========================================================================
def _get_active_device_id(data: dict) -> str:
    return data.get("device_id", "R1")


def _demo_show(device_id: str, command: str) -> str:
    """Simulate Cisco IOS show command output สำหรับ demo mode"""
    dev = DEMO_DEVICES.get(device_id)
    if not dev:
        return f"Error: Device '{device_id}' ไม่พบในระบบ"

    cmd_lower = command.lower().strip()
    name = dev["name"]

    # show ip interface brief
    if "ip int" in cmd_lower or "ip interface brief" in cmd_lower:
        lines = [f"{name}# {command}", f"{'Interface':<25} {'IP-Address':<16} {'OK?':<5} {'Method':<8} {'Status':<22} {'Protocol'}"]
        lines.append("-" * 85)
        for ifname, info in dev["interfaces"].items():
            st = "up" if info["status"] == "up" else "administratively down"
            pr = "up" if info["status"] == "up" else "down"
            mt = "manual" if info["ip"] not in ("unassigned", "") else "unset"
            lines.append(f"{ifname:<25} {info['ip']:<16} {'YES':<5} {mt:<8} {st:<22} {pr}")
        return "\n".join(lines)

    # show interfaces status
    if "interfaces status" in cmd_lower:
        lines = [f"{name}# {command}", f"{'Port':<22} {'Name':<20} {'Status':<12} {'Vlan':<8} {'Speed':<8}"]
        lines.append("-" * 75)
        for ifname, info in dev["interfaces"].items():
            st = "connected" if info["status"] == "up" else "notconnect"
            lines.append(f"{ifname:<22} {'':20} {st:<12} {'1':<8} {'auto':<8}")
        return "\n".join(lines)

    # show ip route
    if "ip route" in cmd_lower and "static" not in cmd_lower:
        routing = dev.get("routing", {})
        default_nh = routing.get("default", {}).get("next_hop", "not set")
        lines = [
            f"{name}# {command}",
            "Codes: L-local, C-connected, S-static, R-RIP, D-EIGRP, O-OSPF, B-BGP",
            f"Gateway of last resort is {default_nh}",
            ""
        ]
        for ifname, info in dev["interfaces"].items():
            if info["status"] == "up" and info["ip"] not in ("unassigned", ""):
                lines.append(f"C    {info['ip']}/{info['mask']} is directly connected, {ifname}")
        for st in routing.get("static", []):
            lines.append(f"S    {st['network']}/{st['mask']} [1/0] via {st['next_hop']}")
        if routing.get("default", {}).get("next_hop"):
            lines.append(f"S*   0.0.0.0/0 [1/0] via {default_nh}")
        return "\n".join(lines)

    # show ip route static
    if "ip route static" in cmd_lower:
        routing = dev.get("routing", {})
        lines = [f"{name}# {command}", ""]
        for st in routing.get("static", []):
            lines.append(f"S    {st['network']}/{st['mask']} [1/0] via {st['next_hop']}")
        return "\n".join(lines)

    # show ip protocols
    if "ip proto" in cmd_lower:
        return f"""{name}# {command}
Routing Protocol is "static"
  Sending updates every 0 seconds

Routing Protocol is "ospf 1"
  Router-ID: 1.1.1.1
  Outgoing update filter list for all interfaces is not set
  Incoming update filter list for all interfaces is not set

Routing Protocol is "rip"
  Sending updates every 30 seconds, next due in 15 seconds
  Invalid after 180 seconds, hold down 180, flushed after 240
  Automatic network summarization is not in effect
  Maximum path: 4"""

    # show ip rip database
    if "ip rip" in cmd_lower:
        return f"""{name}# {command}
10.1.1.0/30    auto-summary
10.1.1.0/30    directly connected, GigabitEthernet0/0/1
192.168.1.0/24 auto-summary
192.168.1.0/24 directly connected, GigabitEthernet0/0/0
10.2.2.0/24    [1] via 10.1.1.2, 00:00:15, GigabitEthernet0/0/1"""

    # show ip eigrp neighbors
    if "eigrp neighbor" in cmd_lower:
        return f"""{name}# {command}
EIGRP-IPv4 Neighbors for AS(100)
H   Address     Interface     Hold Uptime   SRTT   RTO   Q Seq
                              (sec)         (ms)       Cnt Num
0   10.1.1.2    Gi0/0/1      13  01:23:45  1      200   0  45"""

    # show ip eigrp topology
    if "eigrp topo" in cmd_lower:
        return f"""{name}# {command}
EIGRP-IPv4 Topology Table for AS(100)/ID(1.1.1.1)
Codes: P-Passive, A-Active, U-Update, Q-Query, R-Reply, r-reply, s-sia-query, S-sia-reply

P 10.1.1.0/30, 1 successors, FD is 2816
        via Connected, GigabitEthernet0/0/1
P 10.2.2.0/24, 1 successors, FD is 30720
        via 10.1.1.2 (30720/28160), GigabitEthernet0/0/1"""

    # show ip ospf neighbor
    if "ospf neighbor" in cmd_lower:
        return f"""{name}# {command}
Neighbor ID     Pri   State        Dead Time   Address         Interface
2.2.2.2           1   FULL/DR      00:00:36    10.1.1.2        GigabitEthernet0/0/1"""

    # show ip ospf database
    if "ospf database" in cmd_lower:
        return f"""{name}# {command}
            OSPF Router with ID (1.1.1.1) (Process ID 1)

                Router Link States (Area 0)

Link ID       ADV Router    Age    Seq#         Checksum  Link count
1.1.1.1       1.1.1.1       428    0x80000003   0x00CF51  3
2.2.2.2       2.2.2.2       427    0x80000003   0x008A73  3"""

    # show ip ospf interface brief
    if "ospf interface" in cmd_lower:
        return f"""{name}# {command}
Interface    PID   Area         IP Address/Mask    Cost  State    Nbrs F/C
Gi0/0/1      1     0            10.1.1.1/30        1     DR       1/1
Lo0          1     0            1.1.1.1/32         1     LOOP     0/0"""

    # show ip bgp summary
    if "bgp summ" in cmd_lower or "bgp summary" in cmd_lower:
        return f"""{name}# {command}
BGP router identifier 1.1.1.1, local AS number 65001
BGP table version is 4, main routing table version 4

Neighbor        V     AS    MsgRcvd  MsgSent  TblVer  InQ  OutQ  Up/Down    State/PfxRcd
10.1.1.2        4  65002     1234     1235       4      0     0  01:23:45     2"""

    # show ip bgp neighbors
    if "bgp neighbor" in cmd_lower:
        return f"""{name}# {command}
BGP neighbor is 10.1.1.2,  remote AS 65002, external link
  BGP version 4, remote router ID 2.2.2.2
  BGP state = Established, up for 01:23:45
  Hold time is 180, keepalive interval is 60 seconds"""

    # show cdp neighbors detail
    if "cdp" in cmd_lower:
        return f"""{name}# {command}
Device ID: R2
Entry address(es):
  IP address: 10.1.1.2
Platform: cisco 4331, Capabilities: Router Switch
Interface: GigabitEthernet0/0/1, Port ID (outgoing port): GigabitEthernet0/0/1
-------------------------
Device ID: SW1
Entry address(es):
  IP address: 192.168.1.117
Platform: cisco WS-C2960, Capabilities: Switch
Interface: GigabitEthernet0/0/0, Port ID (outgoing port): GigabitEthernet0/1"""

    # show vlan
    if "vlan" in cmd_lower:
        return f"""{name}# {command}
VLAN Name                             Status    Ports
---- -------------------------------- --------- -------------------------------
1    default                          active    Fa0/1, Fa0/2, Gi0/1
10   MANAGEMENT                       active
20   DATA_VLAN                        active
1002 fddi-default                     act/unsup
1003 token-ring-default               act/unsup"""

    # show version
    if "version" in cmd_lower:
        return f"""{name}# {command}
Cisco IOS Software, IOSv Software (VIOS-ADVENTERPRISEK9-M), Version 15.8(3)M2
Technical Support: http://www.cisco.com/techsupport
ROM: Bootstrap program is IOSv

{name} uptime is 1 day, 3 hours, 14 minutes
System image file is "flash0:/vios-adventerprisek9-m"
Processor board ID 9XXXXXXXXXXX
2 Gigabit Ethernet interfaces
2 Serial(sync/async) interfaces
32768K bytes of non-volatile configuration memory."""

    # show running-config
    if "run" in cmd_lower:
        lines = [f"{name}# {command}", "Building configuration...\n!", f"hostname {name}", "!"]
        for ifname, info in dev["interfaces"].items():
            lines.append(f"interface {ifname}")
            if info["ip"] not in ("unassigned", ""):
                lines.append(f" ip address {info['ip']} {info['mask']}")
            lines.append(" no shutdown" if info["status"] == "up" else " shutdown")
            lines.append("!")
        return "\n".join(lines)

    return f"{name}# {command}\n% Command output simulated successfully."


# ===========================================================================
# Routes — UI
# ===========================================================================
@app.route("/")
def index():
    return render_template("index.html")


# ===========================================================================
# Routes — Device Inventory CRUD
# ===========================================================================
@app.route("/api/inventory", methods=["GET"])
def get_inventory():
    """รายชื่อ device ทั้งหมด (จาก devices.json + demo devices)"""
    inv = load_inventory()
    # ถ้าไม่มีในไฟล์ ให้ใช้ demo data
    if not inv:
        inv = [
            {"id": "R1", "name": "Router-R1", "model": "Cisco 4331", "device_type_label": "router",
             "connection_type": "SSH", "ip": "192.168.1.116", "port": 22,
             "username": "cisco", "password": "cisco", "secret": "cisco"},
            {"id": "R2", "name": "Router-R2", "model": "Cisco 4331", "device_type_label": "router",
             "connection_type": "TELNET", "ip": "192.168.1.125", "port": 23,
             "username": "cisco", "password": "cisco", "secret": "cisco"},
            {"id": "SW1", "name": "Switch-SW1", "model": "Cisco Catalyst 2960", "device_type_label": "switch",
             "connection_type": "SSH", "ip": "192.168.1.117", "port": 22,
             "username": "cisco", "password": "cisco", "secret": "cisco"},
        ]
    # เสริมสถานะการเชื่อมต่อ
    for dev in inv:
        dev["connected"] = conn_mgr.is_connected(dev.get("id", ""))
    return jsonify({"success": True, "devices": inv})


@app.route("/api/inventory", methods=["POST"])
def add_device():
    """เพิ่ม device ใหม่"""
    data = request.json or {}
    if not data.get("ip") and data.get("connection_type", "SSH").upper() != "SERIAL":
        return jsonify({"success": False, "message": "IP address จำเป็น"}), 400
    if data.get("ip"):
        valid, msg = ip_is_valid(data["ip"])
        if not valid:
            return jsonify({"success": False, "message": msg}), 400
    device = add_device_to_inventory(data)
    return jsonify({"success": True, "device": device})


@app.route("/api/inventory/<device_id>", methods=["DELETE"])
def delete_device(device_id):
    """ลบ device"""
    if conn_mgr.is_connected(device_id):
        conn_mgr.disconnect(device_id)
    removed = remove_device_from_inventory(device_id)
    return jsonify({"success": removed, "message": "ลบเรียบร้อย" if removed else "ไม่พบ device"})


# ===========================================================================
# Routes — Connection Management
# ===========================================================================
@app.route("/api/ping", methods=["POST"])
def test_ping():
    """Ping test reachability"""
    data = request.json or {}
    ip = data.get("ip", "")
    if not ip:
        return jsonify({"success": False, "message": "ต้องการ IP address"}), 400
    valid, msg = ip_is_valid(ip)
    if not valid:
        return jsonify({"success": False, "message": msg})
    reachable = ping_check(ip)
    return jsonify({
        "success": True,
        "reachable": reachable,
        "message": f"SUCCESS: {ip} ตอบสนอง ping" if reachable else f"FAIL: {ip} ไม่ตอบสนอง ping"
    })


@app.route("/api/connect/<device_id>", methods=["POST"])
def connect_device(device_id):
    """เชื่อมต่อ device และเก็บ session ใน pool"""
    data = request.json or {}
    skip_ping = data.get("skip_ping", False)
    res = conn_mgr.connect(device_id, data, skip_ping=skip_ping)
    return jsonify(res)


@app.route("/api/disconnect/<device_id>", methods=["POST"])
def disconnect_device(device_id):
    """ปิด connection"""
    res = conn_mgr.disconnect(device_id)
    return jsonify(res)


@app.route("/api/connections", methods=["GET"])
def get_connections():
    """รายการ device ที่ connect อยู่"""
    return jsonify({"success": True, "connected": conn_mgr.get_connected_devices()})


# ===========================================================================
# Routes — Interface Configuration
# ===========================================================================
@app.route("/api/config/interface", methods=["POST"])
def configure_interface():
    """กำหนด IP Address และสถานะ Up/Down ของ interface"""
    data = request.json or {}
    device_id = data.get("device_id")
    interface = data.get("interface")
    ip = data.get("ip", "")
    mask = data.get("mask", "255.255.255.0")
    state = data.get("state", "up")
    description = data.get("description", "")

    if not device_id or not interface:
        return jsonify({"success": False, "message": "device_id และ interface จำเป็น"}), 400

    # Validate IP ถ้ามี
    if ip:
        valid, msg = ip_is_valid(ip)
        if not valid:
            return jsonify({"success": False, "message": msg}), 400

    # Build commands
    if ip:
        cmds = build_ip_address_commands(interface, ip, mask, description or None)
        # Override state ถ้า shutdown
        if state == "down":
            cmds = [c for c in cmds if c != "no shutdown"]
            cmds.append("shutdown")
    else:
        cmds = build_interface_state_commands(interface, up=(state == "up"))
        if description:
            cmds.insert(1, f"description {description}")

    # ถ้า connect อยู่ส่งจริง ถ้าไม่ก็ simulate
    if conn_mgr.is_connected(device_id):
        result = conn_mgr.send_config(device_id, cmds)
    else:
        dev = DEMO_DEVICES.get(device_id, {})
        dev_name = dev.get("name", device_id)
        output_lines = [f"{dev_name}(config)# {c}" for c in cmds]
        output_lines = [f"{dev_name}#configure terminal"] + output_lines + [f"{dev_name}#end"]
        # Update demo state
        if device_id in DEMO_DEVICES:
            if_data = DEMO_DEVICES[device_id]["interfaces"]
            if interface not in if_data:
                if_data[interface] = {"ip": "unassigned", "mask": "", "status": "down"}
            if ip:
                if_data[interface]["ip"] = ip
                if_data[interface]["mask"] = mask
            if_data[interface]["status"] = state
        result = {"success": True, "output": "\n".join(output_lines)}

    result["commands"] = cmds
    result["preview"] = preview_commands(cmds)
    return jsonify(result)


# ===========================================================================
# Routes — Routing Protocol Configuration
# ===========================================================================
@app.route("/api/config/routing", methods=["POST"])
def configure_routing():
    """กำหนด Routing Protocol (Static, Default, RIP, EIGRP, OSPF, BGP)"""
    data = request.json or {}
    device_id = data.get("device_id")
    route_type = data.get("route_type", "")

    if not device_id or not route_type:
        return jsonify({"success": False, "message": "device_id และ route_type จำเป็น"}), 400

    cmds = []

    if route_type == "static":
        network = data.get("network", "")
        mask = data.get("mask", "255.255.255.0")
        next_hop = data.get("next_hop", "")
        if not network or not next_hop:
            return jsonify({"success": False, "message": "network และ next_hop จำเป็น"}), 400
        cmds = build_static_route(network, mask, next_hop)

    elif route_type == "default":
        next_hop = data.get("next_hop", "")
        if not next_hop:
            return jsonify({"success": False, "message": "next_hop จำเป็น"}), 400
        cmds = build_default_route(next_hop)

    elif route_type == "rip":
        networks = data.get("networks", [])  # list of strings
        if not networks:
            return jsonify({"success": False, "message": "ต้องมี network อย่างน้อย 1 รายการ"}), 400
        cmds = build_rip(networks)

    elif route_type == "eigrp":
        as_num = int(data.get("as_num", 100))
        networks = data.get("networks", [])  # list of {network, wildcard}
        if not networks:
            return jsonify({"success": False, "message": "ต้องมี network อย่างน้อย 1 รายการ"}), 400
        cmds = build_eigrp(as_num, networks)

    elif route_type == "ospf":
        process_id = int(data.get("process_id", 1))
        router_id = data.get("router_id", "")
        networks = data.get("networks", [])  # list of {network, wildcard, area}
        if not networks:
            return jsonify({"success": False, "message": "ต้องมี network อย่างน้อย 1 รายการ"}), 400
        cmds = build_ospf(process_id, router_id, networks)

    elif route_type == "bgp":
        as_num = int(data.get("as_num", 65001))
        neighbors = data.get("neighbors", [])  # list of {ip, remote_as}
        networks = data.get("networks", [])    # list of {network, mask}
        cmds = build_bgp(as_num, neighbors, networks)

    else:
        return jsonify({"success": False, "message": f"route_type '{route_type}' ไม่รองรับ"}), 400

    # ส่งจริงหรือ simulate
    if conn_mgr.is_connected(device_id):
        result = conn_mgr.send_config(device_id, cmds)
    else:
        dev = DEMO_DEVICES.get(device_id, {})
        dev_name = dev.get("name", device_id)
        output_lines = [f"{dev_name}#configure terminal"] + \
                       [f"{dev_name}(config)# {c}" for c in cmds] + \
                       [f"{dev_name}#end"]
        result = {"success": True, "output": "\n".join(output_lines)}

    result["commands"] = cmds
    result["preview"] = preview_commands(cmds)
    return jsonify(result)


# ===========================================================================
# Routes — Show Commands
# ===========================================================================
@app.route("/api/show", methods=["POST"])
def run_show_command():
    """รัน show command และคืน output"""
    data = request.json or {}
    device_id = data.get("device_id", "R1")
    command = data.get("command", "show ip interface brief")

    # Normalize คำสั่งย่อ
    command = normalize(command)

    if conn_mgr.is_connected(device_id):
        result = conn_mgr.send_command(device_id, command)
        output = result.get("output", "")
    else:
        output = _demo_show(device_id, command)

    return jsonify({"success": True, "device_id": device_id, "command": command, "output": output})


# ===========================================================================
# Routes — CLI Terminal
# ===========================================================================
@app.route("/api/cli/execute", methods=["POST"])
def execute_cli():
    """รัน raw CLI command (อาจเป็น show หรือ config ก็ได้)"""
    data = request.json or {}
    device_id = data.get("device_id", "R1")
    raw_command = data.get("command", "").strip()

    if not raw_command:
        return jsonify({"success": False, "message": "ต้องระบุ command"}), 400

    # Normalize คำสั่งย่อ
    command = normalize(raw_command)

    # ตรวจว่าเป็น show command หรือ config command
    is_show = command.lower().startswith("show") or command.lower().startswith("sh ")

    if conn_mgr.is_connected(device_id):
        if is_show:
            result = conn_mgr.send_command(device_id, command)
        else:
            result = conn_mgr.send_config(device_id, [command])
        output = result.get("output", "")
    else:
        if is_show:
            output = _demo_show(device_id, command)
        else:
            dev = DEMO_DEVICES.get(device_id, {})
            dev_name = dev.get("name", device_id)
            output = f"{dev_name}(config)# {command}\n{dev_name}#"

    return jsonify({"success": True, "device_id": device_id, "command": command, "output": output})


# ===========================================================================
# Routes — Command Autocomplete/Normalization
# ===========================================================================
@app.route("/api/suggestions", methods=["GET"])
def get_command_suggestions():
    """คืน autocomplete suggestions สำหรับ CLI input"""
    partial = request.args.get("q", "")
    suggestions = get_suggestions(partial, max_results=10)
    return jsonify({"success": True, "suggestions": suggestions})


# ===========================================================================
# Routes — Topology (Bonus)
# ===========================================================================
@app.route("/api/topology/json", methods=["GET"])
def get_topology_json():
    """Auto-Discovery และคืน graph JSON สำหรับ vis-network frontend"""
    inv = load_inventory()
    if not inv:
        # Demo mode: คืน demo graph
        return jsonify({"success": True, "demo": True, **DEMO_GRAPH_JSON})

    connected_ids = [d["id"] for d in conn_mgr.get_connected_devices()]

    if NX_AVAILABLE and connected_ids:
        G = build_topology_graph(conn_mgr, connected_ids, inv)
        topo = graph_to_json(G, inv)
    else:
        # Fallback: สร้าง nodes จาก inventory ทั้งหมด
        topo = {
            "nodes": [{"id": d["id"], "name": d.get("name", d["id"]),
                        "type": d.get("device_type_label", "router"),
                        "ip": d.get("ip", ""), "model": d.get("model", ""),
                        "status": "connected" if conn_mgr.is_connected(d["id"]) else "disconnected"}
                      for d in inv],
            "edges": []
        }

    return jsonify({"success": True, "demo": len(connected_ids) == 0, **topo})


@app.route("/api/ports/<device_id>", methods=["GET"])
def get_device_ports(device_id: str):
    """คืนข้อมูล port front-panel สำหรับ Modal (Bonus)"""
    # ลองดึงจาก live device ก่อน
    if conn_mgr.is_connected(device_id):
        result = conn_mgr.send_command(device_id, "show ip interface brief", use_textfsm=True)
        raw = result.get("output", "")
    else:
        raw = _demo_show(device_id, "show ip interface brief")

    # Parse port data
    dev = DEMO_DEVICES.get(device_id, {})
    ports = []
    for if_name, if_info in dev.get("interfaces", {}).items():
        short = _short_if_name(if_name)
        ports.append({
            "name": if_name,
            "short_name": short,
            "type": "serial" if "Serial" in if_name else
                    "virtual" if ("Loopback" in if_name or "Vlan" in if_name) else "ethernet",
            "status": if_info.get("status", "down"),
            "ip": if_info.get("ip", "unassigned"),
            "mask": if_info.get("mask", ""),
            "speed": "1.544Mbps" if "Serial" in if_name else
                     "Virtual" if "Loopback" in if_name else
                     "100Mbps" if "Fast" in if_name else "1Gbps",
            "led": "green" if if_info.get("status") == "up" else "red",
        })

    return jsonify({
        "success": True,
        "device": {
            "id": device_id,
            "name": dev.get("name", device_id),
            "model": dev.get("model", "Cisco IOS"),
            "type": dev.get("type", "router"),
            "ip": dev.get("ip", ""),
            "connected": conn_mgr.is_connected(device_id),
        },
        "ports": ports
    })


def _short_if_name(name: str) -> str:
    for long, short in [("GigabitEthernet", "Gi"), ("FastEthernet", "Fa"),
                         ("Serial", "Se"), ("Loopback", "Lo"), ("Vlan", "Vl")]:
        if name.startswith(long):
            return short + name[len(long):]
    return name


# ===========================================================================
# Routes — Hardware Profiles (spec v3 section 3)
# ===========================================================================
@app.route("/api/models", methods=["GET"])
def get_models():
    """คืนรายชื่อ Model ทั้งหมด (กรองตาม device_type ได้)"""
    device_type = request.args.get("type", None)
    models = get_model_list(device_type)
    return jsonify({"success": True, "models": models})


@app.route("/api/models/<model_name>/interfaces", methods=["GET"])
def get_model_interfaces(model_name):
    """คืน default interfaces ตาม Hardware Profile ของ Model"""
    interfaces = generate_interfaces(model_name)
    return jsonify({"success": True, "model": model_name, "interfaces": interfaces})


# ===========================================================================
# Routes — Interface CRUD (spec v3 section 3.2)
# ===========================================================================
@app.route("/api/devices/<device_id>/interfaces", methods=["GET"])
def get_device_interfaces(device_id):
    """คืน interfaces ทั้งหมดของ device"""
    dev = get_device_by_id(device_id)
    if not dev:
        # ลอง demo devices
        demo_dev = DEMO_DEVICES.get(device_id)
        if not demo_dev:
            return jsonify({"success": False, "message": f"Device '{device_id}' ไม่พบ"}), 404
        ifaces = []
        for if_name, if_info in demo_dev.get("interfaces", {}).items():
            ifaces.append({
                "name": if_name,
                "ip": if_info.get("ip", "unassigned"),
                "mask": if_info.get("mask", ""),
                "status": if_info.get("status", "down"),
                "description": if_info.get("description"),
            })
        return jsonify({"success": True, "device_id": device_id, "interfaces": ifaces})

    return jsonify({
        "success": True,
        "device_id": device_id,
        "interfaces": dev.get("interfaces", []),
    })


@app.route("/api/devices/<device_id>/interfaces", methods=["POST"])
def add_device_interface(device_id):
    """เพิ่ม interface ใหม่ (Loopback, Serial, Vlan)"""
    data = request.json or {}
    iface_type = data.get("type", "loopback")  # loopback, serial, vlan
    number = data.get("number", 0)

    new_iface = create_additional_interface(iface_type, number)
    if not new_iface:
        return jsonify({"success": False, "message": f"ไม่รองรับ interface type: {iface_type}"}), 400

    # อัพเดทใน demo devices ถ้ามี
    if device_id in DEMO_DEVICES:
        DEMO_DEVICES[device_id]["interfaces"][new_iface["name"]] = {
            "ip": "unassigned", "mask": "", "status": "down"
        }

    # อัพเดทใน inventory
    dev = get_device_by_id(device_id)
    if dev:
        if "interfaces" not in dev:
            dev["interfaces"] = []
        dev["interfaces"].append(new_iface)
        devices = load_inventory()
        for i, d in enumerate(devices):
            if d.get("id") == device_id:
                devices[i] = dev
                break
        save_inventory(devices)

    return jsonify({"success": True, "interface": new_iface})


# ===========================================================================
# Routes — Validation (spec v3 section 12, 30)
# ===========================================================================
@app.route("/api/validate", methods=["POST"])
def validate_input():
    """Validate input ก่อนส่งไปยัง device"""
    data = request.json or {}
    ip = data.get("ip")
    mask = data.get("mask")
    wildcard = data.get("wildcard")
    router_id = data.get("router_id")
    as_num = data.get("as_num")

    valid, errors = validate_interface_config(
        ip=ip, mask=mask, wildcard=wildcard,
        router_id=router_id, as_num=as_num
    )
    return jsonify({"success": valid, "errors": errors})


# ===========================================================================
# Routes — Config File Lifecycle (spec v3 section 19)
# ===========================================================================
@app.route("/api/config/<device_id>/running", methods=["GET"])
def export_running(device_id):
    """Export Running Config (spec 19.1)"""
    if conn_mgr.is_connected(device_id):
        result = conn_mgr.export_running_config(device_id)
        output = result.get("output", "")
    else:
        output = _demo_show(device_id, "show running-config")

    # ถ้า query param ?download=true → ส่งเป็นไฟล์
    if request.args.get("download") == "true":
        return Response(
            output,
            mimetype="text/plain",
            headers={"Content-Disposition": f"attachment;filename={device_id}-running-config.txt"}
        )
    return jsonify({"success": True, "device_id": device_id, "config": output})


@app.route("/api/config/<device_id>/startup", methods=["GET"])
def export_startup(device_id):
    """Export Startup Config (spec 19.3)"""
    if conn_mgr.is_connected(device_id):
        result = conn_mgr.export_startup_config(device_id)
        output = result.get("output", "")
    else:
        output = _demo_show(device_id, "show startup-config")

    if request.args.get("download") == "true":
        return Response(
            output,
            mimetype="text/plain",
            headers={"Content-Disposition": f"attachment;filename={device_id}-startup-config.txt"}
        )
    return jsonify({"success": True, "device_id": device_id, "config": output})


@app.route("/api/config/<device_id>/merge", methods=["POST"])
def merge_config(device_id):
    """Merge Running Config จาก text/file (spec 19.2)"""
    data = request.json or {}
    config_text = data.get("config", "")
    if not config_text.strip():
        return jsonify({"success": False, "message": "ต้องมี config text"}), 400

    if conn_mgr.is_connected(device_id):
        result = conn_mgr.merge_config(device_id, config_text)
    else:
        # Simulate
        dev = DEMO_DEVICES.get(device_id, {})
        dev_name = dev.get("name", device_id)
        lines = [l.strip() for l in config_text.splitlines() if l.strip() and not l.strip().startswith("!")]
        output = f"{dev_name}#configure terminal\n"
        output += "\n".join(f"{dev_name}(config)# {l}" for l in lines)
        output += f"\n{dev_name}#end"
        result = {"success": True, "output": output}

    return jsonify(result)


@app.route("/api/config/<device_id>/save", methods=["POST"])
def save_config(device_id):
    """Save Running → Startup (write memory) (spec 19.4)"""
    if conn_mgr.is_connected(device_id):
        result = conn_mgr.save_config(device_id)
    else:
        dev = DEMO_DEVICES.get(device_id, {})
        dev_name = dev.get("name", device_id)
        result = {
            "success": True,
            "output": f"{dev_name}#write memory\nBuilding configuration...\n[OK]"
        }
    return jsonify(result)


# ===========================================================================
if __name__ == "__main__":
    print("Starting NetConfig Tracer Studio (v2) on http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
