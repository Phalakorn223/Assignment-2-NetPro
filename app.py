"""
app.py — NetConfig Tracer Studio Web Server
Flask backend ที่ใช้ ConnectionManager, command_builder, command_normalizer, topology_builder
Spec v3: เพิ่ม hardware_profiles, validators, config lifecycle, interface CRUD
"""

from flask import Flask, render_template, request, jsonify, Response

from connection_manager import (
    ConnectionManager, ip_is_valid, ping_check,
    load_inventory, save_inventory, add_device_to_inventory,
    remove_device_from_inventory, get_device_by_id,
    ensure_inventory_initialized, parse_interface_status,
    parse_ip_interface_brief,
)
from command_builder import (
    build_ip_address_commands, build_interface_state_commands,
    build_static_route, build_default_route,
    build_rip, build_eigrp, build_ospf, build_bgp, preview_commands,
    merge_router_protocol_commands,
)
from command_normalizer import normalize, get_suggestions
from topology_builder import (
    build_topology_graph, graph_to_json, DEMO_GRAPH_JSON, NX_AVAILABLE,
    collect_device_interfaces,
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
DEMO_DEVICES = {}




# ===========================================================================
# Helpers
# ===========================================================================
def _get_active_device_id(data: dict) -> str:
    return data.get("device_id", "R1")





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
    """รายชื่อ device ทั้งหมด (จาก devices.json — seed ถูก persist ครั้งแรก)"""
    inv = ensure_inventory_initialized()
    for dev in inv:
        dev["connected"] = conn_mgr.is_connected(dev.get("id", ""))
        # Ensure port is always present for frontend display
        if "port" not in dev:
            conn_type = (dev.get("connection_type") or "SSH").upper()
            dev["port"] = 22 if conn_type == "SSH" else 23
        if dev.get("device_type_label") == "pc":
            demo = DEMO_DEVICES.get(dev.get("id"))
            if demo:
                dev.setdefault("gateway", demo.get("gateway", ""))
                dev.setdefault("mask", demo.get("mask", "255.255.255.0"))
    return jsonify({"success": True, "devices": inv})


@app.route("/api/inventory", methods=["POST"])
def add_device():
    """เพิ่ม device ใหม่"""
    data = request.json or {}
    dtype = (data.get("device_type_label") or "router").lower()
    conn_type = (data.get("connection_type") or "SSH").upper()
    if dtype == "pc":
        data["connection_type"] = "PC"
        if not data.get("ip"):
            return jsonify({"success": False, "message": "Virtual PC ต้องมี IP address"}), 400
    elif not data.get("ip") and conn_type not in ("SERIAL", "PC"):
        return jsonify({"success": False, "message": "IP address จำเป็น"}), 400
    if data.get("ip"):
        valid, msg = ip_is_valid(data["ip"])
        if not valid:
            return jsonify({"success": False, "message": msg}), 400
    device = add_device_to_inventory(data)
    if dtype == "pc":
        DEMO_DEVICES[device["id"]] = {
            "name": device.get("name", device["id"]),
            "model": device.get("model", "Virtual PC"),
            "type": "pc",
            "ip": device.get("ip", ""),
            "gateway": device.get("gateway", ""),
            "mask": device.get("mask", "255.255.255.0"),
            "connection_type": "PC",
            "interfaces": {},
            "routing": {},
        }
    return jsonify({"success": True, "device": device})


@app.route("/api/inventory/<device_id>", methods=["DELETE"])
def delete_device(device_id):
    """ลบ device"""
    if conn_mgr.is_connected(device_id):
        conn_mgr.disconnect(device_id)
    removed = remove_device_from_inventory(device_id)
    DEMO_DEVICES.pop(device_id, None)
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
    data = request.get_json(silent=True) or {}
    dev = get_device_by_id(device_id) or {}
    if not dev and not data.get("ip"):
        return jsonify({"success": False, "message": f"ไม่พบ device '{device_id}' ใน inventory"}), 404
    if (dev.get("device_type_label") or "").lower() == "pc":
        return jsonify({
            "success": True,
            "message": "Virtual PC ไม่ต้อง SSH — ใช้ฟอร์ม IP Config และ Ping ได้ทันที",
        })
    # เติมพารามิเตอร์จาก inventory ถ้าไม่ได้ส่งมาใน request body
    params = dict(dev)
    params.update(data)
    skip_ping = data.get("skip_ping", False)
    res = conn_mgr.connect(device_id, params, skip_ping=skip_ping)
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
# Helpers — Interface list (with cache)
# ===========================================================================
import time as _time

_interface_cache = {}   # {device_id: {"data": [...], "ts": float}}
_IFACE_CACHE_TTL = 60   # วินาที — ใช้ cache ภายใน 60 วินาที ไม่ต้องไปถาม Router

def _interfaces_for_device(device_id: str, force_refresh: bool = False) -> list:
    """ดึง interface list — ใช้ cache เพื่อไม่ส่งคำสั่งไปรบกวน Router console"""
    now = _time.time()

    # ถ้ามี cache และยังไม่หมดอายุ → ใช้ cache เลย
    if not force_refresh and device_id in _interface_cache:
        cached = _interface_cache[device_id]
        if now - cached["ts"] < _IFACE_CACHE_TTL and cached["data"]:
            return cached["data"]

    # ดึงจาก Router จริง (ผ่าน Netmiko)
    if conn_mgr.is_connected(device_id):
        result = conn_mgr.send_command(device_id, "show ip interface brief", use_textfsm=True)
        parsed = parse_ip_interface_brief(result.get("output", ""))
        if parsed:
            _interface_cache[device_id] = {"data": parsed, "ts": now}
            return parsed
    return _interface_cache.get(device_id, {}).get("data", [])


def _invalidate_interface_cache(device_id: str):
    """ล้าง cache เมื่อมีการเปลี่ยน config interface"""
    _interface_cache.pop(device_id, None)


# ===========================================================================
# Routes — Interface Configuration
# ===========================================================================
@app.route("/api/devices/<device_id>/interfaces", methods=["GET"])
def list_device_interfaces(device_id: str):
    force = request.args.get("force", "").lower() in ("1", "true", "yes")
    return jsonify({"success": True, "device_id": device_id, "interfaces": _interfaces_for_device(device_id, force_refresh=force)})


@app.route("/api/config/interface/state", methods=["POST"])
def set_interface_state_only():
    """Up/Down แยกจาก IP config + verify สถานะหลัง deploy"""
    data = request.json or {}
    device_id = data.get("device_id")
    interface = data.get("interface")
    state = data.get("state", "up")
    if not device_id or not interface:
        return jsonify({"success": False, "message": "device_id และ interface จำเป็น"}), 400
    if state not in ("up", "down"):
        return jsonify({"success": False, "message": "state ต้องเป็น up หรือ down"}), 400

    cmds = build_interface_state_commands(interface, up=(state == "up"))
    if conn_mgr.is_connected(device_id):
        result = conn_mgr.send_config(device_id, cmds)
        verify = conn_mgr.send_command(device_id, f"show interfaces {interface}")
        current = parse_interface_status(verify.get("output", ""), interface)
        result["current_status"] = current
    else:
        return jsonify({"success": False, "message": "Device not connected. Please connect first."})
    result["commands"] = cmds
    result["preview"] = preview_commands(cmds)
    _invalidate_interface_cache(device_id)
    return jsonify(result)


@app.route("/api/config/interface", methods=["POST"])
@app.route("/api/devices/<device_id>/interfaces/configure", methods=["POST"])
def configure_interface(device_id=None):
    """กำหนด IP Address และสถานะ Up/Down ของ interface"""
    data = request.get_json(silent=True) or {}
    dev_id = device_id or data.get("device_id")
    interface = data.get("interface")
    ip = data.get("ip", "")
    mask = data.get("mask", "255.255.255.0")
    state = data.get("state", data.get("status", "up"))
    description = data.get("description", "")

    if not dev_id or not interface:
        return jsonify({"success": False, "message": "device_id และ interface จำเป็น"}), 400

    # Validate IP ถ้ามี (ยกเว้นโหมด DHCP)
    if ip and ip.lower().strip() != "dhcp":
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
    if conn_mgr.is_connected(dev_id):
        result = conn_mgr.send_config(dev_id, cmds)
    else:
        return jsonify({"success": False, "message": "Device not connected. Please connect first."})

    result["commands"] = cmds
    result["preview"] = preview_commands(cmds)
    if "message" not in result:
        result["message"] = f"กำหนดค่า {interface} สำเร็จ" if result.get("success") else result.get("error", "ตั้งค่าไม่สำเร็จ")
    _invalidate_interface_cache(dev_id)
    _interfaces_for_device(dev_id, force_refresh=True)
    return jsonify(result)


# ===========================================================================
# Routes — Routing Protocol Configuration
# ===========================================================================
def _build_routing_commands(data: dict):
    """สร้างคำสั่ง routing จาก data payload คืน (cmds, error_message)"""
    route_type = (data.get("route_type") or data.get("routing_type") or "").lower()
    if not route_type:
        return [], "route_type จำเป็น"

    cmds = []
    if route_type == "static":
        network = data.get("network", "")
        mask = data.get("mask", "255.255.255.0")
        next_hop = data.get("next_hop", "")
        if not network and data.get("networks"):
            nets = data.get("networks")
            if isinstance(nets, list) and nets:
                n0 = nets[0]
                if isinstance(n0, dict):
                    network = n0.get("network", "")
                    mask = n0.get("mask", mask)
                    next_hop = n0.get("next_hop", next_hop)
        if not network or not next_hop:
            return [], "network และ next_hop จำเป็น"
        cmds = build_static_route(network, mask, next_hop)

    elif route_type == "default":
        next_hop = data.get("next_hop", "")
        if not next_hop:
            return [], "next_hop จำเป็น"
        cmds = build_default_route(next_hop)

    elif route_type == "rip":
        networks = data.get("networks", [])
        cleaned = []
        for n in networks:
            if isinstance(n, dict):
                cleaned.append(n.get("network", ""))
            elif isinstance(n, str):
                cleaned.append(n)
        if not cleaned:
            return [], "ต้องมี network อย่างน้อย 1 รายการ"
        rip_version = int(data.get("rip_version", data.get("version", 2)))
        cmds = build_rip(cleaned, version=rip_version)
        cmds = merge_router_protocol_commands(
            cmds, "rip",
            data.get("redistribute"),
            data.get("default_originate"),
        )

    elif route_type == "eigrp":
        as_num = int(data.get("as_num", data.get("as_number", 100)))
        networks = data.get("networks", [])
        if not networks:
            return [], "ต้องมี network อย่างน้อย 1 รายการ"
        cmds = build_eigrp(as_num, networks)
        cmds = merge_router_protocol_commands(
            cmds, "eigrp",
            data.get("redistribute"),
            data.get("default_originate"),
        )

    elif route_type == "ospf":
        process_id = int(data.get("process_id", 1))
        router_id = data.get("router_id", "")
        networks = data.get("networks", [])
        if not networks:
            return [], "ต้องมี network อย่างน้อย 1 รายการ"
        cmds = build_ospf(process_id, router_id, networks)
        cmds = merge_router_protocol_commands(
            cmds, "ospf",
            data.get("redistribute"),
            data.get("default_originate"),
        )

    elif route_type == "bgp":
        as_num = int(data.get("as_num", data.get("as_number", 65001)))
        neighbors = data.get("neighbors", [])
        networks = data.get("networks", [])
        cmds = build_bgp(as_num, neighbors, networks)
        cmds = merge_router_protocol_commands(
            cmds, "bgp",
            data.get("redistribute"),
            data.get("default_originate"),
        )
    else:
        return [], f"route_type '{route_type}' ไม่รองรับ"

    return cmds, ""


@app.route("/api/routing/preview", methods=["POST"])
def preview_routing():
    """Preview CLI commands สำหรับ routing protocol ก่อน deploy"""
    data = request.get_json(silent=True) or {}
    cmds, err = _build_routing_commands(data)
    if err:
        return jsonify({"success": False, "message": err}), 400
    return jsonify({
        "success": True,
        "commands": cmds,
        "preview": preview_commands(cmds)
    })


@app.route("/api/config/routing", methods=["POST"])
@app.route("/api/routing/apply", methods=["POST"])
def configure_routing():
    """กำหนด Routing Protocol หรือ Apply commands ตรงไปยังอุปกรณ์"""
    data = request.get_json(silent=True) or {}
    device_id = data.get("device_id")

    if not device_id:
        return jsonify({"success": False, "message": "device_id จำเป็น"}), 400

    # ถ้าส่ง commands list มาตรง ๆ
    if "commands" in data and isinstance(data["commands"], list):
        cmds = data["commands"]
    else:
        cmds, err = _build_routing_commands(data)
        if err:
            return jsonify({"success": False, "message": err}), 400

    # ส่งจริงหรือ simulate
    if conn_mgr.is_connected(device_id):
        result = conn_mgr.send_config(device_id, cmds)
    else:
        return jsonify({"success": False, "message": "Device not connected. Please connect first."})

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
        return jsonify({"success": False, "message": "Device not connected. Please connect first."})

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
        return jsonify({"success": False, "message": "Device not connected. Please connect first."})
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
@app.route("/api/config/ssh-setup", methods=["POST"])
def ssh_setup_wizard():
    data = request.json or {}
    device_id = data.get("device_id")
    domain = (data.get("domain_name") or "").strip()
    if not device_id or not domain:
        return jsonify({"success": False, "message": "device_id และ domain_name จำเป็น"}), 400
    key_size = int(data.get("key_size", 1024))
    username = data.get("username", "cisco")
    password = data.get("password", "cisco")
    if conn_mgr.is_connected(device_id):
        result = conn_mgr.setup_ssh(device_id, domain, key_size, username, password)
    else:
        return jsonify({"success": False, "message": "Device not connected. Please connect first."})
    return jsonify(result)


@app.route("/api/pc/<device_id>/config", methods=["POST"])
def configure_virtual_pc(device_id: str):
    data = request.json or {}
    dev = get_device_by_id(device_id)
    if not dev or (dev.get("device_type_label") or "").lower() != "pc":
        return jsonify({"success": False, "message": "ไม่ใช่ Virtual PC"}), 400
    ip = data.get("ip", "")
    mask = data.get("mask", "255.255.255.0")
    gateway = data.get("gateway", "")
    if ip:
        valid, msg = ip_is_valid(ip)
        if not valid:
            return jsonify({"success": False, "message": msg}), 400
    devices = load_inventory()
    for d in devices:
        if d.get("id") == device_id:
            d["ip"] = ip
            d["mask"] = mask
            d["gateway"] = gateway
            break
    save_inventory(devices)
    return jsonify({"success": True, "message": "บันทึก IP config ของ Virtual PC แล้ว"})


@app.route("/api/pc/<device_id>/ping", methods=["POST"])
def virtual_pc_ping(device_id: str):
    data = request.json or {}
    target = (data.get("target") or "").strip()
    if not target:
        return jsonify({"success": False, "message": "ต้องระบุ target IP"}), 400
    valid, msg = ip_is_valid(target)
    if not valid:
        return jsonify({"success": False, "message": msg}), 400

    dev = get_device_by_id(device_id) or {}
    gateway_id = data.get("via_device_id") or dev.get("gateway_router")
    gateway_ip = dev.get("gateway", "")

    if gateway_id and conn_mgr.is_connected(gateway_id):
        result = conn_mgr.send_command(gateway_id, f"ping {target} repeat 3")
        output = result.get("output", "")
        success_rate = ("!" in output and "Success rate is 0 percent" not in output)
        return jsonify({
            "success": True,
            "reachable": success_rate,
            "output": f"[Ping from router {gateway_id} as PC gateway proxy]\n{output}",
        })

    reachable = ping_check(target)
    return jsonify({
        "success": True,
        "reachable": reachable,
        "output": (
            f"Virtual PC {dev.get('name', device_id)} ({dev.get('ip', 'N/A')}) "
            f"gateway {gateway_ip or 'N/A'} → ping {target}\n"
            + ("SUCCESS: host ตอบสนอง" if reachable else "FAIL: ไม่ตอบสนอง ping จากเครื่องที่รันแอป")
        ),
    })


@app.route("/api/eveng/import", methods=["POST"])
def import_eveng_topology():
    data = request.json or {}
    host = (data.get("host") or "").strip()
    lab_path = (data.get("lab_path") or "").strip()
    username = data.get("username", "admin")
    password = data.get("password", "eve")
    if not host or not lab_path:
        return jsonify({"success": False, "message": "host และ lab_path จำเป็น"}), 400
    try:
        from eve_ng_client import EveNgClient, eveng_topology_to_graph
        client = EveNgClient(host, username, password)
        topo_raw = client.get_topology(lab_path)
        nodes_raw = client.get_nodes(lab_path)
        try:
            networks_raw = client.get_networks(lab_path)
        except Exception:
            networks_raw = None
        graph = eveng_topology_to_graph(topo_raw, nodes_raw, networks_raw)

        # เพิ่ม Nodes จาก EVE-NG ลงใน Inventory เพื่อให้เลือกและกดใช้งานได้ทันที
        inv = load_inventory()
        existing_names = {d.get("name", "").lower(): d for d in inv}
        existing_ids = {d.get("id", "").lower(): d for d in inv}

        nodes_data_map = nodes_raw.get("data", {}) if isinstance(nodes_raw, dict) else {}
        clean_host = host.replace("http://", "").replace("https://", "").split("/")[0]

        for n in graph.get("nodes", []):
            nid = str(n.get("id"))
            name = n.get("name", f"Node-{nid}")
            dtype = n.get("type", "router")
            
            # ข้ามการเพิ่ม network nodes (cloud/bridge) เข้า inventory — ไม่ใช่ device
            if dtype == "network":
                continue
            
            # ดึง port telnet console จาก EVE-NG node metadata ถ้ามี
            raw_node_info = nodes_data_map.get(nid) if isinstance(nodes_data_map, dict) else {}
            console_port = 23
            if isinstance(raw_node_info, dict):
                console_port = int(raw_node_info.get("port") or raw_node_info.get("url", "").split(":")[-1] or 23)

            matched = existing_names.get(name.lower()) or existing_ids.get(nid.lower())
            if matched:
                matched["ip"] = matched.get("ip") or clean_host
                matched["port"] = matched.get("port") or console_port
                matched["connection_type"] = matched.get("connection_type") or "TELNET"
            else:
                new_dev = {
                    "id": name,
                    "name": name,
                    "model": n.get("model") or "Cisco IOS",
                    "device_type_label": dtype,
                    "connection_type": "TELNET",
                    "ip": clean_host,
                    "port": console_port,
                    "username": "",
                    "password": "",
                    "mask": "255.255.255.0",
                    "gateway": ""
                }
                inv.append(new_dev)


        save_inventory(inv)
        return jsonify({"success": True, "demo": False, "source": "eveng", "devices": inv, **graph})
    except Exception as e:
        return jsonify({"success": False, "message": f"EVE-NG import ล้มเหลว: {e}"}), 502


@app.route("/api/topology/json", methods=["GET"])
def get_topology_json():
    """Auto-Discovery และคืน graph JSON สำหรับ vis-network frontend"""
    inv = ensure_inventory_initialized()
    if not inv:
        return jsonify({"success": True, "demo": True, **DEMO_GRAPH_JSON})

    connected_ids = [d["id"] for d in conn_mgr.get_connected_devices()]

    if NX_AVAILABLE and connected_ids:
        print(f"[Topology] Running auto-discovery for {len(connected_ids)} connected device(s): {connected_ids}")
        G = build_topology_graph(conn_mgr, connected_ids, inv)
        topo = graph_to_json(G, inv)
        print(f"[Topology] Discovered {len(topo.get('nodes', []))} nodes, {len(topo.get('edges', []))} edges")
        for edge in topo.get("edges", []):
            detail = f"  Edge: {edge['from']} ({edge.get('from_port','')}"
            if edge.get('from_ip'):
                detail += f" IP:{edge['from_ip']}"
            detail += f") <-> {edge['to']} ({edge.get('to_port','')}" 
            if edge.get('to_ip'):
                detail += f" IP:{edge['to_ip']}"
            detail += f") [{edge.get('method','')}]"
            if edge.get('subnet'):
                detail += f" subnet={edge['subnet']}"
            print(detail)
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


@app.route("/api/topology/interfaces", methods=["GET"])
def get_all_device_interfaces_for_topology():
    """
    Diagnostic endpoint: ดึง interface IP จริงจากทุก device ที่ connect อยู่
    เพื่อตรวจสอบว่า auto-discovery เห็นอะไรบ้าง
    """
    connected = conn_mgr.get_connected_devices()
    result = {}
    for c in connected:
        dev_id = c["id"]
        ifaces = collect_device_interfaces(conn_mgr, dev_id)
        result[dev_id] = ifaces
        print(f"[Topology Debug] {dev_id} interfaces:")
        for iface in ifaces:
            print(f"  {iface['name']:25s} IP: {iface['ip']:16s} Mask: {iface['mask']:16s} Status: {iface['status']}")
    return jsonify({"success": True, "device_interfaces": result})


@app.route("/api/ports/<device_id>", methods=["GET"])
def get_device_ports(device_id: str):
    """คืนข้อมูล port front-panel สำหรับ Modal (Bonus)"""
    # ลองดึงจาก live device ก่อน
    raw = ""
    if conn_mgr.is_connected(device_id):
        result = conn_mgr.send_command(device_id, "show ip interface brief", use_textfsm=True)
        raw = result.get("output", "")
    
    inv_dev = get_device_by_id(device_id) or {}
    if inv_dev.get("device_type_label") == "pc":
        return jsonify({
            "success": True,
            "device": {
                "id": device_id,
                "name": inv_dev.get("name", device_id),
                "model": inv_dev.get("model", "Virtual PC"),
                "type": "pc",
                "ip": inv_dev.get("ip", ""),
                "connected": False,
            },
            "ports": [{
                "name": "NIC0",
                "short_name": "NIC0",
                "type": "ethernet",
                "status": "up",
                "ip": inv_dev.get("ip", "unassigned"),
                "mask": inv_dev.get("mask", ""),
                "speed": "100Mbps",
                "led": "green",
            }],
        })

    iface_rows = _interfaces_for_device(device_id)
    ports = []
    if iface_rows:
        for row in iface_rows:
            if_name = row["name"]
            st = row.get("status", "down")
            ip = row.get("ip", "unassigned")
            ports.append({
                "name": if_name,
                "short_name": _short_if_name(if_name),
                "type": "serial" if "Serial" in if_name else
                        "virtual" if ("Loopback" in if_name or "Vlan" in if_name) else "ethernet",
                "status": st,
                "ip": ip,
                "mask": "",
                "speed": "1.544Mbps" if "Serial" in if_name else
                         "Virtual" if "Loopback" in if_name else
                         "100Mbps" if "Fast" in if_name else "1Gbps",
                "led": "green" if st == "up" else "red",
            })



    return jsonify({
        "success": True,
        "device": {
            "id": device_id,
            "name": inv_dev.get("name", device_id),
            "model": inv_dev.get("model", "Cisco IOS"),
            "type": inv_dev.get("device_type_label", "router"),
            "ip": inv_dev.get("ip", ""),
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
