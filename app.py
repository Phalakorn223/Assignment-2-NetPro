"""
app.py — NetConfig Tracer Studio Web Server
Flask backend ที่ใช้ ConnectionManager, command_builder, command_normalizer, topology_builder
Spec v3: เพิ่ม hardware_profiles, validators, config lifecycle, interface CRUD
"""

from flask import Flask, render_template, request, jsonify, Response
import re

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


def _demo_show(device_id: str, command: str) -> str:
    """Simulate Cisco IOS show command output สำหรับ demo mode หรือเมื่อ device offline"""
    dev = DEMO_DEVICES.get(device_id) or get_device_by_id(device_id)
    if not dev:
        return f"Error: Device '{device_id}' ไม่พบในระบบ"

    cmd_lower = command.lower().strip()
    name = dev.get("name", device_id)
    raw_ifaces = dev.get("interfaces", {})
    if isinstance(raw_ifaces, list):
        interfaces = {iface.get("name", f"if{i}"): iface for i, iface in enumerate(raw_ifaces)}
    elif isinstance(raw_ifaces, dict):
        interfaces = raw_ifaces
    else:
        interfaces = {}

    # show ip interface brief
    if "ip int" in cmd_lower or "ip interface brief" in cmd_lower:
        lines = [f"{name}# {command}", f"{'Interface':<25} {'IP-Address':<16} {'OK?':<5} {'Method':<8} {'Status':<22} {'Protocol'}"]
        lines.append("-" * 85)
        for ifname, info in interfaces.items():
            st = "up" if info.get("status") == "up" else "administratively down"
            pr = "up" if info.get("status") == "up" else "down"
            ip = info.get("ip", "unassigned")
            mt = "manual" if ip not in ("unassigned", "", None) else "unset"
            lines.append(f"{ifname:<25} {ip:<16} {'YES':<5} {mt:<8} {st:<22} {pr}")
        return "\n".join(lines)

    # show interfaces status
    if "interfaces status" in cmd_lower:
        lines = [f"{name}# {command}", f"{'Port':<22} {'Name':<20} {'Status':<12} {'Vlan':<8} {'Speed':<8}"]
        lines.append("-" * 75)
        for ifname, info in interfaces.items():
            st = "connected" if info.get("status") == "up" else "notconnect"
            lines.append(f"{ifname:<22} {'':20} {st:<12} {'1':<8} {'auto':<8}")
        return "\n".join(lines)

    # show running-config or startup-config
    if "run" in cmd_lower or "start" in cmd_lower:
        lines = [f"{name}# {command}", "Building configuration...\n!", f"hostname {name}", "!"]
        for ifname, info in interfaces.items():
            lines.append(f"interface {ifname}")
            ip = info.get("ip", "unassigned")
            mask = info.get("mask", "")
            if ip not in ("unassigned", "", None):
                lines.append(f" ip address {ip} {mask or '255.255.255.0'}")
            lines.append(" no shutdown" if info.get("status") == "up" else " shutdown")
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
    elif dtype in ("network", "cloud"):
        data["device_type_label"] = "network"
        data["connection_type"] = "NETWORK"
        data["ip"] = data.get("ip") or "192.168.100.0/24"
        data["port"] = 0
    elif conn_type == "SERIAL":
        if not data.get("serial_port"):
            data["serial_port"] = "COM1"
        data["ip"] = ""
        data["port"] = 0
    elif not data.get("ip") and conn_type not in ("SERIAL", "PC", "NETWORK") and dtype not in ("network", "cloud"):
        return jsonify({"success": False, "message": "IP address จำเป็น"}), 400

    if data.get("ip") and conn_type not in ("SERIAL", "NETWORK") and dtype not in ("network", "cloud"):
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


@app.route("/api/serial/ports", methods=["GET"])
def list_serial_ports():
    """สแกนค้นหา COM port / Serial port ที่ต่ออยู่กับเครื่องจริง"""
    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
        res = [{"port": p.device, "description": p.description} for p in ports]
        return jsonify({"success": True, "ports": res})
    except Exception as e:
        return jsonify({"success": False, "ports": [], "error": str(e)})


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

    # ค้นหา dev ใน inventory โดยรองรับทั้ง ID และ Name
    dev = get_device_by_id(device_id)
    actual_id = dev.get("id", device_id) if dev else device_id

    # ตรวจสอบการเชื่อมต่อ หรือ auto-connect สำหรับ live router
    target_id = None
    if conn_mgr.is_connected(actual_id):
        target_id = actual_id
    elif conn_mgr.is_connected(device_id):
        target_id = device_id
    elif dev and (dev.get("device_type_label") or "").lower() not in ("pc", "network"):
        c_res = conn_mgr.connect(actual_id, dev, skip_ping=True)
        if c_res.get("success"):
            target_id = actual_id

    if target_id:
        result = conn_mgr.send_command(target_id, "show ip interface brief", use_textfsm=True)
        parsed = parse_ip_interface_brief(result.get("output", ""))
        if parsed:
            _interface_cache[device_id] = {"data": parsed, "ts": now}
            _interface_cache[actual_id] = {"data": parsed, "ts": now}
            return parsed

    return _interface_cache.get(device_id, {}).get("data", [])


def _invalidate_interface_cache(device_id: str):
    """ล้าง cache เมื่อมีการเปลี่ยน config interface"""
    _interface_cache.pop(device_id, None)
    dev = get_device_by_id(device_id)
    if dev:
        _interface_cache.pop(dev.get("id", ""), None)
        _interface_cache.pop(dev.get("name", ""), None)


# ===========================================================================
# Routes — Interface Configuration
# ===========================================================================
@app.route("/api/devices/<device_id>/interfaces", methods=["GET"])
def list_device_interfaces(device_id: str):
    force = request.args.get("force", "").lower() in ("1", "true", "yes")
    ifaces = _interfaces_for_device(device_id, force_refresh=force)
    if not ifaces:
        dev = get_device_by_id(device_id)
        if dev and dev.get("interfaces"):
            ifaces = dev["interfaces"]
        elif not dev and device_id in DEMO_DEVICES:
            demo_dev = DEMO_DEVICES[device_id]
            ifaces = [
                {
                    "name": k,
                    "ip": v.get("ip", "unassigned"),
                    "mask": v.get("mask", ""),
                    "status": v.get("status", "down"),
                    "description": v.get("description"),
                }
                for k, v in demo_dev.get("interfaces", {}).items()
            ]
    return jsonify({"success": True, "device_id": device_id, "interfaces": ifaces})


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
    dev = get_device_by_id(device_id)
    target_id = dev.get("id", device_id) if dev else device_id

    if not conn_mgr.is_connected(target_id) and not conn_mgr.is_connected(device_id):
        if dev and (dev.get("device_type_label") or "").lower() not in ("pc", "network"):
            conn_mgr.connect(target_id, dev, skip_ping=True)

    active_id = target_id if conn_mgr.is_connected(target_id) else (device_id if conn_mgr.is_connected(device_id) else None)
    if active_id:
        result = conn_mgr.send_config(active_id, cmds)
        verify = conn_mgr.send_command(active_id, f"show interfaces {interface}")
        current = parse_interface_status(verify.get("output", ""), interface)
        result["current_status"] = current
    else:
        result = {"success": False, "message": "Device not connected. Please connect first."}
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

    # Validate IP ถ้ามี (ยกเว้นโหมด DHCP หรือ No IP Address)
    ip_clean = (ip or "").lower().strip()
    is_no_ip = ip_clean in ("no", "no ip", "no ip address", "no ip add", "none", "unassigned", "disable")
    is_dhcp = (ip_clean == "dhcp")

    if ip and not is_dhcp and not is_no_ip:
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

    dev = get_device_by_id(dev_id)
    target_id = dev.get("id", dev_id) if dev else dev_id

    if not conn_mgr.is_connected(target_id) and not conn_mgr.is_connected(dev_id):
        if dev and (dev.get("device_type_label") or "").lower() not in ("pc", "network"):
            conn_mgr.connect(target_id, dev, skip_ping=True)

    active_id = target_id if conn_mgr.is_connected(target_id) else (dev_id if conn_mgr.is_connected(dev_id) else None)
    if active_id:
        result = conn_mgr.send_config(active_id, cmds)
    else:
        result = {"success": False, "message": "Device not connected. Please connect first."}

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

    dev = get_device_by_id(device_id)
    target_id = dev.get("id", device_id) if dev else device_id

    if not conn_mgr.is_connected(target_id) and not conn_mgr.is_connected(device_id):
        if dev and (dev.get("device_type_label") or "").lower() not in ("pc", "network"):
            conn_mgr.connect(target_id, dev, skip_ping=True)

    active_id = target_id if conn_mgr.is_connected(target_id) else (device_id if conn_mgr.is_connected(device_id) else None)
    if active_id:
        result = conn_mgr.send_config(active_id, cmds)
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

    dev = get_device_by_id(device_id)
    target_id = dev.get("id", device_id) if dev else device_id

    if not conn_mgr.is_connected(target_id) and not conn_mgr.is_connected(device_id):
        if dev and (dev.get("device_type_label") or "").lower() not in ("pc", "network"):
            conn_mgr.connect(target_id, dev, skip_ping=True)

    active_id = target_id if conn_mgr.is_connected(target_id) else (device_id if conn_mgr.is_connected(device_id) else None)
    if active_id:
        result = conn_mgr.send_command(active_id, command)
        output = result.get("output", "")
    else:
        return jsonify({"success": False, "message": "Device not connected. Please connect first."})

    return jsonify({"success": True, "device_id": device_id, "command": command, "output": output})


# ===========================================================================
# Routes — CLI Terminal
# ===========================================================================
def _clean_cli_config_output(output: str, cmds: list) -> str:
    """กรอง Netmiko session wrapper lines (เช่น configure terminal, prompts, command echoes, end) 
    เพื่อให้เหลือเฉพาะข้อความตอบกลับหรือ Error จริงของ Cisco IOS เหมือนหน้าจอ Router ปกติ"""
    if not output:
        return ""
    lines = output.splitlines()
    cleaned = []
    ignore_cmds = [c.lower().strip() for c in cmds if c] + ["end", "exit", "configure terminal", "conf t", "config t"]
    
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if "Enter configuration commands" in s:
            continue
        # ตัด Router prompt prefix ออกก่อนตรวจ เช่น Router#, Router(config)#, Router(config-if)#
        unprompted = re.sub(r"^[A-Za-z0-9_\-\.\(\)]+[#>]\s*", "", s).strip()
        if not unprompted:
            continue
        # เช็คว่าเป็น command echo หรือ wrapper command หรือไม่
        if any(unprompted.lower() == c or unprompted.lower().startswith(c) for c in ignore_cmds):
            continue
        cleaned.append(unprompted)
    return "\n".join(cleaned).strip()



@app.route("/api/cli/execute", methods=["POST"])
def execute_cli():
    """รัน CLI command (ส่งไปยัง session ของ Router/Switch โดยตรง พร้อมดึง real prompt)"""
    data = request.json or {}
    device_id = data.get("device_id", "R1")
    raw_command = data.get("command", "")
    if raw_command is None:
        raw_command = ""

    command = normalize(raw_command) if raw_command else ""

    dev = get_device_by_id(device_id)
    target_id = dev.get("id", device_id) if dev else device_id

    conn_err = None
    active_id = target_id if conn_mgr.is_connected(target_id, check_alive=True) else (device_id if conn_mgr.is_connected(device_id, check_alive=True) else None)
    if not active_id:
        if dev and (dev.get("device_type_label") or "").lower() not in ("pc", "network"):
            c_res = conn_mgr.connect(target_id, dev, skip_ping=True)
            if c_res.get("success"):
                active_id = target_id
            else:
                conn_err = c_res.get("message", "เชื่อมต่อล้มเหลว")

    if active_id:
        res = conn_mgr.send_interactive(active_id, raw_command)
        output = res.get("output", "")
        prompt = res.get("prompt", "")
        is_password = res.get("is_password", False)
        return jsonify({
            "success": res.get("success", False),
            "device_id": device_id,
            "command": command or raw_command,
            "output": output,
            "prompt": prompt,
            "is_password": is_password,
            "message": output if not res.get("success") else ""
        })
    else:
        err_msg = conn_err or f"Device '{device_id}' ยังไม่ได้เชื่อมต่อ กรุณากด Connect ก่อนใช้งาน CLI"
        if "PermissionError" in err_msg or "Access is denied" in err_msg:
            err_msg = "ไม่สามารถเปิดพอร์ต COM7 ได้ เนื่องจากพอร์ตถูกใช้งานโดยโปรแกรมอื่น (เช่น Tera Term) — กรุณาปิด Tera Term ก่อนใช้งาน"
        return jsonify({"success": False, "message": err_msg})


@app.route("/api/cli/reconnect", methods=["POST"])
def cli_reconnect():
    """บังคับ Reconnect session สำหรับ CLI Terminal"""
    data = request.json or {}
    device_id = data.get("device_id", "R1")
    dev = get_device_by_id(device_id)
    target_id = dev.get("id", device_id) if dev else device_id
    conn_mgr.disconnect(target_id)
    conn_mgr.disconnect(device_id)
    if dev:
        res = conn_mgr.connect(target_id, dev, skip_ping=True)
        if res.get("success"):
            p_res = conn_mgr.send_interactive(target_id, "")
            return jsonify({
                "success": True,
                "device_id": device_id,
                "message": f"เชื่อมต่อกับ {device_id} สำเร็จแล้ว",
                "prompt": p_res.get("prompt", "")
            })
        return jsonify({"success": False, "message": res.get("message", "Reconnect ล้มเหลว")})
    return jsonify({"success": False, "message": f"ไม่พบ device '{device_id}'"})


@app.route("/api/connections/keepalive", methods=["POST"])
def connections_keepalive():
    """ส่ง Telnet/SSH keepalive NOP เพื่อรักษา connection กับ Switch/Router ไม่ให้ idle timeout"""
    data = request.json or {}
    device_id = data.get("device_id")
    conn_mgr.send_keepalive(device_id)
    return jsonify({"success": True, "connected": conn_mgr.get_connected_devices()})


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
    if mask:
        valid, msg = validate_subnet_mask(mask)
        if not valid:
            return jsonify({"success": False, "message": msg}), 400
    if gateway:
        valid, msg = ip_is_valid(gateway)
        if not valid:
            return jsonify({"success": False, "message": f"Gateway IP ไม่ถูกต้อง: {msg}"}), 400
    devices = load_inventory()
    for d in devices:
        if d.get("id") == device_id:
            d["ip"] = ip
            d["mask"] = mask
            d["gateway"] = gateway
            break
    save_inventory(devices)
    if device_id in DEMO_DEVICES:
        DEMO_DEVICES[device_id]["ip"] = ip
        DEMO_DEVICES[device_id]["mask"] = mask
        DEMO_DEVICES[device_id]["gateway"] = gateway
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


import os, json

_topology_cache = None

def _load_topology_cache():
    global _topology_cache
    if _topology_cache is None:
        try:
            if os.path.exists("topology_cache.json"):
                with open("topology_cache.json", "r", encoding="utf-8") as f:
                    _topology_cache = json.load(f)
        except Exception:
            _topology_cache = None
    return _topology_cache

def _save_topology_cache(data):
    global _topology_cache
    _topology_cache = data
    try:
        with open("topology_cache.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


@app.route("/api/eveng/labs", methods=["GET", "POST"])
def list_eveng_labs():
    """ดึงรายชื่อ Labs ทั้งหมดจาก EVE-NG เพื่อให้ผู้ใช้เลือกได้สะดวก"""
    data = request.json if request.is_json else {}
    host = (request.args.get("host") or data.get("host", "")).strip()
    username = request.args.get("username") or data.get("username", "admin")
    password = request.args.get("password") or data.get("password", "eve")

    if not host:
        inv = load_inventory()
        for d in inv:
            if d.get("ip") and d.get("ip") not in ("127.0.0.1", "localhost"):
                host = d.get("ip")
                break
    if not host:
        return jsonify({"success": False, "message": "กรุณาระบุ EVE-NG Host"}), 400

    try:
        from eve_ng_client import EveNgClient
        client = EveNgClient(host, username, password)
        folders = client.session.get(f"{client.base_url}/folders/", timeout=5).json()
        labs = folders.get("data", {}).get("labs", [])
        return jsonify({"success": True, "host": host, "labs": labs})
    except Exception as e:
        return jsonify({"success": False, "message": f"ไม่สามารถดึงรายชื่อ Labs จาก EVE-NG: {e}"}), 502


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

        # บันทึก Topology ลงใน Cache ทันที เพื่อไม่ให้หายเวลา Refresh หน้าจอ
        _save_topology_cache(graph)

        # เพิ่ม Nodes จาก EVE-NG ลงใน Inventory เพื่อให้เลือกและกดใช้งานได้ทันที
        inv = load_inventory()
        existing_names = {d.get("name", "").lower(): d for d in inv}
        existing_ids = {d.get("id", "").lower(): d for d in inv}

        nodes_data_map = nodes_raw.get("data", {}) if isinstance(nodes_raw, dict) else {}
        clean_host = host.replace("http://", "").replace("https://", "").split("/")[0]

        for n in graph.get("nodes", []):
            nid = str(n.get("node_id") or n.get("id"))
            name = n.get("name", f"Node-{nid}")
            dtype = n.get("type", "router")
            
            # ข้ามการเพิ่ม network nodes (cloud/bridge) เข้า inventory — ไม่ใช่ device
            if dtype == "network":
                continue
            
            # ดึง port telnet console จาก EVE-NG node metadata
            raw_node_info = nodes_data_map.get(nid)
            if not raw_node_info:
                for _, info in nodes_data_map.items():
                    if isinstance(info, dict) and (str(info.get("id")) == nid or info.get("name") == name):
                        raw_node_info = info
                        break

            console_port = 23
            if isinstance(raw_node_info, dict):
                console_port = int(raw_node_info.get("port") or (raw_node_info.get("url", "").split(":")[-1] if ":" in raw_node_info.get("url", "") else 23))

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
    force_refresh = request.args.get("refresh", "").lower() in ("1", "true", "yes")
    inv = ensure_inventory_initialized()
    if not inv:
        return jsonify({"success": True, "demo": True, **DEMO_GRAPH_JSON})

    connected_ids = [d["id"] for d in conn_mgr.get_connected_devices()]

    cached = _load_topology_cache()
    if cached and not force_refresh and cached.get("nodes") and cached.get("edges"):
        # อัปเดตสถานะ connected ของแต่ละ node ใน cache ให้ตรงกับความเป็นจริง
        for node in cached.get("nodes", []):
            nid = node.get("id")
            if node.get("type") not in ("network", "cloud"):
                node["status"] = "connected" if conn_mgr.is_connected(nid) else "discovered"
        return jsonify({"success": True, "cached": True, **cached})

    topo = None
    if NX_AVAILABLE and connected_ids:
        print(f"[Topology] Running auto-discovery for {len(connected_ids)} connected device(s): {connected_ids}")
        G = build_topology_graph(conn_mgr, connected_ids, inv)
        topo = graph_to_json(G, inv)
    else:
        # ถ้ายังไม่มี connected devices ลอง auto-discover จาก EVE-NG host ใน inventory
        try:
            from eve_ng_client import auto_discover_eveng
            for dev in inv:
                ip = dev.get("ip", "")
                if ip and ip not in ("127.0.0.1", "localhost"):
                    eve_topo = auto_discover_eveng(ip, "admin", "eve", inv)
                    if eve_topo and eve_topo.get("nodes") and eve_topo.get("edges"):
                        topo = eve_topo
                        break
        except Exception as e:
            print(f"[Topology] EVE-NG auto-discovery check skipped: {e}")

    if not topo or not topo.get("nodes"):
        if cached and cached.get("nodes"):
            topo = cached
        else:
            topo = {
                "nodes": [{"id": d["id"], "name": d.get("name", d["id"]),
                            "type": d.get("device_type_label", "router"),
                            "ip": d.get("ip", ""), "model": d.get("model", ""),
                            "status": "connected" if conn_mgr.is_connected(d["id"]) else "disconnected"}
                          for d in inv],
                "edges": []
            }

    # อัปเดตสถานะ connected
    for node in topo.get("nodes", []):
        nid = node.get("id")
        if node.get("type") not in ("network", "cloud"):
            node["status"] = "connected" if conn_mgr.is_connected(nid) else "discovered"

    _save_topology_cache(topo)
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
