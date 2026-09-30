"""
tests/test_assignment2_fixes.py
Comprehensive test suite verifying the 7 fixes requested by the user:
1. Enable secret in Add Device
2. Show controllers full output & spacebar paging
3. Tab autocomplete & command normalizer (config router rip, etc.)
4. Topology link IPs match exact router sides without confusion
5. CLI double-enter elimination & prompt deduplication
6. Delete All Devices in Inventory
7. Zero devices -> No mock topology
"""

import sys
import os
import unittest
import json
from unittest.mock import MagicMock, patch

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import networkx as nx
from connection_manager import ConnectionManager, save_inventory, load_inventory
import command_normalizer
from topology_builder import graph_to_json, build_topology_graph, _smart_subnet_matching
import app as flask_app


class TestAssignment2Fixes(unittest.TestCase):
    def setUp(self):
        self.mgr = ConnectionManager()
        self.client = flask_app.app.test_client()
        # Backup inventory
        self.orig_inv = load_inventory()

    def tearDown(self):
        # Restore inventory
        save_inventory(self.orig_inv)

    # -------------------------------------------------------------------------
    # 1. Enable Secret in Add Device
    # -------------------------------------------------------------------------
    def test_add_device_with_enable_secret(self):
        """1. ตรวจสอบการส่ง Enable secret ในหน้า Add device และจัดเก็บลง inventory"""
        device_data = {
            "name": "Router-Secret-Test",
            "model": "Cisco 4331",
            "device_type_label": "router",
            "connection_type": "TELNET",
            "ip": "192.168.10.1",
            "port": 23,
            "username": "admin",
            "password": "login_pass",
            "secret": "my_super_secret"
        }
        res = self.client.post("/api/inventory", json=device_data)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        created = data.get("device")
        self.assertEqual(created.get("secret"), "my_super_secret")

        # Verify it persisted in inventory
        inv = load_inventory()
        matched = [d for d in inv if d.get("name") == "Router-Secret-Test"]
        self.assertTrue(len(matched) > 0)
        self.assertEqual(matched[0].get("secret"), "my_super_secret")

        # Clean up
        self.client.delete(f"/api/inventory/{created.get('id')}")

    # -------------------------------------------------------------------------
    # 2. Show controllers full output & spacebar paging
    # -------------------------------------------------------------------------
    def test_show_controllers_paging_and_spacebar(self):
        """2. sh controllers แสดงรายละเอียดจนครบ และรองรับ spacebar paging"""
        class MockControllersChannel:
            def __init__(self):
                self.writes = []
                self.page_count = 0

            def clear_buffer(self):
                pass

            def write_channel(self, text):
                self.writes.append(text)
                if text == " ":
                    self.page_count += 1

            def read_channel(self):
                if self.page_count < 40:
                    self.page_count += 1
                    return f"Controller Serial0/1/0 page {self.page_count}\r\n--More--"
                else:
                    return "Final controller details completed.\r\nR1#"

        mock_ch = MockControllersChannel()
        self.mgr.pool["R1"] = {"handler": mock_ch, "type": "TELNET", "params": {"id": "R1"}}

        # send_interactive will auto-page beyond 30 pages
        res = self.mgr.send_interactive("R1", "sh controllers")
        self.assertTrue(res.get("success"))
        self.assertIn("Controller Serial0/1/0", res["output"])
        self.assertIn("Final controller details completed.", res["output"])
        self.assertEqual(res["prompt"], "R1#")
        self.assertFalse(res["is_more"])

        # Test Spacebar explicit continuation
        mock_ch.page_count = 0
        res_space = self.mgr.send_interactive("R1", " ")
        self.assertIn(" ", mock_ch.writes)

    # -------------------------------------------------------------------------
    # 3. Tab Autocomplete & Normalizer (config router rip, etc.)
    # -------------------------------------------------------------------------
    def test_tab_autocomplete_and_command_normalizer(self):
        """3. คำสั่ง router rip, show controllers, enable ทำงานถูกต้องใน normalizer"""
        # "en" should normalize to "enable" (not "end")
        self.assertEqual(command_normalizer.normalize("en"), "enable")
        # "router r" -> "router rip"
        self.assertEqual(command_normalizer.normalize("router r"), "router rip")
        # "sh controllers" -> "show controllers"
        self.assertEqual(command_normalizer.normalize("sh controllers"), "show controllers")
        self.assertEqual(command_normalizer.normalize("sh cont"), "show controllers")

        # Suggestions API for partial router command
        suggs = command_normalizer.get_suggestions("router")
        self.assertIn("router rip", suggs)

        suggs_cont = command_normalizer.get_suggestions("show cont")
        self.assertIn("show controllers", suggs_cont)

    # -------------------------------------------------------------------------
    # 4. Topology Link IPs Match Router Sides
    # -------------------------------------------------------------------------
    def test_topology_ip_matches_router_side_even_when_inverted(self):
        """4. IP ของแต่ละขาตรงกับ Router ของฝั่งนั้น ไม่สับสนเมื่อ NetworkX สลับ u, v"""
        # Case A: G edge u="R1", v="R2", original_from="R1"
        G1 = nx.MultiGraph()
        G1.add_node("R1", name="Router-R1", type="router", ip="192.168.1.116", model="Cisco 4331", status="connected")
        G1.add_node("R2", name="Router-R2", type="router", ip="192.168.1.125", model="Cisco 4331", status="connected")
        G1.add_edge("R1", "R2",
                    original_from="R1",
                    local_port="Ethernet0/0", remote_port="Ethernet0/1",
                    local_ip="192.168.0.1", remote_ip="192.168.0.2",
                    subnet="192.168.0.0/24", status="up", method="subnet_match")

        json1 = graph_to_json(G1)
        self.assertEqual(len(json1["edges"]), 1)
        e1 = json1["edges"][0]
        if e1["from"] == "R1":
            self.assertEqual(e1["from_port"], "Ethernet0/0")
            self.assertEqual(e1["from_ip"], "192.168.0.1")
            self.assertEqual(e1["to"], "R2")
            self.assertEqual(e1["to_port"], "Ethernet0/1")
            self.assertEqual(e1["to_ip"], "192.168.0.2")
        else:
            self.assertEqual(e1["from"], "R2")
            self.assertEqual(e1["from_port"], "Ethernet0/1")
            self.assertEqual(e1["from_ip"], "192.168.0.2")
            self.assertEqual(e1["to"], "R1")
            self.assertEqual(e1["to_port"], "Ethernet0/0")
            self.assertEqual(e1["to_ip"], "192.168.0.1")

        # Case B: G edge added with R2 as first node, but NetworkX returns R1 first
        G2 = nx.MultiGraph()
        G2.add_node("R1", name="Router-R1")
        G2.add_node("R2", name="Router-R2")
        G2.add_edge("R2", "R1",
                    original_from="R2",
                    local_port="Serial0/0", remote_port="Serial0/1",
                    local_ip="10.0.0.2", remote_ip="10.0.0.1",
                    subnet="10.0.0.0/30", status="up", method="subnet_match")

        json2 = graph_to_json(G2)
        e2 = json2["edges"][0]
        # Whoever is in e2["from"], their port and ip MUST match!
        if e2["from"] == "R2":
            self.assertEqual(e2["from_port"], "Serial0/0")
            self.assertEqual(e2["from_ip"], "10.0.0.2")
            self.assertEqual(e2["to"], "R1")
            self.assertEqual(e2["to_port"], "Serial0/1")
            self.assertEqual(e2["to_ip"], "10.0.0.1")
        else:
            self.assertEqual(e2["from"], "R1")
            self.assertEqual(e2["from_port"], "Serial0/1")
            self.assertEqual(e2["from_ip"], "10.0.0.1")
            self.assertEqual(e2["to"], "R2")
            self.assertEqual(e2["to_port"], "Serial0/0")
            self.assertEqual(e2["to_ip"], "10.0.0.2")

    # -------------------------------------------------------------------------
    # 5. CLI Double-Enter Elimination & Prompt Deduplication
    # -------------------------------------------------------------------------
    def test_cli_double_enter_deduplication(self):
        """5. CLI ไม่เบิ้ล Enter และลบ prompt ซ้ำซ้อนที่หาง output"""
        class MockEchoHandler:
            def __init__(self):
                self.written = []
                self.buffer = ""

            def clear_buffer(self):
                pass

            def write_channel(self, text):
                self.written.append(text)
                # Simulate Cisco double return response: command echo + newline + prompt + duplicate prompt
                self.buffer = "conf t\r\nEnter configuration commands.\r\nR1(config)#\r\nR1(config)#"

            def read_channel(self):
                out = self.buffer
                self.buffer = ""
                return out

        mock_h = MockEchoHandler()
        self.mgr.pool["R1"] = {"handler": mock_h, "type": "SSH", "params": {"id": "R1"}}

        res = self.mgr.send_interactive("R1", "conf t")
        self.assertTrue(res["success"])
        # SSH newline MUST be \n, NOT \r\n (which caused double return)
        self.assertEqual(mock_h.written[0], "conf t\n")
        # Prompt must be extracted
        self.assertEqual(res["prompt"], "R1(config)#")
        # Duplicate prompt must be stripped from clean output
        self.assertNotIn("R1(config)#", res["output"])
        self.assertEqual(res["output"], "Enter configuration commands.")

    # -------------------------------------------------------------------------
    # 6. Delete All Device Inventory
    # -------------------------------------------------------------------------
    def test_delete_all_devices(self):
        """6. ปุ่ม Delete All Devices ลบทุกตัวและตัดการเชื่อมต่อทั้งหมด"""
        # Seed 2 devices
        save_inventory([
            {"id": "Test-D1", "name": "Test-D1", "ip": "1.1.1.1", "device_type_label": "router"},
            {"id": "Test-D2", "name": "Test-D2", "ip": "1.1.1.2", "device_type_label": "router"}
        ])
        flask_app.conn_mgr.pool["Test-D1"] = {"handler": MagicMock(), "type": "TELNET", "params": {"id": "Test-D1"}}

        # Send DELETE /api/inventory
        res = self.client.delete("/api/inventory")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))

        # Inventory must be empty
        self.assertEqual(load_inventory(), [])
        # Pool must be empty
        self.assertEqual(len(flask_app.conn_mgr.pool), 0)


    # -------------------------------------------------------------------------
    # 7. Zero Devices -> No Mock Topology
    # -------------------------------------------------------------------------
    def test_no_mock_topology_when_inventory_empty(self):
        """7. เวลาที่ยังไม่มี device เลยสักตัว ต้องไม่มี topo mockup ขึ้นมาโชว์"""
        save_inventory([])
        res = self.client.get("/api/topology/json?refresh=1")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertFalse(data.get("demo"))
        self.assertEqual(data.get("nodes"), [])
        self.assertEqual(data.get("edges"), [])


    # -------------------------------------------------------------------------
    # 8. Duplicate Device Name & IP:Port Collision Prevention
    # -------------------------------------------------------------------------
    def test_duplicate_device_name_prevention(self):
        """8. ป้องกันการเพิ่ม Device Name ซ้ำ (Case-insensitive)"""
        save_inventory([
            {"id": "Router-Main", "name": "Router-Main", "ip": "10.0.0.1", "port": 22, "connection_type": "SSH"}
        ])
        # Attempt to add exact duplicate name
        res = self.client.post("/api/inventory", json={
            "name": "router-main",  # lowercase duplicate
            "ip": "10.0.0.2",
            "port": 22,
            "connection_type": "SSH"
        })
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get("success"))
        self.assertIn("มีอยู่ในระบบแล้ว", data.get("message"))

    def test_duplicate_device_ip_port_collision(self):
        """9. ป้องกัน IP:Port Socket Collision ซ้ำกับอุปกรณ์อื่น"""
        save_inventory([
            {"id": "R1", "name": "R1", "ip": "192.168.1.1", "port": 23, "connection_type": "TELNET"}
        ])
        # Attempt to add different name but identical IP:port
        res = self.client.post("/api/inventory", json={
            "name": "R2",
            "ip": "192.168.1.1",
            "port": 23,
            "connection_type": "TELNET"
        })
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get("success"))
        self.assertIn("ชนกับอุปกรณ์", data.get("message"))

    def test_duplicate_serial_port_collision(self):
        """10. ป้องกันการผูก COM Port ซ้ำกับอุปกรณ์อื่นในโหมด Serial"""
        save_inventory([
            {"id": "R-Serial", "name": "R-Serial", "serial_port": "COM3", "connection_type": "SERIAL"}
        ])
        res = self.client.post("/api/inventory", json={
            "name": "Switch-Serial",
            "serial_port": "COM3",
            "connection_type": "SERIAL"
        })
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get("success"))
        self.assertIn("ถูกใช้งานแล้ว", data.get("message"))

    def test_host_ip_validation_rejects_network_and_broadcast(self):
        """11. การตั้งค่า Interface ต้องปฏิเสธ Network Address (.0) และ Broadcast Address (.255)"""
        save_inventory([
            {"id": "R1", "name": "R1", "ip": "10.0.0.1", "connection_type": "SSH"}
        ])
        # Try assigning 192.168.1.0/24 (network address)
        res = self.client.post("/api/config/interface", json={
            "device_id": "R1",
            "interface": "GigabitEthernet0/0",
            "ip": "192.168.1.0",
            "mask": "255.255.255.0"
        })
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertIn("Network Address", data.get("message"))

        # Try assigning 192.168.1.255/24 (broadcast address)
        res_bc = self.client.post("/api/config/interface", json={
            "device_id": "R1",
            "interface": "GigabitEthernet0/0",
            "ip": "192.168.1.255",
            "mask": "255.255.255.0"
        })
        self.assertEqual(res_bc.status_code, 400)
        data_bc = res_bc.get_json()
        self.assertIn("Broadcast Address", data_bc.get("message"))


if __name__ == "__main__":
    unittest.main()

