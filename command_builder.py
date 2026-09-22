"""
command_builder.py — Pure functions สำหรับแปลง form data → Cisco IOS CLI commands
อ้างอิง: spec section 6.2
"""


def build_ip_address_commands(interface: str, ip: str, mask: str, description: str = None) -> list:
    """กำหนด IP Address บน interface พร้อม no shutdown"""
    cmds = [f"interface {interface}"]
    if description:
        cmds.append(f"description {description}")
    cmds.append(f"ip address {ip} {mask}")
    cmds.append("no shutdown")
    return cmds


def build_interface_state_commands(interface: str, up: bool) -> list:
    """สั่ง no shutdown (up=True) หรือ shutdown (up=False)"""
    return [
        f"interface {interface}",
        "no shutdown" if up else "shutdown",
    ]


def build_interface_description(interface: str, description: str) -> list:
    return [f"interface {interface}", f"description {description}"]


def build_static_route(dest_network: str, mask: str, next_hop: str) -> list:
    """Static Route: ip route <dest> <mask> <next_hop>"""
    return [f"ip route {dest_network} {mask} {next_hop}"]


def build_default_route(next_hop: str) -> list:
    """Default Static Route: ip route 0.0.0.0 0.0.0.0 <next_hop>"""
    return [f"ip route 0.0.0.0 0.0.0.0 {next_hop}"]


def build_rip(networks: list) -> list:
    """
    RIP v2 configuration
    networks: list of network addresses (str), e.g. ["10.1.1.0", "192.168.1.0"]
    """
    cmds = ["router rip", "version 2"]
    for net in networks:
        net = net.strip()
        if net:
            cmds.append(f"network {net}")
    cmds.append("no auto-summary")
    return cmds


def build_eigrp(as_number: int, networks: list) -> list:
    """
    EIGRP configuration
    networks: list of dicts {"network": "10.1.1.0", "wildcard": "0.0.0.255"}
    """
    cmds = [f"router eigrp {as_number}"]
    for entry in networks:
        net = entry.get("network", "").strip()
        wildcard = entry.get("wildcard", "0.0.0.255").strip()
        if net:
            cmds.append(f"network {net} {wildcard}")
    cmds.append("no auto-summary")
    return cmds


def build_ospf(process_id: int, router_id: str, network_area_pairs: list) -> list:
    """
    OSPF configuration
    network_area_pairs: list of dicts {"network": "10.1.1.0", "wildcard": "0.0.0.3", "area": 0}
    """
    cmds = [f"router ospf {process_id}"]
    if router_id and router_id.strip():
        cmds.append(f"router-id {router_id.strip()}")
    for entry in network_area_pairs:
        net = entry.get("network", "").strip()
        wildcard = entry.get("wildcard", "0.0.0.255").strip()
        area = entry.get("area", 0)
        if net:
            cmds.append(f"network {net} {wildcard} area {area}")
    return cmds


def build_bgp(as_number: int, neighbors: list, networks: list) -> list:
    """
    BGP configuration
    neighbors: list of dicts {"ip": "10.1.1.2", "remote_as": 65002}
    networks: list of dicts {"network": "192.168.1.0", "mask": "255.255.255.0"}
    """
    cmds = [f"router bgp {as_number}"]
    for n in neighbors:
        ip = n.get("ip", "").strip()
        remote_as = n.get("remote_as", "")
        if ip and remote_as:
            cmds.append(f"neighbor {ip} remote-as {remote_as}")
    for net in networks:
        network = net.get("network", "").strip()
        mask = net.get("mask", "255.255.255.0").strip()
        if network:
            cmds.append(f"network {network} mask {mask}")
    return cmds


def preview_commands(cmds: list) -> str:
    """
    สร้าง preview string ของ Cisco IOS commands สำหรับแสดงใน UI
    ก่อนกด Apply จริง
    """
    # Top-level keywords ที่ไม่ต้อง indent
    TOP_LEVEL = ("interface ", "router ", "ip route ", "ip route0",
                 "no ip route", "router rip", "router eigrp", "router ospf",
                 "router bgp", "ip route")
    lines = ["configure terminal"]
    in_block = False
    for cmd in cmds:
        stripped = cmd.strip()
        is_top = any(stripped.startswith(kw) for kw in TOP_LEVEL)
        if is_top:
            lines.append(stripped)
            in_block = True
        else:
            lines.append(f" {stripped}")
    lines.append("end")
    return "\n".join(lines)
