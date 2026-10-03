"""
tests/test_live_router_recovery.py
ทดสอบกับอุปกรณ์จริง R3 (192.168.1.1) ว่าถ้าพิมพ์ค้างไว้ใน (config-if)# แล้วไม่ได้พิมพ์ end
ระบบหน้าเว็บจะยังคงสั่งงาน show / config ได้ตามปกติโดยไม่ค้าง ไม่เอ๋อ และไม่ต้องรีสตาร์ท
"""

import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from connection_manager import ConnectionManager, get_device_by_id

def test_live_recovery():
    cm = ConnectionManager()
    dev = get_device_by_id("R3")
    if not dev:
        print("[SKIP] Device R3 not found in devices.json")
        return

    print(f"[TEST 1] Connecting to real device R3 ({dev.get('ip')})...")
    conn_res = cm.connect("R3", dev, skip_ping=False)
    if not conn_res.get("success"):
        print(f"[SKIP] Cannot connect to R3: {conn_res.get('message')}")
        return
    print(" -> Connected successfully to R3!")

    # 1. จำลองผู้ใช้พิมพ์เล่นใน Router แล้วค้างไว้ที่ (config-if)# โดยไม่พิมพ์ end
    print("\n[TEST 2] Simulating user typing in Router CLI into (config-if)# without typing 'end'...")
    res1 = cm.send_interactive("R3", "configure terminal")
    print(f" -> Prompt after 'conf t': {res1.get('prompt')}")
    res2 = cm.send_interactive("R3", "interface GigabitEthernet0/1")
    print(f" -> Prompt after 'interface Gi0/1': {res2.get('prompt')}")

    # ตรวจสอบว่าค้างอยู่ที่ config-if จริงๆ
    handler = cm.pool["R3"]["handler"]
    is_cfg = handler.check_config_mode()
    print(f" -> Current Router State: is_config_mode = {is_cfg}")
    assert is_cfg, "Router should be in config mode"

    # 2. จำลองผู้ใช้เปิดหน้าเว็บมากดดู Interface หรือ Show Commands (ระบบเรียก send_command)
    print("\n[TEST 3] Calling send_command('show ip interface brief') while Router is stuck in (config-if)#...")
    t0 = time.time()
    show_res = cm.send_command("R3", "show ip interface brief")
    elapsed = time.time() - t0
    print(f" -> Elapsed time: {elapsed:.2f}s (should be fast, not hanging)")
    print(f" -> Success: {show_res.get('success')}")
    assert show_res.get("success"), f"Show command failed: {show_res}"
    print(f" -> Output received ({len(show_res.get('output', ''))} bytes)")

    # 3. จำลองผู้ใช้เปิดหน้าเว็บมากด Apply Config หรือ Routing (ระบบเรียก send_config)
    print("\n[TEST 4] Calling send_config (Apply Static Route) while Router was left in config mode...")
    test_cmds = [
        "ip route 10.99.99.0 255.255.255.0 192.168.1.254",
        "no ip route 10.99.99.0 255.255.255.0 192.168.1.254"
    ]
    t0 = time.time()
    cfg_res = cm.send_config("R3", test_cmds)
    elapsed = time.time() - t0
    print(f" -> Elapsed time: {elapsed:.2f}s")
    print(f" -> Success: {cfg_res.get('success')}")
    assert cfg_res.get("success"), f"Config failed: {cfg_res}"
    print(" -> Configuration successfully applied without '% Invalid input' error!")

    # 4. ทดสอบส่งคำสั่งซ้ำอีกครั้ง เพื่อยืนยันว่า session ยังมีชีวิตและไม่เอ๋อ
    print("\n[TEST 5] Verifying session health with another show command...")
    v_res = cm.send_command("R3", "show ip route")
    print(f" -> Success: {v_res.get('success')}")
    assert v_res.get("success")

    # 5. ทดสอบจำลองผู้ใช้ค้างไว้ที่ (config-router)# แล้วทิ้งไว้ (มี background show commands รัน)
    print("\n[TEST 6] Simulating user in (config-router)# leaving terminal idle while background tasks run...")
    cm.send_interactive("R3", "configure terminal")
    res_rip = cm.send_interactive("R3", "router rip")
    print(f" -> Current prompt: {res_rip.get('prompt')}")
    assert "config-router" in res_rip.get('prompt', '')

    # Background task รัน show commands ซ้ำๆ
    for bg_cmd in ("show ip interface brief", "show cdp neighbors detail"):
        bg_res = cm.send_command("R3", bg_cmd)
        assert bg_res.get("success"), f"Background command {bg_cmd} failed: {bg_res}"

    # ตรวจสอบว่าผู้ใช้ยังคงอยู่ที่ (config-router)# 100% ไม่ถูกเตะออกมา!
    chk_res = cm.send_interactive("R3", "")
    print(f" -> Prompt after background tasks: {chk_res.get('prompt')}")
    assert "config-router" in chk_res.get('prompt', ''), f"User was unexpectedly kicked out! Prompt is {chk_res.get('prompt')}"
    print(" -> SUCCESS: Router stayed in (config-router)# without being kicked out!")

    # 6. คืนสถานะและ disconnect
    cm.send_interactive("R3", "end")
    cm.disconnect("R3")
    print("\n[RESULT] ALL LIVE TESTS PASSED! Problem is 100% resolved on real Router R3!")

if __name__ == "__main__":
    test_live_recovery()
