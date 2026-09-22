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
        return json.load(f)


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
                }
                conn = ConnectHandler(**params)
                conn.enable()
                self.pool[device_id] = {"handler": conn, "type": "SSH"}
                return {"success": True, "message": f"SSH เชื่อมต่อ {ip} สำเร็จ"}

            elif conn_type == "TELNET":
                params = {
                    "device_type": "cisco_ios_telnet",
                    "ip": ip,
                    "username": device_params.get("username", "cisco"),
                    "password": device_params.get("password", "cisco"),
                    "secret":   device_params.get("secret", device_params.get("password", "cisco")),
                    "port":     int(device_params.get("port", 23)),
                }
                conn = ConnectHandler(**params)
                conn.enable()
                self.pool[device_id] = {"handler": conn, "type": "TELNET"}
                return {"success": True, "message": f"Telnet เชื่อมต่อ {ip} สำเร็จ"}

            elif conn_type == "SERIAL":
                if not PYSERIAL_AVAILABLE:
                    return {"success": False, "message": "PySerial ไม่ได้ติดตั้ง (pip install pyserial)"}
                serial_port = device_params.get("serial_port", "COM1")
                baudrate = int(device_params.get("baudrate", 9600))
                ser = serial.Serial(serial_port, baudrate=baudrate, timeout=2)
                self.pool[device_id] = {"handler": ser, "type": "SERIAL"}
                return {"success": True, "message": f"Serial เชื่อมต่อ {serial_port} ({baudrate} baud) สำเร็จ"}

            else:
                return {"success": False, "message": f"ไม่รองรับ connection_type: {conn_type}"}

        except NetmikoAuthenticationException:
            return {"success": False, "message": "Authentication failed — username/password ไม่ถูกต้อง"}
        except NetmikoTimeoutException:
            return {"success": False, "message": f"Connection timeout — ไม่ได้รับการตอบกลับจาก {ip}"}
        except Exception as e:
            return {"success": False, "message": f"เชื่อมต่อล้มเหลว: {str(e)}"}

    def send_command(self, device_id: str, command: str, use_textfsm: bool = False) -> dict:
        """
        ส่ง show command ไปยัง device
        use_textfsm=True เพื่อ parse output เป็น structured data (สำหรับ CDP/LLDP)
        """
        if device_id not in self.pool:
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
                return {"success": True, "output": output if isinstance(output, str) else json.dumps(output)}

            elif conn_type == "SERIAL":
                ser = handler
                ser.write(f"{command}\n".encode("utf-8"))
                time.sleep(1)
                raw = ser.read_all().decode("utf-8", errors="ignore")
                return {"success": True, "output": raw}

        except Exception as e:
            return {"success": False, "output": f"Error: {str(e)}"}

        return {"success": False, "output": "Unknown connection type"}

    def send_config(self, device_id: str, commands: list) -> dict:
        """
        ส่ง configuration commands ไปยัง device
        ใช้ send_config_set() สำหรับ SSH/Telnet
        ตรวจ IOS syntax error ใน output
        """
        if device_id not in self.pool:
            return {"success": False, "output": f"Device '{device_id}' ยังไม่ได้เชื่อมต่อ"}

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
                        "error": "IOS ตรวจพบ syntax error ในคำสั่ง — ตรวจสอบ command ที่ส่งไป"
                    }
                return {"success": True, "output": output}

            elif conn_type == "SERIAL":
                ser = handler
                output_parts = []
                for cmd in commands:
                    ser.write(f"{cmd}\n".encode("utf-8"))
                    time.sleep(0.5)
                    output_parts.append(ser.read_all().decode("utf-8", errors="ignore"))
                return {"success": True, "output": "\n".join(output_parts)}

        except Exception as e:
            return {"success": False, "output": f"Error: {str(e)}"}

        return {"success": False, "output": "Unknown connection type"}

    def disconnect(self, device_id: str) -> dict:
        """ปิด connection และลบออกจาก pool"""
        if device_id not in self.pool:
            return {"success": False, "message": f"Device '{device_id}' ไม่ได้อยู่ใน pool"}
        try:
            entry = self.pool[device_id]
            if entry["type"] in ("SSH", "TELNET"):
                entry["handler"].disconnect()
            elif entry["type"] == "SERIAL":
                entry["handler"].close()
            del self.pool[device_id]
            return {"success": True, "message": f"Disconnected {device_id}"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def disconnect_all(self):
        """ปิด connection ทั้งหมดใน pool"""
        for device_id in list(self.pool.keys()):
            self.disconnect(device_id)

    def is_connected(self, device_id: str) -> bool:
        return device_id in self.pool

    def get_connected_devices(self) -> list:
        return [{"id": k, "type": v["type"]} for k, v in self.pool.items()]
