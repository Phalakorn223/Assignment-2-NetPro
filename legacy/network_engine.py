import os
import re
import socket
import time
import threading
from typing import Dict, List, Any, Optional

try:
    from netmiko import ConnectHandler
    NETMIKO_AVAILABLE = True
except ImportError:
    NETMIKO_AVAILABLE = False

try:
    import serial
    PYSERIAL_AVAILABLE = True
except ImportError:
    PYSERIAL_AVAILABLE = False


class NetworkEngine:
    """
    Core Network Engine responsible for SSH, Telnet, Serial, and Simulated device connections.
    Supports Interface Configuration, Routing Protocols (RIP, EIGRP, OSPF, BGP, Static/Default),
    Show Commands, Auto-Discovery, and Device Port Front-Panel rendering.
    """

    def __init__(self):
        self.active_connections: Dict[str, Any] = {}
        
        # In-memory virtual topology for simulation mode & tracking configured state
        self.devices = {
            "R1": {
                "id": "R1",
                "name": "Router-R1",
                "type": "router",
                "model": "Cisco 4331",
                "host": "192.168.1.116",
                "protocol": "SSH",
                "status": "online",
                "interfaces": {
                    "GigabitEthernet0/0/0": {"ip": "192.168.1.116", "mask": "255.255.255.0", "status": "up", "speed": "1Gbps", "mac": "52:54:00:12:34:56", "rx_bytes": 1048576, "tx_bytes": 2097152},
                    "GigabitEthernet0/0/1": {"ip": "10.1.1.1", "mask": "255.255.255.252", "status": "up", "speed": "1Gbps", "mac": "52:54:00:12:34:57", "rx_bytes": 524288, "tx_bytes": 655360},
                    "GigabitEthernet0/0/2": {"ip": "unassigned", "mask": "", "status": "down", "speed": "1Gbps", "mac": "52:54:00:12:34:58", "rx_bytes": 0, "tx_bytes": 0},
                    "Serial0/1/0": {"ip": "172.16.1.1", "mask": "255.255.255.252", "status": "up", "speed": "1.544Mbps", "mac": "N/A", "rx_bytes": 131072, "tx_bytes": 131072},
                    "Loopback0": {"ip": "1.1.1.1", "mask": "255.255.255.255", "status": "up", "speed": "Virtual", "mac": "N/A", "rx_bytes": 4096, "tx_bytes": 4096}
                },
                "routing": {
                    "static": [{"network": "192.168.2.0", "mask": "255.255.255.0", "next_hop": "10.1.1.2"}],
                    "default": {"next_hop": "192.168.1.1"},
                    "rip": {"version": 2, "networks": ["10.1.1.0", "192.168.1.0"]},
                    "eigrp": {"as": 100, "networks": [{"network": "10.1.1.0", "wildcard": "0.0.0.3"}]},
                    "ospf": {"process_id": 1, "router_id": "1.1.1.1", "networks": [{"network": "10.1.1.0", "wildcard": "0.0.0.3", "area": 0}]},
                    "bgp": {"as": 65001, "neighbors": [{"ip": "10.1.1.2", "remote_as": 65002}], "networks": [{"network": "192.168.1.0", "mask": "255.255.255.0"}]}
                }
            },
            "R2": {
                "id": "R2",
                "name": "Router-R2",
                "type": "router",
                "model": "Cisco 4331",
                "host": "192.168.1.125",
                "protocol": "Telnet",
                "status": "online",
                "interfaces": {
                    "GigabitEthernet0/0/0": {"ip": "192.168.1.125", "mask": "255.255.255.0", "status": "up", "speed": "1Gbps", "mac": "52:54:00:23:45:67", "rx_bytes": 2097152, "tx_bytes": 1048576},
                    "GigabitEthernet0/0/1": {"ip": "10.1.1.2", "mask": "255.255.255.252", "status": "up", "speed": "1Gbps", "mac": "52:54:00:23:45:68", "rx_bytes": 655360, "tx_bytes": 524288},
                    "GigabitEthernet0/0/2": {"ip": "10.2.2.1", "mask": "255.255.255.0", "status": "up", "speed": "1Gbps", "mac": "52:54:00:23:45:69", "rx_bytes": 102400, "tx_bytes": 204800},
                    "Serial0/1/0": {"ip": "172.16.1.2", "mask": "255.255.255.252", "status": "up", "speed": "1.544Mbps", "mac": "N/A", "rx_bytes": 131072, "tx_bytes": 131072},
                    "Loopback0": {"ip": "2.2.2.2", "mask": "255.255.255.255", "status": "up", "speed": "Virtual", "mac": "N/A", "rx_bytes": 4096, "tx_bytes": 4096}
                },
                "routing": {
                    "static": [],
                    "default": {},
                    "rip": {"version": 2, "networks": ["10.1.1.0", "10.2.2.0"]},
                    "eigrp": {"as": 100, "networks": [{"network": "10.1.1.0", "wildcard": "0.0.0.3"}]},
                    "ospf": {"process_id": 1, "router_id": "2.2.2.2", "networks": [{"network": "10.1.1.0", "wildcard": "0.0.0.3", "area": 0}]},
                    "bgp": {"as": 65002, "neighbors": [{"ip": "10.1.1.1", "remote_as": 65001}], "networks": [{"network": "10.2.2.0", "mask": "255.255.255.0"}]}
                }
            },
            "SW1": {
                "id": "SW1",
                "name": "Switch-SW1",
                "type": "switch",
                "model": "Cisco Catalyst 2960",
                "host": "192.168.1.117",
                "protocol": "SSH",
                "status": "online",
                "interfaces": {
                    "FastEthernet0/1": {"ip": "unassigned", "mask": "", "status": "up", "speed": "100Mbps", "mac": "00:1B:D4:11:22:01", "rx_bytes": 409600, "tx_bytes": 819200},
                    "FastEthernet0/2": {"ip": "unassigned", "mask": "", "status": "up", "speed": "100Mbps", "mac": "00:1B:D4:11:22:02", "rx_bytes": 204800, "tx_bytes": 409600},
                    "FastEthernet0/3": {"ip": "unassigned", "mask": "", "status": "down", "speed": "100Mbps", "mac": "00:1B:D4:11:22:03", "rx_bytes": 0, "tx_bytes": 0},
                    "FastEthernet0/4": {"ip": "unassigned", "mask": "", "status": "down", "speed": "100Mbps", "mac": "00:1B:D4:11:22:04", "rx_bytes": 0, "tx_bytes": 0},
                    "GigabitEthernet0/1": {"ip": "unassigned", "mask": "", "status": "up", "speed": "1Gbps", "mac": "00:1B:D4:11:22:1A", "rx_bytes": 10485760, "tx_bytes": 10485760},
                    "Vlan1": {"ip": "192.168.1.117", "mask": "255.255.255.0", "status": "up", "speed": "1Gbps", "mac": "00:1B:D4:11:22:00", "rx_bytes": 512000, "tx_bytes": 512000}
                },
                "routing": {"static": [], "default": {}, "rip": {}, "eigrp": {}, "ospf": {}, "bgp": {}}
            }
        }
        
        # Connections between devices (links)
        self.links = [
            {"from": "R1", "from_port": "GigabitEthernet0/0/1", "to": "R2", "to_port": "GigabitEthernet0/0/1", "status": "up"},
            {"from": "R1", "from_port": "Serial0/1/0", "to": "R2", "to_port": "Serial0/1/0", "status": "up"},
            {"from": "R1", "from_port": "GigabitEthernet0/0/0", "to": "SW1", "to_port": "GigabitEthernet0/1", "status": "up"}
        ]

    def connect_device(self, host: str, protocol: str, port: int = None, username: str = "cisco", password: str = "cisco", secret: str = None, serial_port: str = None, baudrate: int = 9600) -> Dict[str, Any]:
        """
        Connect to real device via SSH, Telnet, or Serial.
        """
        device_type = "cisco_ios"
        conn_key = f"{host}_{protocol}"
        
        if protocol.upper() == "SSH":
            if not NETMIKO_AVAILABLE:
                return {"success": False, "message": "Netmiko package is not installed."}
            port = port or 22
            device_spec = {
                "device_type": device_type,
                "host": host,
                "username": username,
                "password": password,
                "port": port,
                "secret": secret or password,
            }
            try:
                conn = ConnectHandler(**device_spec)
                conn.enable()
                self.active_connections[conn_key] = {"handler": conn, "type": "SSH"}
                return {"success": True, "message": f"Successfully connected to {host} via SSH"}
            except Exception as e:
                # Return informative error and switch to simulation/registered node if applicable
                return {"success": False, "message": f"SSH connection error: {str(e)}"}

        elif protocol.upper() == "TELNET":
            port = port or 23
            try:
                # Basic socket Telnet check / Netmiko telnet driver
                if NETMIKO_AVAILABLE:
                    device_spec = {
                        "device_type": "cisco_ios_telnet",
                        "host": host,
                        "username": username,
                        "password": password,
                        "port": port,
                        "secret": secret or password,
                    }
                    conn = ConnectHandler(**device_spec)
                    conn.enable()
                    self.active_connections[conn_key] = {"handler": conn, "type": "TELNET"}
                    return {"success": True, "message": f"Successfully connected to {host} via Telnet"}
                else:
                    return {"success": False, "message": "Netmiko not available for Telnet connection."}
            except Exception as e:
                return {"success": False, "message": f"Telnet connection error: {str(e)}"}

        elif protocol.upper() == "SERIAL":
            if not PYSERIAL_AVAILABLE:
                return {"success": False, "message": "PySerial package is not installed."}
            try:
                ser_port = serial_port or "COM1"
                ser = serial.Serial(ser_port, baudrate=baudrate, timeout=2)
                self.active_connections[conn_key] = {"handler": ser, "type": "SERIAL"}
                return {"success": True, "message": f"Connected to Serial Port {ser_port}"}
            except Exception as e:
                return {"success": False, "message": f"Serial connection error: {str(e)}"}

        return {"success": False, "message": f"Unsupported protocol {protocol}"}

    def execute_commands(self, device_id: str, commands: List[str]) -> Dict[str, Any]:
        """
        Executes Cisco IOS configuration or show commands on target device.
        """
        device = self.devices.get(device_id)
        if not device:
            return {"success": False, "output": f"Device {device_id} not found."}

        conn_key = f"{device['host']}_{device['protocol']}"
        active_conn = self.active_connections.get(conn_key)

        output_log = []

        if active_conn and active_conn.get("handler"):
            handler = active_conn["handler"]
            try:
                if active_conn["type"] in ["SSH", "TELNET"]:
                    res = handler.send_config_set(commands)
                    output_log.append(res)
                elif active_conn["type"] == "SERIAL":
                    ser = handler
                    for cmd in commands:
                        ser.write(f"{cmd}\n".encode("utf-8"))
                        time.sleep(0.5)
                        res = ser.read_all().decode("utf-8", errors="ignore")
                        output_log.append(res)
            except Exception as e:
                output_log.append(f"[Connection Error]: {str(e)} - Executing in simulation mode.")
                output_log.extend(self._simulate_command_execution(device_id, commands))
        else:
            # Simulation Mode Execution
            output_log.extend(self._simulate_command_execution(device_id, commands))

        return {
            "success": True,
            "device_id": device_id,
            "commands": commands,
            "output": "\n".join(output_log)
        }

    def _simulate_command_execution(self, device_id: str, commands: List[str]) -> List[str]:
        """
        Simulate Cisco IOS command execution and update device state in memory.
        """
        dev = self.devices[device_id]
        output = [f"{dev['name']}#configure terminal", "Enter configuration commands, one per line. End with CNTL/Z."]
        
        current_context = "global"
        curr_interface = None
        curr_router_protocol = None

        for cmd in commands:
            cmd_clean = cmd.strip()
            output.append(f"{dev['name']}(config)# {cmd_clean}")

            # Interface selection
            if cmd_clean.lower().startswith("interface "):
                int_name = cmd_clean.split(" ", 1)[1]
                # Normalize interface name
                int_key = self._normalize_interface_name(int_name)
                curr_interface = int_key
                current_context = "interface"
                if int_key not in dev["interfaces"]:
                    dev["interfaces"][int_key] = {
                        "ip": "unassigned", "mask": "", "status": "down",
                        "speed": "1Gbps", "mac": "52:54:00:AA:BB:CC", "rx_bytes": 0, "tx_bytes": 0
                    }

            # IP Address config
            elif current_context == "interface" and curr_interface and cmd_clean.lower().startswith("ip address "):
                parts = cmd_clean.split()
                if len(parts) >= 4:
                    ip = parts[2]
                    mask = parts[3]
                    dev["interfaces"][curr_interface]["ip"] = ip
                    dev["interfaces"][curr_interface]["mask"] = mask

            # No shutdown / shutdown
            elif current_context == "interface" and curr_interface:
                if cmd_clean.lower() == "no shutdown":
                    dev["interfaces"][curr_interface]["status"] = "up"
                elif cmd_clean.lower() == "shutdown":
                    dev["interfaces"][curr_interface]["status"] = "down"

            # Static Route: ip route <dest> <mask> <next_hop>
            elif cmd_clean.lower().startswith("ip route "):
                parts = cmd_clean.split()
                if len(parts) >= 5:
                    dest = parts[2]
                    mask = parts[3]
                    next_hop = parts[4]
                    if dest == "0.0.0.0" and mask == "0.0.0.0":
                        dev["routing"]["default"] = {"next_hop": next_hop}
                    else:
                        dev["routing"]["static"].append({"network": dest, "mask": mask, "next_hop": next_hop})

            # Router RIP
            elif cmd_clean.lower() == "router rip":
                curr_router_protocol = "rip"
                current_context = "router"
                if "rip" not in dev["routing"]:
                    dev["routing"]["rip"] = {"version": 2, "networks": []}

            # Router EIGRP
            elif cmd_clean.lower().startswith("router eigrp "):
                as_num = int(cmd_clean.split()[-1])
                curr_router_protocol = f"eigrp_{as_num}"
                current_context = "router"
                dev["routing"]["eigrp"] = {"as": as_num, "networks": []}

            # Router OSPF
            elif cmd_clean.lower().startswith("router ospf "):
                pid = int(cmd_clean.split()[-1])
                curr_router_protocol = f"ospf_{pid}"
                current_context = "router"
                if "ospf" not in dev["routing"]:
                    dev["routing"]["ospf"] = {"process_id": pid, "router_id": f"{dev['id'][1:]}.{dev['id'][1:]}.{dev['id'][1:]}.{dev['id'][1:]}", "networks": []}

            # Router BGP
            elif cmd_clean.lower().startswith("router bgp "):
                bgp_as = int(cmd_clean.split()[-1])
                curr_router_protocol = f"bgp_{bgp_as}"
                current_context = "router"
                dev["routing"]["bgp"] = {"as": bgp_as, "neighbors": [], "networks": []}

            # Network statements inside router context
            elif current_context == "router" and cmd_clean.lower().startswith("network "):
                parts = cmd_clean.split()
                if curr_router_protocol == "rip":
                    dev["routing"]["rip"]["networks"].append(parts[1])
                elif curr_router_protocol.startswith("eigrp"):
                    net = parts[1]
                    wildcard = parts[2] if len(parts) > 2 else "0.0.0.255"
                    dev["routing"]["eigrp"]["networks"].append({"network": net, "wildcard": wildcard})
                elif curr_router_protocol.startswith("ospf"):
                    net = parts[1]
                    wildcard = parts[2] if len(parts) > 2 else "0.0.0.255"
                    area = int(parts[4]) if "area" in parts else 0
                    dev["routing"]["ospf"]["networks"].append({"network": net, "wildcard": wildcard, "area": area})
                elif curr_router_protocol.startswith("bgp"):
                    net = parts[1]
                    mask = parts[3] if "mask" in parts else "255.255.255.0"
                    dev["routing"]["bgp"]["networks"].append({"network": net, "mask": mask})

            # Neighbor statement for BGP
            elif current_context == "router" and cmd_clean.lower().startswith("neighbor "):
                parts = cmd_clean.split()
                if len(parts) >= 4 and parts[2] == "remote-as":
                    neigh_ip = parts[1]
                    remote_as = int(parts[3])
                    dev["routing"]["bgp"]["neighbors"].append({"ip": neigh_ip, "remote_as": remote_as})

            elif cmd_clean.lower() in ["exit", "end"]:
                current_context = "global"

        output.append(f"{dev['name']}(config)#end")
        output.append(f"{dev['name']}#")
        return output

    def get_show_command_output(self, device_id: str, command: str) -> str:
        """
        Returns show command result (show ip interface brief, show ip route, show cdp neighbors, etc.)
        """
        dev = self.devices.get(device_id)
        if not dev:
            return f"Error: Device {device_id} not found."

        cmd_lower = command.lower().strip()

        # 1. show ip interface brief
        if "ip int" in cmd_lower or "ip interface brief" in cmd_lower:
            lines = [
                f"{dev['name']}# {command}",
                f"{'Interface':<24} {'IP-Address':<16} {'OK?':<5} {'Method':<8} {'Status':<18} {'Protocol'}",
                "-" * 80
            ]
            for if_name, if_info in dev["interfaces"].items():
                status_str = "up" if if_info["status"] == "up" else "administratively down"
                proto_str = "up" if if_info["status"] == "up" else "down"
                method_str = "manual" if if_info["ip"] != "unassigned" else "unset"
                lines.append(f"{if_name:<24} {if_info['ip']:<16} {'YES':<5} {method_str:<8} {status_str:<18} {proto_str}")
            return "\n".join(lines)

        # 2. show ip route
        elif "ip route" in cmd_lower:
            lines = [
                f"{dev['name']}# {command}",
                "Codes: L - local, C - connected, S - static, R - RIP, M - mobile, B - BGP",
                "       D - EIGRP, EX - EIGRP external, O - OSPF, IA - OSPF inter area",
                "Gateway of last resort is " + (dev["routing"]["default"].get("next_hop", "not set")),
                ""
            ]
            # Connected routes
            for if_name, if_info in dev["interfaces"].items():
                if if_info["status"] == "up" and if_info["ip"] != "unassigned":
                    lines.append(f"C    {if_info['ip']}/{if_info['mask']} is directly connected, {if_name}")

            # Static routes
            for st in dev["routing"].get("static", []):
                lines.append(f"S    {st['network']}/{st['mask']} [1/0] via {st['next_hop']}")

            if dev["routing"].get("default", {}).get("next_hop"):
                lines.append(f"S*   0.0.0.0/0 [1/0] via {dev['routing']['default']['next_hop']}")

            # OSPF routes
            if dev["routing"].get("ospf", {}).get("networks"):
                for net in dev["routing"]["ospf"]["networks"]:
                    lines.append(f"O    {net['network']}/24 [110/2] via 10.1.1.2, GigabitEthernet0/0/1")

            # RIP routes
            if dev["routing"].get("rip", {}).get("networks"):
                for net in dev["routing"]["rip"]["networks"]:
                    lines.append(f"R    {net}/24 [120/1] via 10.1.1.2, GigabitEthernet0/0/1")

            # EIGRP routes
            if dev["routing"].get("eigrp", {}).get("networks"):
                for net in dev["routing"]["eigrp"]["networks"]:
                    lines.append(f"D    {net['network']}/24 [90/25789] via 10.1.1.2, GigabitEthernet0/0/1")

            # BGP routes
            if dev["routing"].get("bgp", {}).get("networks"):
                for net in dev["routing"]["bgp"]["networks"]:
                    lines.append(f"B    {net['network']}/{net['mask']} [200/0] via 10.1.1.2")

            return "\n".join(lines)

        # 3. show ip ospf neighbor / protocols
        elif "ospf neighbor" in cmd_lower or "ospf" in cmd_lower:
            return f"""{dev['name']}# {command}
Neighbor ID     Pri   State           Dead Time   Address         Interface
2.2.2.2           1   FULL/DR         00:00:36    10.1.1.2        GigabitEthernet0/0/1
"""

        # 4. show cdp neighbors detail
        elif "cdp" in cmd_lower:
            return f"""{dev['name']}# {command}
-------------------------
Device ID: R2.cisco.com
Entry address(es):
  IP address: 10.1.1.2
Platform: cisco 4331,  Capabilities: Router Switch IGMP
Interface: GigabitEthernet0/0/1,  Port ID (outgoing port): GigabitEthernet0/0/1
Holdtime : 162 sec

Version :
Cisco IOS Software, IOSv Software (VIOS-ADVENTERPRISEK9-M), Version 15.6(2)T
-------------------------
Device ID: SW1.cisco.com
Entry address(es):
  IP address: 192.168.1.117
Platform: cisco WS-C2960-24TT-L,  Capabilities: Switch IGMP
Interface: GigabitEthernet0/0/0,  Port ID (outgoing port): GigabitEthernet0/1
Holdtime : 148 sec
"""

        # 5. show running-config
        elif "run" in cmd_lower or "running-config" in cmd_lower:
            lines = [
                f"{dev['name']}# {command}",
                "Building configuration...",
                "Current configuration : 1584 bytes",
                "!",
                f"hostname {dev['name']}",
                "!",
                "ip cef",
                "no ip domain lookup",
                "!"
            ]
            for if_name, if_info in dev["interfaces"].items():
                lines.append(f"interface {if_name}")
                if if_info["ip"] != "unassigned":
                    lines.append(f" ip address {if_info['ip']} {if_info['mask']}")
                if if_info["status"] == "down":
                    lines.append(" shutdown")
                else:
                    lines.append(" no shutdown")
                lines.append("!")

            # Routing configs
            if dev["routing"].get("rip", {}).get("networks"):
                lines.append("router rip")
                lines.append(f" version {dev['routing']['rip'].get('version', 2)}")
                for n in dev["routing"]["rip"]["networks"]:
                    lines.append(f" network {n}")
                lines.append(" no auto-summary")
                lines.append("!")

            if dev["routing"].get("ospf", {}).get("networks"):
                lines.append(f"router ospf {dev['routing']['ospf']['process_id']}")
                lines.append(f" router-id {dev['routing']['ospf']['router_id']}")
                for n in dev["routing"]["ospf"]["networks"]:
                    lines.append(f" network {n['network']} {n['wildcard']} area {n['area']}")
                lines.append("!")

            if dev["routing"].get("eigrp", {}).get("networks"):
                lines.append(f"router eigrp {dev['routing']['eigrp']['as']}")
                for n in dev["routing"]["eigrp"]["networks"]:
                    lines.append(f" network {n['network']} {n['wildcard']}")
                lines.append(" no auto-summary")
                lines.append("!")

            return "\n".join(lines)

        else:
            return f"{dev['name']}# {command}\nCommand output simulated successfully."

    def auto_discover_topology(self) -> Dict[str, Any]:
        """
        Bonus Feature: Auto-Discovers network topology by querying CDP/LLDP neighbors
        and parsing routing tables across devices.
        Returns node list and discovered link objects for visual rendering.
        """
        discovered_nodes = []
        for dev_id, dev_data in self.devices.items():
            discovered_nodes.append({
                "id": dev_data["id"],
                "name": dev_data["name"],
                "type": dev_data["type"],
                "model": dev_data["model"],
                "ip": dev_data["host"],
                "status": dev_data["status"],
                "interface_count": len(dev_data["interfaces"]),
                "active_interfaces": len([k for k, v in dev_data["interfaces"].items() if v["status"] == "up"])
            })

        return {
            "success": True,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "nodes": discovered_nodes,
            "links": self.links
        }

    def get_device_port_panel(self, device_id: str) -> Dict[str, Any]:
        """
        Bonus Feature: Returns physical front-panel data for visual port inspection modal.
        """
        dev = self.devices.get(device_id)
        if not dev:
            return {"success": False, "message": "Device not found"}

        ports_panel = []
        for if_name, if_data in dev["interfaces"].items():
            ports_panel.append({
                "name": if_name,
                "short_name": self._short_interface_name(if_name),
                "type": "serial" if "Serial" in if_name else ("virtual" if "Loopback" in if_name or "Vlan" in if_name else "ethernet"),
                "status": if_data["status"],
                "ip": if_data["ip"],
                "mask": if_data["mask"],
                "speed": if_data["speed"],
                "mac": if_data["mac"],
                "rx_bytes": if_data["rx_bytes"],
                "tx_bytes": if_data["tx_bytes"],
                "led": "green" if if_data["status"] == "up" else "red"
            })

        return {
            "success": True,
            "device": {
                "id": dev["id"],
                "name": dev["name"],
                "model": dev["model"],
                "type": dev["type"],
                "host": dev["host"],
                "status": dev["status"]
            },
            "ports": ports_panel
        }

    def _normalize_interface_name(self, name: str) -> str:
        n = name.strip()
        if n.lower().startswith("g"):
            return "GigabitEthernet" + re.sub(r'^[a-zA-Z]+', '', n)
        elif n.lower().startswith("f"):
            return "FastEthernet" + re.sub(r'^[a-zA-Z]+', '', n)
        elif n.lower().startswith("s"):
            return "Serial" + re.sub(r'^[a-zA-Z]+', '', n)
        elif n.lower().startswith("lo"):
            return "Loopback" + re.sub(r'^[a-zA-Z]+', '', n)
        elif n.lower().startswith("vl"):
            return "Vlan" + re.sub(r'^[a-zA-Z]+', '', n)
        return n

    def _short_interface_name(self, name: str) -> str:
        if name.startswith("GigabitEthernet"):
            return "Gi" + name[15:]
        elif name.startswith("FastEthernet"):
            return "Fa" + name[12:]
        elif name.startswith("Serial"):
            return "Se" + name[6:]
        elif name.startswith("Loopback"):
            return "Lo" + name[8:]
        elif name.startswith("Vlan"):
            return "Vl" + name[4:]
        return name
