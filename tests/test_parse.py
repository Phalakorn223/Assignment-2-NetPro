import sys
from connection_manager import parse_ip_interface_brief

out = """Interface                  IP-Address      OK? Method Status                Protocol
Ethernet0/0                192.168.74.133  YES DHCP   up                    up      
Ethernet0/1                unassigned      YES NVRAM  administratively down down    
Ethernet0/2                unassigned      YES NVRAM  administratively down down    
Ethernet0/3                unassigned      YES NVRAM  administratively down down    
R1#"""

print(parse_ip_interface_brief(out))
