# NetConfig Tracer Studio v3 (Up-to-Date Edition)
### Network Automation & Topology Visualization Studio — Real Cisco IOS Lab Integration
**Network Programming — Assignment 2 (10 คะแนนหลัก + 3 คะแนนโบนัส = 13 คะแนนเต็ม)**

---

## ภาพรวม (Overview)
**NetConfig Tracer Studio** เป็น Web Application สำหรับการจัดการ ตรวจสอบ และตั้งค่าอุปกรณ์เครือข่าย Cisco IOS แบบอัตโนมัติ (Network Automation) โดยมีหน้าต่างควบคุมแบบกราฟิกคล้าย Cisco Packet Tracer ครอบคลุมฟังก์ชันตามเกณฑ์การให้คะแนนทุกข้อ:

- 🔌 **Multi-Protocol Connection Engine**: รองรับการเชื่อมต่อกับอุปกรณ์จริงและ Virtual Lab (EVE-NG, GNS3, Physical Devices) ผ่าน **SSH**, **Telnet (Console Port)**, และ **Serial Console (COM Port)**
- 🔒 **Thread-Safe Session Lock & Concurrency Protection**: มีระบบ Per-Device Mutex Lock (`threading.Lock`) ป้องกันคำสั่งจาก Interactive CLI และ Background Tasks ชนกันใน Socket เดียวกัน แก้ปัญหาตัวอักษรแตกขาด (`inrfc`, `seail`) 100%
- 🛡️ **Intelligent Socket Health Monitoring**: แยกแยะระหว่าง Network Socket ขาดจริง (`BrokenPipe`, `ConnectionReset`) กับคำสั่งที่ตอบกลับช้า (`ReadTimeout`) เพื่อป้องกันการ Disconnect อุปกรณ์โดยไม่จำเป็น
- 🔄 **Config Mode Aware (`do` Fallback)**: ตรวจจับกรณี Router อยู่ในโหมด Configuration (`(config)#`) แล้วสั่งคำสั่ง Show ด้วย `do <command>` ให้อัตโนมัติ
- 🌐 **Auto-Discovery Topology Engine**: พัฒนาด้วย NetworkX MultiGraph + IP Subnet Overlap Matching รองรับการเชื่อมโยงหลายสายระหว่างอุปกรณ์ (Multi-Leg) และเครือข่าย Multi-Access Cloud บน Vis.js Dark Theme Canvas
- ⚙️ **Interface Configuration (Tri-Mode)**: รองรับทั้ง **Static IP**, **DHCP Client Mode (`ip address dhcp`)**, และ **No IP Mode (`no ip address`)** พร้อมระบบสลับฟอร์มอัตโนมัติ, Auto-Refresh ทุกครั้งที่เปลี่ยน Target Router และ Live Cache Sync
- 🛣️ **Routing Protocols Suite**: กำหนดค่า Routing ครบถ้วน ได้แก่ **Static Route**, **Default Route**, **RIP v2**, **EIGRP**, **OSPF**, และ **BGP** พร้อมกล่อง Cisco IOS Preview ก่อนส่งคำสั่งจริง
- 💻 **Interactive CLI Terminal**: Terminal เสมือนพร้อม Real-time Prompt Detection, Autocomplete Suggestions (Tab to complete), Command History (ลูกศรขึ้น/ลง), ANSI Escape & Pager Stripping (`terminal length 0`, `terminal width 512`)
- 💾 **Config Lifecycle Management**: สำรองและกู้คืนการตั้งค่าอุปกรณ์ ได้แก่ **Export Running-Config**, **Export Startup-Config**, **Merge Configuration**, และ **Save Config (`write memory`)**
- 🖲️ **Physical Front Panel & LED Indicators (Bonus +1.5)**: แสดงแผงพอร์ตด้านหน้า (Chassis Front Panel) ไฟสถานะ LED (เขียว/แดง), ความเร็ว และ IP บนแต่ละช่องพอร์ต
- 🧭 **EVE-NG REST API Integration**: ค้นหา Lab และดึงหมายเลขพอร์ต Telnet Console มาลง Device Inventory ให้อัตโนมัติ
- 🧪 **ผ่านการทดสอบสมบูรณ์**: ครอบคลุมทั้งชุดทดสอบอัตโนมัติ **28 End-to-End Tests** และ **13 CLI & Telnet Switch Stability Tests** (100% Pass)

---

## สิ่งที่ต้องมีก่อนรัน (Prerequisites)

### 1. Python
- **Python 3.8 ขึ้นไป** (แนะนำ Python 3.10 หรือ Python 3.13)
- ตรวจสอบเวอร์ชัน: `python --version`
- ดาวน์โหลด: [python.org](https://www.python.org/downloads/)

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

---

## วิธีติดตั้งและรันระบบ (Quick Start)

### 1. ติดตั้ง Dependencies
```bash
pip install -r requirements.txt
```
*หรือติดตั้งรายตัว:*
```bash
pip install flask netmiko paramiko pyserial networkx requests
```

### 2. ตรวจสอบความถูกต้องของการติดตั้ง
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

### 3. รัน Web Server
```bash
python app.py
```
เปิดใช้งานผ่านเว็บเบราว์เซอร์ที่: **`http://127.0.0.1:5000`** หรือ **`http://localhost:5000`**

### 4. รันชุดทดสอบอัตโนมัติ (Automated Test Suites)
- **ชุดทดสอบฟังก์ชันระบบครบวงจร (28 Tests):**
  ```bash
  python tests/test_all_features.py
  ```
- **ชุดทดสอบเสถียรภาพ CLI & Telnet Switch (13 Tests):**
  ```bash
  python -m unittest tests/test_cli_and_telnet_switch.py
  ```

---

## โครงสร้างไฟล์ของโปรเจกต์ (Project Directory Structure)

```text
Assignment-2-NetPro/
├── app.py                                    # Flask Backend Server หลัก (REST API endpoints)
├── connection_manager.py                     # Netmiko Pool Manager พร้อม Thread-safe Locks และ Auto-Reconnect
├── command_builder.py                        # ตัวสร้างคำสั่ง Cisco IOS CLI (Pure Functions)
├── command_normalizer.py                     # ตัวแปลงคำสั่งย่อ และระบบ Autocomplete Suggestions
├── topology_builder.py                       # NetworkX MultiGraph Engine & Discovery Matching
├── hardware_profiles.py                      # ฐานข้อมูลโมเดลเราเตอร์/สวิตช์ (Cisco 2901, 4331, 2960, etc.)
├── validators.py                             # ตัวตรวจสอบความถูกต้องของ IP, Subnet Mask, Wildcard, AS Number
├── eve_ng_client.py                          # EVE-NG REST API Client
├── devices.json                              # Device Inventory Database (JSON Persistence)
├── topology_cache.json                       # Topology Cache บันทึกผังโครงสร้างเน็ตเวิร์ก
├── requirements.txt                          # รายการ Python Dependencies
├── README.md                                 # เอกสารคู่มือการติดตั้งและการใช้งาน (เอกสารนี้)
├── USER_GUIDE.md                             # คู่มือการใช้งานฉบับสมบูรณ์ทีละฟังก์ชัน
├── TEST_CASES_CHECKLIST.md                   # รายการตรวจสอบ Test Cases ตามเกณฑ์รูบริก 13 คะแนน
├── assignment-2-v3-network-automation-ui-spec.md   # ข้อกำหนดระบบ v3 (Source of Truth)
│
├── tests/                                    # โฟลเดอร์ชุดทดสอบและสคริปต์ตรวจสอบระบบ
│   ├── test_all_features.py                  # ชุดทดสอบ End-to-End ครบทั้ง 28 ฟังก์ชัน (100% Pass)
│   ├── test_cli_and_telnet_switch.py         # ชุดทดสอบเสถียรภาพ CLI, Telnet Switch, Paging, Keepalive (13 Pass)
│   ├── test_multi_subnet_topology.py         # ชุดทดสอบ Multi-Subnet Discovery & Matching (9 Pass)
│   ├── test_linux_ssh.py                     # ชุดทดสอบการเชื่อมต่อ Linux Node ผ่าน SSH
│   ├── test_cdp.py                           # ทดสอบ CDP Protocol Parsing
│   ├── test_cmd.py                           # ทดสอบ Netmiko Command Execution
│   ├── test_parse.py                         # ทดสอบ Regex Parser
│   └── reconnect.py                          # ทดสอบ Reconnect สำหรับ EVE-NG
│
├── templates/
│   └── index.html                            # หน้าเว็บหลัก (Vis.js Topology, Side Drawers, CLI, Modals)
│
└── static/
    ├── css/styles.css                        # Modern Dark Glassmorphism Stylesheet
    ├── js/app.js                             # Frontend Controller & Topology Canvas Logic
    └── icons/                                # Custom SVG Icons สำหรับ Router, Switch, และ PC
```

---

## ฟีเจอร์ทั้งหมดในระบบ (Core Features Breakdown)

### 1. การเชื่อมต่ออุปกรณ์ & Session Resiliency (Connection Manager)
- **Multi-Protocol Support**: รองรับ SSH (`cisco_ios`), Telnet (`cisco_ios_telnet`), และ Serial (`pyserial`)
- **Per-Device Mutex Lock**: มี Lock ประจำแต่ละอุปกรณ์ (`get_device_lock`) ป้องกัน Race Condition เมื่อมีการรันคำสั่งพร้อมกันระหว่าง CLI Terminal กับ Background Polling
- **Smart Disconnect Prevention**: ไม่ตัดสายเมื่อเกิดเพียง `ReadTimeout` จากคำสั่งที่ตอบกลับช้า โดยจะตัดสายเฉพาะเมื่อ Socket ขาดจริงเท่านั้น (`closed`, `eof`, `broken pipe`, `connection reset`)
- **Config Mode Aware (`do` Fallback)**: หากเราเตอร์ค้างอยู่ในโหมด `(config)#` ระบบจะแปลงคำสั่ง Show เป็น `do <command>` ให้อัตโนมัติ ไม่เกิด Error
- **Paging Elimination**: ส่งคำสั่ง `terminal length 0` และ `terminal width 512` อัตโนมัติ ป้องกันโปรแกรมค้างจาก `--More--`
- **Pre-flight Ping Check**: ตรวจสอบความพร้อมของ IP ก่อนเชื่อมต่อ เพื่อแจ้งเตือนผู้ใช้ได้อย่างรวดเร็ว

### 2. Interface Configuration (Tri-Mode) & Live Sync
- **Tri-Mode IP Configuration**:
  - **Static IP Mode**: ระบุ IP Address และ Subnet Mask มาตรฐาน
  - **DHCP Client Mode**: สร้างคำสั่ง `ip address dhcp` โดยอัตโนมัติ
  - **No IP Mode (`no ip address`)**: ลบ/ถอน IP Address ออกจากขา Interface
- **Smart Form Adaptation**: เมื่อพิมพ์ `dhcp` หรือ `no ip` ฟอร์มจะสลับโหมดและปิดช่อง Subnet Mask ให้อัตโนมัติ
- **Live Cache Force Refresh**: ปุ่ม Refresh ส่งพารามิเตอร์ `?force=1` เพื่อดึงข้อมูลสดจากอุปกรณ์จริง และอัปเดต Topology Graph ทันที

### 3. Routing Protocols Suite
- **Static Route & Default Route**: กำหนด Destination Network, Subnet Mask, และ Next-Hop IP
- **RIP v2**: เปิดใช้งาน RIPv2, เพิ่ม Networks, และสร้างคำสั่ง `no auto-summary`
- **EIGRP**: ระบุ Autonomous System (AS Number), กำหนด Networks พร้อม Wildcard Mask
- **OSPF**: ระบุ Process ID, Router-ID, กำหนด Networks พร้อม Wildcard Mask และ Area ID
- **BGP**: กำหนด Local AS Number, เพิ่ม Neighbors (IP + Remote AS), และประกาศ Networks
- **Syntax Preview**: มีกล่อง Cisco IOS Preview แสดงคำสั่งที่กำลังจะส่งให้ตรวจสอบก่อนกด Deploy

### 4. Auto-Discovery Topology (MultiGraph Engine)
- **Multi-Leg Link Support**: ใช้ NetworkX `MultiGraph` รองรับการต่อสายหลายเส้นระหว่างเราเตอร์คู่เดิม
- **Subnet Overlap Matching Algorithm**: ค้นหาและจับคู่การเชื่อมโยงข้าม Interface แม้ Subnet Mask จะต่างกัน ด้วย `ipaddress.overlaps()`
- **Dual Connection Types**: รองรับทั้งแบบ Point-to-Point (สายตรง) และ Multi-Access Cloud (ก้อนเมฆ Subnet)
- **Vis.js Dark Theme Canvas**: กราฟิก Dark Glassmorphism, มีพื้นหลังรองข้อความป้องกันสายทับ, รองรับ Drag & Drop และ Zoom

### 5. Interactive CLI Terminal & Autocomplete
- รองรับคำสั่งย่อมาตรฐาน Cisco IOS เช่น `sh ip int br`, `sh run`, `conf t`, `wr`
- **Autocomplete Suggestions**: แนะนำคำสั่งขณะพิมพ์ (กด Tab เพื่อเติมคำสั่งเต็ม)
- **Command History**: เลื่อนดูประวัติคำสั่งด้วยปุ่มลูกศรขึ้น/ลง
- **Break Signal**: มีปุ่มส่งสัญญาณ `Ctrl+C` (`\x03`) เพื่อยกเลิกคำสั่งที่ค้างอยู่

### 6. Config File Lifecycle Management
- **Export Running-Config**: ดึงคอนฟิกปัจจุบันจาก RAM มาแสดงและดาวน์โหลด
- **Export Startup-Config**: ดึงคอนฟิกจาก NVRAM
- **Merge Configuration**: อัปโหลดไฟล์คอนฟิกหรือพิมพ์ข้อความเพื่อ Merge เข้า Running-Config
- **Save Configuration**: สั่งบันทึกคอนฟิกลง NVRAM (`write memory`) ผ่านปุ่มเดียว

### 7. Physical Front Panel & LED Indicators (Bonus +1.5)
- แผงแสดงพอร์ตจำลองตามโมเดลฮาร์ดแวร์ (Chassis Front Panel)
- แสดงไฟสถานะ LED เขียว (Up) / แดง (Down)
- คลิกดูข้อมูลเชิงลึกของพอร์ต เช่น IP, Subnet Mask, Port Type, และ Speed

---

## ชุดการทดสอบระบบ (Test Suite Results)

สามารถทดสอบฟังก์ชันทั้งหมดได้ผ่านคำสั่ง:
```bash
python tests/test_all_features.py
python -m unittest tests/test_cli_and_telnet_switch.py
```

### สรุปผลการทดสอบ (28/28 Tests Passed - 100%):
```text
================================================================================
          NETCONFIG TRACER STUDIO - AUTOMATED TEST SUITE v3
================================================================================
 [1/28]  Device Inventory (List)                  ... [ PASS ]
 [2/28]  Device Inventory (Add/Remove)            ... [ PASS ]
 [3/28]  Device Connection (R1, R2, R3)           ... [ PASS ]
 [4/28]  Active Connections Pool                  ... [ PASS ]
 [5/28]  Interfaces List (Parsing & Schema)       ... [ PASS ]
 [6/28]  Interface Configure (Live Set Status)    ... [ PASS ]
 [7/28]  Routing Preview (Static Route)           ... [ PASS ]
 [8/28]  Routing Preview (OSPF)                   ... [ PASS ]
 [9/28]  Routing Preview (RIP)                    ... [ PASS ]
 [10/28] Routing Preview (EIGRP)                  ... [ PASS ]
 [11/28] Routing Preview (BGP)                    ... [ PASS ]
 [12/28] Routing Apply (Live Push & Revert)       ... [ PASS ]
 [13/28] Show Command Execution (show ip route)   ... [ PASS ]
 [14/28] Freeform CLI Execution                   ... [ PASS ]
 [15/28] Topology Auto-Discovery (Real Links)     ... [ PASS ]
 [16/28] Front Panel Port Data                    ... [ PASS ]
 [17/28] Command Suggestions (Fuzzy Autocomplete) ... [ PASS ]
 [18/28] Command Normalization Engine             ... [ PASS ]
 [19/28] Virtual PC Config (Set IP & Gateway)     ... [ PASS ]
 [20/28] Virtual PC Ping via Router Proxy         ... [ PASS ]
 [21/28] Direct ICMP Ping Check Endpoint          ... [ PASS ]
 [22/28] Interface Up/Down State Toggle           ... [ PASS ]
 [23/28] Direct Interface Config Endpoint        ... [ PASS ]
 [24/28] Routing Redistribution Preview           ... [ PASS ]
 [25/28] Topology Interfaces Diagnostics          ... [ PASS ]
 [26/28] EVE-NG Direct Import Endpoint            ... [ PASS ]
 [27/28] Interface DHCP Configuration             ... [ PASS ]
 [28/28] Interface No IP Configuration            ... [ PASS ]
================================================================================
 ALL 28 TESTS PASSED! (100% SUCCESS RATE)
================================================================================
```

---

## การแก้ปัญหาเบื้องต้น (Troubleshooting)

| ปัญหา | สาเหตุ | วิธีแก้ไข |
|---|---|---|
| `ModuleNotFoundError: No module named '...'` | ติดตั้ง dependencies ไม่ครบ | รัน `pip install -r requirements.txt` |
| อุปกรณ์ Online/Offline สลับรัวๆ | Flask Watchdog รีสตาร์ทตัวเองบน Windows | ใน `app.py` มีการตั้งค่า `use_reloader=False` เพื่อป้องกันปัญหานี้แล้ว |
| ตัวอักษรแตกขาดบน Terminal (`inrfc`, `seail`) | Race Condition ระหว่าง CLI กับ Background Polling | ระบบเพิ่ม Per-Device Mutex Lock ป้องกันการอ่าน Socket ชนกันเรียบร้อยแล้ว |
| `Socket error / telnet connection closed` | มีโปรแกรมอื่นเปิดพอร์ต Telnet ค้างไว้ | ปิดโปรแกรมภายนอก (เช่น PuTTY, SecureCRT, Tera Term) ที่เปิดพอร์ตซ้ำซ้อน |
| Terminal ค้างเวลาสั่ง Show Command | อุปกรณ์ส่งข้อความ `--More--` | ระบบส่ง `terminal length 0` และ `terminal width 512` ให้อัตโนมัติ |
| `Syntax error % Invalid input detected` เมื่อพิมพ์ Show | เราเตอร์ค้างอยู่ในโหมด `(config)#` | พิมพ์คำสั่งโดยมี `do` นำหน้า เช่น `do sh ip int br` (ระบบมี fallback `do` ให้ใน background) |
| หน้า Topology ไม่แสดงโหนด | ไม่ได้เชื่อมต่ออินเทอร์เน็ตเพื่อโหลด Vis.js CDN | ตรวจสอบการเชื่อมต่ออินเทอร์เน็ตแล้วกด Refresh หน้าเว็บ |

---

## เอกสารอ้างอิงและเกณฑ์การตรวจ (Rubric & Checklist)
- 📘 **คู่มือการใช้งานฉบับสมบูรณ์ (User Guide)**: [USER_GUIDE.md](USER_GUIDE.md) — คู่มือการใช้งานทุกฟังก์ชันและวิธีตั้งค่า EVE-NG ฉบับละเอียด
- ✅ **รายการตรวจสอบเกณฑ์การให้คะแนน (Test Cases Checklist)**: [TEST_CASES_CHECKLIST.md](TEST_CASES_CHECKLIST.md) — เอกสารจับคู่เกณฑ์คะแนน (13 คะแนนเต็ม) และขั้นตอนทดสอบทีละข้อ
- 📐 **ข้อกำหนดระบบ v3 (Technical Specification)**: [assignment-2-v3-network-automation-ui-spec.md](assignment-2-v3-network-automation-ui-spec.md) — สถาปัตยกรรมและรายละเอียดทางเทคนิค
