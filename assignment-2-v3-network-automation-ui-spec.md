# Network Automation UI — Implementation Specification

> **Purpose:** เอกสารนี้แปลงข้อกำหนดและแนวทางจากไฟล์ต้นฉบับให้เป็น Specification ที่สามารถใช้เป็นฐานสำหรับการ implement code ต่อได้ โดยคงขอบเขต ฟังก์ชัน และ workflow ตามต้นฉบับเป็นหลัก

---

## 1. Project Overview

โปรเจกต์คือ **Network Automation UI** ที่มีแนวคิดคล้าย Cisco Packet Tracer โดยผู้ใช้สามารถวาง/สร้างอุปกรณ์บน UI, เชื่อมต่ออุปกรณ์ และกำหนดค่าผ่าน GUI หรือ CLI ได้

### เป้าหมายหลัก

- สร้าง UI สำหรับจัดการ Network Device
- รองรับ EVE-NG/GNS3 และอุปกรณ์จริง
- รองรับการเชื่อมต่อ:
  - SSH
  - Telnet
  - Serial
- กำหนดค่า Interface
- กำหนด Routing
- ดูคำสั่ง `show`
- มี Free-form CLI Terminal
- มี Auto Discovery เป็นฟีเจอร์โบนัส
- แยกขั้นตอนการออกแบบ Topology ออกจากการเชื่อมต่ออุปกรณ์จริง

---

# 2. Functional Requirements

## 2.1 Device Management

### Add Device

การสร้างอุปกรณ์ใหม่ **ไม่จำเป็นต้องกรอกข้อมูล Connection ตั้งแต่แรก**

ข้อมูลที่ต้องกรอก:

| Field | Required | Description |
|---|---:|---|
| Device Name | Yes | ชื่ออุปกรณ์ |
| Device Type | Yes | Router / Switch |
| Model | Yes | รุ่นของอุปกรณ์ |

### Device Type

รองรับอย่างน้อย:

- Router
- Switch

### Model

Model ควรเป็น Dropdown และมีประมาณ 3–4 รุ่นยอดนิยมที่ใช้ใน Packet Tracer

> รายละเอียดรุ่นจริงสามารถขยายเพิ่มเติมภายหลัง

---

# 3. Device Interface Model

## 3.1 Default Interfaces

เมื่อเลือก Model ระบบควรสร้าง Interface ตาม Hardware Profile ของ Model โดยอัตโนมัติ

แนวคิด:

```text
Select Model
     │
     ▼
Hardware Profile
     │
     ▼
Factory creates Interfaces
```

### Router

ควรมี GigabitEthernet ตาม Model เช่น:

```text
GigabitEthernet0/0
GigabitEthernet0/1
```

จำนวนจริงขึ้นอยู่กับ Model

### Switch

ตัวอย่าง Hardware Profile:

```text
Catalyst 2960
IOS 15

FastEthernet 24 ports
GigabitEthernet 2 ports
```

ตัวอย่าง:

```text
FastEthernet0/1
FastEthernet0/2
...
FastEthernet0/24

GigabitEthernet0/1
GigabitEthernet0/2
```

---

## 3.2 Additional Interfaces

ไม่จำเป็นต้องสร้าง Serial หรือ Loopback ตั้งแต่ตอน Add Device

ผู้ใช้สามารถเพิ่มภายหลังจาก Device Settings

รองรับแนวคิด:

- Loopback Interface
- Serial Interface / WIC-2T
- Interface Expansion

---

# 4. Connection Profile

Connection Configuration ต้องแยกออกจาก Device Data

## 4.1 Design Phase

ตอนสร้าง Topology ผู้ใช้ยังไม่จำเป็นต้องกรอก:

- IP Address
- Username
- Password
- Connection Type

จุดประสงค์คือให้สามารถสร้าง Topology แบบ Offline ได้ก่อน

---

## 4.2 Execution Phase

เมื่อผู้ใช้ต้องการ Deploy หรือส่ง Configuration จริง จึงค่อยกำหนด Connection Profile

### Connection Type

```text
SSH
Telnet
Serial
```

### Connection Data

สำหรับ SSH/Telnet:

```text
host
port
username
password
```

สำหรับ Serial:

```text
COM Port
baud rate
username/password (ถ้าจำเป็น)
```

> ข้อมูล Credential ไม่ควรผูกติดกับ Device Definition โดยตรงใน Design Phase

---

# 5. Recommended Architecture

## Backend

```text
Python
FastAPI
Netmiko
PySerial
NetworkX
```

### Responsibilities

| Component | Responsibility |
|---|---|
| FastAPI | REST API / WebSocket |
| Netmiko | SSH/Telnet device automation |
| PySerial | Serial Console |
| NetworkX | Topology / graph processing |
| AsyncIO / ThreadPool | Concurrent operations |

---

## Frontend

```text
React
React Flow / Vis-network
Xterm.js
WebSocket
```

### Responsibilities

| Component | Responsibility |
|---|---|
| React | UI / State Management |
| React Flow / Vis-network | Network Topology |
| Xterm.js | CLI Terminal |
| WebSocket | Real-time CLI output |

---

# 6. Suggested System Architecture

```text
┌──────────────────────────────────────────────┐
│                  Frontend                    │
│                                              │
│ React                                        │
│ ├── Topology Editor                          │
│ ├── Device Settings                          │
│ ├── Config Builder                           │
│ ├── Show Commands                            │
│ └── Xterm.js Terminal                        │
│                                              │
└───────────────────┬──────────────────────────┘
                    │
             REST / WebSocket
                    │
┌───────────────────▼──────────────────────────┐
│                  Backend                     │
│                                              │
│ FastAPI                                      │
│ ├── Device API                               │
│ ├── Topology API                             │
│ ├── Configuration API                        │
│ ├── Routing API                              │
│ ├── Connection Manager                       │
│ └── Terminal WebSocket                       │
│                                              │
├──────────────────────────────────────────────┤
│ Network Automation Layer                     │
│ ├── Netmiko                                  │
│ ├── PySerial                                 │
│ ├── AsyncIO / ThreadPool                     │
│ └── Command Builder                          │
└──────────────────────────────────────────────┘
```

---

# 7. Device Data Model

แนะนำให้แยก Device Definition ออกจาก Connection Profile

## Device

```json
{
  "id": "device-001",
  "name": "R1",
  "type": "router",
  "model": "router-model",
  "interfaces": []
}
```

## Interface

```json
{
  "id": "interface-001",
  "name": "GigabitEthernet0/0",
  "type": "gigabitEthernet",
  "ipAddress": null,
  "subnetMask": null,
  "status": "down",
  "description": null
}
```

## Connection Profile

```json
{
  "deviceId": "device-001",
  "type": "ssh",
  "host": null,
  "port": 22,
  "username": null,
  "password": null
}
```

> ตัวอย่าง JSON เป็น implementation guideline จากโครงสร้างใน specification ไม่ใช่ schema ที่ถูกกำหนดตายตัวในต้นฉบับ

---

# 8. Topology Editor

ผู้ใช้สามารถ:

1. Add Device
2. เลือก Device Type
3. เลือก Model
4. วาง Device บน Canvas
5. เชื่อมสายระหว่าง Device
6. Double-click Device เพื่อเลือกเป็น Active Device
7. เปิด Configuration / Terminal ของ Device ที่เลือก

ตัวอย่าง:

```text
        ┌───────┐
        │  R1   │
        └───┬───┘
            │
            │
        ┌───▼───┐
        │  R2   │
        └───┬───┘
            │
        ┌───▼───┐
        │  SW1  │
        └───────┘
```

---

# 9. Active Device System

ระบบต้องมี Global State:

```text
activeDeviceId
```

## Selection Workflow

```text
User double-clicks Device
        │
        ▼
Set activeDeviceId
        │
        ▼
Enable Terminal
        │
        ▼
CLI commands target selected device
```

## ถ้ายังไม่มี Active Device

ต้อง:

- Disable CLI Input
- แสดง Overlay / Warning
- ห้ามส่งคำสั่งไปยัง Device ใด ๆ

ตัวอย่างข้อความ:

```text
Please select a device first.
Double-click a device in the topology.
```

### เหตุผล

ป้องกันการส่ง Configuration ผิดอุปกรณ์

---

# 10. Command Input

ระบบรองรับ 3 รูปแบบ

## 10.1 Raw CLI

ผู้ใช้สามารถพิมพ์ Cisco IOS command ได้โดยตรง

ตัวอย่าง:

```text
show running-config
show ip interface brief
show ip route
```

---

## 10.2 Command Builder

ผู้ใช้กรอกข้อมูลผ่าน Form แล้วระบบสร้าง Cisco IOS command

ตัวอย่าง:

```text
Input:
IP Address = 192.168.1.1
Subnet Mask = 255.255.255.0

Generated:

ip address 192.168.1.1 255.255.255.0
```

---

## 10.3 Command Abbreviation

รองรับคำสั่งย่อเพื่อความสะดวก เช่น:

```text
conf t
int g0/0
sh ip int br
```

ควรมี Local Abbreviation Normalizer Table

---

# 11. Interface Configuration

ระบบต้องรองรับ:

- IP Address
- Subnet Mask
- Up Interface
- Down Interface
- Description

## Configuration Example

```text
interface GigabitEthernet0/0
 ip address 192.168.1.1 255.255.255.0
 no shutdown
 description LAN Connection
```

## Shutdown

```text
interface GigabitEthernet0/0
 shutdown
```

## No Shutdown

```text
interface GigabitEthernet0/0
 no shutdown
```

---

# 12. Input Validation

Backend ต้องตรวจสอบข้อมูลก่อนส่งไปยัง Device

อย่างน้อยควรตรวจสอบ:

- IP Address
- Subnet Mask
- Wildcard Mask
- IP Class ตาม requirement ของระบบ
- Configuration syntax ที่สร้างจาก Form

ตัวอย่าง Flow:

```text
User Input
   │
   ▼
Frontend Validation
   │
   ▼
Backend Validation
   │
   ├── Invalid → Return Error
   │
   └── Valid
         │
         ▼
     Generate CLI
         │
         ▼
     Send to Device
```

---

# 13. Routing Configuration

ระบบต้องรองรับ:

1. Static Route
2. Default Static Route
3. RIP v2
4. EIGRP
5. OSPF
6. BGP

---

## 13.1 Static Route

ตัวอย่างรูปแบบ:

```text
ip route <network> <mask> <next-hop>
```

เช่น:

```text
ip route 192.168.2.0 255.255.255.0 10.0.0.2
```

---

## 13.2 Default Static Route

ตัวอย่าง:

```text
ip route 0.0.0.0 0.0.0.0 <next-hop>
```

---

## 13.3 RIP v2

ตัวอย่าง Configuration:

```text
router rip
 version 2
 network <network>
 no auto-summary
```

---

## 13.4 EIGRP

ตัวอย่าง:

```text
router eigrp <AS>
 network <network>
 no auto-summary
```

---

## 13.5 OSPF

ตัวอย่าง:

```text
router ospf <process-id>
 router-id <router-id>
 network <network> <wildcard> area <area-id>
```

---

## 13.6 BGP

ตัวอย่าง:

```text
router bgp <AS>
 neighbor <neighbor-ip> remote-as <remote-as>
 network <network> mask <mask>
```

---

# 14. Show Commands

ระบบต้องมีชุดคำสั่งพื้นฐานสำหรับตรวจสอบ Network

## Required Commands

### Running Configuration

```text
show running-config
```

### Startup Configuration

```text
show startup-config
```

### Interface Status

```text
show ip interface brief
```

### Routing Table

```text
show ip route
```

### Free-form Show

ผู้ใช้สามารถพิมพ์:

```text
show <command>
```

เองได้

---

# 15. Free-form Terminal

ใช้ Xterm.js สำหรับ Terminal UI

## Requirements

- รับ CLI Input
- แสดง stdout แบบ Real-time
- แสดง Error จาก Device
- รองรับ Command History
- เชื่อมต่อกับ Active Device เท่านั้น

---

# 16. WebSocket Terminal

สำหรับ Real-time Terminal แนะนำให้ใช้ WebSocket

```text
Xterm.js
    │
    │ WebSocket
    ▼
FastAPI
    │
    ▼
Connection Manager
    │
    ▼
Netmiko / PySerial
    │
    ▼
Network Device
```

Output:

```text
Device
  │
  ▼
Netmiko
  │
  ▼
FastAPI WebSocket
  │
  ▼
Xterm.js
```

---

# 17. Connection Management

ระบบควรมี Connection Manager สำหรับ:

- Connection Pool
- Multi-device connection
- Connection reuse
- Concurrent operations

รองรับการเชื่อมต่อหลายอุปกรณ์พร้อมกัน

แนะนำ:

```text
AsyncIO
+
ThreadPoolExecutor
```

สำหรับงานที่ต้องติดต่อหลายอุปกรณ์

---

# 18. Supported Connection Types

## SSH

แนะนำ:

```text
Netmiko
```

หรือ Raw SSH:

```text
Paramiko
```

## Telnet

รองรับผ่าน:

```text
Netmiko
```

หรือ `telnetlib` ตาม implementation ที่เลือก

## Serial

ใช้:

```text
PySerial
```

---

# 19. Configuration File Lifecycle

ระบบต้องรองรับทั้ง Running Config และ Startup Config

---

## 19.1 Export Running Config

Workflow:

```text
User clicks Export Running Config
        │
        ▼
show running-config
        │
        ▼
Receive output
        │
        ▼
Save as text file
```

ตัวอย่าง:

```text
R1-running-config.txt
```

---

## 19.2 Merge Running Config

รับ Configuration จาก:

- File
- Text input

Workflow:

```text
Config File
    │
    ▼
Read lines
    │
    ▼
Remove comments (!)
    │
    ▼
Validate / Normalize
    │
    ▼
send_config_set()
    │
    ▼
Device
```

---

## 19.3 Export Startup Config

ใช้:

```text
show startup-config
```

แล้วบันทึกเป็นไฟล์

---

## 19.4 Save Running → Startup

ใช้:

```text
write memory
```

หรือ command ที่เทียบเท่ากับ platform ที่รองรับ

---

# 20. Error Handling

ระบบต้องตรวจสอบ Error ทั้งก่อนและหลังส่ง Command

## Pre-Execution Validation

ตัวอย่าง:

```text
Invalid IP
Invalid Subnet Mask
Missing Required Field
No Active Device
No Connection Profile
```

## Device Response Validation

ตรวจสอบข้อความจาก Cisco IOS เช่น:

```text
% Invalid input detected at
```

หากพบ Error:

```text
Command
   │
   ▼
Device
   │
   ▼
Error Response
   │
   ▼
Backend detects error
   │
   ▼
Frontend displays error
```

---

# 21. Connection Test

ก่อน Deploy Configuration ควรมีระบบ Test Connection

ตัวอย่าง:

```text
Test Connection
      │
      ▼
Check Host
      │
      ▼
Ping / Reachability
      │
      ▼
Try SSH / Telnet / Serial
      │
      ▼
Return Connection Status
```

สถานะตัวอย่าง:

```text
Connected
Connection Failed
Timeout
Authentication Failed
Unreachable
```

---

# 22. Auto Discovery — Bonus

Auto Discovery เป็นฟีเจอร์โบนัส

เป้าหมาย:

```text
Network Device
      │
      ▼
Discover Neighbors
      │
      ▼
Build Topology Graph
      │
      ▼
Render Interactive Topology
```

วิธีที่ระบุไว้:

- CDP
- LLDP
- TextFSM
- ARP / Subnet matching

---

## CDP / LLDP

สามารถใช้ข้อมูลจาก:

```text
show cdp neighbors
show lldp neighbors
```

แล้ว Parse Output

แนวทาง:

```text
Cisco CLI
    │
    ▼
Raw Output
    │
    ▼
TextFSM
    │
    ▼
Structured Data
    │
    ▼
NetworkX Graph
    │
    ▼
React Flow / Vis-network
```

---

# 23. Topology Data Flow

```text
Device
  │
  ├── Device Definition
  │
  ├── Interfaces
  │
  ├── Connection Profile
  │
  └── Neighbors
          │
          ▼
      Network Graph
          │
          ▼
       Frontend
          │
          ▼
      Topology UI
```

---

# 24. Suggested Backend Modules

โครงสร้างที่สามารถนำไป implement ต่อ:

```text
backend/
├── app/
│   ├── main.py
│   │
│   ├── api/
│   │   ├── devices.py
│   │   ├── interfaces.py
│   │   ├── connections.py
│   │   ├── routing.py
│   │   ├── configs.py
│   │   ├── commands.py
│   │   └── topology.py
│   │
│   ├── services/
│   │   ├── connection_manager.py
│   │   ├── command_builder.py
│   │   ├── config_manager.py
│   │   ├── discovery.py
│   │   └── validation.py
│   │
│   ├── drivers/
│   │   ├── netmiko_driver.py
│   │   ├── serial_driver.py
│   │   └── telnet_driver.py
│   │
│   ├── models/
│   │   ├── device.py
│   │   ├── interface.py
│   │   ├── connection.py
│   │   └── topology.py
│   │
│   └── utils/
│       ├── parser.py
│       └── errors.py
│
└── requirements.txt
```

> โครงสร้างนี้เป็นข้อเสนอสำหรับการนำ specification ไป implement ไม่ใช่โครงสร้างที่ถูกกำหนดตายตัวในไฟล์ต้นฉบับ

---

# 25. Suggested Frontend Modules

```text
frontend/
├── src/
│   ├── components/
│   │   ├── Topology/
│   │   ├── Device/
│   │   ├── Interface/
│   │   ├── Routing/
│   │   ├── Terminal/
│   │   └── Config/
│   │
│   ├── pages/
│   │   ├── TopologyPage
│   │   ├── DeviceSettingsPage
│   │   └── ConfigPage
│   │
│   ├── stores/
│   │   └── topologyStore
│   │
│   ├── services/
│   │   ├── api
│   │   └── websocket
│   │
│   └── utils/
│       ├── commandNormalizer
│       └── validators
```

---

# 26. Main User Workflow

## Workflow A — Create Topology

```text
Open Application
      │
      ▼
Create / Open Project
      │
      ▼
Add Device
      │
      ▼
Select Router / Switch
      │
      ▼
Select Model
      │
      ▼
Device created
      │
      ▼
Interfaces generated
      │
      ▼
Place device on topology
      │
      ▼
Connect devices
```

---

## Workflow B — Configure Device

```text
Double-click Device
        │
        ▼
activeDeviceId = selected device
        │
        ▼
Open Configuration
        │
        ├── Interface
        ├── Routing
        └── CLI
```

---

## Workflow C — Connect to Real Device

```text
Select Device
      │
      ▼
Connection Settings
      │
      ▼
Select SSH / Telnet / Serial
      │
      ▼
Enter Credentials / Port
      │
      ▼
Test Connection
      │
      ▼
Connected
```

---

## Workflow D — Deploy Configuration

```text
Form Input
    │
    ▼
Validate
    │
    ▼
Command Builder
    │
    ▼
Generate Cisco CLI
    │
    ▼
Send to Active Device
    │
    ▼
Read Response
    │
    ├── Success
    │
    └── Error
```

---

# 27. State Management

Frontend ต้องเก็บอย่างน้อย:

```text
activeDeviceId
devices
connections
topology
selectedInterface
terminalState
connectionStatus
```

ตัวอย่าง:

```javascript
{
  activeDeviceId: null,

  devices: [],

  topology: {
    nodes: [],
    edges: []
  },

  terminal: {
    connected: false,
    output: []
  }
}
```

---

# 28. API Concept

## Device

```http
GET    /devices
POST   /devices
GET    /devices/{id}
PUT    /devices/{id}
DELETE /devices/{id}
```

## Interface

```http
GET  /devices/{id}/interfaces
POST /devices/{id}/interfaces
PUT  /interfaces/{id}
```

## Connection

```http
POST /devices/{id}/connection
POST /devices/{id}/connection/test
DELETE /devices/{id}/connection
```

## Configuration

```http
POST /devices/{id}/config/interface
POST /devices/{id}/config/routing
GET  /devices/{id}/config/running
GET  /devices/{id}/config/startup
POST /devices/{id}/config/merge
POST /devices/{id}/config/save
```

## Show Commands

```http
POST /devices/{id}/commands/show
```

## Topology

```http
GET  /topology
POST /topology/nodes
POST /topology/edges
DELETE /topology/nodes/{id}
DELETE /topology/edges/{id}
```

## Terminal

```text
WebSocket:

/ws/devices/{device_id}/terminal
```

---

# 29. Command Builder Design

แนะนำให้แยก Command Builder ออกจาก API Layer

```text
UI Form
   │
   ▼
Command Builder
   │
   ▼
Cisco CLI Commands
   │
   ▼
Connection Driver
```

ตัวอย่าง Interface Builder:

```text
build_interface_config(
    interface,
    ip_address,
    subnet_mask,
    status,
    description
)
```

ผลลัพธ์:

```text
interface GigabitEthernet0/0
 ip address 192.168.1.1 255.255.255.0
 no shutdown
 description LAN
```

Routing Builder:

```text
build_static_route(...)
build_default_route(...)
build_rip_config(...)
build_eigrp_config(...)
build_ospf_config(...)
build_bgp_config(...)
```

---

# 30. Validation Design

แยก Validation เป็น Service

```text
validation/
├── ip.py
├── subnet.py
├── wildcard.py
├── routing.py
└── connection.py
```

ตัวอย่าง:

```text
validate_ip()
validate_subnet_mask()
validate_wildcard_mask()
validate_router_id()
validate_as_number()
validate_port()
```

---

# 31. Connection Driver Abstraction

ไม่ควรให้ UI ติดต่อ Netmiko/PySerial โดยตรง

ควรใช้ Interface กลาง:

```text
ConnectionDriver
```

เช่น:

```text
ConnectionDriver
      │
      ├── NetmikoDriver
      │       ├── SSH
      │       └── Telnet
      │
      └── SerialDriver
```

ตัวอย่าง Concept:

```python
class ConnectionDriver:
    connect()
    disconnect()
    send_command()
    send_config()
    is_connected()
```

ข้อดีคือสามารถเปลี่ยน Library หรือเพิ่ม Driver ภายหลังได้ง่าย

---

# 32. Security Considerations

Credentials เป็นข้อมูลสำคัญ

ไม่ควร:

- Hard-code password
- ส่ง password กลับ frontend โดยไม่จำเป็น
- เก็บ plaintext credentials แบบถาวรโดยไม่มีการป้องกัน

ควร:

- เก็บ Credential แยกจาก Device Definition
- จำกัดสิทธิ์ API
- ใช้ HTTPS/WSS เมื่อ Deploy จริง
- Mask Password ใน UI
- ไม่แสดง Password ใน Log

---

# 33. Error Response Format

แนะนำให้ Backend ส่ง Error รูปแบบเดียวกัน

```json
{
  "success": false,
  "error": {
    "code": "INVALID_COMMAND",
    "message": "Device rejected the command",
    "details": "% Invalid input detected at '^' marker."
  }
}
```

Success:

```json
{
  "success": true,
  "data": {}
}
```

---

# 34. Implementation Priority

แนะนำแบ่ง Development เป็น Phase

## Phase 1 — Core UI

- [ ] React project
- [ ] Topology Canvas
- [ ] Add Device
- [ ] Device Type
- [ ] Model
- [ ] Default Interfaces
- [ ] Device Selection
- [ ] activeDeviceId

## Phase 2 — Device Configuration

- [ ] Interface Configuration
- [ ] IP Address
- [ ] Subnet Mask
- [ ] Up / Down
- [ ] Description
- [ ] Validation
- [ ] Command Builder

## Phase 3 — Routing

- [ ] Static Route
- [ ] Default Static Route
- [ ] RIP v2
- [ ] EIGRP
- [ ] OSPF
- [ ] BGP

## Phase 4 — Connection

- [ ] SSH
- [ ] Telnet
- [ ] Serial
- [ ] Connection Profile
- [ ] Test Connection
- [ ] Connection Manager

## Phase 5 — Terminal

- [ ] Xterm.js
- [ ] WebSocket
- [ ] Active Device Guardrail
- [ ] Real-time Output
- [ ] Error Handling

## Phase 6 — Config Files

- [ ] Export Running Config
- [ ] Merge Running Config
- [ ] Export Startup Config
- [ ] Write Memory

## Phase 7 — Bonus

- [ ] CDP
- [ ] LLDP
- [ ] TextFSM
- [ ] ARP/Subnet Discovery
- [ ] Interactive Auto Topology

---

# 35. Definition of Done

## Device

- [ ] User can create Router/Switch
- [ ] User can select Model
- [ ] Interfaces are generated from Model
- [ ] Additional interfaces can be added
- [ ] Device can be placed on topology

## Topology

- [ ] Devices can be connected
- [ ] Device can be selected
- [ ] Double-click sets Active Device
- [ ] Commands cannot be sent without Active Device

## Interface

- [ ] IP can be configured
- [ ] Subnet Mask can be configured
- [ ] Interface can be shutdown
- [ ] Interface can be brought up
- [ ] Description can be configured

## Routing

- [ ] Static
- [ ] Default Static
- [ ] RIP v2
- [ ] EIGRP
- [ ] OSPF
- [ ] BGP

## Connection

- [ ] SSH
- [ ] Telnet
- [ ] Serial
- [ ] Connection Test
- [ ] Multi-device support

## Terminal

- [ ] Raw CLI
- [ ] Real-time output
- [ ] Command error handling
- [ ] Active Device restriction

## Configuration

- [ ] Export Running
- [ ] Merge Running
- [ ] Export Startup
- [ ] Save Running → Startup

## Bonus

- [ ] Auto Discovery
- [ ] CDP
- [ ] LLDP
- [ ] Interactive topology generation

---

# 36. Important Design Principles

## 36.1 Separate Design and Execution

```text
Design
  ↓
Create Devices
  ↓
Create Topology
  ↓
Configure Interfaces
  ↓
Save Project

Execution
  ↓
Set Connection Profile
  ↓
Test Connection
  ↓
Deploy Configuration
```

---

## 36.2 Active Device Is the Command Boundary

ทุกคำสั่ง CLI ต้องมี Device Target ที่ชัดเจน

```text
activeDeviceId
```

เป็นตัวกำหนดว่า Command จะถูกส่งไปยังอุปกรณ์ใด

ห้าม fallback ไปยัง Device อื่นโดยอัตโนมัติ

---

## 36.3 UI ไม่ควรสร้าง CLI โดยตรง

ควรใช้:

```text
UI
 ↓
Command Builder
 ↓
Validation
 ↓
Driver
 ↓
Device
```

ไม่ควร:

```text
UI
 ↓
Netmiko
```

โดยตรง

---

# 37. Future Extension

Architecture ควรสามารถต่อยอดไปยัง:

- QoS Automation
- Network Telemetry
- เพิ่ม Vendor อื่น
- เพิ่ม Device Driver
- เพิ่ม Configuration Templates
- เพิ่ม Automated Testing
- เพิ่ม Network Health Monitoring

---

# 38. Final Implementation Target

ระบบสุดท้ายควรมีภาพรวมดังนี้:

```text
                     Network Automation UI
                              │
             ┌────────────────┴────────────────┐
             │                                 │
        Topology UI                         Terminal
             │                                 │
       React Flow                          Xterm.js
             │                                 │
             └──────────────┬──────────────────┘
                            │
                     FastAPI Backend
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
       Devices          Config Builder     Topology
          │                 │                 │
          └─────────────────┼─────────────────┘
                            │
                    Connection Manager
                            │
              ┌─────────────┼─────────────┐
              │             │             │
           Netmiko       PySerial       Discovery
              │             │             │
           SSH/Telnet     Serial        CDP/LLDP
              │             │             │
              └─────────────┼─────────────┘
                            │
                    Network Devices
```

---

## Source Scope

เอกสารนี้ยึดเนื้อหาจากไฟล์ **NETWORK AUTOMATION UI PROJECT COMPILATION** ซึ่งระบุ Assignment, ขอบเขตระบบ, UX refinement, architecture และแนวทาง implementation ที่สรุปจากการพัฒนาโปรเจกต์ก่อนหน้า

ส่วนที่เป็น **โครงสร้างโฟลเดอร์, JSON schema ตัวอย่าง, API endpoint naming และ implementation abstractions** ถูกจัดรูปแบบเพิ่มเติมเพื่อให้สามารถนำไปเริ่มเขียน code ได้ง่ายขึ้น และไม่ควรถือว่าเป็นข้อกำหนดตายตัวจาก Assignment เดิม
