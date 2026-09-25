"""
tests/test_multi_subnet_topology.py
Unit tests verifying multi-subnet auto-discovery in topology_builder.py
"""

import unittest
import networkx as nx
from topology_builder import _smart_subnet_matching, graph_to_json, collect_device_interfaces


class TestMultiSubnetTopology(unittest.TestCase):

    def test_two_routers_with_two_distinct_subnets(self):
        """
        Scenario 1: R1 and R2 have 2 separate links on 2 different subnets:
        - Subnet 1: 10.1.1.0/24 on Gi0/1 (10.1.1.1 <-> 10.1.1.2)
        - Subnet 2: 10.2.2.0/24 on Gi0/2 (10.2.2.1 <-> 10.2.2.2)
        Both links must be created as edges.
        """
        G = nx.MultiGraph()
        G.add_node("R1", name="R1", type="router")
        G.add_node("R2", name="R2", type="router")

        ifaces = {
            "R1": [
                {"name": "Gi0/1", "ip": "10.1.1.1", "mask": "255.255.255.0"},
                {"name": "Gi0/2", "ip": "10.2.2.1", "mask": "255.255.255.0"}
            ],
            "R2": [
                {"name": "Gi0/1", "ip": "10.1.1.2", "mask": "255.255.255.0"},
                {"name": "Gi0/2", "ip": "10.2.2.2", "mask": "255.255.255.0"}
            ]
        }

        G = _smart_subnet_matching(G, ifaces)
        res = graph_to_json(G)
        edges = res["edges"]

        self.assertEqual(len(edges), 2, f"Expected 2 edges for 2 subnets, got {len(edges)}")
        subnets = {e.get("subnet") for e in edges}
        self.assertIn("10.1.1.0/24", subnets)
        self.assertIn("10.2.2.0/24", subnets)

    def test_three_subnets_daisy_chain(self):
        """
        Scenario 2: Three devices in a line across 3 different subnets:
        R1 (10.1.1.1/24) <-> (10.1.1.2/24) R2
        R2 (10.2.2.1/24) <-> (10.2.2.2/24) R3
        R3 (192.168.1.1/24) <-> (192.168.1.10/24) PC1
        """
        G = nx.MultiGraph()
        G.add_node("R1", name="R1", type="router")
        G.add_node("R2", name="R2", type="router")
        G.add_node("R3", name="R3", type="router")
        G.add_node("PC1", name="PC1", type="pc")

        ifaces = {
            "R1": [{"name": "Gi0/1", "ip": "10.1.1.1", "mask": "255.255.255.0"}],
            "R2": [
                {"name": "Gi0/1", "ip": "10.1.1.2", "mask": "255.255.255.0"},
                {"name": "Gi0/2", "ip": "10.2.2.1", "mask": "255.255.255.0"}
            ],
            "R3": [
                {"name": "Gi0/1", "ip": "10.2.2.2", "mask": "255.255.255.0"},
                {"name": "Gi0/2", "ip": "192.168.1.1", "mask": "255.255.255.0"}
            ],
            "PC1": [{"name": "ens3", "ip": "192.168.1.10", "mask": "255.255.255.0"}]
        }

        G = _smart_subnet_matching(G, ifaces)
        res = graph_to_json(G)
        edges = res["edges"]

        self.assertEqual(len(edges), 3, f"Expected 3 edges for 3 subnets, got {len(edges)}")
        pairs = {(e["from"], e["to"]) for e in edges} | {(e["to"], e["from"]) for e in edges}
        self.assertIn(("R1", "R2"), pairs)
        self.assertIn(("R2", "R3"), pairs)
        self.assertIn(("R3", "PC1"), pairs)

    def test_multi_access_and_point_to_point_subnets_coexist(self):
        """
        Scenario 3:
        Subnet A: 192.168.80.0/24 is a Multi-access segment with 3 routers (R1, R2, R3).
        Subnet B: 10.10.10.0/30 is a PTP link between R1 (10.10.10.1) and R2 (10.10.10.2).
        Subnet C: 172.16.0.0/24 is between R3 (172.16.0.1) and PC1 (172.16.0.50).
        """
        G = nx.MultiGraph()
        for d in ["R1", "R2", "R3", "PC1"]:
            G.add_node(d, name=d, type="router" if d.startswith("R") else "pc")

        ifaces = {
            "R1": [
                {"name": "Et0/0", "ip": "192.168.80.138", "mask": "255.255.255.0"},
                {"name": "Et0/1", "ip": "10.10.10.1", "mask": "255.255.255.252"}
            ],
            "R2": [
                {"name": "Et0/0", "ip": "192.168.80.137", "mask": "255.255.255.0"},
                {"name": "Et0/1", "ip": "10.10.10.2", "mask": "255.255.255.252"}
            ],
            "R3": [
                {"name": "Et0/0", "ip": "192.168.80.136", "mask": "255.255.255.0"},
                {"name": "Et0/1", "ip": "172.16.0.1", "mask": "255.255.255.0"}
            ],
            "PC1": [
                {"name": "ens3", "ip": "172.16.0.50", "mask": "255.255.255.0"}
            ]
        }

        G = _smart_subnet_matching(G, ifaces)
        res = graph_to_json(G)
        edges = res["edges"]

        # Should have:
        # - R1 <-> R2 on 10.10.10.0/30
        # - R3 <-> PC1 on 172.16.0.0/24
        # - R1, R2, R3 connected to Net_192_168_80_0_24
        # Total edges = 1 + 1 + 3 = 5
        self.assertEqual(len(edges), 5)

    def test_cdp_does_not_suppress_subnet_matching_on_other_subnets(self):
        """
        Scenario 4 (CRITICAL BUG REPRODUCTION):
        R1 and R2 are connected via CDP on Subnet 1 (192.168.80.0/24).
        R2 and R3 are on Subnet 2 (10.1.1.0/24) where CDP is NOT present.
        R3 and PC1 are on Subnet 3 (172.16.1.0/24).
        CDP discovery must NOT suppress Subnet-matching on Subnet 2 and Subnet 3!
        """
        from topology_builder import build_topology_graph

        class MockConnMgr:
            def is_connected(self, d):
                return True
            def send_command(self, d, cmd, **kwargs):
                if "cdp" in cmd and d == "R1":
                    # CDP finds R2
                    return {
                        "success": True,
                        "output": "Device ID: R2\nIP address: 192.168.80.137\nInterface: Et0/0, Port ID: Et0/0\n"
                    }
                return {"success": False, "output": ""}

        inv = [
            {"id": "R1", "name": "R1", "device_type_label": "router", "ip": "192.168.80.138"},
            {"id": "R2", "name": "R2", "device_type_label": "router", "ip": "192.168.80.137"},
            {"id": "R3", "name": "R3", "device_type_label": "router", "ip": "10.1.1.2"},
            {"id": "PC1", "name": "PC1", "device_type_label": "pc", "ip": "172.16.1.10"}
        ]

        # Patch collect_device_interfaces to return multi-subnet interfaces
        import topology_builder
        orig_collect = topology_builder.collect_device_interfaces
        try:
            topology_builder.collect_device_interfaces = lambda mgr, d: {
                "R1": [
                    {"name": "Et0/0", "ip": "192.168.80.138", "mask": "255.255.255.0"}
                ],
                "R2": [
                    {"name": "Et0/0", "ip": "192.168.80.137", "mask": "255.255.255.0"},
                    {"name": "Et0/1", "ip": "10.1.1.1", "mask": "255.255.255.0"}
                ],
                "R3": [
                    {"name": "Et0/1", "ip": "10.1.1.2", "mask": "255.255.255.0"},
                    {"name": "Et0/2", "ip": "172.16.1.1", "mask": "255.255.255.0"}
                ],
                "PC1": [
                    {"name": "ens3", "ip": "172.16.1.10", "mask": "255.255.255.0"}
                ]
            }.get(d, [])

            G = build_topology_graph(MockConnMgr(), ["R1", "R2", "R3", "PC1"], inv)
            res = graph_to_json(G)
            edges = res["edges"]

            # Edge 1: R1 <-> R2 (from CDP)
            # Edge 2: R2 <-> R3 on 10.1.1.0/24 (from Subnet-matching)
            # Edge 3: R3 <-> PC1 on 172.16.1.0/24 (from Subnet-matching)
            pairs = {(e["from"], e["to"]) for e in edges} | {(e["to"], e["from"]) for e in edges}

            self.assertIn(("R1", "R2"), pairs, "R1 and R2 should be connected via CDP")
            self.assertIn(("R2", "R3"), pairs, "R2 and R3 must be connected via Subnet 2 matching even when CDP is found on R1-R2!")
            self.assertIn(("R3", "PC1"), pairs, "R3 and PC1 must be connected via Subnet 3 matching!")
        finally:
            topology_builder.collect_device_interfaces = orig_collect

    def test_collect_device_interfaces_for_linux_pc(self):
        """
        Scenario 5 (LINUX PC BUG REPRODUCTION):
        When PC1 is connected via SSH, collect_device_interfaces must execute
        'ip -br addr' or similar Linux command, rather than 'show ip interface brief'
        which fails on Linux and causes PC1 to have no interfaces in topology.
        """
        from topology_builder import collect_device_interfaces

        class MockLinuxConnMgr:
            def is_connected(self, d):
                return True
            def send_command(self, d, cmd, **kwargs):
                if "show ip interface brief" in cmd:
                    # Cisco command fails on Linux
                    return {"success": False, "output": "bash: show: command not found"}
                if "ip -br addr" in cmd or "ip -o addr" in cmd:
                    return {
                        "success": True,
                        "output": "lo               UNKNOWN        127.0.0.1/8 ::1/128 \nens3             UP             192.168.80.139/24 fe80::5054:ff:fe12:3456/64"
                    }
                return {"success": False, "output": ""}

        ifaces = collect_device_interfaces(MockLinuxConnMgr(), "PC1")
        self.assertTrue(len(ifaces) > 0, "Linux PC interfaces must not be empty!")
        ens3 = next((i for i in ifaces if i["name"] == "ens3"), None)
        self.assertIsNotNone(ens3, "Should have parsed 'ens3'")
        self.assertEqual(ens3["ip"], "192.168.80.139")


if __name__ == "__main__":
    unittest.main()
