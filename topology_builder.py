"""
topology_builder.py — Auto-Discovery และ Topology graph builder
อ้างอิง: spec section 6.4, 3.6
ใช้ networkx สร้าง graph และ CDP/LLDP parsing ผ่าน netmiko use_textfsm=True

Enhanced: ดึง IP จริงจากอุปกรณ์ที่เชื่อมต่อ เพื่อ subnet-matching ที่แม่นยำ
"""

import json
import re
import struct
import socket
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
# Collect Real Interface Data (ดึง IP จริงจากอุปกรณ์ที่ connect อยู่)
# ---------------------------------------------------------------------------
def collect_device_interfaces(conn_manager, device_id: str) -> list:
    """
    ดึง interface list จริงจากอุปกรณ์ที่เชื่อมต่ออยู่
    คืน list of dict: [{"name": "Gi0/0", "ip": "10.1.1.1", "mask": "255.255.255.252", "status": "up"}, ...]
    """
    if not conn_manager.is_connected(device_id):
        return []

    # ลอง show ip interface brief + show ip interface ก่อน เพื่อดึง mask ด้วย
    result = conn_manager.send_command(device_id, "show ip interface brief")
    if not result.get("success"):
        return []

    output = result.get("output", "")
    brief_entries = _parse_ip_int_brief(output)

    # ดึง mask จาก show ip interface (เพื่อให้ subnet matching แม่นยำกว่า /24 เดา)
    mask_result = conn_manager.send_command(device_id, "show ip interface")
    mask_map = {}
    if mask_result.get("success"):
        mask_map = _parse_ip_interface_masks(mask_result.get("output", ""))

    enriched = []
    for ip, if_name, status in brief_entries:
        mask = mask_map.get(if_name, "255.255.255.0")
        enriched.append({
            "name": if_name,
            "ip": ip,
            "mask": mask,
            "status": status,
        })
    return enriched


def _parse_ip_interface_masks(raw_output: str) -> dict:
    """
    Parse 'show ip interface' output เพื่อดึง subnet mask ของแต่ละ interface
    คืน dict: {"GigabitEthernet0/0": "255.255.255.252", ...}
    """
    result = {}
    current_intf = ""
    for line in raw_output.splitlines():
        # ตรวจจับชื่อ interface (บรรทัดที่ไม่มี leading space)
        m = re.match(r"^(\S+)\s+is\s+", line)
        if m:
            current_intf = m.group(1)
            continue
        # ตรวจจับ "Internet address is x.x.x.x/prefix"
        m = re.search(r"Internet address is ([\d.]+)/(\d+)", line.strip())
        if m and current_intf:
            prefix_len = int(m.group(2))
            mask = _prefix_to_mask(prefix_len)
            result[current_intf] = mask
            continue
        # ตรวจจับ "address is x.x.x.x, subnet mask is y.y.y.y"
        m = re.search(r"address is [\d.]+,\s*subnet mask is ([\d.]+)", line.strip(), re.IGNORECASE)
        if m and current_intf:
            result[current_intf] = m.group(1)
    return result


def _prefix_to_mask(prefix: int) -> str:
    """แปลง prefix length (เช่น 30) เป็น dotted-decimal mask (255.255.255.252)"""
    mask = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF
    return socket.inet_ntoa(struct.pack(">I", mask))


def _mask_to_prefix(mask: str) -> int:
    """Convert dotted-decimal mask to prefix length"""
    try:
        mask_int = struct.unpack(">I", socket.inet_aton(mask))[0]
        return bin(mask_int).count("1")
    except Exception:
        return 24


def _ip_to_network(ip: str, mask: str) -> str:
    """Calculate network address from IP and mask"""
    try:
        ip_int = struct.unpack(">I", socket.inet_aton(ip))[0]
        mask_int = struct.unpack(">I", socket.inet_aton(mask))[0]
        net_int = ip_int & mask_int
        prefix = bin(mask_int).count("1")
        net_str = socket.inet_ntoa(struct.pack(">I", net_int))
        return f"{net_str}/{prefix}"
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Topology Graph Builder (spec section 6.4) - Enhanced
# ---------------------------------------------------------------------------
def build_topology_graph(conn_manager, device_ids: list, inventory_devices: list) -> Any:
    """
    Build networkx Graph from real interface IP of connected devices.
    Steps:
    1. Collect real interface IPs
    2. Try EVE-NG Auto-Discovery first (if lab exists, gives exact physical wiring)
    3. Standalone fallback: CDP discovery (matched by real router IP)
    4. Subnet-matching: group by network overlap (handles /30 vs /24 mismatch)
       - 2 interfaces in subnet -> Point-to-Point direct link
       - 3+ interfaces in subnet -> Connected to Cloud/Network node ('Net')
    """
    if not NX_AVAILABLE:
        return None

    # เก็บ interface IP จริงจากทุก device ที่ connected
    all_device_interfaces = {}
    primary_ips = {}
    for device_id in device_ids:
        if not conn_manager.is_connected(device_id):
            continue
        ifaces = collect_device_interfaces(conn_manager, device_id)
        if ifaces:
            all_device_interfaces[device_id] = ifaces
            for iface in ifaces:
                ip = iface.get("ip", "")
                if ip and ip not in ("unassigned", "-"):
                    primary_ips[device_id] = ip
                    break

    # ----- ขั้นตอน 1: ลอง EVE-NG Auto-Discovery ก่อน -----
    try:
        from eve_ng_client import auto_discover_eveng
        # หา EVE-NG host จาก inventory
        eve_hosts = set()
        for dev in inventory_devices:
            ip = dev.get("ip", "")
            if ip and ip != "127.0.0.1":
                eve_hosts.add(ip)
        for host in eve_hosts:
            eve_topo = auto_discover_eveng(host, "admin", "eve", inventory_devices, all_device_interfaces)
            if eve_topo and eve_topo.get("nodes") and eve_topo.get("edges"):
                print(f"[Topology] Successfully auto-discovered topology from EVE-NG ({host})!")
                G = nx.MultiGraph()
                for n in eve_topo["nodes"]:
                    G.add_node(n["id"], **n)
                for e in eve_topo["edges"]:
                    G.add_edge(e["from"], e["to"],
                               original_from=e["from"],
                               local_port=e.get("from_port", ""),
                               remote_port=e.get("to_port", ""),
                               local_ip=e.get("from_ip", ""),
                               remote_ip=e.get("to_ip", ""),
                               status=e.get("status", "up"),
                               method="eveng")
                return G
    except Exception as e:
        print(f"[Topology] EVE-NG auto-discovery skipped: {e}")

    # ----- ขั้นตอน 2: Fallback — Standalone Network Discovery -----
    G = nx.MultiGraph()

    # เพิ่ม nodes จาก inventory
    for dev in inventory_devices:
        dev_id = dev.get("id", "")
        real_ip = primary_ips.get(dev_id, dev.get("ip", ""))
        G.add_node(dev_id, **{
            "name": dev.get("name", dev_id),
            "type": dev.get("device_type_label", "router"),
            "ip": real_ip,
            "model": dev.get("model", "Cisco IOS"),
            "status": "connected" if conn_manager.is_connected(dev_id) else "disconnected",
        })

    # CDP Discovery (จับคู่ข้ามเครื่องด้วย IP จริง)
    cdp_edges_found = False
    for device_id in device_ids:
        if not conn_manager.is_connected(device_id):
            continue

        neighbors = discover_neighbors_cdp(conn_manager, device_id)
        if not neighbors:
            neighbors = discover_neighbors_lldp(conn_manager, device_id)

        for n in neighbors:
            remote_host = n.get("destination_host", "")
            local_port = n.get("local_port", "")
            remote_port = n.get("remote_port", "")
            remote_ip = n.get("management_ip", "")

            matched_id = _match_device_by_ip_or_name(remote_host, remote_ip, inventory_devices, all_device_interfaces)
            if not matched_id or matched_id == device_id:
                continue

            target_id = matched_id
            if target_id not in G:
                G.add_node(target_id, name=remote_host, type="router", ip=remote_ip, model="", status="discovered")

            # เช็คว่ามี edge ขานี้อยู่แล้วหรือยัง
            edge_exists = False
            if G.has_edge(device_id, target_id):
                for _, edge_data in G.get_edge_data(device_id, target_id).items():
                    if edge_data.get("local_port") == local_port and edge_data.get("remote_port") == remote_port:
                        edge_exists = True
                        break

            if not edge_exists:
                G.add_edge(device_id, target_id,
                           local_port=local_port,
                           remote_port=remote_port,
                           local_ip=primary_ips.get(device_id, ""),
                           remote_ip=remote_ip,
                           status="up",
                           method="cdp")
                cdp_edges_found = True

    # Subnet-matching (ใช้ Subnet Overlap Clustering)
    if not cdp_edges_found and all_device_interfaces:
        G = _smart_subnet_matching(G, all_device_interfaces, primary_ips)

    return G


def _match_device_by_ip_or_name(hostname: str, mgmt_ip: str, inventory_devices: list, all_device_interfaces: dict) -> str:
    """
    จับคู่ hostname หรือ IP จาก CDP/LLDP กับ device ID ที่ถูกต้อง
    """
    # 1. ลอง match จาก IP กับ interface ทั้งหมดของทุกอุปกรณ์
    if mgmt_ip and all_device_interfaces:
        for dev_id, ifaces in all_device_interfaces.items():
            for iface in ifaces:
                if iface.get("ip") == mgmt_ip:
                    return dev_id

    # 2. ลอง match จาก inventory device IP
    if mgmt_ip and inventory_devices:
        for dev in inventory_devices:
            if dev.get("ip") == mgmt_ip:
                return dev.get("id", "")

    # 3. ลอง match จาก hostname
    if hostname:
        hostname_lower = hostname.lower().strip()
        for dev in inventory_devices:
            dev_id = dev.get("id", "")
            dev_name = dev.get("name", "")
            if dev_id.lower() == hostname_lower or dev_name.lower() == hostname_lower:
                return dev_id

    return ""


def _smart_subnet_matching(G, all_device_interfaces: dict, primary_ips: dict = None):
    """
    Subnet-matching ด้วย IP network overlap clustering:
    - แก้ปัญหา subnet mask mismatch (/30 vs /24)
    - ถ้าใน network เดียวกันมี interface ตรงกันแค่ 2 เครื่อง → จับคู่ Point-to-Point ขาชนขา
    - ถ้ามี 3 เครื่องขึ้นไป (เช่น 192.168.74.0/24) → สร้าง Net node กลาง (Cloud) แล้วเชื่อมทุกเครื่องเข้า Net
    """
    import ipaddress

    flat_ifaces = []
    for dev_id, if_list in all_device_interfaces.items():
        for iface in if_list:
            ip = iface.get("ip")
            mask = iface.get("mask", "255.255.255.0")
            if_name = iface.get("name", "")
            if not ip or ip in ("unassigned", "-", ""):
                continue
            if if_name.lower().startswith("loopback") or if_name.lower().startswith("lo"):
                continue
            try:
                net = ipaddress.IPv4Interface(f"{ip}/{mask}").network
                flat_ifaces.append({
                    "dev": dev_id,
                    "if_name": if_name,
                    "ip": ip,
                    "mask": mask,
                    "network": net,
                })
            except Exception:
                pass

    # จัด Cluster ของ interface ที่ overlap กัน
    clusters = []
    for iface in flat_ifaces:
        matched_cluster = None
        for c in clusters:
            for member in c:
                if iface["network"].overlaps(member["network"]) or \
                   ipaddress.IPv4Address(iface["ip"]) in member["network"] or \
                   ipaddress.IPv4Address(member["ip"]) in iface["network"]:
                    matched_cluster = c
                    break
            if matched_cluster:
                break
        if matched_cluster is not None:
            matched_cluster.append(iface)
        else:
            clusters.append([iface])

    for c in clusters:
        unique_devs = list({m["dev"] for m in c})
        if len(unique_devs) < 2:
            continue

        if len(unique_devs) == 2 and len(c) == 2:
            # Point-to-point link (เช่น e0/1 บน R1 ชนกับ e0/1 บน R2)
            m1 = c[0]
            m2 = c[1]
            G.add_edge(m1["dev"], m2["dev"],
                       local_port=m1["if_name"],
                       remote_port=m2["if_name"],
                       local_ip=m1["ip"],
                       remote_ip=m2["ip"],
                       subnet=str(m1["network"]),
                       status="up",
                       method="subnet_match")
        else:
            # Multi-access segment (เช่น 3+ devices บน 192.168.74.0/24 ต่อเข้า Net)
            net_name = "Net"
            net_ip = str(c[0]["network"])
            if net_name not in G:
                G.add_node(net_name, name=net_name, type="network",
                           ip=net_ip, model="cloud", status="discovered")
            for m in c:
                G.add_edge(m["dev"], net_name,
                           local_port=m["if_name"],
                           remote_port="",
                           local_ip=m["ip"],
                           remote_ip="",
                           subnet=net_ip,
                           status="up",
                           method="subnet_match")

    return G


# ---------------------------------------------------------------------------
# Legacy helpers (ยังคงใช้ใน fallback scenarios)
# ---------------------------------------------------------------------------
def _parse_ip_int_brief(output) -> list:
    """
    Parse output ของ 'show ip interface brief' เป็น list of (ip, interface_name, status)
    รองรับทั้ง TextFSM list of dict และ raw text
    """
    result = []
    if isinstance(output, list):
        for row in output:
            ip = row.get("ipaddr", row.get("ip_address", ""))
            intf = row.get("intf", row.get("interface", ""))
            status_raw = (row.get("status", row.get("admin", "")) or "").lower()
            status = "up" if "up" in status_raw else "down"
            if ip and ip not in ("unassigned", "-"):
                result.append((ip, intf, status))
    elif isinstance(output, str):
        for line in output.splitlines():
            parts = line.split()
            if len(parts) >= 6 and re.match(r"\d+\.\d+\.\d+\.\d+", parts[1]):
                intf = parts[0]
                ip = parts[1]
                # status is typically column 5 (0-indexed 4)
                status = "up" if parts[4].lower() == "up" else "down"
                result.append((ip, intf, status))
    return result


def _same_subnet(ip_a: str, ip_b: str, prefix: int = 24) -> bool:
    """ตรวจว่า IP 2 ตัวอยู่ /24 subnet เดียวกัน"""
    try:
        parts_a = ip_a.split(".")
        parts_b = ip_b.split(".")
        return parts_a[:3] == parts_b[:3]  # /24 comparison
    except Exception:
        return False


def _get_subnet_prefix(ip: str, prefix: int = 24) -> str:
    """คืน subnet prefix (เช่น '192.168.74') จาก IP address"""
    try:
        parts = ip.split(".")
        if len(parts) == 4:
            return ".".join(parts[:3])
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# Graph → JSON Export (ตาม spec format) — Enhanced with IP info on edges
# ---------------------------------------------------------------------------
def graph_to_json(G, inventory_devices: list = None) -> dict:
    """
    แปลง networkx graph เป็น JSON ตามรูปแบบที่ spec กำหนด:
    {"nodes": [...], "edges": [...]}
    Enhanced: เพิ่ม local_ip, remote_ip, subnet ใน edge data
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
        orig_from = data.get("original_from", u)
        from_port = data.get("local_port", "")
        to_port = data.get("remote_port", "")
        from_ip = data.get("local_ip", "")
        to_ip = data.get("remote_ip", "")

        # ถ้า NetworkX สลับทิศทาง u, v ให้สลับ port และ ip ให้ตรงกับ u, v เสมอ
        if orig_from != u:
            from_port, to_port = to_port, from_port
            from_ip, to_ip = to_ip, from_ip

        edge = {
            "from": u,
            "to": v,
            "from_port": from_port,
            "to_port": to_port,
            "status": data.get("status", "up"),
            "method": data.get("method", "cdp"),
        }
        if from_ip:
            edge["from_ip"] = from_ip
        if to_ip:
            edge["to_ip"] = to_ip
        if data.get("subnet"):
            edge["subnet"] = data["subnet"]
        edges.append(edge)

    return {"nodes": nodes, "edges": edges}


# ---------------------------------------------------------------------------
# Simulated fallback data (ใช้เมื่อยังไม่มี device จริง)
# ---------------------------------------------------------------------------
DEMO_GRAPH_JSON = {
    "nodes": [
        {"id": "R1", "name": "Router-R1", "type": "router", "ip": "192.168.1.116", "model": "Cisco 4331", "status": "connected"},
        {"id": "R2", "name": "Router-R2", "type": "router", "ip": "192.168.1.125", "model": "Cisco 4331", "status": "connected"},
        {"id": "SW1", "name": "Switch-SW1", "type": "switch", "ip": "192.168.1.117", "model": "Cisco Catalyst 2960", "status": "connected"},
        {"id": "PC1", "name": "PC-Workstation", "type": "pc", "ip": "192.168.1.10", "model": "Virtual PC", "status": "connected"},
    ],
    "edges": [
        {"from": "R1", "to": "R2",  "from_port": "GigabitEthernet0/0/1", "to_port": "GigabitEthernet0/0/1", "status": "up", "method": "demo"},
        {"from": "R1", "to": "R2",  "from_port": "Serial0/1/0",          "to_port": "Serial0/1/0",          "status": "up", "method": "demo"},
        {"from": "R1", "to": "SW1", "from_port": "GigabitEthernet0/0/0", "to_port": "GigabitEthernet0/1",   "status": "up", "method": "demo"},
        {"from": "SW1", "to": "PC1", "from_port": "FastEthernet0/1",      "to_port": "NIC0",                   "status": "up", "method": "demo"},
    ]
}
