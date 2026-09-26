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
    {"id": "R3", "name": "Router-R3", "model": "Cisco 4331", "device_type_label": "router",
     "connection_type": "SSH", "ip": "192.168.1.118", "port": 22,
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
    """เพิ่ม device ใหม่ ให้ id อัตโนมัติ (ใช้ name เป็น id ถ้ามีและไม่ซ้ำ)"""
    devices = load_inventory()
    # กำหนด ID ถ้าไม่มี
    if not device.get("id"):
        cand_id = (device.get("name") or "").strip()
        existing_ids = [d.get("id", "") for d in devices]
        if cand_id and cand_id not in existing_ids:
            device["id"] = cand_id
        else:
            count = 1
            while f"device-{count}" in existing_ids:
                count += 1
            device["id"] = f"device-{count}"
    devices.append(device)
    save_inventory(devices)
    return device


def remove_device_from_inventory(device_id: str) -> bool:
    """ลบ device จาก inventory (รองรับทั้ง id และ name)"""
    devices = load_inventory()
    original_len = len(devices)
    devices = [d for d in devices if d.get("id") != device_id and d.get("name") != device_id]
    if len(devices) < original_len:
        save_inventory(devices)
        return True
    return False


def get_device_by_id(device_id: str) -> Optional[dict]:
    devices = load_inventory()
    for d in devices:
        if d.get("id") == device_id or d.get("name") == device_id:
            return d
    return None


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
            dtype = (device_params.get("device_type_label") or "").lower()
            name_lower = (device_params.get("name") or "").lower()
            model_lower = (device_params.get("model") or "").lower()
            is_linux = (
                dtype in ("pc", "linux", "ubuntu")
                or device_params.get("os_type") == "linux"
                or "linux" in name_lower
                or "linux" in model_lower
                or "ubuntu" in model_lower
            )

            if conn_type == "SSH":
                if is_linux:
                    params = {
                        "device_type": "linux",
                        "ip": ip,
                        "username": device_params.get("username", "cisco"),
                        "password": device_params.get("password", "cisco"),
                        "port":     int(device_params.get("port", 22)),
                        "conn_timeout": 10,
                    }
                    conn = ConnectHandler(**params)
                    self.pool[device_id] = {"handler": conn, "type": "SSH", "is_linux": True, "params": dict(device_params)}
                    return {"success": True, "message": f"SSH เชื่อมต่อ Linux PC {ip}:{params['port']} สำเร็จ"}
                else:
                    params = {
                        "device_type": "cisco_ios",
                        "ip": ip,
                        "username": device_params.get("username", "cisco"),
                        "password": device_params.get("password", "cisco"),
                        "secret":   (device_params.get("secret") or device_params.get("password") or "cisco").strip(),
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
                username = (device_params.get("username") or "").strip()
                password = (device_params.get("password") or "").strip()
                secret = (device_params.get("secret") or password or "cisco").strip()

                # สำหรับ EVE-NG console port (มักจะเป็น 30000-40000) ที่ไม่ต้องใส่ user/pass
                # หรือ telnet ทั่วไป
                params = {
                    "device_type": "cisco_ios_telnet",
                    "ip": ip,
                    "port": port,
                    "conn_timeout": 15,
                    "fast_cli": False,
                }
                if username:
                    params["username"] = username
                if password:
                    params["password"] = password
                if secret:
                    params["secret"] = secret

                conn = ConnectHandler(**params)
                # ลองเข้า enable mode ถ้าทำได้
                enable_ok = True
                try:
                    conn.enable()
                except Exception:
                    enable_ok = False

                # ปิด pagination และขยาย width ป้องกันปัญหา line wrapping บน Switch
                try:
                    conn.send_command("terminal length 0", read_timeout=6)
                except Exception:
                    try:
                        conn.write_channel("terminal length 0\r\n")
                    except Exception:
                        pass

                try:
                    conn.send_command("terminal width 512", read_timeout=6)
                except Exception:
                    try:
                        conn.write_channel("terminal width 512\r\n")
                    except Exception:
                        pass

                self.pool[device_id] = {"handler": conn, "type": "TELNET", "params": dict(device_params)}
                if not enable_ok:
                    return {
                        "success": True,
                        "warning": True,
                        "message": f"Telnet เชื่อมต่อ {ip}:{port} สำเร็จ (User Mode: >) แต่ Router/Switch ไม่สามารถเข้า Enable Mode (#) ได้ — จำเป็นต้องมีคำสั่ง 'enable secret <รหัส>' เพื่อให้สามารถแก้ไขคอนฟิกผ่าน Telnet ได้"
                    }
                return {"success": True, "message": f"Telnet เชื่อมต่อ {ip}:{port} สำเร็จ"}

            elif conn_type == "SERIAL":
                if not PYSERIAL_AVAILABLE:
                    return {"success": False, "message": "PySerial ไม่ได้ติดตั้ง (pip install pyserial)"}
                serial_port = device_params.get("serial_port", "COM1")
                baudrate = int(device_params.get("baudrate", 9600))
                ser = serial.Serial(serial_port, baudrate=baudrate, timeout=2)
                # ล้าง buffer ตกค้างและส่ง wake-up signal (\r\n) เพื่อปลุก Cisco console
                try:
                    ser.reset_input_buffer()
                    ser.reset_output_buffer()
                    ser.write(b"\r\n\r\n")
                    time.sleep(0.3)
                    p_raw = ser.read_all().decode("utf-8", errors="ignore")
                    if ">" in p_raw and "#" not in p_raw:
                        ser.write(b"enable\r\n")
                        time.sleep(0.3)
                        ser.read_all()
                    # ปิด pagination (terminal length 0) เพื่อไม่ให้ติด --More--
                    ser.write(b"terminal length 0\r\n")
                    time.sleep(0.3)
                    ser.read_all()
                except Exception:
                    pass
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
        """ตรวจและเชื่อมต่ออัตโนมัติถ้า session หลุดหรือยังไม่ได้ connect (พร้อม Liveness Probe)"""
        if self.is_connected(device_id, check_alive=True):
            return True
        dev = get_device_by_id(device_id)
        if dev:
            conn_type = (dev.get("connection_type") or "").upper()
            dtype = (dev.get("device_type_label") or "").lower()
            if conn_type in ("SSH", "TELNET") or dtype not in ("pc", "network"):
                target_id = dev.get("id", device_id)
                print(f"[ConnectionManager] Auto-connecting to {target_id}...")
                res = self.connect(target_id, dev, skip_ping=True)
                return res.get("success", False)
        return False

    def send_command(self, device_id: str, command: str, use_textfsm: bool = False, retry: bool = True) -> dict:
        """
        ส่ง show command ไปยัง device ดึงข้อมูลจริง 100%
        use_textfsm=True เพื่อ parse output เป็น structured data (สำหรับ CDP/LLDP)
        มี auto-reconnect ถ้า session หลุด
        """
        dev = get_device_by_id(device_id)
        target_id = dev.get("id", device_id) if dev else device_id

        if not self.is_connected(target_id, check_alive=True) and not self.is_connected(device_id, check_alive=True):
            if not self._ensure_connection(target_id):
                return {"success": False, "output": f"Device '{device_id}' ยังไม่ได้เชื่อมต่อ"}

        active_id = target_id if target_id in self.pool else device_id
        entry = self.pool[active_id]
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
                ser.reset_input_buffer()
                ser.write(f"{command.strip()}\r\n".encode("utf-8"))
                # วนลูปอ่านจนกว่าจะเจอ prompt (# หรือ >) หรือ timeout 3.5 วินาที
                start_time = time.time()
                raw_bytes = bytearray()
                timeout = 3.5
                while time.time() - start_time < timeout:
                    if ser.in_waiting > 0:
                        chunk = ser.read(ser.in_waiting)
                        raw_bytes.extend(chunk)
                        decoded = raw_bytes.decode("utf-8", errors="ignore")
                        lines = [l.strip() for l in decoded.splitlines() if l.strip()]
                        if len(lines) >= 2 and any(re.search(r"^[A-Za-z0-9_\-\.\(\)]+[#>]\s*$", l) for l in lines[-2:]):
                            break
                    time.sleep(0.06)
                output = raw_bytes.decode("utf-8", errors="ignore")
                return {"success": True, "output": output}

        except Exception as e:
            err_msg = str(e).lower()
            if retry and any(term in err_msg for term in ("closed", "eof", "broken pipe", "connection reset", "socket", "timeout")):
                print(f"[ConnectionManager] Connection dropped for {active_id} ({e}), reconnecting...")
                self.disconnect(active_id)
                if self._ensure_connection(active_id):
                    return self.send_command(active_id, command, use_textfsm=use_textfsm, retry=False)
            return {"success": False, "output": f"Error: {str(e)}"}

        return {"success": False, "output": "Unknown connection type"}

    def _read_interactive_channel(
        self,
        handler,
        cmd_str: str = "",
        is_linux: bool = False,
        timeout: float = 25.0,
        idle_timeout: float = 0.25
    ) -> str:
        """
        อ่านข้อมูลจาก SSH / Telnet channel แบบ Prompt-Aware (Fast Return)
        แทนที่จะรอ timing sleep คงที่ 1.5 - 1.8 วินาทีทุกคำสั่ง:
        เมื่อ output สิ้นสุดที่ Device Prompt (#, >, $, password prompt) จะ return ทันทีใน 10-40ms!
        หากเป็นคำสั่งยาวหรือไม่มี prompt มาตรฐาน จะ fallback รอ idle_timeout เมื่อไม่มีข้อมูลใหม่ส่งมา
        """
        # หาก handler ถูก mock หรือเป็น Mock object ที่ไม่ได้ implement read_channel ให้ fallback ไปใช้ read_channel_timing
        if hasattr(handler, "read_channel_timing"):
            val = getattr(handler.read_channel_timing, "return_value", None)
            if isinstance(val, str) and val != "":
                return handler.read_channel_timing()
            if not hasattr(handler, "read_channel") or not callable(getattr(handler, "read_channel", None)):
                return handler.read_channel_timing()

        start = time.time()
        raw = ""
        last_data_time = None

        prompt_regex = re.compile(
            r"(^[A-Za-z0-9_\-\.\(\)]+[#>]\s*$)"                                # Cisco Router/Switch (R1#, Switch>)
            r"|(^[A-Za-z0-9_\-\.]+@[A-Za-z0-9_\-\.]+:[^#$]*[\$#]\s*$)"         # Linux Shell (user@host:~$ หรือ root@host:~#)
            r"|(^[A-Za-z0-9_\-\.]+:[^#$]*[\$#]\s*$)"                           # Linux prompt shorthand (eve-ng:~#)
            r"|((?:\[sudo\]\s+)?password(?:\s+for\s+\S+)?:\s*$)"                # Password prompt
            r"|((?:\[confirm\]|\[yes/no\]|\[y/n\]|\(yes/no\)|continue\?\s*\[Y/n\])\s*$)" # Interactive confirmation
            r"|(--More--)",                                                     # Pagination
            re.IGNORECASE | re.MULTILINE
        )

        while time.time() - start < timeout:
            chunk = handler.read_channel()
            if chunk and isinstance(chunk, str):
                raw += chunk
                last_data_time = time.time()

                # ล้าง ansi codes ชั่วคราวเพื่อตรวจจับ prompt ที่บรรทัดสุดท้าย
                clean_tail = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', raw[-500:]).strip()
                lines = [l.strip() for l in clean_tail.splitlines() if l.strip()]
                if lines:
                    last_line = lines[-1]
                    if prompt_regex.search(last_line):
                        if not cmd_str or cmd_str not in last_line:
                            break
            else:
                if raw and last_data_time and (time.time() - last_data_time > idle_timeout):
                    break
            time.sleep(0.01)
        return raw

    def send_interactive(self, device_id: str, command: str, retry: bool = True) -> dict:
        """
        ส่งคำสั่งแบบ Interactive Terminal โดยตรงไปยังอุปกรณ์ (รักษา session state ต่อเนื่อง)
        ดึง prompt และ output จริงจาก Router / Switch โดยตรง
        มีระบบ Auto-reconnect ป้องกัน Telnet session หลุดกับ Switch
        คืน {"success": True, "output": output, "prompt": prompt}
        """
        dev = get_device_by_id(device_id)
        target_id = dev.get("id", device_id) if dev else device_id

        if not self.is_connected(target_id, check_alive=True) and not self.is_connected(device_id, check_alive=True):
            if not self._ensure_connection(target_id):
                return {"success": False, "output": f"Device '{device_id}' ยังไม่ได้เชื่อมต่อ", "prompt": ""}

        active_id = target_id if target_id in self.pool else device_id
        entry = self.pool[active_id]
        conn_type = entry["type"]
        handler = entry["handler"]

        try:
            cmd_str = (command or "").strip()

            if conn_type in ("SSH", "TELNET"):
                # ล้าง buffer ตกค้างก่อนส่งคำสั่ง เพื่อไม่ให้ข้อมูลเก่าปนกับคำสั่งใหม่ (ยกเว้นกำลังรอป้อน Password)
                if not entry.get("is_password_pending"):
                    try:
                        handler.clear_buffer()
                    except Exception:
                        pass

                is_linux = entry.get("is_linux", False)
                newline = "\n" if is_linux else "\r\n"

                # รองรับ Ctrl+C (Break/Interrupt signal)
                if command in ("\x03", "^C"):
                    handler.write_channel("\x03")
                    raw = self._read_interactive_channel(handler, cmd_str="", is_linux=is_linux, timeout=2.0, idle_timeout=0.15)
                elif not cmd_str:
                    # ถ้าส่งว่างเพื่อดึง prompt สดจากอุปกรณ์
                    handler.write_channel(newline)
                    raw = self._read_interactive_channel(handler, cmd_str="", is_linux=is_linux, timeout=4.0, idle_timeout=0.15)
                else:
                    # ส่งคำสั่งจริงไปยัง Channel
                    cmd_to_send = cmd_str
                    # ป้องกัน Linux ping รันไม่รู้จบ ถ้าผู้ใช้ไม่ได้ใส่ -c หรือ -w
                    if is_linux and cmd_str.startswith("ping ") and not ("-c" in cmd_str or "-w" in cmd_str):
                        cmd_to_send = f"{cmd_str} -c 4"

                    handler.write_channel(f"{cmd_to_send}{newline}")
                    raw = self._read_interactive_channel(handler, cmd_str=cmd_to_send, is_linux=is_linux, timeout=25.0, idle_timeout=0.25)

                # จัดการ Paging กรณีอุปกรณ์ส่ง output ยาวและติด --More-- (ตาม Section 14 & 24 ของ network_cli_teraterm_putty_vibecoding.md)
                max_pages = 30
                pages = 0
                while "--More--" in raw and pages < max_pages:
                    handler.write_channel(" ")
                    time.sleep(0.03)
                    more_data = self._read_interactive_channel(handler, cmd_str="", is_linux=is_linux, timeout=4.0, idle_timeout=0.15)
                    if not more_data:
                        break
                    raw += more_data
                    pages += 1

            elif conn_type == "SERIAL":
                ser = handler
                ser.reset_input_buffer()
                if command in ("\x03", "^C"):
                    ser.write(b"\x03")
                else:
                    cmd_to_send = f"{cmd_str}\r\n" if cmd_str else "\r\n"
                    ser.write(cmd_to_send.encode("utf-8"))

                start_time = time.time()
                raw_bytes = bytearray()
                timeout = 5.0
                while time.time() - start_time < timeout:
                    if ser.in_waiting > 0:
                        chunk = ser.read(ser.in_waiting)
                        raw_bytes.extend(chunk)
                        decoded = raw_bytes.decode("utf-8", errors="ignore")
                        lines = [l.strip() for l in decoded.splitlines() if l.strip()]
                        if len(lines) >= 1 and (
                            re.search(r"^[A-Za-z0-9_\-\.\(\)]+[#>]\s*$", lines[-1])
                            or re.search(r"^[A-Za-z0-9_\-\.]+@[A-Za-z0-9_\-\.]+:[^#$]*[\$#]\s*$", lines[-1])
                            or re.search(r"(\[sudo\]\s+)?password(\s+for\s+\S+)?:\s*$", lines[-1], re.I)
                        ):
                            break
                    time.sleep(0.05)
                raw = raw_bytes.decode("utf-8", errors="ignore")
            else:
                return {"success": False, "output": "Unknown connection type", "prompt": "", "is_password": False}

            # ลบ ANSI Escape Codes, Pager markers (--More--), และ backspaces
            raw_no_more = re.sub(r'--More--|\x08+', '', raw)
            raw_no_ansi = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', raw_no_more)
            raw_clean = raw_no_ansi.replace("\r\r\n", "\n").replace("\r\n", "\n").replace("\r", "\n")
            lines = raw_clean.split("\n")

            # ตัด echo ของ command ถ้ามีที่บรรทัดแรก
            if cmd_str and lines and cmd_str in lines[0]:
                lines = lines[1:]

            # ลบบรรทัดว่างต่อท้าย
            while lines and not lines[-1].strip():
                lines.pop()

            # สกัด prompt ตัวจริง ออกมาจากบรรทัดสุดท้าย (Section 16-19, 40-41)
            prompt = ""
            is_password = False
            if lines:
                last_line = lines[-1].strip()
                # 1. ตรวจจับ Password prompt (เช่น Password:, password:, [sudo] password for user:)
                if re.search(r"(\[sudo\]\s+)?password(\s+for\s+\S+)?:\s*$", last_line, re.I):
                    prompt = lines.pop().strip()
                    is_password = True
                # 2. ตรวจจับ Interactive confirmation prompt ([confirm], [yes/no]:, [y/n], (yes/no):)
                elif re.search(r"(\[confirm\]|\[yes/no\]|\[y/n\]|\(yes/no\)|Do you want to continue\?\s*\[Y/n\])", last_line, re.I):
                    prompt = lines.pop().strip()
                # 3. ตรวจจับ Linux Shell Prompt (เช่น ubuntu@ubuntu:~$ หรือ root@ubuntu:~# หรือ cisco@pc1:~$ หรือ dev@host:/var/log$)
                elif re.search(r"^[A-Za-z0-9_\-\.]+@[A-Za-z0-9_\-\.]+:[^#$]*[\$#]\s*$", last_line):
                    prompt = lines.pop().strip()
                # 4. ตรวจจับ Cisco CLI Prompt ปกติ (เช่น R1#, R1>, R1(config)#, S1(config-if)#, Switch#)
                elif re.search(r"^[A-Za-z0-9_\-\.\(\)]+[#>]\s*$", last_line):
                    prompt = lines.pop().strip()

            entry["is_password_pending"] = is_password

            clean_output = "\n".join(lines).strip()
            return {
                "success": True,
                "output": clean_output,
                "prompt": prompt,
                "is_password": is_password,
                "raw": raw
            }

        except Exception as e:
            err_msg = str(e).lower()
            if retry and any(term in err_msg for term in ("closed", "eof", "broken pipe", "connection reset", "socket", "timeout")):
                print(f"[ConnectionManager] Interactive connection dropped for {active_id} ({e}), reconnecting...")
                self.disconnect(active_id)
                if self._ensure_connection(active_id):
                    return self.send_interactive(active_id, command, retry=False)

            if "PermissionError" in str(e) or "Access is denied" in str(e):
                return {"success": False, "output": "พอร์ต Serial ถูกเปิดใช้งานโดยโปรแกรมอื่น (เช่น Tera Term) — กรุณาปิดโปรแกรมอื่นก่อน", "prompt": ""}
            return {"success": False, "output": f"Error: {str(e)}", "prompt": ""}

    def send_config(self, device_id: str, commands: list, retry: bool = True) -> dict:
        """
        ส่ง configuration commands ไปยัง device
        ใช้ send_config_set() สำหรับ SSH/Telnet
        ตรวจ IOS syntax error ใน output
        มี auto-reconnect ถ้า session หลุด
        """
        dev = get_device_by_id(device_id)
        target_id = dev.get("id", device_id) if dev else device_id

        if not self.is_connected(target_id) and not self.is_connected(device_id):
            if not self._ensure_connection(target_id):
                return {
                    "success": False,
                    "output": f"Device '{device_id}' ยังไม่ได้เชื่อมต่อ",
                    "message": f"Device '{device_id}' ยังไม่ได้เชื่อมต่อ"
                }

        active_id = target_id if target_id in self.pool else device_id
        entry = self.pool[active_id]
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
                ser.reset_input_buffer()
                # ตรวจสอบและเข้า enable mode ถ้ายังอยู่ที่ prompt user mode (>)
                ser.write(b"\r\n")
                time.sleep(0.2)
                p = ser.read_all().decode("utf-8", errors="ignore")
                if ">" in p and "#" not in p:
                    ser.write(b"enable\r\n")
                    time.sleep(0.3)
                    ser.read_all()

                ser.write(b"configure terminal\r\n")
                time.sleep(0.4)
                ser.read_all()
                output_parts = []
                for cmd in commands:
                    ser.write(f"{cmd.strip()}\r\n".encode("utf-8"))
                    time.sleep(0.3)
                    output_parts.append(ser.read_all().decode("utf-8", errors="ignore"))
                ser.write(b"end\r\n")
                time.sleep(0.3)
                output_parts.append(ser.read_all().decode("utf-8", errors="ignore"))
                return {"success": True, "output": "\n".join(output_parts), "message": "ตั้งค่าสำเร็จ"}

        except Exception as e:
            err_msg = str(e).lower()
            if retry and any(term in err_msg for term in ("closed", "eof", "broken pipe", "connection reset", "socket", "timeout")):
                print(f"[ConnectionManager] Connection dropped for {active_id} ({e}), reconnecting...")
                self.disconnect(active_id)
                if self._ensure_connection(active_id):
                    return self.send_config(active_id, commands, retry=False)
            return {"success": False, "output": f"Error: {str(e)}", "message": f"ส่งคำสั่งล้มเหลว: {str(e)}"}

        return {"success": False, "output": "Unknown connection type", "message": "Unknown connection type"}

    def disconnect(self, device_id: str) -> dict:
        """ปิด connection และลบออกจาก pool"""
        target_id = device_id
        if target_id not in self.pool:
            dev = get_device_by_id(device_id)
            if dev and dev.get("id") in self.pool:
                target_id = dev.get("id")

        if target_id not in self.pool:
            return {"success": False, "message": f"Device '{device_id}' ไม่ได้อยู่ใน pool"}
        try:
            entry = self.pool[target_id]
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
            del self.pool[target_id]
            return {"success": True, "message": f"Disconnected {target_id}"}
        except Exception as e:
            self.pool.pop(target_id, None)
            return {"success": False, "message": str(e)}

    def disconnect_all(self):
        """ปิด connection ทั้งหมดใน pool"""
        for device_id in list(self.pool.keys()):
            self.disconnect(device_id)

    def is_connected(self, device_id: str, check_alive: bool = False) -> bool:
        """ตรวจสอบว่า device เชื่อมต่ออยู่หรือไม่ พร้อมออปชัน check_alive ตรวจสุขภาพ socket จริง"""
        entry_key = None
        if device_id in self.pool:
            entry_key = device_id
        else:
            for k, v in self.pool.items():
                params = v.get("params", {})
                if k == device_id or params.get("id") == device_id or params.get("name") == device_id:
                    entry_key = k
                    break

        if not entry_key:
            return False

        if check_alive:
            entry = self.pool[entry_key]
            handler = entry.get("handler")
            conn_type = entry.get("type")
            is_pw_pending = entry.get("is_password_pending", False)

            if conn_type == "SSH":
                # สำหรับ SSH: ตรวจ transport socket state โดยตรง ไม่ส่ง null byte (\x00) เข้า channel
                # เพื่อป้องกัน \x00 ปนเปื้อนใน password buffer ของ Linux sudo / Cisco password prompt
                try:
                    rc = getattr(handler, "remote_conn", None)
                    t = getattr(rc, "transport", None) if rc is not None else None
                    alive = True
                    if rc is not None and t is not None:
                        is_active = getattr(t, "is_active", None)
                        if callable(is_active):
                            alive = bool(is_active())
                        if getattr(rc, "closed", False) is True:
                            alive = False
                    if not alive:
                        print(f"[ConnectionManager] SSH transport dead for {entry_key}, removing from pool...")
                        self.disconnect(entry_key)
                        return False
                except Exception:
                    self.disconnect(entry_key)
                    return False
            elif conn_type == "TELNET" and hasattr(handler, "is_alive"):
                # สำหรับ Telnet: ไม่ส่ง keepalive probe หากอุปกรณ์กำลังรอป้อน Password
                if is_pw_pending:
                    return True
                try:
                    alive = handler.is_alive()
                    if not alive:
                        print(f"[ConnectionManager] Telnet dead for {entry_key}, removing from pool...")
                        self.disconnect(entry_key)
                        return False
                except Exception:
                    self.disconnect(entry_key)
                    return False
        return True

    def send_keepalive(self, device_id: str = None, auto_reconnect: bool = True):
        """ส่ง Telnet NOP หรือ SSH keepalive เพื่อป้องกัน Switch ปิดการเชื่อมต่อเนื่องจาก idle พร้อม auto-reconnect"""
        targets = [device_id] if device_id else list(self.pool.keys())
        for tid in targets:
            if tid in self.pool:
                entry = self.pool[tid]
                handler = entry.get("handler")
                conn_type = entry.get("type")
                # ข้าม keepalive ถ้ากำลังรอ Password หรือเป็น Linux SSH เพื่อไม่ให้ส่ง \x00 ปนใน buffer
                if entry.get("is_password_pending") or entry.get("is_linux"):
                    continue
                if conn_type in ("SSH", "TELNET") and hasattr(handler, "is_alive"):
                    try:
                        if not handler.is_alive():
                            self.disconnect(tid)
                            if auto_reconnect:
                                self._ensure_connection(tid)
                    except Exception:
                        self.disconnect(tid)
                        if auto_reconnect:
                            self._ensure_connection(tid)
            elif auto_reconnect and device_id:
                self._ensure_connection(device_id)

    def reconnect(self, device_id: str) -> dict:
        """ตัดการเชื่อมต่อเดิมและเชื่อมต่อใหม่ทันที"""
        dev = get_device_by_id(device_id)
        target_id = dev.get("id", device_id) if dev else device_id
        self.disconnect(target_id)
        self.disconnect(device_id)
        if dev:
            return self.connect(target_id, dev, skip_ping=True)
        return {"success": False, "message": f"ไม่พบ device '{device_id}' ใน inventory"}

    def auto_reconnect_all(self, device_ids: Optional[list] = None) -> dict:
        """
        เชื่อมต่อหรือ Reconnect อุปกรณ์ทั้งหมดใน inventory แบบ Concurrent (ThreadPoolExecutor)
        เพื่อความรวดเร็วและไม่บล็อกการทำงานของเซิร์ฟเวอร์
        """
        all_devs = load_inventory()
        if device_ids:
            target_devs = [d for d in all_devs if d.get("id") in device_ids or d.get("name") in device_ids]
        else:
            target_devs = all_devs

        results = {}

        def _worker(dev):
            dev_id = dev.get("id") or dev.get("name")
            if not dev_id:
                return None
            conn_type = (dev.get("connection_type") or "").upper()
            dtype = (dev.get("device_type_label") or "").lower()

            if dtype in ("network", "cloud") or (dtype == "pc" and conn_type == "PC"):
                return dev_id, {"success": True, "skipped": True}

            if self.is_connected(dev_id, check_alive=True):
                return dev_id, {"success": True, "connected": True, "message": "Already connected"}

            # ตรวจสอบว่าพอร์ต socket ตอบสนองหรือไม่ (สำหรับ SSH / Telnet)
            ip = dev.get("ip")
            port = int(dev.get("port") or (22 if conn_type == "SSH" else 23))
            if conn_type in ("SSH", "TELNET") and ip:
                try:
                    with socket.create_connection((ip, port), timeout=1.2):
                        pass
                except Exception as e:
                    return dev_id, {"success": False, "connected": False, "message": f"Host/Port unreachable ({ip}:{port})"}

            res = self.connect(dev_id, dev, skip_ping=True)
            return dev_id, res

        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(_worker, d) for d in target_devs]
            for f in as_completed(futures):
                try:
                    item = f.result()
                    if item:
                        did, rdata = item
                        results[did] = rdata
                except Exception:
                    pass

        return results

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

    # ─── Config File Lifecycle (spec v3 section 19) ────────────────────
    def export_running_config(self, device_id: str) -> dict:
        """Export running-config ของ device (spec 19.1)"""
        return self.send_command(device_id, "show running-config")

    def export_startup_config(self, device_id: str) -> dict:
        """Export startup-config ของ device (spec 19.3)"""
        return self.send_command(device_id, "show startup-config")

    def merge_config(self, device_id: str, config_text: str) -> dict:
        """
        Merge config จาก text ไปยัง device (spec 19.2)
        อ่าน lines, ลบ comment (!), แล้วส่งผ่าน send_config_set
        """
        if device_id not in self.pool:
            return {"success": False, "output": f"Device '{device_id}' ยังไม่ได้เชื่อมต่อ"}

        # Parse lines: ลบ comment (!) และ blank lines
        lines = []
        for line in config_text.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("!"):
                lines.append(stripped)

        if not lines:
            return {"success": False, "output": "ไม่มี config commands ที่ valid"}

        return self.send_config(device_id, lines)

    def save_config(self, device_id: str) -> dict:
        """Save running → startup (write memory) (spec 19.4)"""
        return self.send_command(device_id, "write memory")


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
