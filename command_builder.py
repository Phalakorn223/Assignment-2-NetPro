"""
command_builder.py — Pure functions สำหรับแปลง form data → Cisco IOS CLI commands
อ้างอิง: spec section 6.2
"""


def build_ip_address_commands(interface: str, ip: str, mask: str = None, description: str = None) -> list:
    """กำหนด IP Address บน interface (Static, DHCP หรือ No IP) พร้อม no shutdown"""
    cmds = [f"interface {interface}"]
    if description:
        cmds.append(f"description {description}")
    ip_clean = (ip or "").lower().strip()
    if ip_clean == "dhcp":
        cmds.append("ip address dhcp")
    elif ip_clean in ("no", "no ip", "no ip address", "no ip add", "none", "unassigned", "disable"):
        cmds.append("no ip address")
    else:
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


def build_rip(networks: list, version: int = 2) -> list:
    """
    RIP configuration — version 1 หรือ 2
    networks: list of network addresses (str)
    """
    version = 1 if int(version) == 1 else 2
    cmds = ["router rip", f"version {version}"]
    for net in networks:
        net = net.strip()
        if net:
            cmds.append(f"network {net}")
    if version == 2:
        cmds.append("no auto-summary")
    return cmds


def build_redistribute(protocol: str, source: str, **kwargs) -> list:
    """
    protocol: rip | eigrp | ospf | bgp (ปลายทาง)
    source: static | connected | rip | eigrp | ospf | bgp
    """
    protocol = protocol.lower()
    source = source.lower()
    line = f"redistribute {source}"

    if source == "ospf" and protocol != "ospf":
        pid = kwargs.get("process_id")
        if pid is not None:
            line += f" {pid}"
    if source == "eigrp" and protocol != "eigrp":
        asn = kwargs.get("as_number")
        if asn is not None:
            line += f" {asn}"

    if protocol == "eigrp":
        bw = kwargs.get("metric_bw", 10000)
        delay = kwargs.get("metric_delay", 100)
        rel = kwargs.get("metric_reliability", 255)
        load = kwargs.get("metric_load", 1)
        mtu = kwargs.get("metric_mtu", 1500)
        line += f" metric {bw} {delay} {rel} {load} {mtu}"

    if protocol == "ospf":
        if kwargs.get("subnets", True):
            line += " subnets"
        if kwargs.get("metric") is not None:
            line += f" metric {kwargs['metric']}"
        if kwargs.get("metric_type") is not None:
            line += f" metric-type {kwargs['metric_type']}"

    if protocol == "rip" and kwargs.get("metric") is not None:
        line += f" metric {kwargs['metric']}"

    return [line]


def build_default_information_originate(protocol: str, always: bool = False) -> list:
    protocol = protocol.lower()
    if protocol == "ospf":
        cmd = "default-information originate"
        if always:
            cmd += " always"
        return [cmd]
    if protocol == "rip":
        return ["default-information originate"]
    if protocol == "bgp":
        return ["network 0.0.0.0 mask 0.0.0.0"]
    if protocol == "eigrp":
        raise ValueError(
            "EIGRP ไม่มี default-information originate โดยตรง — ใช้ ip default-network หรือ redistribute static"
        )
    raise ValueError(f"ไม่รู้จัก protocol: {protocol}")


def merge_router_protocol_commands(
    base_cmds: list,
    protocol: str,
    redistribute_entries: list = None,
    default_originate: dict = None,
) -> list:
    """
    แทรก redistribute / default-information หลัง network statements ภายใน router block
    base_cmds เริ่มด้วย 'router ...'
    """
    if not redistribute_entries and not default_originate:
        return base_cmds

    protocol_key = protocol.lower()
    if protocol_key in ("static", "default"):
        return base_cmds

    router_line = base_cmds[0] if base_cmds else ""
    if not router_line.startswith("router "):
        return base_cmds

    inner = base_cmds[1:]
    extras = []
    for entry in redistribute_entries or []:
        entry_kwargs = dict(entry)
        source = entry_kwargs.pop("source", None) or entry_kwargs.pop("protocol", None)
        if not source or source.lower() == protocol_key:
            continue
        extras.extend(build_redistribute(protocol_key, source, **entry_kwargs))

    if default_originate and default_originate.get("enabled"):
        try:
            extras.extend(
                build_default_information_originate(
                    protocol_key,
                    always=bool(default_originate.get("always")),
                )
            )
        except ValueError:
            pass

    return [router_line] + inner + extras


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
