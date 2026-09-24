"""
connection_manager.py — จัดการ netmiko session pool, IP validation, ping check, error handling
อ้างอิง: spec section 6.1, 3.1, 8
"""

import os
import re
import json
import subprocess
import socket
import time
from typing import Dict, Any, Optional

try:
    from netmiko import ConnectHandler
    from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException
    NETMIKO_AVAILABLE = True
except ImportError:
    NETMIKO_AVAILABLE = False
    NetmikoTimeoutException = Exception
    NetmikoAuthenticationException = Exception

try:
    import serial
    PYSERIAL_AVAILABLE = True
except ImportError:
    PYSERIAL_AVAILABLE = False

# ไฟล์เก็บ device inventory
INVENTORY_FILE = os.path.join(os.path.dirname(__file__), "devices.json")

DEFAULT_SEED_DEVICES = [
    {"id": "R1", "name": "Router-R1", "model": "Cisco 4331", "device_type_label": "router",
     "connection_type": "SSH", "ip": "192.168.1.116", "port": 22,
     "username": "cisco", "password": "cisco", "secret": "cisco"},
    {"id": "R2", "name": "Router-R2", "model": "Cisco 4331", "device_type_label": "router",
     "connection_type": "TELNET", "ip": "192.168.1.125", "port": 23,
     "username": "cisco", "password": "cisco", "secret": "cisco"},
    {"id": "SW1", "name": "Switch-SW1", "model": "Cisco Catalyst 2960", "device_type_label": "switch",
     "connection_type": "SSH", "ip": "192.168.1.117", "port": 22,
     "username": "cisco", "password": "cisco", "secret": "cisco"},
    {"id": "PC1", "name": "PC-Workstation", "model": "Virtual PC", "device_type_label": "pc",
     "connection_type": "PC", "ip": "192.168.1.10", "mask": "255.255.255.0", "gateway": "192.168.1.116"},
]


# ---------------------------------------------------------------------------
# IP Validation (ตาม spec section 8 + Ch6 thread1.py)
# ---------------------------------------------------------------------------
def ip_is_valid(ip: str) -> tuple:
    """
    ตรวจ IP address:
    - format ถูก (4 octets, แต่ละ octet 0-255)
    - ไม่ใช่ 127.x.x.x (loopback)
    - ไม่ใช่ 224.x.x.x+ (multicast)
    - ไม่ใช่ 0.0.0.0 หรือ 255.255.255.255
    คืน (True, "") หรือ (False, "ข้อความ error")
    """
    parts = ip.strip().split(".")
    if len(parts) != 4:
        return False, f"IP '{ip}' รูปแบบไม่ถูกต้อง (ต้องการ 4 ส่วน)"
    try:
        octets = [int(p) for p in parts]
    except ValueError:
        return False, f"IP '{ip}' มีตัวอักษรที่ไม่ใช่ตัวเลข"

    for o in octets:
        if not (0 <= o <= 255):
            return False, f"IP '{ip}' มี octet ออกนอกช่วง 0-255"
    if octets[0] == 127:
        return False, f"IP '{ip}' เป็น loopback address ไม่สามารถเชื่อมต่อได้"
    if octets[0] >= 224:
        return False, f"IP '{ip}' เป็น multicast/reserved address"
    if octets[0] == 0:
        return False, f"IP '{ip}' ไม่ใช่ unicast address ที่ถูกต้อง"
    return True, ""


def ping_check(ip: str, count: int = 2) -> bool:
    """
    Ping ตรวจ reachability ก่อน connect จริง
    คืน True ถ้า reachable, False ถ้าไม่ตอบสนอง
    """
    import platform
    system = platform.system().lower()
    if system == "windows":
        cmd = ["ping", "-n", str(count), "-w", "1000", ip]
    else:
        cmd = ["ping", "-c", str(count), "-W", "1", ip]
    try:
        result = subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return result == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Device Inventory CRUD
# ---------------------------------------------------------------------------
def load_inventory() -> list:
    """โหลด device list จากไฟล์ devices.json"""
    if not os.path.exists(INVENTORY_FILE):
        return []
    with open(INVENTORY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data if isinstance(data, list) else []


def ensure_inventory_initialized() -> list:
    """โหลด inventory — ถ้าไฟล์ devices.json ยังไม่เคยถูกสร้าง บันทึก seed ลง devices.json ครั้งแรก"""
    if not os.path.exists(INVENTORY_FILE):
        save_inventory(list(DEFAULT_SEED_DEVICES))
        return list(DEFAULT_SEED_DEVICES)
    return load_inventory()


def save_inventory(devices: list):
    """บันทึก device list ลงไฟล์ devices.json"""
    with open(INVENTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(devices, f, indent=2, ensure_ascii=False)


def add_device_to_inventory(device: dict) -> dict:
    """เพิ่ม device ใหม่ ให้ id อัตโนมัติ"""
    devices = load_inventory()
    # กำหนด ID ถ้าไม่มี
    if not device.get("id"):
        existing_ids = [d.get("id", "") for d in devices]
        count = 1
        while f"device-{count}" in existing_ids:
            count += 1
        device["id"] = f"device-{count}"
    devices.append(device)
    save_inventory(devices)
    return device


def remove_device_from_inventory(device_id: str) -> bool:
    """ลบ device จาก inventory"""
    devices = load_inventory()
    original_len = len(devices)
    devices = [d for d in devices if d.get("id") != device_id]
    if len(devices) < original_len:
        save_inventory(devices)
        return True
    return False


def get_device_by_id(device_id: str) -> Optional[dict]:
    devices = load_inventory()
    return next((d for d in devices if d.get("id") == device_id), None)


# ---------------------------------------------------------------------------
# Connection Manager (Session Pool)
# ---------------------------------------------------------------------------
class ConnectionManager:
    """
    จัดการ netmiko connection pool
    pool: {device_id: {"handler": conn_or_serial, "type": "SSH"|"TELNET"|"SERIAL"}}
    """

    def __init__(self):
        self.pool: Dict[str, Any] = {}

    def connect(self, device_id: str, device_params: dict, skip_ping: bool = False) -> dict:
        """
        เชื่อมต่ออุปกรณ์ผ่าน SSH / Telnet / Serial
        device_params ตัวอย่าง:
        {
            "connection_type": "SSH",       # SSH | TELNET | SERIAL
            "ip": "192.168.1.120",          # สำหรับ SSH/Telnet
            "port": 22,                     # optional
            "username": "cisco",
            "password": "cisco",
            "secret": "cisco",              # enable password
            "serial_port": "COM3",          # สำหรับ Serial
            "baudrate": 9600,
        }
        """
        conn_type = device_params.get("connection_type", "SSH").upper()
        ip = device_params.get("ip", "")

        # --- Validate IP (สำหรับ SSH/Telnet) ---
        if conn_type in ("SSH", "TELNET") and ip:
            valid, msg = ip_is_valid(ip)
            if not valid:
                return {"success": False, "message": msg}

            # --- Ping check ก่อน connect ---
            if not skip_ping:
                if not ping_check(ip):
                    return {
                        "success": False,
                        "message": f"ไม่สามารถ ping ถึง {ip} ได้ — อุปกรณ์อาจ offline หรือ IP ไม่ถูกต้อง"
                    }

        if not NETMIKO_AVAILABLE and conn_type in ("SSH", "TELNET"):
            return {"success": False, "message": "Netmiko ไม่ได้ติดตั้ง (pip install netmiko)"}

        try:
            if conn_type == "SSH":
                params = {
                    "device_type": "cisco_ios",
                    "ip": ip,
                    "username": device_params.get("username", "cisco"),
                    "password": device_params.get("password", "cisco"),
                    "secret":   device_params.get("secret", device_params.get("password", "cisco")),
                    "port":     int(device_params.get("port", 22)),
                    "conn_timeout": 10,
                }
                conn = ConnectHandler(**params)
                try:
                    conn.enable()
                except Exception:
                    pass
                try:
                    conn.send_command("terminal length 0")
                except Exception:
                    pass
                self.pool[device_id] = {"handler": conn, "type": "SSH", "params": dict(device_params)}
                return {"success": True, "message": f"SSH เชื่อมต่อ {ip}:{params['port']} สำเร็จ"}

            elif conn_type == "TELNET":
                port = int(device_params.get("port", 23))
                username = device_params.get("username", "").strip()
                password = device_params.get("password", "").strip()
                secret = device_params.get("secret", password).strip()

                # สำหรับ EVE-NG console port (มักจะเป็น 30000-40000) ที่ไม่ต้องใส่ user/pass
                # หรือ telnet ทั่วไป
                params = {
                    "device_type": "cisco_ios_telnet",
                    "ip": ip,
                    "port": port,
                    "conn_timeout": 12,
                }
                if username:
                    params["username"] = username
                if password:
                    params["password"] = password
                if secret:
                    params["secret"] = secret

                conn = ConnectHandler(**params)
                # ลองเข้า enable mode ถ้าทำได้
                try:
                    conn.enable()
                except Exception:
                    pass
                try:
                    conn.send_command("terminal length 0")
                except Exception:
                    pass
                self.pool[device_id] = {"handler": conn, "type": "TELNET", "params": dict(device_params)}
                return {"success": True, "message": f"Telnet เชื่อมต่อ {ip}:{port} สำเร็จ"}

            elif conn_type == "SERIAL":
                if not PYSERIAL_AVAILABLE:
                    return {"success": False, "message": "PySerial ไม่ได้ติดตั้ง (pip install pyserial)"}
                serial_port = device_params.get("serial_port", "COM1")
                baudrate = int(device_params.get("baudrate", 9600))
                ser = serial.Serial(serial_port, baudrate=baudrate, timeout=2)
                self.pool[device_id] = {"handler": ser, "type": "SERIAL", "params": dict(device_params)}
                return {"success": True, "message": f"Serial เชื่อมต่อ {serial_port} ({baudrate} baud) สำเร็จ"}

            else:
                return {"success": False, "message": f"ไม่รองรับ connection_type: {conn_type}"}

        except NetmikoAuthenticationException:
            return {"success": False, "message": "Authentication failed — username/password ไม่ถูกต้อง หรือเครื่องไม่ต้องการ auth"}
        except NetmikoTimeoutException:
            return {"success": False, "message": f"Connection timeout — ไม่ได้รับการตอบกลับจาก {ip}:{device_params.get('port', '')}"}
        except Exception as e:
            return {"success": False, "message": f"เชื่อมต่อล้มเหลว: {str(e)}"}

    def _ensure_connection(self, device_id: str) -> bool:
        """ตรวจและเชื่อมต่ออัตโนมัติถ้า session หลุดหรือยังไม่ได้ connect"""
        if device_id in self.pool:
            return True
        dev = get_device_by_id(device_id)
        if dev and (dev.get("device_type_label") or "").lower() not in ("pc", "network"):
            print(f"[ConnectionManager] Auto-connecting to {device_id}...")
            res = self.connect(device_id, dev, skip_ping=True)
            return res.get("success", False)
        return False

    def send_command(self, device_id: str, command: str, use_textfsm: bool = False, retry: bool = True) -> dict:
        """
        ส่ง show command ไปยัง device
        use_textfsm=True เพื่อ parse output เป็น structured data (สำหรับ CDP/LLDP)
        มี auto-reconnect ถ้า session หลุด
        """
        if device_id not in self.pool:
            if not self._ensure_connection(device_id):
                return {"success": False, "output": f"Device '{device_id}' ยังไม่ได้เชื่อมต่อ"}

        entry = self.pool[device_id]
        conn_type = entry["type"]
        handler = entry["handler"]

        try:
            if conn_type in ("SSH", "TELNET"):
                output = handler.send_command(command, use_textfsm=use_textfsm)
                # ตรวจ IOS syntax error
                if isinstance(output, str) and re.search(r"% Invalid input detected at", output):
                    return {
                        "success": False,
                        "output": output,
                        "error": "IOS ไม่รู้จักคำสั่ง — ตรวจสอบ syntax หรือ IOS version ของอุปกรณ์"
                    }
                return {"success": True, "output": output}

            elif conn_type == "SERIAL":
                ser = handler
                ser.write(f"{command}\n".encode("utf-8"))
                time.sleep(1)
                raw = ser.read_all().decode("utf-8", errors="ignore")
                return {"success": True, "output": raw}

        except Exception as e:
            err_msg = str(e).lower()
            if retry and any(term in err_msg for term in ("closed", "eof", "broken pipe", "connection reset", "socket", "timeout")):
                print(f"[ConnectionManager] Connection dropped for {device_id} ({e}), reconnecting...")
                self.disconnect(device_id)
                if self._ensure_connection(device_id):
                    return self.send_command(device_id, command, use_textfsm=use_textfsm, retry=False)
            return {"success": False, "output": f"Error: {str(e)}"}

        return {"success": False, "output": "Unknown connection type"}

    def send_config(self, device_id: str, commands: list, retry: bool = True) -> dict:
        """
        ส่ง configuration commands ไปยัง device
        ใช้ send_config_set() สำหรับ SSH/Telnet
        ตรวจ IOS syntax error ใน output
        มี auto-reconnect ถ้า session หลุด
        """
        if device_id not in self.pool:
            if not self._ensure_connection(device_id):
                return {
                    "success": False,
                    "output": f"Device '{device_id}' ยังไม่ได้เชื่อมต่อ",
                    "message": f"Device '{device_id}' ยังไม่ได้เชื่อมต่อ"
                }

        entry = self.pool[device_id]
        conn_type = entry["type"]
        handler = entry["handler"]

        try:
            if conn_type in ("SSH", "TELNET"):
                output = handler.send_config_set(commands)
                # ตรวจ IOS syntax error
                if re.search(r"% Invalid input detected at", output):
                    return {
                        "success": False,
                        "output": output,
                        "error": "IOS ตรวจพบ syntax error ในคำสั่ง — ตรวจสอบ command ที่ส่งไป",
                        "message": "IOS ตรวจพบ syntax error ในคำสั่ง"
                    }
                return {"success": True, "output": output, "message": "ตั้งค่าสำเร็จ"}

            elif conn_type == "SERIAL":
                ser = handler
                output_parts = []
                for cmd in commands:
                    ser.write(f"{cmd}\n".encode("utf-8"))
                    time.sleep(0.5)
                    output_parts.append(ser.read_all().decode("utf-8", errors="ignore"))
                return {"success": True, "output": "\n".join(output_parts), "message": "ตั้งค่าสำเร็จ"}

        except Exception as e:
            err_msg = str(e).lower()
            if retry and any(term in err_msg for term in ("closed", "eof", "broken pipe", "connection reset", "socket", "timeout")):
                print(f"[ConnectionManager] Connection dropped for {device_id} ({e}), reconnecting...")
                self.disconnect(device_id)
                if self._ensure_connection(device_id):
                    return self.send_config(device_id, commands, retry=False)
            return {"success": False, "output": f"Error: {str(e)}", "message": f"ส่งคำสั่งล้มเหลว: {str(e)}"}

        return {"success": False, "output": "Unknown connection type", "message": "Unknown connection type"}

    def disconnect(self, device_id: str) -> dict:
        """ปิด connection และลบออกจาก pool"""
        if device_id not in self.pool:
            return {"success": False, "message": f"Device '{device_id}' ไม่ได้อยู่ใน pool"}
        try:
            entry = self.pool[device_id]
            if entry["type"] in ("SSH", "TELNET"):
                try:
                    entry["handler"].disconnect()
                except Exception:
                    pass
            elif entry["type"] == "SERIAL":
                try:
                    entry["handler"].close()
                except Exception:
                    pass
            del self.pool[device_id]
            return {"success": True, "message": f"Disconnected {device_id}"}
        except Exception as e:
            self.pool.pop(device_id, None)
            return {"success": False, "message": str(e)}

    def disconnect_all(self):
        """ปิด connection ทั้งหมดใน pool"""
        for device_id in list(self.pool.keys()):
            self.disconnect(device_id)

    def is_connected(self, device_id: str) -> bool:
        if device_id in self.pool:
            return True
        return self._ensure_connection(device_id)

    def get_connected_devices(self) -> list:
        return [{"id": k, "type": v["type"]} for k, v in self.pool.items()]

    def setup_ssh(
        self,
        device_id: str,
        domain_name: str,
        key_size: int = 1024,
        username: str = "cisco",
        password: str = "cisco",
    ) -> dict:
        """SSH Setup Wizard: domain-name → RSA key (interactive) → local user + vty ssh"""
        if device_id not in self.pool:
            return {"success": False, "output": f"Device '{device_id}' ยังไม่ได้เชื่อมต่อ"}
        entry = self.pool[device_id]
        if entry["type"] not in ("SSH", "TELNET"):
            return {"success": False, "output": "SSH setup ใช้ได้กับ SSH/Telnet session เท่านั้น"}
        conn = entry["handler"]
        try:
            output_parts = []
            output_parts.append(conn.send_config_set([f"ip domain-name {domain_name}"]))
            conn.config_mode()
            rsa_out = conn.send_command_timing("crypto key generate rsa", delay_factor=2, max_loops=30)
            output_parts.append(rsa_out)
            prompt_lower = rsa_out.lower()
            if "how many bits" in prompt_lower or "modulus" in prompt_lower:
                rsa_out2 = conn.send_command_timing(str(key_size), delay_factor=2, max_loops=60)
                output_parts.append(rsa_out2)
            tail_cmds = [
                f"username {username} privilege 15 password {password}",
                "line vty 0 4",
                "login local",
                "transport input ssh",
            ]
            output_parts.append(conn.send_config_set(tail_cmds))
            conn.exit_config_mode()
            full = "\n".join(output_parts)
            if re.search(r"% Invalid input detected at", full):
                return {
                    "success": False,
                    "output": full,
                    "error": "IOS ตรวจพบ syntax error ระหว่าง SSH setup",
                }
            return {"success": True, "output": full}
        except Exception as e:
            return {"success": False, "output": str(e)}


def parse_interface_status(show_output: str, interface_name: str) -> str:
    """Parse admin/oper status จาก show interfaces <name> หรือ brief"""
    if not show_output:
        return "unknown"
    name_lower = interface_name.lower()
    for line in show_output.splitlines():
        if name_lower in line.lower() and "administratively down" in line.lower():
            return "administratively down"
    block = show_output.lower()
    if "administratively down" in block:
        return "administratively down"
    if re.search(r"\bis up\b", block) and re.search(r"line protocol is up", block):
        return "up"
    if re.search(r"\bis down\b", block):
        return "down"
    return "unknown"


def parse_ip_interface_brief(output) -> list:
    """
    คืน list ของ dict: name, ip, status (up|down), protocol
    รองรับ TextFSM list หรือ raw text
    """
    rows = []
    if isinstance(output, list):
        for row in output:
            intf = row.get("intf") or row.get("interface") or ""
            ip = row.get("ipaddr") or row.get("ip_address") or "unassigned"
            status_raw = (row.get("status") or row.get("admin") or "").lower()
            proto = row.get("proto") or row.get("protocol") or ""
            if "administratively down" in status_raw:
                status = "down"
            elif "up" in status_raw:
                status = "up"
            else:
                status = "down"
            rows.append({
                "name": intf,
                "ip": ip if ip not in ("", "-") else "unassigned",
                "status": status,
                "protocol": proto or ("up" if status == "up" else "down"),
            })
        return rows

    if not isinstance(output, str):
        return rows

    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("-") or "Interface" in line and "IP-Address" in line:
            continue
        parts = line.split()
        if len(parts) < 6:
            continue
        intf = parts[0]
        ip = parts[1]
        if not re.match(r"[\w./-]+", intf):
            continue
        status_field = " ".join(parts[4:6]).lower() if len(parts) >= 6 else ""
        if "administratively down" in status_field:
            status = "down"
        elif parts[4].lower() == "up":
            status = "up"
        else:
            status = "down"
        proto = parts[5] if len(parts) > 5 else ""
        rows.append({
            "name": intf,
            "ip": ip,
            "status": status,
            "protocol": proto,
        })
    return rows
