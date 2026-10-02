"""
validators.py — Input Validation สำหรับ Network Configuration
อ้างอิง: spec v3 section 12, 30
ตรวจสอบ IP, Subnet Mask, Wildcard Mask, Router-ID, AS Number, Port
"""

import re


def validate_ip(ip: str) -> tuple:
    """
    ตรวจ IP address format
    คืน (True, "") หรือ (False, "error message")
    """
    if not ip or not ip.strip():
        return False, "IP address ต้องไม่เป็นค่าว่าง"
    parts = ip.strip().split(".")
    if len(parts) != 4:
        return False, f"IP '{ip}' รูปแบบไม่ถูกต้อง (ต้องการ 4 octets)"
    try:
        octets = [int(p) for p in parts]
    except ValueError:
        return False, f"IP '{ip}' มีตัวอักษรที่ไม่ใช่ตัวเลข"
    for o in octets:
        if not (0 <= o <= 255):
            return False, f"IP '{ip}' มี octet ออกนอกช่วง 0-255"
    return True, ""


def validate_subnet_mask(mask: str) -> tuple:
    """
    ตรวจ Subnet Mask ว่าถูกต้องหรือไม่ (contiguous 1-bits ตามด้วย 0-bits)
    ตัวอย่าง valid: 255.255.255.0, 255.255.252.0
    ตัวอย่าง invalid: 255.255.255.3, 255.0.255.0
    """
    if not mask or not mask.strip():
        return False, "Subnet Mask ต้องไม่เป็นค่าว่าง"

    parts = mask.strip().split(".")
    if len(parts) != 4:
        return False, f"Subnet Mask '{mask}' รูปแบบไม่ถูกต้อง (ต้องการ 4 octets)"
    try:
        octets = [int(p) for p in parts]
    except ValueError:
        return False, f"Subnet Mask '{mask}' มีตัวอักษรที่ไม่ใช่ตัวเลข"
    for o in octets:
        if not (0 <= o <= 255):
            return False, f"Subnet Mask '{mask}' มี octet ออกนอกช่วง 0-255"

    # ตรวจ contiguous bits: แปลงเป็น 32-bit แล้วเช็คว่า 1s ติดกัน
    binary = "".join(f"{o:08b}" for o in octets)
    # Valid pattern: 1...10...0 or all 1s or all 0s
    if "01" in binary.replace("10", "", 1):
        # ตรวจซ้ำ: หลังจากเจอ 0 แล้วต้องไม่มี 1 อีก
        found_zero = False
        for bit in binary:
            if bit == "0":
                found_zero = True
            elif found_zero:
                return False, f"Subnet Mask '{mask}' ไม่ valid (bits ต้องเป็น contiguous 1s ตามด้วย 0s)"
    return True, ""


def validate_wildcard_mask(wildcard: str) -> tuple:
    """
    ตรวจ Wildcard Mask — ต้องเป็น inverse ของ subnet mask (contiguous 0s ตามด้วย 1s)
    ตัวอย่าง valid: 0.0.0.255, 0.0.3.255
    """
    if not wildcard or not wildcard.strip():
        return False, "Wildcard Mask ต้องไม่เป็นค่าว่าง"

    parts = wildcard.strip().split(".")
    if len(parts) != 4:
        return False, f"Wildcard Mask '{wildcard}' รูปแบบไม่ถูกต้อง (ต้องการ 4 octets)"
    try:
        octets = [int(p) for p in parts]
    except ValueError:
        return False, f"Wildcard Mask '{wildcard}' มีตัวอักษรที่ไม่ใช่ตัวเลข"
    for o in octets:
        if not (0 <= o <= 255):
            return False, f"Wildcard Mask '{wildcard}' มี octet ออกนอกช่วง 0-255"

    # Wildcard = inverse ของ subnet → contiguous 0s ตามด้วย 1s
    binary = "".join(f"{o:08b}" for o in octets)
    found_one = False
    for bit in binary:
        if bit == "1":
            found_one = True
        elif found_one:
            return False, f"Wildcard Mask '{wildcard}' ไม่ valid (bits ต้องเป็น contiguous 0s ตามด้วย 1s)"
    return True, ""


def validate_router_id(router_id: str) -> tuple:
    """ตรวจ Router-ID — ต้องเป็น format เดียวกับ IP address"""
    if not router_id or not router_id.strip():
        return True, ""  # Router-ID เป็น optional
    return validate_ip(router_id)


def validate_as_number(as_num) -> tuple:
    """
    ตรวจ AS Number — ต้องเป็น 1-4294967295 (32-bit)
    Private ASN: 64512-65534 (16-bit) หรือ 4200000000-4294967294 (32-bit)
    """
    try:
        as_int = int(as_num)
    except (ValueError, TypeError):
        return False, f"AS Number '{as_num}' ต้องเป็นตัวเลข"
    if as_int < 1 or as_int > 4294967295:
        return False, f"AS Number {as_int} ออกนอกช่วง (1-4294967295)"
    return True, ""


def validate_port(port) -> tuple:
    """ตรวจ Port Number — ต้องเป็น 1-65535"""
    try:
        port_int = int(port)
    except (ValueError, TypeError):
        return False, f"Port '{port}' ต้องเป็นตัวเลข"
    if port_int < 1 or port_int > 65535:
        return False, f"Port {port_int} ออกนอกช่วง (1-65535)"
    return True, ""


def validate_interface_config(ip: str = None, mask: str = None,
                               wildcard: str = None, router_id: str = None,
                               as_num=None) -> tuple:
    """
    Validate หลายค่าพร้อมกัน
    คืน (True, []) ถ้าผ่านทั้งหมด
    คืน (False, [error1, error2, ...]) ถ้ามี error
    """
    errors = []
    if ip:
        valid, msg = validate_ip(ip)
        if not valid:
            errors.append(msg)
    if mask:
        valid, msg = validate_subnet_mask(mask)
        if not valid:
            errors.append(msg)
    if wildcard:
        valid, msg = validate_wildcard_mask(wildcard)
        if not valid:
            errors.append(msg)
    if router_id:
        valid, msg = validate_router_id(router_id)
        if not valid:
            errors.append(msg)
    if as_num is not None:
        valid, msg = validate_as_number(as_num)
        if not valid:
            errors.append(msg)

    return (len(errors) == 0, errors)


import ipaddress


def validate_host_ip(ip: str, mask: str) -> tuple:
    """
    ตรวจสอบว่า IP Address เป็น Host IP ที่ใช้งานได้จริงหรือไม่ (ไม่ใช่ Network ID หรือ Broadcast)
    """
    valid_ip, msg = validate_ip(ip)
    if not valid_ip:
        return False, msg
    valid_mask, msg = validate_subnet_mask(mask)
    if not valid_mask:
        return False, msg
    try:
        interface = ipaddress.IPv4Interface(f"{ip.strip()}/{mask.strip()}")
        network = interface.network
        if network.prefixlen < 31:  # /31 และ /32 รองรับ RFC 3021
            if interface.ip == network.network_address:
                return False, f"IP '{ip}' เป็น Network Address ของเครือข่าย {network} (ไม่สามารถกำหนดให้กับ Host ได้)"
            if interface.ip == network.broadcast_address:
                return False, f"IP '{ip}' เป็น Broadcast Address ของเครือข่าย {network} (ไม่สามารถกำหนดให้กับ Host ได้)"
        return True, ""
    except Exception as e:
        return False, f"รูปแบบ IP/Mask ไม่ถูกต้อง: {e}"


def check_subnet_overlap(ip1: str, mask1: str, ip2: str, mask2: str) -> bool:
    """ตรวจสอบว่า 2 interfaces อยู่ใน Subnet ที่ทับซ้อนกันหรือไม่ (เหมือน Cisco IOS overlap check)"""
    try:
        net1 = ipaddress.IPv4Interface(f"{ip1.strip()}/{mask1.strip()}").network
        net2 = ipaddress.IPv4Interface(f"{ip2.strip()}/{mask2.strip()}").network
        return net1.overlaps(net2)
    except Exception:
        return False


def validate_device_payload(data: dict, existing_devices: list, current_device_id: str = None) -> tuple:
    """
    ตรวจสอบความถูกต้องของ Device Config ทั้งหมดก่อนจัดเก็บลง Inventory:
    - ตรวจสอบชื่ออุปกรณ์ (Device Name): ห้ามว่าง, ห้ามซ้ำ (Case-Insensitive), ห้ามมีอักขระพิเศษแปลกปลอม
    - ตรวจสอบ IP Address: รูปแบบ IPv4 ที่ถูกต้อง (สำหรับ SSH, TELNET, PC)
    - ตรวจสอบ Port: ตัวเลข 1-65535
    - ตรวจสอบ IP:Port Collision: ห้ามใช้อุปกรณ์อื่นที่มี IP เดียวกันและ Port เดียวกัน
    - ตรวจสอบ Serial Port: ห้ามกำหนด COM Port เดียวกันให้กับอุปกรณ์ที่เชื่อมต่อ Serial พร้อมกัน
    - ตรวจสอบ PC Gateway / Subnet Mask
    คืนค่า (is_valid: bool, errors: list[str])
    """
    errors = []
    name = (data.get("name") or "").strip()
    if not name:
        errors.append("ชื่ออุปกรณ์ (Device Name) ต้องไม่เป็นค่าว่าง")
    elif len(name) > 64:
        errors.append("ชื่ออุปกรณ์ยาวเกินไป (ไม่เกิน 64 ตัวอักษร)")
    elif not re.match(r"^[A-Za-z0-9_\-\.\s]+$", name):
        errors.append("ชื่ออุปกรณ์มีอักขระที่ไม่รองรับ (ใช้ได้เฉพาะ A-Z, 0-9, _, -, .)")

    dtype = (data.get("device_type_label") or "router").lower()
    conn_type = (data.get("connection_type") or "SSH").upper()
    ip = (data.get("ip") or "").strip()
    port = data.get("port")
    serial_port = (data.get("serial_port") or "").strip().upper()

    # Normalize port
    if port is None or port == "":
        port = 22 if conn_type == "SSH" else (23 if conn_type == "TELNET" else 0)
    try:
        port_num = int(port)
    except (ValueError, TypeError):
        errors.append(f"Port '{port}' ต้องเป็นตัวเลข")
        port_num = 0

    # 1. ตรวจสอบชื่อซ้ำ (Duplicate Name Check)
    for dev in existing_devices:
        dev_id = dev.get("id", "")
        dev_name = (dev.get("name") or "").strip()
        if current_device_id and (dev_id == current_device_id or dev_name == current_device_id):
            continue
        if dev_name.lower() == name.lower() or dev_id.lower() == name.lower():
            errors.append(f"ชื่ออุปกรณ์ '{name}' มีอยู่ในระบบแล้ว (ห้ามตั้งชื่อซ้ำ)")
            break

    # 2. ตรวจสอบตามประเภทการเชื่อมต่อ
    if dtype in ("network", "cloud"):
        # วง Network / Subnet
        if ip:
            try:
                ipaddress.IPv4Network(ip, strict=False)
            except Exception:
                errors.append(f"Network CIDR '{ip}' รูปแบบไม่ถูกต้อง เช่น 192.168.100.0/24")
    elif conn_type == "SERIAL":
        if not serial_port:
            errors.append("กรุณาระบุ Serial Port (เช่น COM1 หรือ /dev/ttyUSB0)")
        else:
            # ตรวจสอบ Serial Port ซ้ำ
            for dev in existing_devices:
                dev_id = dev.get("id", "")
                if current_device_id and dev_id == current_device_id:
                    continue
                dev_conn = (dev.get("connection_type") or "").upper()
                dev_serial = (dev.get("serial_port") or "").strip().upper()
                if dev_conn == "SERIAL" and dev_serial == serial_port:
                    errors.append(f"Serial Port '{serial_port}' ถูกใช้งานแล้วโดยอุปกรณ์ '{dev.get('name', dev_id)}'")
                    break
    elif dtype == "pc" or conn_type == "PC":
        # ตรวจสอบ Virtual PC
        if not ip:
            errors.append("IP Address จำเป็นสำหรับ Virtual PC")
        else:
            v_ip, msg_ip = validate_ip(ip)
            if not v_ip:
                errors.append(msg_ip)
            else:
                for dev in existing_devices:
                    dev_id = dev.get("id", "")
                    if current_device_id and dev_id == current_device_id:
                        continue
                    dev_ip = (dev.get("ip") or "").strip()
                    if dev_ip == ip:
                        errors.append(f"IP '{ip}' ชนกับอุปกรณ์ '{dev.get('name', dev_id)}' ที่มีอยู่ในระบบแล้ว")
                        break

        gateway = (data.get("gateway") or "").strip()
        mask = (data.get("mask") or "").strip()
        if gateway:
            v_gw, msg_gw = validate_ip(gateway)
            if not v_gw:
                errors.append(f"Gateway: {msg_gw}")
        if mask:
            v_mask, msg_mask = validate_subnet_mask(mask)
            if not v_mask:
                errors.append(f"Subnet Mask: {msg_mask}")
        if ip and mask:
            v_host, msg_host = validate_host_ip(ip, mask if mask else "255.255.255.0")
            if not v_host:
                errors.append(msg_host)
    else:
        # IP-based: SSH, TELNET (Routers / Switches)
        if not ip:
            errors.append("IP Address จำเป็นสำหรับอุปกรณ์เชื่อมต่อผ่านเครือข่าย")
        else:
            v_ip, msg_ip = validate_ip(ip)
            if not v_ip:
                errors.append(msg_ip)
            else:
                # ตรวจ Port Range
                if port_num < 1 or port_num > 65535:
                    errors.append(f"Port {port_num} ออกนอกช่วง (1-65535)")
                else:
                    # ตรวจสอบ IP + Port Collision ซ้ำกับอุปกรณ์อื่น
                    for dev in existing_devices:
                        dev_id = dev.get("id", "")
                        if current_device_id and dev_id == current_device_id:
                            continue
                        dev_conn = (dev.get("connection_type") or "").upper()
                        if dev_conn == "SERIAL":
                            continue
                        dev_ip = (dev.get("ip") or "").strip()
                        dev_port = dev.get("port")
                        if dev_port is None or dev_port == "":
                            dev_port = 22 if dev_conn == "SSH" else 23
                        try:
                            dev_port_num = int(dev_port)
                        except Exception:
                            dev_port_num = 0

                        # ถ้า IP เดียวกัน และ Port เดียวกัน -> Socket Collision
                        if dev_ip == ip and dev_port_num == port_num:
                            errors.append(
                                f"IP '{ip}' พอร์ต '{port_num}' ชนกับอุปกรณ์ '{dev.get('name', dev_id)}' ที่มีอยู่ในระบบแล้ว"
                            )
                            break

    return (len(errors) == 0, errors)

