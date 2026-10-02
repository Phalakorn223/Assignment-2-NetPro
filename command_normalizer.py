"""
command_normalizer.py — รองรับคำสั่งย่อ (abbreviated commands) สำหรับ UI autocomplete
อ้างอิง: spec section 6.3 และตารางใน section 3.2
"""

# Mapping คำสั่งย่อ → คำสั่งเต็ม
# ใช้เฉพาะสำหรับ UI autocomplete / suggestion
# เวลาส่งจริงให้ส่งคำสั่งดิบตรง ๆ ให้ IOS parse เอง
COMMAND_ALIASES = {
    # Interface
    "int":                  "interface",
    "inte":                 "interface",
    "interf":               "interface",
    # Configure
    "conf":                 "configure terminal",
    "conf t":               "configure terminal",
    "config":               "configure terminal",
    "config t":             "configure terminal",
    "conf term":            "configure terminal",
    "config term":          "configure terminal",
    # Shutdown
    "no shut":              "no shutdown",
    "no sh":                "no shutdown",
    "shut":                 "shutdown",
    # IP address
    "ip add":               "ip address",
    "ip addr":              "ip address",
    "ip add dhcp":          "ip address dhcp",
    "ip addr dhcp":         "ip address dhcp",
    "no ip add":            "no ip address",
    "no ip addr":           "no ip address",
    # Show commands — General
    "sh run":               "show running-config",
    "show run":             "show running-config",
    "sh start":             "show startup-config",
    "show start":           "show startup-config",
    "sh ver":               "show version",
    "show ver":             "show version",
    "sh vlan":              "show vlan",
    "sh vlan br":           "show vlan brief",
    "show vlan br":         "show vlan brief",
    "sh arp":               "show arp",
    "sh clock":             "show clock",
    "show cl":              "show clock",
    "sh hist":              "show history",
    "show hist":            "show history",
    # Show commands — Interfaces & Controllers
    "sh ip int br":         "show ip interface brief",
    "sh ip int brief":      "show ip interface brief",
    "show ip int br":       "show ip interface brief",
    "show ip int brief":    "show ip interface brief",
    "sh ip int":            "show ip interface",
    "show ip int":          "show ip interface",
    "sh int stat":          "show interfaces status",
    "show int stat":        "show interfaces status",
    "sh int":               "show interfaces status",
    "show int":             "show interfaces status",
    "sh interfaces":        "show interfaces status",
    "show interfaces":      "show interfaces status",
    "sh controllers":       "show controllers",
    "sh controller":        "show controllers",
    "sh contr":             "show controllers",
    "sh cont":              "show controllers",
    "show cont":            "show controllers",
    "show contr":           "show controllers",
    # Show commands — Routing
    "sh ip route":          "show ip route",
    "sh ip ro":             "show ip route",
    "show ip ro":           "show ip route",
    "sh ip proto":          "show ip protocols",
    "show ip proto":        "show ip protocols",
    # Show commands — Protocols
    "sh ip rip":            "show ip rip database",
    "sh ip rip db":         "show ip rip database",
    "show ip rip db":       "show ip rip database",
    "sh ip rip database":   "show ip rip database",
    "sh ip ospf neigh":     "show ip ospf neighbor",
    "show ip ospf neigh":   "show ip ospf neighbor",
    "sh ip ospf db":        "show ip ospf database",
    "show ip ospf db":      "show ip ospf database",
    "sh ip ospf int br":    "show ip ospf interface brief",
    "show ip ospf int br":  "show ip ospf interface brief",
    "sh ip ospf int":       "show ip ospf interface brief",
    "show ip ospf int":     "show ip ospf interface brief",
    "sh ip eigrp neigh":    "show ip eigrp neighbors",
    "show ip eigrp neigh":  "show ip eigrp neighbors",
    "sh ip eigrp top":      "show ip eigrp topology",
    "show ip eigrp top":    "show ip eigrp topology",
    "sh ip eigrp int":      "show ip eigrp interfaces",
    "show ip eigrp int":    "show ip eigrp interfaces",
    "sh ip bgp sum":        "show ip bgp summary",
    "show ip bgp sum":      "show ip bgp summary",
    "sh ip bgp neigh":      "show ip bgp neighbors",
    "show ip bgp neigh":    "show ip bgp neighbors",
    # Show commands — CDP / LLDP
    "sh cdp":               "show cdp neighbors",
    "show cdp":             "show cdp neighbors",
    "sh cdp neigh":         "show cdp neighbors",
    "show cdp neigh":       "show cdp neighbors",
    "show cdp neighbor":    "show cdp neighbors",
    "sh cdp neighbor":      "show cdp neighbors",
    "sh cdp neigh det":     "show cdp neighbors detail",
    "sh cdp neigh detail":  "show cdp neighbors detail",
    "show cdp neigh detail":"show cdp neighbors detail",
    "sh lldp":              "show lldp neighbors",
    "show lldp":            "show lldp neighbors",
    "sh lldp neigh":        "show lldp neighbors",
    "show lldp neigh":      "show lldp neighbors",
    "sh lldp neighbor":     "show lldp neighbors",
    "sh lldp neigh det":    "show lldp neighbors detail",
    "show lldp neigh detail":"show lldp neighbors detail",
    # Save & Terminal commands
    "wr":                   "write memory",
    "wr mem":               "write memory",
    "write mem":            "write memory",
    "copy run start":       "copy running-config startup-config",
    "copy run sta":         "copy running-config startup-config",
    "copy run":             "copy running-config startup-config",
    "term len 0":           "terminal length 0",
    "term len":             "terminal length 0",
    "term length 0":        "terminal length 0",
    "term length":          "terminal length 0",
    "term width 512":       "terminal width 512",
    "term wid":             "terminal width 512",
    # Routing protocols configuration
    "router r":             "router rip",
    "router ri":            "router rip",
    "router rip":           "router rip",
    "router o":             "router ospf 1",
    "router os":            "router ospf 1",
    "router ospf":          "router ospf 1",
    "router e":             "router eigrp 100",
    "router ei":            "router eigrp 100",
    "router eigrp":         "router eigrp 100",
    "router b":             "router bgp 65001",
    "router bg":            "router bgp 65001",
    "router bgp":           "router bgp 65001",
    "net":                  "network",
    "neigh":                "neighbor",
    "pass":                 "passive-interface",
    "passive":              "passive-interface",
    "no auto":              "no auto-summary",
    "auto-summary":         "auto-summary",
    "default-info orig":    "default-information originate",
    "default-info":         "default-information originate",
    "default-information orig": "default-information originate",
    "redist":               "redistribute",
    "ver 2":                "version 2",
    # General / Line / Exec
    "en":                   "enable",
    "dis":                  "disable",
    "line con 0":           "line console 0",
    "line vty 0 4":         "line vty 0 4",
}

# รายชื่อคำสั่งทั้งหมดสำหรับ autocomplete dropdown
ALL_COMMANDS = [
    # Show — General
    "show running-config",
    "show startup-config",
    "show version",
    "show ip interface brief",
    "show ip interface",
    "show interfaces status",
    "show controllers",
    "show vlan",
    "show vlan brief",
    "show arp",
    "show clock",
    "show history",
    "show users",
    # Show — Routing
    "show ip route",
    "show ip route static",
    "show ip route connected",
    "show ip protocols",
    # Show — RIP
    "show ip rip database",
    # Show — EIGRP
    "show ip eigrp neighbors",
    "show ip eigrp topology",
    "show ip eigrp interfaces",
    # Show — OSPF
    "show ip ospf neighbor",
    "show ip ospf database",
    "show ip ospf interface brief",
    # Show — BGP
    "show ip bgp summary",
    "show ip bgp neighbors",
    # Show — CDP/LLDP
    "show cdp neighbors detail",
    "show lldp neighbors detail",
    # Save & Utilities
    "write memory",
    "write erase",
    "copy running-config startup-config",
    "terminal length 0",
    "terminal width 512",
    "enable",
    "disable",
    "reload",
    # Linux / PC Commands
    "ip addr",
    "ip route",
    "ip link",
    "ifconfig",
    "uname -a",
    "whoami",
    "sudo apt update",
    "sudo apt install",
    "systemctl status ssh",
    "df -h",
    "free -m",
    "ss -tuln",
    "netstat -tuln",
    "cat /etc/os-release",
    "cat /etc/netplan",
    "hostname -I",
    "traceroute",
    "ping",
    "clock set",
    "clear",
    # Cisco Configure
    "configure terminal",
    "interface",
    "interface GigabitEthernet0/0",
    "interface GigabitEthernet0/1",
    "interface Ethernet0/0",
    "interface Ethernet0/1",
    "interface Serial0/0",
    "interface Loopback0",
    "ip address",
    "ip address dhcp",
    "no ip address",
    "no shutdown",
    "shutdown",
    "ip route",
    "ip default-gateway",
    "router rip",
    "router eigrp 100",
    "router ospf 1",
    "router bgp 65001",
    "network",
    "neighbor",
    "passive-interface",
    "no auto-summary",
    "default-information originate",
    "redistribute",
    "hostname",
    "line console 0",
    "line vty 0 4",
    "enable secret",
    "end",
    "exit",
]

# Add Linux Aliases
COMMAND_ALIASES.update({
    "ip a": "ip addr",
    "ip r": "ip route",
    "ip l": "ip link",
    "ifc": "ifconfig",
    "apt update": "sudo apt update",
    "apt install": "sudo apt install",
    "status ssh": "systemctl status ssh",
    "os": "cat /etc/os-release",
})


def _expand_interface_token(token: str) -> str:
    """ขยายชื่อ interface ย่อ เช่น gi0/0 -> GigabitEthernet0/0"""
    import re
    m = re.match(r'^(g|gi|gig|gigabitethernet)(\d.*)$', token, re.I)
    if m: return f"GigabitEthernet{m.group(2)}"
    m = re.match(r'^(fa|fast|fastethernet)(\d.*)$', token, re.I)
    if m: return f"FastEthernet{m.group(2)}"
    m = re.match(r'^(e|eth|ethernet)(\d.*)$', token, re.I)
    if m: return f"Ethernet{m.group(2)}"
    m = re.match(r'^(s|se|ser|serial)(\d.*)$', token, re.I)
    if m: return f"Serial{m.group(2)}"
    m = re.match(r'^(lo|loop|loopback)(\d.*)$', token, re.I)
    if m: return f"Loopback{m.group(2)}"
    m = re.match(r'^(vl|vlan)(\d.*)$', token, re.I)
    if m: return f"Vlan{m.group(2)}"
    return token


def normalize(raw_command: str) -> str:
    """
    แปลงคำสั่งย่อเป็นคำสั่งเต็ม
    ถ้าไม่พบ alias ให้คืนค่าเดิม (IOS จะ parse เอง)
    """
    import re
    cmd = raw_command.strip()
    key = cmd.lower()

    # รองรับ do นำหน้า (เช่น "do sh ip ro" -> "do show ip route")
    if key.startswith("do "):
        sub_cmd = cmd[3:].strip()
        norm_sub = normalize(sub_cmd)
        return f"do {norm_sub}"

    # ตรวจสอบ alias ตรงตัว
    if key in COMMAND_ALIASES:
        return COMMAND_ALIASES[key]

    # ตรวจสอบคำสั่ง interface ย่อ เช่น "int gi0/0" -> "interface GigabitEthernet0/0"
    m_int = re.match(r'^(?:int|interface)\s+([a-zA-Z]+\d.*)$', cmd, re.I)
    if m_int:
        expanded_if = _expand_interface_token(m_int.group(1))
        return f"interface {expanded_if}"

    return raw_command


def get_suggestions(partial: str, max_results: int = 10) -> list:
    """
    คืนรายการคำสั่งที่ขึ้นต้นด้วย partial string
    ใช้สำหรับ dropdown/autocomplete ใน UI
    """
    partial_strip = partial.strip()
    partial_lower = partial_strip.lower()
    if not partial_lower:
        return []

    is_do = False
    prefix_do = ""
    if partial_lower.startswith("do "):
        is_do = True
        prefix_do = "do "
        partial_lower = partial_lower[3:].strip()
        if not partial_lower:
            return ["do show running-config", "do show ip interface brief", "do show ip route", "do write memory"]

    suggestions = []

    # 1. ตรวจจาก aliases ก่อน
    for alias, full_cmd in COMMAND_ALIASES.items():
        if alias.startswith(partial_lower) or partial_lower.startswith(alias):
            target = f"{prefix_do}{full_cmd}" if is_do else full_cmd
            if target not in suggestions:
                suggestions.append(target)

    # 2. ตรวจจาก all commands
    for cmd in ALL_COMMANDS:
        target = f"{prefix_do}{cmd}" if is_do else cmd
        if target.lower().startswith(f"{prefix_do}{partial_lower}".lower()) and target not in suggestions:
            suggestions.append(target)

    # 3. ตรวจ word-by-word prefix matching (เช่น "sh ip r" -> "show ip route", "show ip rip database")
    words = partial_lower.split()
    if len(words) > 1:
        for cmd in ALL_COMMANDS:
            cmd_words = cmd.lower().split()
            if len(cmd_words) >= len(words):
                match = True
                for i, w in enumerate(words):
                    cw = cmd_words[i]
                    if not (cw.startswith(w) or COMMAND_ALIASES.get(w, w) == cw or cw.startswith(COMMAND_ALIASES.get(w, w))):
                        match = False
                        break
                if match:
                    target = f"{prefix_do}{cmd}" if is_do else cmd
                    if target not in suggestions:
                        suggestions.append(target)

    return suggestions[:max_results]
