"""
tests/test_unended_config_recovery.py — ทดสอบการฟื้นฟู session เมื่อผู้ใช้พิมพ์คำสั่งค้างไว้ใน Router แล้วไม่ได้พิมพ์ end
"""

import unittest
from unittest.mock import MagicMock, patch
from connection_manager import ConnectionManager


class MockNetmikoHandler:
    def __init__(self, initial_prompt="Router(config-if)#"):
        self.prompt = initial_prompt
        self.channel_writes = []
        self.clear_buffer_count = 0
        self.enabled = False

    def clear_buffer(self):
        self.clear_buffer_count += 1

    def write_channel(self, text):
        self.channel_writes.append(text)
        if "\x03" in text or "end" in text:
            self.prompt = "Router#"
        elif "enable" in text:
            self.prompt = "Router#"
            self.enabled = True

    def check_config_mode(self):
        return ")#" in self.prompt or "(config" in self.prompt

    def exit_config_mode(self):
        if self.check_config_mode():
            self.prompt = "Router#"
            return "end\r\nRouter#"
        return ""

    def check_enable_mode(self):
        return self.prompt.endswith("#")

    def enable(self):
        self.prompt = "Router#"
        self.enabled = True

    def send_command(self, command, use_textfsm=False):
        if self.check_config_mode() and command.startswith("show "):
            return "% Invalid input detected at '^' marker."
        return f"Output for {command}\n{self.prompt}"

    def send_config_set(self, commands):
        if self.check_config_mode() and "config-if" in self.prompt:
            # If still in subconfig mode, commands like ip route fail
            for c in commands:
                if c.startswith("ip route") or c.startswith("router "):
                    return f"{c}\n% Invalid input detected at '^' marker."
        return f"Configured: {'; '.join(commands)}"


class TestUnendedConfigRecovery(unittest.TestCase):
    def setUp(self):
        self.cm = ConnectionManager()

    def test_ensure_clean_exec_mode_from_normal(self):
        """เมื่อ Router อยู่ที่ Privileged EXEC (#) ปกติ ไม่ต้องส่ง end"""
        handler = MockNetmikoHandler(initial_prompt="Router#")
        entry = {"handler": handler, "type": "SSH", "is_linux": False}
        res = self.cm._ensure_clean_exec_mode("R1", entry)
        self.assertTrue(res)
        self.assertEqual(handler.prompt, "Router#")
        self.assertFalse(any("end" in w for w in handler.channel_writes))

    def test_ensure_clean_exec_mode_from_config_global(self):
        """เมื่อค้างอยู่ที่ Router(config)# ต้อง auto-exit สู่ Router#"""
        handler = MockNetmikoHandler(initial_prompt="Router(config)#")
        entry = {"handler": handler, "type": "SSH", "is_linux": False}
        res = self.cm._ensure_clean_exec_mode("R1", entry)
        self.assertTrue(res)
        self.assertEqual(handler.prompt, "Router#")

    def test_ensure_clean_exec_mode_from_subconfig_interface(self):
        """เมื่อค้างอยู่ที่ Router(config-if)# ต้อง auto-exit สู่ Router#"""
        handler = MockNetmikoHandler(initial_prompt="Router(config-if)#")
        entry = {"handler": handler, "type": "SSH", "is_linux": False}
        res = self.cm._ensure_clean_exec_mode("R1", entry)
        self.assertTrue(res)
        self.assertEqual(handler.prompt, "Router#")

    def test_ensure_clean_exec_mode_from_subconfig_router(self):
        """เมื่อค้างอยู่ที่ Router(config-router)# ต้อง auto-exit สู่ Router#"""
        handler = MockNetmikoHandler(initial_prompt="Router(config-router)#")
        entry = {"handler": handler, "type": "SSH", "is_linux": False}
        res = self.cm._ensure_clean_exec_mode("R1", entry)
        self.assertTrue(res)
        self.assertEqual(handler.prompt, "Router#")

    def test_ensure_clean_exec_mode_from_user_mode(self):
        """เมื่อหลุดไปอยู่ที่ User Mode (Switch>) ต้อง auto-enter Enable Mode (#)"""
        handler = MockNetmikoHandler(initial_prompt="Switch>")
        entry = {"handler": handler, "type": "TELNET", "is_linux": False}
        res = self.cm._ensure_clean_exec_mode("SW1", entry)
        self.assertTrue(res)
        self.assertEqual(handler.prompt, "Router#")
        self.assertTrue(handler.enabled)

    def test_ensure_clean_exec_mode_linux_pc_skipped(self):
        """Linux PC ไม่ต้องรันคำสั่ง Cisco IOS"""
        handler = MagicMock()
        entry = {"handler": handler, "type": "SSH", "is_linux": True}
        res = self.cm._ensure_clean_exec_mode("PC1", entry)
        self.assertTrue(res)
        handler.write_channel.assert_not_called()

    def test_send_command_auto_recovers_from_unended_config(self):
        """send_command สามารถรันคำสั่ง show ได้แม้ Router ติดอยู่ใน config-if โดยใช้ 'do <cmd>' ไม่เตะผู้ใช้ออก"""
        handler = MockNetmikoHandler(initial_prompt="Router(config-if)#")
        self.cm.pool["R1"] = {"handler": handler, "type": "SSH", "is_linux": False}
        
        with patch.object(self.cm, "is_connected", return_value=True):
            res = self.cm.send_command("R1", "show ip interface brief")
            self.assertTrue(res.get("success"))
            self.assertIn("do show ip interface brief", res.get("output"))
            # Router ยังคงอยู่ที่ config-if ตามเดิม ไม่ถูกเตะออกมา
            self.assertEqual(handler.prompt, "Router(config-if)#")

    def test_send_config_auto_recovers_from_unended_config(self):
        """send_config สามารถ apply ip route ได้สำเร็จแม้ Router เคยติดอยู่ใน config-if"""
        handler = MockNetmikoHandler(initial_prompt="Router(config-if)#")
        self.cm.pool["R1"] = {"handler": handler, "type": "SSH", "is_linux": False}

        with patch.object(self.cm, "is_connected", return_value=True):
            res = self.cm.send_config("R1", ["ip route 10.0.0.0 255.255.255.0 192.168.1.1"])
            self.assertTrue(res.get("success"))
            self.assertNotIn("% Invalid input", res.get("output", ""))
            self.assertEqual(handler.prompt, "Router#")

    def test_serial_ensure_clean_exec_mode(self):
        """ทดสอบ Serial Console ฟื้นฟูจาก config mode"""
        mock_ser = MagicMock()
        mock_ser.read_all.return_value = "Router(config-if)#"
        entry = {"handler": mock_ser, "type": "SERIAL", "is_linux": False}
        res = self.cm._ensure_clean_exec_mode("R1", entry)
        self.assertTrue(res)
        mock_ser.write.assert_any_call(b"end\r\n")

    def test_timeout_auto_reconnect(self):
        """เมื่อเกิด ReadTimeout ต้องตัดการเชื่อมต่อและ reconnect อัตโนมัติ"""
        handler = MagicMock()
        handler.send_command.side_effect = Exception("ReadTimeout: Pattern not detected: 'Router#' in output")
        self.cm.pool["R1"] = {"handler": handler, "type": "SSH", "is_linux": False}

        reconnect_called = []
        def fake_disconnect(did):
            self.cm.pool.pop(did, None)
            reconnect_called.append("disconnect")

        def fake_ensure(did):
            new_handler = MockNetmikoHandler(initial_prompt="Router#")
            self.cm.pool[did] = {"handler": new_handler, "type": "SSH", "is_linux": False}
            reconnect_called.append("ensure")
            return True

        with patch.object(self.cm, "is_connected", return_value=True), \
             patch.object(self.cm, "disconnect", side_effect=fake_disconnect), \
             patch.object(self.cm, "_ensure_connection", side_effect=fake_ensure):
            res = self.cm.send_command("R1", "show version")
            self.assertTrue(res.get("success"))
            self.assertIn("disconnect", reconnect_called)
            self.assertIn("ensure", reconnect_called)

    def test_active_interactive_not_ejected_by_background_send_command(self):
        """ขณะผู้ใช้พิมพ์อยู่ใน CLI Terminal background show commands จะใช้ 'do <cmd>' โดยไม่เตะผู้ใช้ออกจาก (config)#"""
        import time
        handler = MockNetmikoHandler(initial_prompt="Router(config)#")
        self.cm.pool["R1"] = {
            "handler": handler,
            "type": "SSH",
            "is_linux": False,
            "last_interactive": time.time()
        }

        with patch.object(self.cm, "is_connected", return_value=True):
            res = self.cm.send_command("R1", "show cdp neighbors detail")
            self.assertTrue(res.get("success"))
            self.assertIn("do show cdp neighbors detail", res.get("output"))
            self.assertEqual(handler.prompt, "Router(config)#")

    def test_idle_terminal_never_ejected_by_background_tasks(self):
        """แม้ผู้ใช้จะทิ้งหน้าจอ Terminal ค้างไว้ใน (config-router)# นานแค่ไหน background tasks ก็จะไม่เตะผู้ใช้ออกเด็ดขาด"""
        import time
        handler = MockNetmikoHandler(initial_prompt="Router(config-router)#")
        self.cm.pool["R1"] = {
            "handler": handler,
            "type": "SSH",
            "is_linux": False,
            "last_interactive": time.time() - 3600  # ทิ้งไว้เป็นชั่วโมง
        }

        with patch.object(self.cm, "is_connected", return_value=True):
            res = self.cm.send_command("R1", "show ip interface brief")
            self.assertTrue(res.get("success"))
            self.assertIn("do show ip interface brief", res.get("output"))
            # Router ยังคงอยู่ที่ (config-router)# 100% ไม่ถูกส่ง 'end' ออกมา
            self.assertEqual(handler.prompt, "Router(config-router)#")

    def test_flask_api_routing_when_router_left_in_subconfig(self):
        """ผู้ใช้พิมพ์คาไว้ที่ Router(config-if)# แล้วมากด Apply OSPF ในหน้าเว็บ → ทำงานสำเร็จ ไม่ค้าง"""
        import app as flask_app
        client = flask_app.app.test_client()
        handler = MockNetmikoHandler(initial_prompt="Router(config-if)#")
        flask_app.conn_mgr.pool["R3"] = {"handler": handler, "type": "SSH", "is_linux": False}

        with patch.object(flask_app.conn_mgr, "is_connected", return_value=True):
            payload = {
                "device_id": "R3",
                "route_type": "ospf",
                "process_id": 1,
                "router_id": "1.1.1.1",
                "networks": [{"network": "192.168.1.0", "wildcard": "0.0.0.255", "area": 0}]
            }
            res = client.post("/api/config/routing", json=payload)
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data.get("success"))
            # Router คืนสถานะกลับสู่ privileged EXEC (#) เรียบร้อย ไม่เอ๋อ
            self.assertEqual(handler.prompt, "Router#")

    def test_flask_api_interface_configure_when_router_left_in_subconfig(self):
        """ผู้ใช้พิมพ์คาไว้ที่ Router(config-router)# แล้วมากด Configure Interface ในหน้าเว็บ → ทำงานสำเร็จ ไม่ค้าง"""
        import app as flask_app
        client = flask_app.app.test_client()
        handler = MockNetmikoHandler(initial_prompt="Router(config-router)#")
        flask_app.conn_mgr.pool["R3"] = {"handler": handler, "type": "SSH", "is_linux": False}

        with patch.object(flask_app.conn_mgr, "is_connected", return_value=True):
            payload = {
                "device_id": "R3",
                "interface": "GigabitEthernet0/1",
                "ip": "192.168.1.1",
                "mask": "255.255.255.0",
                "state": "up"
            }
            res = client.post("/api/config/interface", json=payload)
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data.get("success"))
            self.assertEqual(handler.prompt, "Router#")

    def test_flask_api_show_when_router_left_in_subconfig(self):
        """ผู้ใช้พิมพ์คาไว้ที่ Router(config-if)# แล้วมากดดู Show Commands ในหน้าเว็บ → ทำงานสำเร็จ ไม่ค้าง"""
        import app as flask_app
        client = flask_app.app.test_client()
        handler = MockNetmikoHandler(initial_prompt="Router(config-if)#")
        flask_app.conn_mgr.pool["R3"] = {"handler": handler, "type": "SSH", "is_linux": False}

        with patch.object(flask_app.conn_mgr, "is_connected", return_value=True):
            res = client.post("/api/show", json={"device_id": "R3", "command": "show ip route"})
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data.get("success"))
            # Router ไม่ถูกเตะออกจาก config mode
            self.assertEqual(handler.prompt, "Router(config-if)#")


if __name__ == "__main__":
    unittest.main()


