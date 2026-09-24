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
