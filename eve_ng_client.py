"""
eve_ng_client.py — REST client สำหรับดึง topology / nodes จาก EVE-NG (ทางเลือก)
"""

from typing import Any, Optional

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class EveNgClient:
    def __init__(self, host: str, username: str, password: str):
        if not REQUESTS_AVAILABLE:
            raise RuntimeError("ต้องติดตั้ง requests (pip install requests)")
        clean_host = host.strip().rstrip('/')
        if clean_host.endswith("/api"):
            clean_host = clean_host[:-4].rstrip('/')
        if not clean_host.startswith("http://") and not clean_host.startswith("https://"):
            self.schemes = ["http", "https"]
        else:
            self.schemes = [clean_host.split("://")[0]]
            clean_host = clean_host.split("://")[1]
        if clean_host.endswith("/api"):
            clean_host = clean_host[:-4].rstrip('/')

        self.session = requests.Session()
        self.session.verify = False
        self.base_url = ""
        self._login(clean_host, username, password)

    def _login(self, clean_host: str, username: str, password: str):
        last_err = None
        for scheme in self.schemes:
            url = f"{scheme}://{clean_host}/api"
            try:
                resp = self.session.post(
                    f"{url}/auth/login",
                    json={"username": username, "password": password, "html5": "-1"},
                    timeout=10,
                )
                if resp.status_code == 200:
                    self.base_url = url
                    return
                resp.raise_for_status()
            except Exception as e:
                last_err = e
        if last_err:
            raise last_err

    def list_labs(self) -> Any:
        resp = self.session.get(f"{self.base_url}/labs", timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_topology(self, lab_path: str) -> Any:
        path = lab_path.strip("/")
        resp = self.session.get(f"{self.base_url}/labs/{path}/topology", timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_nodes(self, lab_path: str) -> Any:
        path = lab_path.strip("/")
        resp = self.session.get(f"{self.base_url}/labs/{path}/nodes", timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_networks(self, lab_path: str) -> Any:
        """ดึงข้อมูล networks (cloud/bridge) จาก EVE-NG lab"""
        path = lab_path.strip("/")
        resp = self.session.get(f"{self.base_url}/labs/{path}/networks", timeout=15)
        resp.raise_for_status()
        return resp.json()


def eveng_topology_to_graph(topology_data: dict, nodes_data: dict, networks_data: dict = None, inventory_devices: list = None, live_interfaces: dict = None) -> dict:
    """
    แปลง response จาก EVE-NG เป็น {nodes, edges} แบบ vis-network
    รองรับรูปแบบ JSON ทั้งแบบ dict และ list ตามเวอร์ชัน EVE-NG
    จับคู่ node กับ inventory device name (เช่น R1, R2, R3)
    กรอง internal bridge networks (visibility 0) ออก และ enrich ด้วย interface IP จริง
    """
    nodes_out = []
    edges_out = []

    # Map inventory devices by id/name for fallback
    inv_map = {}
    if inventory_devices:
        for d in inventory_devices:
            inv_map[d.get("id", "")] = d
            inv_map[d.get("name", "")] = d

    # --- Parse device nodes ---
    raw_nodes = nodes_data.get("data") if isinstance(nodes_data, dict) else nodes_data
    if isinstance(raw_nodes, dict):
        raw_nodes = raw_nodes.values()

    node_id_to_name = {}
    if raw_nodes:
        for n in raw_nodes:
            if not isinstance(n, dict):
                continue
            nid = str(n.get("id", n.get("node_id", "")))
            name = n.get("name") or n.get("label") or nid
            node_id_to_name[nid] = name
            node_id_to_name[f"node{nid}"] = name

            ntype = (n.get("type") or n.get("template") or "router").lower()
            if "switch" in ntype:
                dtype = "switch"
            elif "pc" in ntype or "host" in ntype:
                dtype = "pc"
            else:
                dtype = "router"

            # หา IP จริงของ device จาก live_interfaces
            dev_ip = ""
            if live_interfaces and name in live_interfaces:
                for iface in live_interfaces[name]:
                    if iface.get("ip") and iface["ip"] not in ("unassigned", "-"):
                        dev_ip = iface["ip"]
                        break
            if not dev_ip and name in inv_map:
                dev_ip = inv_map[name].get("ip", "")

            nodes_out.append({
                "id": name,
                "name": name,
                "type": dtype,
                "ip": dev_ip,
                "model": n.get("image", ""),
                "status": "connected" if dev_ip else "discovered",
            })

    # --- Parse network objects (cloud/bridge) ---
    net_id_to_name = {}
    if networks_data:
        raw_nets = networks_data.get("data") if isinstance(networks_data, dict) else networks_data
        if isinstance(raw_nets, dict):
            raw_nets = raw_nets.values()
        if raw_nets:
            for net in raw_nets:
                if not isinstance(net, dict):
                    continue
                # ข้าม internal bridge network ที่ visibility == '0'
                if str(net.get("visibility", "1")) == "0":
                    continue

                net_id = str(net.get("id", ""))
                net_name = net.get("name") or net.get("label") or f"Net-{net_id}"
                net_id_to_name[net_id] = net_name
                net_id_to_name[f"network{net_id}"] = net_name
                nodes_out.append({
                    "id": net_name,
                    "name": net_name,
                    "type": "network",
                    "ip": "192.168.74.0/24",
                    "model": "cloud",
                    "status": "discovered",
                })

    # --- Parse topology links ---
    raw_topo = topology_data.get("data") if isinstance(topology_data, dict) else topology_data
    links = raw_topo.values() if isinstance(raw_topo, dict) else (raw_topo if isinstance(raw_topo, list) else [])

    def normalize_port(port_str):
        if not port_str:
            return ""
        p = port_str.strip()
        m = re.match(r"^e(\d+/\d+)$", p, re.IGNORECASE)
        if m:
            return f"Ethernet{m.group(1)}"
        return p

    def find_iface_ip(dev_name, port_name):
        if not live_interfaces or dev_name not in live_interfaces:
            return ""
        norm_p = normalize_port(port_name).lower()
        for iface in live_interfaces[dev_name]:
            if normalize_port(iface.get("name", "")).lower() == norm_p:
                return iface.get("ip", "")
        return ""

    import re
    for link in links:
        if not isinstance(link, dict):
            continue
        src = str(link.get("source", link.get("left", "")))
        dst = str(link.get("destination", link.get("right", "")))
        src_type = link.get("source_type", "node")
        dst_type = link.get("destination_type", "node")

        if not src or not dst:
            continue

        from_id = node_id_to_name.get(src, src) if src_type == "node" else net_id_to_name.get(src, src)
        to_id = node_id_to_name.get(dst, dst) if dst_type == "node" else net_id_to_name.get(dst, dst)

        src_port = normalize_port(link.get("source_label", ""))
        dst_port = normalize_port(link.get("destination_label", ""))

        from_ip = find_iface_ip(from_id, src_port)
        to_ip = find_iface_ip(to_id, dst_port)

        edge = {
            "from": from_id,
            "to": to_id,
            "from_port": src_port,
            "to_port": dst_port,
            "status": "up",
            "method": "eveng",
        }
        if from_ip:
            edge["from_ip"] = from_ip
        if to_ip:
            edge["to_ip"] = to_ip
        edges_out.append(edge)

    return {"nodes": nodes_out, "edges": edges_out}


def auto_discover_eveng(host: str, username: str = "admin", password: str = "eve", inventory_devices: list = None, live_interfaces: dict = None) -> Optional[dict]:
    """
    พยายามเชื่อมต่อ EVE-NG API อัตโนมัติ เพื่อดึง topology ที่ถูกต้องที่สุด
    """
    if not REQUESTS_AVAILABLE:
        return None
    try:
        client = EveNgClient(host, username, password)
        folders = client.session.get(f"{client.base_url}/folders/", timeout=4).json()
        labs = folders.get("data", {}).get("labs", [])
        if not labs:
            return None
        lab_file = labs[0]["file"]
        nodes_data = client.get_nodes(lab_file)
        nets_data = client.get_networks(lab_file)
        topo_data = client.get_topology(lab_file)
        return eveng_topology_to_graph(topo_data, nodes_data, nets_data, inventory_devices, live_interfaces)
    except Exception as e:
        print(f"[EVE-NG Auto-Discovery] Skipped or failed ({e})")
        return None
