"""
command_normalizer.py — รองรับคำสั่งย่อ (abbreviated commands) สำหรับ UI autocomplete
อ้างอิง: spec section 6.3 และตารางใน section 3.2
"""

# Mapping คำสั่งย่อ → คำสั่งเต็ม
# ใช้เฉพาะสำหรับ UI autocomplete / suggestion
# เวลาส่งจริงให้ส่งคำสั่งดิบตรง ๆ ให้ IOS parse เอง
COMMAND_ALIASES = {
    # Interface
    "int":          "interface",
    "inte":         "interface",
    "interf":       "interface",
    # Configure
    "conf t":       "configure terminal",
    "config t":     "configure terminal",
    "conf term":    "configure terminal",
    "config term":  "configure terminal",
    # Shutdown
    "no shut":      "no shutdown",
    "no sh":        "no shutdown",
    "shut":         "shutdown",
    # IP address
    "ip add":       "ip address",
    "ip addr":      "ip address",
    # Show commands
    "sh run":               "show running-config",
    "show run":             "show running-config",
    "sh ip int br":         "show ip interface brief",
    "sh ip int brief":      "show ip interface brief",
    "show ip int br":       "show ip interface brief",
    "show ip int brief":    "show ip interface brief",
    "sh ip route":          "show ip route",
    "sh ip ro":             "show ip route",
    "sh ip proto":          "show ip protocols",
    "show ip proto":        "show ip protocols",
    "sh ver":               "show version",
    "show ver":             "show version",
    "sh vlan":              "show vlan",
    "sh int stat":          "show interfaces status",
    # Routing protocols
    "router osp":   "router ospf",
    "router ei":    "router eigrp",
    "en":           "end",
    # BGP
    "sh ip bgp sum":        "show ip bgp summary",
    "show ip bgp sum":      "show ip bgp summary",
    # OSPF
    "sh ip ospf neigh":     "show ip ospf neighbor",
    "show ip ospf neigh":   "show ip ospf neighbor",
    # EIGRP
    "sh ip eigrp neigh":    "show ip eigrp neighbors",
    "show ip eigrp neigh":  "show ip eigrp neighbors",
    # CDP
    "sh cdp neigh":         "show cdp neighbors detail",
    "show cdp neigh":       "show cdp neighbors detail",
}

# รายชื่อคำสั่งทั้งหมดสำหรับ autocomplete dropdown
ALL_COMMANDS = [
    # Show — General
    "show running-config",
    "show startup-config",
    "show version",
    "show ip interface brief",
    "show interfaces status",
    "show vlan",
    "show arp",
    # Show — Routing
    "show ip route",
    "show ip route static",
    "show ip protocols",
    # Show — RIP
    "show ip rip database",
    # Show — EIGRP
    "show ip eigrp neighbors",
    "show ip eigrp topology",
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
    "clear",
    # Cisco Configure
    "configure terminal",
    "interface",
    "ip address",
    "no shutdown",
    "shutdown",
    "ip route",
    "router rip",
    "router eigrp",
    "router ospf",
    "router bgp",
    "network",
    "neighbor",
    "no auto-summary",
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


def normalize(raw_command: str) -> str:
    """
    แปลงคำสั่งย่อเป็นคำสั่งเต็ม
    ถ้าไม่พบ alias ให้คืนค่าเดิม (IOS จะ parse เอง)
    """
    key = raw_command.strip().lower()
    return COMMAND_ALIASES.get(key, raw_command)


def get_suggestions(partial: str, max_results: int = 10) -> list:
    """
    คืนรายการคำสั่งที่ขึ้นต้นด้วย partial string
    ใช้สำหรับ dropdown/autocomplete ใน UI
    """
    partial_lower = partial.strip().lower()
    if not partial_lower:
        return []

    suggestions = []
    # ตรวจจาก aliases ก่อน
    for alias, full_cmd in COMMAND_ALIASES.items():
        if alias.startswith(partial_lower) and full_cmd not in suggestions:
            suggestions.append(full_cmd)

    # ตรวจจาก all commands
    for cmd in ALL_COMMANDS:
        if cmd.lower().startswith(partial_lower) and cmd not in suggestions:
            suggestions.append(cmd)

    return suggestions[:max_results]
