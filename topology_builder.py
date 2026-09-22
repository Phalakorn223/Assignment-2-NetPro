"""
topology_builder.py — Auto-Discovery และ Topology graph builder
อ้างอิง: spec section 6.4, 3.6
ใช้ networkx สร้าง graph และ CDP/LLDP parsing ผ่าน netmiko use_textfsm=True
"""

import json
import re
from typing import Any

try:
    import networkx as nx
    NX_AVAILABLE = True
except ImportError:
    NX_AVAILABLE = False


# ---------------------------------------------------------------------------
# CDP / LLDP Discovery (วิธีที่ 1 จาก spec)
# ---------------------------------------------------------------------------
def discover_neighbors_cdp(conn_manager, device_id: str) -> list:
    """
    ใช้ 'show cdp neighbors detail' ด้วย use_textfsm=True เพื่อ parse เป็น list of dict
    คืน list เช่น:
    [{"destination_host": "SW1", "local_port": "Gi0/0", "remote_port": "Gi0/1", "management_ip": "..."}]
    """
    result = conn_manager.send_command(device_id, "show cdp neighbors detail", use_textfsm=True)
    if not result.get("success"):
        return []
    output = result.get("output", "")
    # ถ้า TextFSM parse ได้ จะเป็น list of dict โดยตรง
    if isinstance(output, list):
        return output
    # ถ้าได้ string (TextFSM ไม่ทำงาน) ให้ parse เอง
    return _parse_cdp_raw(output)


def discover_neighbors_lldp(conn_manager, device_id: str) -> list:
    """Fallback: ใช้ 'show lldp neighbors detail' ถ้า CDP ไม่มี"""
    result = conn_manager.send_command(device_id, "show lldp neighbors detail", use_textfsm=True)
    if not result.get("success"):
        return []
    output = result.get("output", "")
    if isinstance(output, list):
        return output
    return []


def _parse_cdp_raw(raw_output: str) -> list:
    """
    Parse raw 'show cdp neighbors detail' output ถ้า TextFSM ไม่ available
    """
    neighbors = []
    current = {}
    for line in raw_output.splitlines():
        line = line.strip()
        m = re.match(r"Device ID:\s*(\S+)", line, re.IGNORECASE)
        if m:
            if current:
                neighbors.append(current)
            current = {"destination_host": m.group(1).split(".")[0], "local_port": "", "remote_port": "", "management_ip": ""}
        m = re.match(r"IP address:\s*([\d.]+)", line, re.IGNORECASE)
        if m and current:
            current["management_ip"] = m.group(1)
        m = re.match(r"Interface:\s*([^,]+),\s*Port ID.*:\s*(\S+)", line, re.IGNORECASE)
        if m and current:
            current["local_port"] = m.group(1).strip()
            current["remote_port"] = m.group(2).strip()
    if current:
        neighbors.append(current)
    return neighbors


# ---------------------------------------------------------------------------
# Topology Graph Builder (spec section 6.4)
# ---------------------------------------------------------------------------
def build_topology_graph(conn_manager, device_ids: list, inventory_devices: list) -> Any:
    """
    สร้าง networkx Graph จากการ query CDP ทุก device ที่ connect อยู่
    device_ids: list ของ device_id ที่ต้องการ scan
    inventory_devices: รายการข้อมูล device ทั้งหมด (สำหรับ enrichment)
    """
    if not NX_AVAILABLE:
        return None

    G = nx.Graph()

    # เพิ่ม nodes จาก inventory ทั้งหมดก่อน
    for dev in inventory_devices:
        dev_id = dev.get("id", "")
        G.add_node(dev_id, **{
            "name": dev.get("name", dev_id),
            "type": dev.get("device_type_label", "router"),
            "ip": dev.get("ip", ""),
            "model": dev.get("model", "Cisco IOS"),
            "status": "connected" if conn_manager.is_connected(dev_id) else "disconnected",
        })

    # CDP Discovery สำหรับ device ที่ connect อยู่
    for device_id in device_ids:
        if not conn_manager.is_connected(device_id):
            continue

        # ลอง CDP ก่อน แล้ว fallback LLDP
        neighbors = discover_neighbors_cdp(conn_manager, device_id)
        if not neighbors:
            neighbors = discover_neighbors_lldp(conn_manager, device_id)

        for n in neighbors:
            remote_id = n.get("destination_host", "")
            local_port = n.get("local_port", "")
            remote_port = n.get("remote_port", "")
            remote_ip = n.get("management_ip", "")

            if not remote_id:
                continue

            # เพิ่ม node ถ้ายังไม่มี
            if remote_id not in G:
                G.add_node(remote_id, name=remote_id, type="unknown", ip=remote_ip, model="", status="discovered")

            # เพิ่ม edge ถ้ายังไม่มี
            if not G.has_edge(device_id, remote_id):
                G.add_edge(device_id, remote_id,
                           local_port=local_port,
                           remote_port=remote_port,
                           status="up")

    # Fallback: Subnet-matching (spec วิธีที่ 2) ถ้าไม่มี edge ใด ๆ
    if G.number_of_edges() == 0:
        G = _subnet_matching_fallback(G, conn_manager, device_ids)

    return G


def _subnet_matching_fallback(G, conn_manager, device_ids: list):
    """
    Fallback: เปรียบเทียบ subnet ของ interface แต่ละตัว
    ถ้า 2 device มี interface ที่ IP อยู่ subnet เดียวกัน → สร้าง edge
    """
    device_interfaces = {}

    for device_id in device_ids:
        if not conn_manager.is_connected(device_id):
            continue
        result = conn_manager.send_command(device_id, "show ip interface brief", use_textfsm=True)
        if result.get("success"):
            output = result.get("output", "")
            # Parse list of (ip, interface_name)
            iface_list = _parse_ip_int_brief(output)
            device_interfaces[device_id] = iface_list

    # เปรียบเทียบ subnet
    added = set()
    dev_list = list(device_interfaces.keys())
    for i, dev_a in enumerate(dev_list):
        for dev_b in dev_list[i+1:]:
            pair_key = tuple(sorted([dev_a, dev_b]))
            if pair_key in added:
                continue
            # ตรวจว่ามี IP ที่ subnet ตรงกัน
            for ip_a, if_a in device_interfaces[dev_a]:
                for ip_b, if_b in device_interfaces[dev_b]:
                    if _same_subnet(ip_a, ip_b):
                        G.add_edge(dev_a, dev_b,
                                   local_port=if_a,
                                   remote_port=if_b,
                                   status="up",
                                   method="subnet_match")
                        added.add(pair_key)
                        break
    return G


def _parse_ip_int_brief(output) -> list:
    """Parse output ของ 'show ip interface brief' เป็น list of (ip, interface_name)"""
    result = []
    if isinstance(output, list):
        for row in output:
            ip = row.get("ipaddr", row.get("ip_address", ""))
            intf = row.get("intf", row.get("interface", ""))
            if ip and ip not in ("unassigned", "-"):
                result.append((ip, intf))
    elif isinstance(output, str):
        for line in output.splitlines():
            parts = line.split()
            if len(parts) >= 2 and re.match(r"\d+\.\d+\.\d+\.\d+", parts[1]):
                result.append((parts[1], parts[0]))
    return result


def _same_subnet(ip_a: str, ip_b: str, prefix: int = 24) -> bool:
    """ตรวจว่า IP 2 ตัวอยู่ /24 subnet เดียวกัน"""
    try:
        parts_a = ip_a.split(".")
        parts_b = ip_b.split(".")
        return parts_a[:3] == parts_b[:3]  # /24 comparison
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Graph → JSON Export (ตาม spec format)
# ---------------------------------------------------------------------------
def graph_to_json(G, inventory_devices: list = None) -> dict:
    """
    แปลง networkx graph เป็น JSON ตามรูปแบบที่ spec กำหนด:
    {"nodes": [...], "edges": [...]}
    """
    if G is None:
        return {"nodes": [], "edges": []}

    inv_map = {}
    if inventory_devices:
        for dev in inventory_devices:
            inv_map[dev.get("id", "")] = dev

    nodes = []
    for node_id, attrs in G.nodes(data=True):
        inv_dev = inv_map.get(node_id, {})
        nodes.append({
            "id": node_id,
            "name": attrs.get("name", node_id),
            "type": attrs.get("type", inv_dev.get("device_type_label", "router")),
            "ip": attrs.get("ip", inv_dev.get("ip", "")),
            "model": attrs.get("model", inv_dev.get("model", "")),
            "status": attrs.get("status", "unknown"),
        })

    edges = []
    for u, v, data in G.edges(data=True):
        edges.append({
            "from": u,
            "to": v,
            "from_port": data.get("local_port", ""),
            "to_port": data.get("remote_port", ""),
            "status": data.get("status", "up"),
            "method": data.get("method", "cdp"),
        })

    return {"nodes": nodes, "edges": edges}


# ---------------------------------------------------------------------------
# Simulated fallback data (ใช้เมื่อยังไม่มี device จริง)
# ---------------------------------------------------------------------------
DEMO_GRAPH_JSON = {
    "nodes": [
        {"id": "R1", "name": "Router-R1", "type": "router", "ip": "192.168.1.116", "model": "Cisco 4331", "status": "connected"},
        {"id": "R2", "name": "Router-R2", "type": "router", "ip": "192.168.1.125", "model": "Cisco 4331", "status": "connected"},
        {"id": "SW1", "name": "Switch-SW1", "type": "switch", "ip": "192.168.1.117", "model": "Cisco Catalyst 2960", "status": "connected"},
    ],
    "edges": [
        {"from": "R1", "to": "R2",  "from_port": "GigabitEthernet0/0/1", "to_port": "GigabitEthernet0/0/1", "status": "up", "method": "demo"},
        {"from": "R1", "to": "R2",  "from_port": "Serial0/1/0",          "to_port": "Serial0/1/0",          "status": "up", "method": "demo"},
        {"from": "R1", "to": "SW1", "from_port": "GigabitEthernet0/0/0", "to_port": "GigabitEthernet0/1",   "status": "up", "method": "demo"},
    ]
}
