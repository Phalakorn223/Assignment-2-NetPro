"""
tests/test_redistribution.py
Comprehensive test suite verifying Route Redistribution for Cross-Protocol Routing:
1. Redistribution from OSPF into EIGRP (with 5 seed metrics & Process ID)
2. Redistribution from EIGRP into OSPF (with subnets & AS Number)
3. Redistribution from OSPF into RIP (with seed metric & Process ID)
4. Redistribution from RIP into OSPF (with subnets)
5. Redistribution from RIP into EIGRP (with 5 seed metrics)
6. Redistribution of Connected & Static routes into OSPF, EIGRP, RIP
7. Redistribution with BGP
8. Mutual / Two-Way Redistribution generator (OSPF <-> EIGRP)
9. Mutual / Two-Way Redistribution generator (OSPF <-> RIP)
10. Mutual / Two-Way Redistribution generator (EIGRP <-> RIP)
11. Flask API Endpoint: POST /api/routing/mutual-redistribute/preview
12. Flask API Endpoint: POST /api/routing/mutual-redistribute/apply
13. Flask API Endpoint: POST /api/routing/preview with dynamic redistribution payloads
"""

import sys
import os
import unittest
import json
from unittest.mock import MagicMock, patch

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from command_builder import (
    build_redistribute,
    build_mutual_redistribution,
    merge_router_protocol_commands,
    preview_commands,
)
import app as flask_app


class TestRouteRedistribution(unittest.TestCase):
    def setUp(self):
        self.client = flask_app.app.test_client()

    # -------------------------------------------------------------------------
    # 1. Single Redistribution Command Generation
    # -------------------------------------------------------------------------
    def test_redistribute_ospf_into_eigrp(self):
        """OSPF -> EIGRP ต้องระบุ Process ID และ Metric 5 ค่า (BW, DLY, REL, LOAD, MTU)"""
        cmds = build_redistribute("eigrp", "ospf", process_id=1)
        self.assertEqual(len(cmds), 1)
        self.assertIn("redistribute ospf 1 metric 10000 100 255 1 1500", cmds[0])

        # Custom metrics and PID
        cmds2 = build_redistribute("eigrp", "ospf", process_id=10, metric="20000 50 255 1 1500")
        self.assertIn("redistribute ospf 10 metric 20000 50 255 1 1500", cmds2[0])

    def test_redistribute_eigrp_into_ospf(self):
        """EIGRP -> OSPF ต้องระบุ AS Number และ subnets เพื่อกระจาย Classless routes"""
        cmds = build_redistribute("ospf", "eigrp", as_number=100)
        self.assertEqual(len(cmds), 1)
        self.assertIn("redistribute eigrp 100 subnets", cmds[0])

        # With optional metric and metric-type
        cmds2 = build_redistribute("ospf", "eigrp", as_number=200, metric=30, metric_type=1)
        self.assertIn("redistribute eigrp 200 subnets metric 30 metric-type 1", cmds2[0])

    def test_redistribute_ospf_into_rip(self):
        """OSPF -> RIP ต้องมี seed metric (Hop count) เพื่อไม่ให้ถูกกำหนดเป็น Infinity (16)"""
        cmds = build_redistribute("rip", "ospf", process_id=1)
        self.assertEqual(len(cmds), 1)
        self.assertIn("redistribute ospf 1 metric 1", cmds[0])

        cmds2 = build_redistribute("rip", "ospf", process_id=2, metric=3)
        self.assertIn("redistribute ospf 2 metric 3", cmds2[0])

    def test_redistribute_rip_into_ospf(self):
        """RIP -> OSPF ต้องใส่ subnets"""
        cmds = build_redistribute("ospf", "rip")
        self.assertEqual(len(cmds), 1)
        self.assertIn("redistribute rip subnets", cmds[0])

    def test_redistribute_rip_into_eigrp(self):
        """RIP -> EIGRP ต้องมี Metric 5 ค่า"""
        cmds = build_redistribute("eigrp", "rip")
        self.assertEqual(len(cmds), 1)
        self.assertIn("redistribute rip metric 10000 100 255 1 1500", cmds[0])

    def test_redistribute_connected_and_static(self):
        """Connected & Static redistribute เข้า OSPF, EIGRP, RIP"""
        # Connected into OSPF
        ospf_conn = build_redistribute("ospf", "connected", subnets=True)
        self.assertIn("redistribute connected subnets", ospf_conn[0])

        # Static into EIGRP
        eigrp_stat = build_redistribute("eigrp", "static")
        self.assertIn("redistribute static metric 10000 100 255 1 1500", eigrp_stat[0])

        # Connected into RIP
        rip_conn = build_redistribute("rip", "connected", metric=1)
        self.assertIn("redistribute connected metric 1", rip_conn[0])

    def test_redistribute_bgp(self):
        """BGP redistribution with OSPF & EIGRP"""
        # BGP into OSPF
        ospf_bgp = build_redistribute("ospf", "bgp", as_number=65001)
        self.assertIn("redistribute bgp 65001 subnets", ospf_bgp[0])

        # OSPF into BGP
        bgp_ospf = build_redistribute("bgp", "ospf", process_id=1)
        self.assertIn("redistribute ospf 1", bgp_ospf[0])

    # -------------------------------------------------------------------------
    # 2. Mutual / Two-Way Redistribution Generator
    # -------------------------------------------------------------------------
    def test_mutual_redistribution_ospf_eigrp(self):
        """Two-Way Redistribution ระหว่าง OSPF 1 กับ EIGRP 100"""
        proto_a = {"protocol": "ospf", "process_id": 1, "subnets": True}
        proto_b = {"protocol": "eigrp", "as_number": 100, "metric": "10000 100 255 1 1500"}
        cmds = build_mutual_redistribution(proto_a, proto_b)

        # ต้องมี router ospf 1 -> redistribute eigrp 100 subnets
        self.assertIn("router ospf 1", cmds)
        self.assertIn("redistribute eigrp 100 subnets", cmds)

        # ต้องมี router eigrp 100 -> redistribute ospf 1 metric 10000 100 255 1 1500
        self.assertIn("router eigrp 100", cmds)
        self.assertIn("redistribute ospf 1 metric 10000 100 255 1 1500", cmds)
        self.assertIn("no auto-summary", cmds)

    def test_mutual_redistribution_ospf_rip(self):
        """Two-Way Redistribution ระหว่าง OSPF 1 กับ RIPv2"""
        proto_a = {"protocol": "ospf", "process_id": 1, "subnets": True}
        proto_b = {"protocol": "rip", "metric": 2}
        cmds = build_mutual_redistribution(proto_a, proto_b)

        self.assertIn("router ospf 1", cmds)
        self.assertIn("redistribute rip subnets", cmds)
        self.assertIn("router rip", cmds)
        self.assertIn("version 2", cmds)
        self.assertIn("redistribute ospf 1 metric 2", cmds)

    def test_mutual_redistribution_eigrp_rip(self):
        """Two-Way Redistribution ระหว่าง EIGRP 100 กับ RIPv2"""
        proto_a = {"protocol": "eigrp", "as_number": 100}
        proto_b = {"protocol": "rip", "metric": 1}
        cmds = build_mutual_redistribution(proto_a, proto_b)

        self.assertIn("router eigrp 100", cmds)
        self.assertIn("redistribute rip metric 10000 100 255 1 1500", cmds)
        self.assertIn("router rip", cmds)
        self.assertIn("redistribute eigrp 100 metric 1", cmds)

    def test_mutual_redistribution_same_protocol_error(self):
        """การทำ Mutual Redistribution ต้องใช้ protocol ที่ต่างกัน"""
        with self.assertRaises(ValueError):
            build_mutual_redistribution({"protocol": "ospf"}, {"protocol": "ospf"})

    # -------------------------------------------------------------------------
    # 3. Flask API Endpoints Test
    # -------------------------------------------------------------------------
    def test_api_mutual_redistribute_preview(self):
        """POST /api/routing/mutual-redistribute/preview คืนคำสั่ง Cisco ครบทั้งสองฝั่ง"""
        payload = {
            "proto_a": {
                "protocol": "ospf",
                "process_id": 1,
                "subnets": True
            },
            "proto_b": {
                "protocol": "eigrp",
                "as_number": 100,
                "metric": "10000 100 255 1 1500"
            }
        }
        res = self.client.post("/api/routing/mutual-redistribute/preview", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        cmds = data.get("commands", [])
        self.assertTrue(any("redistribute eigrp 100 subnets" in c for c in cmds))
        self.assertTrue(any("redistribute ospf 1 metric" in c for c in cmds))

        # Check preview string
        preview = data.get("preview", "")
        self.assertIn("configure terminal", preview)
        self.assertIn("end", preview)

    def test_api_mutual_redistribute_apply_validation(self):
        """POST /api/routing/mutual-redistribute/apply ตรวจสอบ device_id และการเชื่อมต่อ"""
        # Missing device_id
        res = self.client.post("/api/routing/mutual-redistribute/apply", json={})
        self.assertEqual(res.status_code, 400)

        # Same protocol error
        res2 = self.client.post("/api/routing/mutual-redistribute/apply", json={
            "device_id": "R1",
            "proto_a": {"protocol": "ospf"},
            "proto_b": {"protocol": "ospf"}
        })
        self.assertEqual(res2.status_code, 400)

    def test_api_routing_preview_with_redistribute(self):
        """POST /api/routing/preview สร้างคำสั่ง redistribute OSPF เข้า EIGRP พร้อม 5 metrics"""
        payload = {
            "route_type": "eigrp",
            "as_num": 100,
            "networks": [{"network": "192.168.10.0", "wildcard": "0.0.0.255"}],
            "redistribute": [
                {
                    "source": "ospf",
                    "process_id": 1,
                    "metric": "10000 100 255 1 1500"
                }
            ]
        }
        res = self.client.post("/api/routing/preview", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        cmds = data.get("commands", [])
        self.assertTrue(any("redistribute ospf 1 metric 10000 100 255 1 1500" in c for c in cmds))


if __name__ == "__main__":
    unittest.main()
