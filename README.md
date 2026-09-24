# NetConfig Tracer Studio v3
### Network Automation & Topology Visualization Studio — Real Cisco IOS Lab Integration
**Network Programming — Assignment 2**

---

## ภาพรวม (Overview)
**NetConfig Tracer Studio v3** เป็น Web Application สำหรับการจัดการและตั้งค่าอุปกรณ์เครือข่าย Cisco IOS แบบอัตโนมัติ (Network Automation) โดยมีหน้าต่างควบคุมแบบกราฟิกคล้าย Cisco Packet Tracer
- รองรับการเชื่อมต่อกับอุปกรณ์จริงและ Virtual Lab (EVE-NG, GNS3, Physical Devices) ผ่าน **SSH**, **Telnet (Console Port)**, และ **Serial Console**
- มีระบบ **Auto-Reconnect Engine** ทนทานต่อ Socket Drops / Idle Timeouts บน Telnet Console ของ EVE-NG
- บูรณาการ **EVE-NG REST API** ดึงโครงสร้าง Topology, Nodes, และ Console Port เข้า Device Inventory ได้โดยตรง
- **Auto-Discovery Topology Engine** พัฒนาด้วย NetworkX MultiGraph + IP Subnet Overlap Matching รองรับการเชื่อมโยงหลายสายระหว่างอุปกรณ์ (Multi-Leg) และเครือข่าย Multi-Access Cloud
- **Interface Configuration** รองรับทั้ง **Static IP** และ **DHCP Client Mode (`ip address dhcp`)** พร้อมระบบสลับฟอร์มอัตโนมัติและ Live Cache Sync
- กำหนดค่า Routing Protocols ยอดนิยม (Static, RIP v2, EIGRP, OSPF, BGP) พร้อมระบบตรวจสอบไวยากรณ์ (Syntax Preview) และส่งคำสั่งไปยัง Router จริง
- มี **Interactive CLI Terminal** รองรับคำสั่งย่อ, Autocomplete Dropdown, ประวัติคำสั่ง (History), และการทดสอบเชื่อมต่อด้วย **Virtual PC Ping**
- ผ่านการทดสอบโดยสมบูรณ์ด้วยชุดทดสอบอัตโนมัติ **27 การทดสอบ (100% Pass)**

---

## สิ่งที่ต้องมีก่อนรัน (Prerequisites)

### 1. Python
- **Python 3.8** ขึ้นไป (แนะนำ Python 3.10 หรือใหม่กว่า)
- ตรวจสอบเวอร์ชัน: `python --version`
- ดาวน์โหลด: https://www.python.org/downloads/

### 2. pip (Python Package Manager)
- มาพร้อมกับ Python
- ตรวจสอบ: `pip --version`

### 3. อินเทอร์เน็ต
- จำเป็นสำหรับการดาวน์โหลด CDN ในครั้งแรก (vis-network, Font Awesome, Google Fonts)

---

## Libraries / Modules ที่ต้องติดตั้ง

### Python Libraries (ติดตั้งผ่าน pip)

| # | Library | เวอร์ชันขั้นต่ำ | วัตถุประสงค์ | จำเป็น? |
|---|---------|---------------|-------------|:---:|
| 1 | `flask` | ≥ 2.3.0 | Web Framework สำหรับ REST API Backend และให้บริการหน้าเว็บ | ✅ **จำเป็น** |
| 2 | `netmiko` | ≥ 4.2.0 | จัดการการเชื่อมต่อ SSH / Telnet กับอุปกรณ์ Cisco IOS | ✅ **จำเป็น** |
| 3 | `paramiko` | ≥ 3.0.0 | SSH Transport Layer เบื้องหลังของ Netmiko | ✅ **จำเป็น** |
| 4 | `pyserial` | ≥ 3.5 | เชื่อมต่อผ่าน Serial Console (COM port / `/dev/ttyUSB`) | ✅ **จำเป็น** |
| 5 | `networkx` | ≥ 3.0 | สร้างและประมวลผล MultiGraph สำหรับ Topology Auto-Discovery | ✅ **จำเป็น** |
| 6 | `requests` | ≥ 2.28.0 | เชื่อมต่อ EVE-NG REST API เพื่อนำเข้าแล็บและพอร์ตคอนโซล | ✅ **จำเป็น** |

### รายละเอียดการทำงานของ Library หลัก
1. **Flask (`flask`)**: จัดการ Routing, API Endpoints, JSON Serialization, และทำหน้าที่เป็น Application Core
2. **Netmiko (`netmiko`)**: จัดการ Session Pooling, ส่งคำสั่ง Show/Configuration, และจัดการ Prompt ของ Cisco IOS
3. **Paramiko (`paramiko`)**: Dependency ของ Netmiko สำหรับการเข้ารหัส SSH Transport
4. **PySerial (`pyserial`)**: เปิดการเชื่อมต่อตรงกับพอร์ต Serial ของเราเตอร์
5. **NetworkX (`networkx`)**: คำนวณความสัมพันธ์ของโหนด (MultiGraph) และจัดกลุ่ม IP Overlap สำหรับวาดเส้นเชื่อมโยง
6. **Requests (`requests`)**: ส่ง HTTP/HTTPS Request ไปยัง EVE-NG REST API (`/api/auth/login`, `/api/labs/...`)

---

## วิธีติดตั้งและรันระบบ (Quick Start)

### 1. Clone โปรเจกต์
```bash
git clone https://github.com/Phalakorn223/Assignment-2-NetPro.git
cd Assignment-2-NetPro
```

### 2. ติดตั้ง Dependencies
```bash
pip install -r requirements.txt
```
*หรือติดตั้งรายตัว:*
```bash
pip install flask netmiko paramiko pyserial networkx requests
```

### 3. ตรวจสอบความถูกต้องของการติดตั้ง
```bash
python -c "
import flask, netmiko, paramiko, serial, networkx, requests
print('Flask:', flask.__version__)
print('Netmiko:', netmiko.__version__)
print('NetworkX:', networkx.__version__)
print('Requests:', requests.__version__)
print('All libraries installed successfully!')
"
```

### 4. รัน Web Server
```bash
python app.py
```
เข้าใช้งานผ่านเบราว์เซอร์ที่: **`http://127.0.0.1:5000`**

### 5. รันชุดทดสอบอัตโนมัติ (Automated Test Suite)
```bash
python tests/test_all_features.py
```

---

## โครงสร้างไฟล์ของโปรเจกต์ (Project Directory Structure)

```text
Assignment-2-NetPro/
├── app.py                                    # Flask Backend Server หลัก (REST API endpoints)
├── connection_manager.py                     # Netmiko Pool Manager พร้อม Auto-Reconnect Engine
├── command_builder.py                        # ตัวสร้างคำสั่ง Cisco IOS CLI (Pure Functions)
├── command_normalizer.py                     # ตัวแปลงคำสั่งย่อ และระบบ Autocomplete Suggestions
├── topology_builder.py                       # NetworkX MultiGraph Engine & Discovery Matching
├── eve_ng_client.py                          # EVE-NG REST API Client
├── devices.json                              # Device Inventory Database (JSON Persistence)
├── requirements.txt                          # รายการ Python Dependencies
├── README.md                                 # เอกสารคู่มือการติดตั้งและการใช้งาน v3 (เอกสารนี้)
├── assignment-2-network-automation-ui-spec.md      # ข้อกำหนดระบบ v1
├── assignment-2-v2-network-automation-ui-spec.md   # ข้อกำหนดระบบ v2
├── assignment-2-v3-network-automation-ui-spec.md   # ข้อกำหนดระบบ v3 (Source of Truth ปัจจุบัน)
│
├── tests/                                    # โฟลเดอร์ชุดทดสอบและสคริปต์ตรวจสอบระบบ
│   ├── test_all_features.py                  # ชุดทดสอบ End-to-End ครบทั้ง 27 ฟังก์ชัน (100% Pass)
│   ├── test_cdp.py                           # สคริปต์ทดสอบ CDP Protocol Parsing
│   ├── test_cmd.py                           # สคริปต์ทดสอบ Netmiko Command Execution
│   ├── test_parse.py                         # สคริปต์ทดสอบ Regex Parser
│   ├── test_parse2.py                        # สคริปต์ทดสอบ Subnet Overlap Logic
│   └── reconnect.py                          # สคริปต์ทดสอบ Reconnect สำหรับ EVE-NG
│
├── legacy/                                   # โฟลเดอร์สำหรับโค้ดเก่าที่ปลดระวางแล้ว
│   └── network_engine.py                     # โมดูลเดิมก่อนการ Refactor
│
├── templates/
│   └── index.html                            # หน้าเว็บหลัก (Vis.js Topology, Side Drawers, CLI)
│
└── static/
    ├── css/styles.css                        # Modern Dark Glassmorphism Stylesheet
    ├── js/app.js                             # Frontend Controller & Topology Canvas Logic
    └── icons/                                # Custom SVG Icons สำหรับ Router, Switch, และ PC
```

---

## ฟีเจอร์ทั้งหมดในระบบ v3 (Core Features)

### 1. การเชื่อมต่ออุปกรณ์ & Session Resiliency (Connection Manager)
- **Multi-Protocol Support**: รองรับ SSH (`cisco_ios`), Telnet (`cisco_ios_telnet`), และ Serial (`pyserial`)
- **Auto-Reconnect Engine**: ดักจับกรณี EVE-NG Telnet Socket ขาดหรือ Idle Timeout (`closed`, `eof`, `broken pipe`) แล้วทำการต่อใหม่และรันคำสั่งเดิมซ้ำให้อัตโนมัติ
- **Paging Elimination**: ส่งคำสั่ง `terminal length 0` อัตโนมัติทันทีที่เชื่อมต่อ ป้องกันโปรแกรมค้างจาก `--More--`
- **On-Demand Connection**: เชื่อมต่ออุปกรณ์จาก `devices.json` ให้โดยอัตโนมัติเมื่อมีการเรียกใช้งานคำสั่ง
- **Pre-flight Ping Check**: ทดสอบความพร้อมของ IP Address ก่อนเริ่มเชื่อมต่อ

### 2. Interface Configuration & DHCP Support
- **Dual Mode IP Configuration**:
  - **Static IP Mode**: ระบุ IP Address และ Subnet Mask ตามมาตรฐาน
  - **DHCP Client Mode**: สร้างคำสั่ง `ip address dhcp` โดยไม่ใส่ Subnet Mask
- **Smart Form Adaptation**:
  - เมื่อเลือกโหมด DHCP หรือพิมพ์ `dhcp` ลงในช่อง IP ระบบจะสลับโหมดและปิดช่อง Subnet Mask ให้อัตโนมัติ
  - เมื่อคลิกเลือกแถว Interface ในตาราง Step 1 หากขา Interface ได้รับ DHCP ระบบจะปรับฟอร์มเป็นโหมด DHCP ให้ทันที
- **Interface State**: สั่งเปิด (`no shutdown`) หรือปิด (`shutdown`) ขาเชื่อมต่อ
- **Description**: ตั้งคำอธิบาย Interface ได้อิสระ
- **Live Cache Force Refresh**: ปุ่ม Refresh และการ Deploy จะส่ง `?force=1` ดึงข้อมูลสดจาก Router และอัปเดต Topology Graph ทันที

### 3. Routing Protocols Configuration
- **Static Route & Default Route**: กำหนด Destination Network, Subnet Mask, และ Next-Hop IP
- **RIP v2**: เปิดใช้งาน RIPv2, เพิ่ม Networks, และสร้างคำสั่ง `no auto-summary`
- **EIGRP**: ระบุ Autonomous System (AS Number), กำหนด Networks พร้อม Wildcard Mask
- **OSPF**: ระบุ Process ID, Router-ID, กำหนด Networks พร้อม Wildcard Mask และ Area ID
- **BGP**: กำหนด Local AS Number, เพิ่ม Neighbors (IP + Remote AS), และประกาศ Networks
- **Live Deployment & Preview**: มีกล่อง Cisco IOS Preview ให้ตรวจสอบคำสั่งก่อนส่งจริง

### 4. Auto-Discovery Topology (MultiGraph Engine)
- **Multi-Leg Link Support**: ใช้ NetworkX `MultiGraph` เพื่อรองรับการต่อสายหลายเส้นระหว่าง Router สองตัว
- **Subnet Overlap Matching Algorithm**: ตรวจสอบการเชื่อมโยงข้าม Interface แม้ Subnet Mask จะต่างกัน ด้วย `ipaddress.overlaps()`
- **Dual Connection Types**:
  - **Point-to-Point**: ลากสายตรงระหว่าง Router เช่น `R1 e0/1 <-> R2 e0/1`
  - **Multi-Access Cloud**: สร้าง Node ก้อนเมฆ (`Net x.x.x.x/xx`) อัตโนมัติเมื่อมีโหนดเชื่อมต่อใน Subnet มากกว่า 2 ตัว
- **Vis.js Dark Theme Canvas**: กราฟิกสี Dark Glassmorphism, ตัวหนังสือมีพื้นหลังป้องกันสายทับข้อความ, ลากย้ายและซูมได้อย่างลื่นไหล

### 5. EVE-NG Lab REST API Integration
- นำเข้า Lab จาก EVE-NG Server ได้โดยตรงผ่านหน้า UI
- ค้นหา Node ทั้งหมดและดึงหมายเลขพอร์ต Telnet Console (เช่น `32769`, `32770`, `32771`) มาบันทึกลง Device Inventory ให้อัตโนมัติ
- ป้องกันปัญหา URL ซ้ำซ้อน (`/api/api/auth/login`) ด้วยระบบทำความสะอาด URL อัตโนมัติ

### 6. Interactive CLI Terminal & Autocomplete
- รองรับคำสั่งย่อ เช่น `sh ip int br`, `sh run`, `conf t`, `wr`
- **Autocomplete Suggestions**: แสดง Dropdown แนะนำคำสั่งขณะพิมพ์ (กด Tab เพื่อเติมคำสั่งเต็ม)
- **Command History**: เลื่อนดูประวัติคำสั่งที่เคยพิมพ์ด้วยปุ่มลูกศรขึ้น/ลง (Arrow Up/Down)
- แยกการส่งคำสั่งโหมด Exec (`send_command`) และ Config (`send_config_set`) ให้อัตโนมัติ

### 7. Virtual PC Simulation & Ping Proxy
- จำลองการตั้งค่า IP Address, Subnet Mask, และ Default Gateway ของ Virtual PC
- ทดสอบ Reachability ด้วยการสั่ง Ping เสมือนผ่าน Router Gateway พร้อมรองรับ Cisco IOS ARP Delay Pattern (`.!!`)

### 8. Physical Front Panel & LED Indicators
- แสดงสถานะไฟ LED เขียว/แดง บนพอร์ตแต่ละช่องตามสถานะของ Interface
- คลิกที่พอร์ตเพื่อดูรายละเอียด IP, Speed, MTU, และสถานะการทำงาน

---

## ชุดการทดสอบระบบ 27 ฟังก์ชัน (Test Suite Results)

สามารถทดสอบการทำงานของระบบทั้งหมดผ่านคำสั่ง:
```bash
python tests/test_all_features.py
```

### สรุปผลการทดสอบ (27/27 Tests Passed - 100%):
```text
================================================================================
          NETCONFIG TRACER STUDIO - AUTOMATED TEST SUITE v3
================================================================================
 [1/27]  Device Inventory (List)                  ... [ PASS ]
 [2/27]  Device Inventory (Add/Remove)            ... [ PASS ]
 [3/27]  Device Connection (R1, R2, R3)           ... [ PASS ]
 [4/27]  Active Connections Pool                  ... [ PASS ]
 [5/27]  Interfaces List (Parsing & Schema)       ... [ PASS ]
 [6/27]  Interface Configure (Live Set Status)    ... [ PASS ]
 [7/27]  Routing Preview (Static Route)           ... [ PASS ]
 [8/27]  Routing Preview (OSPF)                   ... [ PASS ]
 [9/27]  Routing Preview (RIP)                    ... [ PASS ]
 [10/27] Routing Preview (EIGRP)                  ... [ PASS ]
 [11/27] Routing Preview (BGP)                    ... [ PASS ]
 [12/27] Routing Apply (Live Push & Revert)       ... [ PASS ]
 [13/27] Show Command Execution (show ip route)   ... [ PASS ]
 [14/27] Freeform CLI Execution                   ... [ PASS ]
 [15/27] Topology Auto-Discovery (Real Links)     ... [ PASS ]
 [16/27] Front Panel Port Data                    ... [ PASS ]
 [17/27] Command Suggestions (Fuzzy Autocomplete) ... [ PASS ]
 [18/27] Command Normalization Engine             ... [ PASS ]
 [19/27] Virtual PC Config (Set IP & Gateway)     ... [ PASS ]
 [20/27] Virtual PC Ping via Router Proxy         ... [ PASS ]
 [21/27] Direct ICMP Ping Check Endpoint          ... [ PASS ]
 [22/27] Interface Up/Down State Toggle           ... [ PASS ]
 [23/27] Direct Interface Config Endpoint        ... [ PASS ]
 [24/27] Routing Redistribution Preview           ... [ PASS ]
 [25/27] Topology Interfaces Diagnostics          ... [ PASS ]
 [26/27] EVE-NG Direct Import Endpoint            ... [ PASS ]
 [27/27] Interface DHCP Configuration             ... [ PASS ]
================================================================================
 ALL 27 TESTS PASSED! (100% SUCCESS RATE)
================================================================================
```

---

## การแก้ปัญหาเบื้องต้น (Troubleshooting)

| ปัญหา | สาเหตุ | วิธีแก้ไข |
|---|---|---|
| `ModuleNotFoundError: No module named '...'` | ติดตั้ง dependencies ไม่ครบ | รัน `pip install -r requirements.txt` |
| `Socket error / telnet connection closed` | EVE-NG อนุญาตให้ต่อ Telnet ได้เพียง 1 client ต่อ 1 node | ระบบ v3 มี Auto-Reconnect จัดการให้ หรือปิดโปรแกรมภายนอก (เช่น PuTTY, SecureCRT) ที่เปิดคาไว้ |
| `Terminal freezes on show command` | อุปกรณ์ส่งข้อความ `--More--` | ระบบ v3 ส่ง `terminal length 0` ให้โดยอัตโนมัติแล้ว |
| หน้า Topology ไม่แสดงโหนด | ไม่ได้เชื่อมต่ออินเทอร์เน็ตเพื่อโหลด Vis.js CDN | ตรวจสอบการเชื่อมต่ออินเทอร์เน็ตแล้วกด Refresh หน้าเว็บ |
| `Syntax error % Invalid input detected` | ไวยากรณ์คำสั่ง IOS ไม่ตรงกับ IOS Version | ตรวจสอบคำสั่งผ่านกล่อง Preview หรือพิมพ์คำสั่งผ่าน CLI Terminal |

---

## เอกสารอ้างอิงและประวัติรุ่น (Version History & Specs)
- **v1**: [assignment-2-network-automation-ui-spec.md](assignment-2-network-automation-ui-spec.md) — ข้อกำหนด UI และโครงร่างเริ่มต้น
- **v2**: [assignment-2-v2-network-automation-ui-spec.md](assignment-2-v2-network-automation-ui-spec.md) — การขยายผลการตั้งค่า Routing และ CLI Normalizer
- **v3 (Latest)**: [assignment-2-v3-network-automation-ui-spec.md](assignment-2-v3-network-automation-ui-spec.md) — สถาปัตยกรรมปฏิบัติการจริง, MultiGraph Auto-Discovery, Auto-Reconnect, DHCP Client Mode และชุดทดสอบ 27 รายการ
