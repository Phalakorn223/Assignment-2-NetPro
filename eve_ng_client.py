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
                    timeout=3,
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

    def normalize_lab_path(self, lab_path: str) -> str:
        raw = (lab_path or "").strip().strip("/")
        if not raw:
            return ""
        # ค้นหา match case-insensitive จากรายการ lab จริงใน EVE-NG
        try:
            folders = self.session.get(f"{self.base_url}/folders/", timeout=5).json()
            labs = folders.get("data", {}).get("labs", [])
            for lab in labs:
                f_name = lab.get("file", "")
                p_name = lab.get("path", "").strip("/")
                clean_f = f_name.replace(".unl", "").lower()
                clean_raw = raw.replace(".unl", "").lower()
                if clean_raw == clean_f or raw.lower() == f_name.lower() or raw.lower() == p_name.lower():
                    return p_name if p_name else f_name
        except Exception:
            pass
        if not raw.endswith(".unl"):
            raw += ".unl"
        return raw

    def list_labs(self) -> Any:
        resp = self.session.get(f"{self.base_url}/labs", timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_topology(self, lab_path: str) -> Any:
        path = self.normalize_lab_path(lab_path)
        resp = self.session.get(f"{self.base_url}/labs/{path}/topology", timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_nodes(self, lab_path: str) -> Any:
        path = self.normalize_lab_path(lab_path)
        resp = self.session.get(f"{self.base_url}/labs/{path}/nodes", timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_networks(self, lab_path: str) -> Any:
        """ดึงข้อมูล networks (cloud/bridge) จาก EVE-NG lab"""
        path = self.normalize_lab_path(lab_path)
        resp = self.session.get(f"{self.base_url}/labs/{path}/networks", timeout=15)
        resp.raise_for_status()
        return resp.json()


def eveng_topology_to_graph(topology_data: dict, nodes_data: dict, networks_data: dict = None, inventory_devices: list = None, live_interfaces: dict = None) -> dict:
    """
    แปลง response จาก EVE-NG เป็น {nodes, edges} แบบ vis-network
    รองรับรูปแบบ JSON ทั้งแบบ dict และ list ตามเวอร์ชัน EVE-NG
    จับคู่ node กับ inventory device name (เช่น R1, R2, R3)
    รองรับหลายเครือข่าย/หลายวง (Multi-Network Clouds) พร้อมคำนวณ subnet อัตโนมัติจาก Interface IP
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
                "node_id": nid,
                "name": name,
                "type": dtype,
                "ip": dev_ip,
                "model": n.get("image", ""),
                "status": "connected" if dev_ip else "discovered",
            })

    # --- Parse network objects (cloud/bridge) ---
    net_id_to_name = {}
    net_nodes_map = {}
    if networks_data:
        raw_nets = networks_data.get("data") if isinstance(networks_data, dict) else networks_data
        if isinstance(raw_nets, dict):
            raw_nets = raw_nets.values()
        if raw_nets:
            for net in raw_nets:
                if not isinstance(net, dict):
                    continue
                # ข้าม internal bridge network ที่ visibility == '0' และมีเพียง 2 endpoints
                # แต่ถ้ามี 3+ endpoints หรือ visibility == 1 ให้แสดงเป็นวง Network Cloud
                count = int(net.get("count", 0))
                vis = str(net.get("visibility", "1"))
                if vis == "0" and count <= 2:
                    continue

                net_id = str(net.get("id", ""))
                net_name = net.get("name") or net.get("label") or f"Net-{net_id}"
                net_id_to_name[net_id] = net_name
                net_id_to_name[f"network{net_id}"] = net_name
                
                net_obj = {
                    "id": net_name,
                    "name": net_name,
                    "type": "network",
                    "ip": "",  # จะคำนวณ subnet จาก IP ของ interface ที่ต่ออยู่ด้านล่าง
                    "model": "cloud",
                    "status": "discovered",
                }
                net_nodes_map[net_name] = net_obj
                nodes_out.append(net_obj)

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
    # ตรวจจับ Subnet สำหรับแต่ละ Network Cloud จาก Interface IP ของอุปกรณ์ที่ต่ออยู่
    net_subnets = {}
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

        # เก็บ subnet เข้าสู่ network node ที่เกี่ยวข้อง
        target_net = None
        cand_ip = ""
        if src_type == "network" or from_id in net_nodes_map:
            target_net = from_id
            cand_ip = to_ip
        elif dst_type == "network" or to_id in net_nodes_map:
            target_net = to_id
            cand_ip = from_ip

        if target_net and cand_ip and cand_ip not in ("unassigned", "-"):
            parts = cand_ip.split(".")
            if len(parts) == 4:
                sub = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
                net_subnets.setdefault(target_net, []).append(sub)

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

    # อัปเดต Subnet ให้กับแต่ละ Network Cloud ("วง")
    for net_name, net_obj in net_nodes_map.items():
        subs = net_subnets.get(net_name, [])
        if subs:
            net_obj["ip"] = subs[0]
        elif not net_obj.get("ip"):
            # Fallback หากยังไม่ได้ต่อ IP
            net_obj["ip"] = "Multi-Access Network"

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
