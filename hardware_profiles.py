"""
hardware_profiles.py — Hardware Profile สำหรับสร้าง Interface อัตโนมัติตาม Model
อ้างอิง: spec v3 section 3.1, 3.2
เมื่อผู้ใช้เลือก Model ระบบจะสร้าง Interface ตาม Hardware Profile โดยอัตโนมัติ
"""

# ---------------------------------------------------------------------------
# Hardware Profile Registry
# ---------------------------------------------------------------------------
HARDWARE_PROFILES = {
    # ─── Router Models ─────────────────────────────────────────────────
    "Cisco 4331": {
        "type": "router",
        "description": "Cisco ISR 4331 Integrated Services Router",
        "interfaces": [
            {"name": "GigabitEthernet0/0/0", "type": "gigabitEthernet"},
            {"name": "GigabitEthernet0/0/1", "type": "gigabitEthernet"},
            {"name": "GigabitEthernet0/0/2", "type": "gigabitEthernet"},
        ],
    },
    "Cisco 2901": {
        "type": "router",
        "description": "Cisco 2901 Integrated Services Router",
        "interfaces": [
            {"name": "GigabitEthernet0/0", "type": "gigabitEthernet"},
            {"name": "GigabitEthernet0/1", "type": "gigabitEthernet"},
        ],
    },
    "Cisco 1941": {
        "type": "router",
        "description": "Cisco 1941 Integrated Services Router",
        "interfaces": [
            {"name": "GigabitEthernet0/0", "type": "gigabitEthernet"},
            {"name": "GigabitEthernet0/1", "type": "gigabitEthernet"},
        ],
    },
    "Cisco 2911": {
        "type": "router",
        "description": "Cisco 2911 Integrated Services Router",
        "interfaces": [
            {"name": "GigabitEthernet0/0", "type": "gigabitEthernet"},
            {"name": "GigabitEthernet0/1", "type": "gigabitEthernet"},
            {"name": "GigabitEthernet0/2", "type": "gigabitEthernet"},
        ],
    },

    # ─── Switch Models ─────────────────────────────────────────────────
    "Cisco Catalyst 2960": {
        "type": "switch",
        "description": "Cisco Catalyst 2960-24TT-L (24 FE + 2 GE)",
        "interfaces": (
            [{"name": f"FastEthernet0/{i}", "type": "fastEthernet"} for i in range(1, 25)]
            + [
                {"name": "GigabitEthernet0/1", "type": "gigabitEthernet"},
                {"name": "GigabitEthernet0/2", "type": "gigabitEthernet"},
                {"name": "Vlan1", "type": "vlan"},
            ]
        ),
    },
    "Cisco Catalyst 3560": {
        "type": "switch",
        "description": "Cisco Catalyst 3560-24PS (24 FE + 2 GE, L3)",
        "interfaces": (
            [{"name": f"FastEthernet0/{i}", "type": "fastEthernet"} for i in range(1, 25)]
            + [
                {"name": "GigabitEthernet0/1", "type": "gigabitEthernet"},
                {"name": "GigabitEthernet0/2", "type": "gigabitEthernet"},
                {"name": "Vlan1", "type": "vlan"},
            ]
        ),
    },
    "Cisco Catalyst 3750": {
        "type": "switch",
        "description": "Cisco Catalyst 3750-24T (24 GE + 2 SFP, L3)",
        "interfaces": (
            [{"name": f"GigabitEthernet1/0/{i}", "type": "gigabitEthernet"} for i in range(1, 25)]
            + [
                {"name": "GigabitEthernet1/0/25", "type": "gigabitEthernet"},
                {"name": "GigabitEthernet1/0/26", "type": "gigabitEthernet"},
                {"name": "Vlan1", "type": "vlan"},
            ]
        ),
    },
}

# ---------------------------------------------------------------------------
# Additional Interface Templates (สำหรับเพิ่มทีหลัง)
# ---------------------------------------------------------------------------
ADDITIONAL_INTERFACES = {
    "loopback": {"name_prefix": "Loopback", "type": "loopback"},
    "serial": {"name_prefix": "Serial", "type": "serial"},
    "vlan": {"name_prefix": "Vlan", "type": "vlan"},
}


def get_model_list(device_type: str = None) -> list:
    """คืนรายชื่อ Model ทั้งหมด หรือกรองตาม type (router/switch)"""
    result = []
    for model_name, profile in HARDWARE_PROFILES.items():
        if device_type and profile["type"] != device_type.lower():
            continue
        result.append({
            "model": model_name,
            "type": profile["type"],
            "description": profile["description"],
            "interface_count": len(profile["interfaces"]),
        })
    return result


def generate_interfaces(model: str) -> list:
    """
    สร้าง Interface list จาก Hardware Profile ตาม Model ที่เลือก
    คืน list of dict:
    [{"name": "GigabitEthernet0/0", "type": "gigabitEthernet", "ip": null, "mask": null, "status": "down", "description": null}]
    """
    profile = HARDWARE_PROFILES.get(model)
    if not profile:
        # Default: สร้าง 2 GigabitEthernet
        return [
            _make_interface("GigabitEthernet0/0", "gigabitEthernet"),
            _make_interface("GigabitEthernet0/1", "gigabitEthernet"),
        ]

    return [_make_interface(iface["name"], iface["type"]) for iface in profile["interfaces"]]


def create_additional_interface(interface_type: str, number: int) -> dict:
    """
    สร้าง interface เพิ่มเติม (Loopback, Serial, Vlan)
    เช่น create_additional_interface("loopback", 0) → {"name": "Loopback0", ...}
    """
    template = ADDITIONAL_INTERFACES.get(interface_type.lower())
    if not template:
        return None
    name = f"{template['name_prefix']}{number}"
    return _make_interface(name, template["type"])


def _make_interface(name: str, iface_type: str) -> dict:
    """สร้าง interface dict พร้อมค่า default"""
    return {
        "name": name,
        "type": iface_type,
        "ip": None,
        "mask": None,
        "status": "down",
        "description": None,
    }
