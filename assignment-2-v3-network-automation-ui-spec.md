# Spec v3 — NetConfig Tracer Studio: Real-Lab Integration, Auto-Discovery & Resilient Architecture

> เอกสารนี้เป็น **ส่วนขยายระดับปฏิบัติการจริง (Operational & Production Spec)** ต่อเนื่องจาก `assignment-2-network-automation-ui-spec.md` (v1) และ `assignment-2-v2-network-automation-ui-spec.md` (v2)
> รวบรวมสถาปัตยกรรมที่พัฒนาขึ้นจริง, ปัญหาทางเทคนิคระดับลึกที่ตรวจพบจากการทดสอบกับ Cisco IOS บน EVE-NG, การแก้ไขบั๊กทั้งหมด, และผลลัพธ์ของชุดทดสอบ 27 ฟังก์ชัน (100% Pass)
> ให้ใช้ไฟล์ v3 นี้เป็น **เกณฑ์อ้างอิงล่าสุด (Source of Truth)** ของระบบ

---

## สารบัญ
1. [ภาพรวมสถาปัตยกรรมระบบ (Architecture Overview)](#1-ภาพรวมสถาปัตยกรรมระบบ-architecture-overview)
2. [ระบบเชื่อมต่อและ Session Resiliency (Auto-Reconnect Engine)](#2-ระบบเชื่อมต่อและ-session-resiliency-auto-reconnect-engine)
3. [ระบบ Auto-Discovery Topology (Multi-Leg & Subnet Overlap Matching)](#3-ระบบ-auto-discovery-topology-multi-leg--subnet-overlap-matching)
4. [การบูรณาการ EVE-NG REST API เต็มรูปแบบ](#4-การบูรณาการ-eve-ng-rest-api-เต็มรูปแบบ)
5. [Interface Configuration Lifecycle & Live Cache Sync](#5-interface-configuration-lifecycle--live-cache-sync)
6. [การปรับปรุง Vis.js Topology UI & Dark Aesthetics](#6-การปรับปรุง-visjs-topology-ui--dark-aesthetics)
7. [ชุดทดสอบระบบ 27 ฟังก์ชัน (Test Suite Specification)](#7-ชุดทดสอบระบบ-27-ฟังก์ชัน-test-suite-specification)
8. [โครงสร้างไฟล์และไดเรกทอรีมาตรฐาน (Project Organization)](#8-โครงสร้างไฟล์และไดเรกทอรีมาตรฐาน-project-organization)

---

## 1. ภาพรวมสถาปัตยกรรมระบบ (Architecture Overview)

NetConfig Tracer Studio v3 ถูกออกแบบให้เชื่อมต่ออุปกรณ์เครือข่าย Cisco IOS จริงผ่านโปรโตคอล Telnet/SSH/Serial โดยมีโครงสร้างหลัก 3 เลเยอร์:

```
+-----------------------------------------------------------------------+
|                         Frontend Web UI                               |
|   - Vis.js Dynamic Network Canvas (MultiGraph, Subnet Badges)         |
|   - Packet Tracer Style Device Drawer (Physical, Config, Terminal)    |
|   - Live Interface Table, Routing Generator & Realtime CLI Console    |
+-----------------------------------------------------------------------+
                                  │ HTTP / JSON REST APIs
                                  ▼
+-----------------------------------------------------------------------+
|                          Flask Application Core                       |
|   - app.py: REST Endpoints, Cache Management, Route Handlers         |
|   - command_builder.py: Cisco IOS Syntax Engine (RIP, EIGRP, OSPF, BGP)|
|   - command_normalizer.py: Fuzzy Normalizer & Suggestion Engine       |
|   - topology_builder.py: NetworkX MultiGraph + IP Overlap Engine      |
|   - eve_ng_client.py: EVE-NG REST API Client                          |
+-----------------------------------------------------------------------+
                                  │ Netmiko Session Pool
                                  ▼
+-----------------------------------------------------------------------+
|                  Connection Manager & Auto-Reconnect Engine           |
|   - Connection Pooling (SSH, Telnet, Serial)                          |
|   - Auto-Detection of Socket Drops / Idle Timeouts                    |
|   - On-Demand Reconnection & Command Retry System                     |
|   - Terminal Paging Suppression ("terminal length 0")                 |
+-----------------------------------------------------------------------+
                                  │ Console Ports (32769, 32770, 32771)
                                  ▼
+-----------------------------------------------------------------------+
|                    EVE-NG Virtual Lab Environment                     |
|   - Router R1, R2, R3 (Cisco IOL/Dynamips)                            |
|   - Point-to-Point Links & Multi-Access Cloud Networks                |
+-----------------------------------------------------------------------+
```

---

## 2. ระบบเชื่อมต่อและ Session Resiliency (Auto-Reconnect Engine)

### 2.1 ปัญหาทางเทคนิคในแล็บจริง (Root Cause in Real Lab)
- **EVE-NG Telnet Single-Client Restriction**: พอร์ต Console ของ Node ใน EVE-NG (เช่น `32769`, `32770`) รองรับ Telnet Client ได้เพียง 1 Session ต่อพอร์ต หากมีสคริปต์ภายนอกหรือ Session อื่นเชื่อมต่อ หรือ Idle Timeout ขาดหาย Socket จะถูกตัดทันที (`telnet connection closed` หรือ `EOFError`)
- **Stale Pool State**: ในระบบเดิม หาก Socket ขาด `conn_mgr.is_connected()` ยังคงคืนค่า `True` เนื่องจาก Object ยังค้างอยู่ใน Memory ทำให้คำสั่งถัดไปทั้งหมดล้มเหลว และแจ้งเตือนผู้ใช้ว่า `Config failed`

### 2.2 โครงสร้าง Auto-Reconnect ใน `connection_manager.py`
ใน v3 ได้เพิ่มระบบตรวจจับและ Reconnect อัตโนมัติ:

1. **Parameters Caching**: บันทึก `device_params` (IP, Port, Credentials) ไว้ใน Pool เสมอ
2. **Paging Freeze Elimination**: ส่ง `terminal length 0` ทันทีหลัง Connect เพื่อป้องกัน Netmiko แฮงก์จากข้อความ `--More--`
3. **On-Demand Auto-Connection**: หากฟังก์ชันถูกเรียกแต่ Session ยังไม่ได้ต่อ หรือเซิร์ฟเวอร์เพิ่งรีสตาร์ท ระบบจะดึงข้อมูลจาก `devices.json` มาเชื่อมต่อให้อัตโนมัติ (`_ensure_connection()`)
4. **Transparent Retry**: ดักจับ Socket Error (เช่น `closed`, `eof`, `broken pipe`, `reset`) แล้วทำการ Disconnect ขยะทิ้ง -> Reconnect ใหม่ -> Re-execute คำสั่งเดิมทันที

```python
def send_config(self, device_id: str, commands: list, retry: bool = True) -> dict:
    if device_id not in self.pool:
        if not self._ensure_connection(device_id):
            return {"success": False, "message": f"Device '{device_id}' ยังไม่ได้เชื่อมต่อ"}

    entry = self.pool[device_id]
    handler = entry["handler"]
    try:
        output = handler.send_config_set(commands)
        if re.search(r"% Invalid input detected at", output):
            return {"success": False, "output": output, "message": "IOS syntax error"}
        return {"success": True, "output": output, "message": "ตั้งค่าสำเร็จ"}
    except Exception as e:
        err_msg = str(e).lower()
        if retry and any(k in err_msg for k in ("closed", "eof", "broken pipe", "reset", "socket", "timeout")):
            print(f"[ConnectionManager] Socket drop for {device_id}, auto-reconnecting...")
            self.disconnect(device_id)
            if self._ensure_connection(device_id):
                return self.send_config(device_id, commands, retry=False)
        return {"success": False, "output": f"Error: {str(e)}", "message": f"ส่งคำสั่งล้มเหลว: {str(e)}"}
```

---

## 3. ระบบ Auto-Discovery Topology (Multi-Leg & Subnet Overlap Matching)

### 3.1 ข้อจำกัดของ Graph ปกติ และการเปลี่ยนเป็น `nx.MultiGraph`
ในเครือข่ายจริง เราเตอร์สองตัวสามารถเชื่อมต่อกันได้มากกว่า 1 เส้น (Multi-Leg / Dual-Link) หากใช้ `nx.Graph()` ปกติ เส้นที่สองจะทับเส้นแรก
- **v3 Solution**: ใช้ `nx.MultiGraph()` พร้อมเก็บ Metadata ประจำ Edge แต่ละเส้นอย่างละเอียด:
  - `from`, `to`
  - `from_port`, `to_port`
  - `from_ip`, `to_ip`
  - `subnet`, `method`

### 3.2 อัลกอริทึม Subnet Overlap Matching (แก้ปัญหา Mask ไม่ตรงกัน)
ในกรณีที่ไม่ได้เปิดใช้งาน CDP หรือเชื่อมต่อผ่าน Cloud Bridge:
- Router R1 มีขา `Ethernet0/1` ไอพี `192.168.75.1/30`
- Router R2 มีขา `Ethernet0/1` ไอพี `192.168.75.2/24`
การเปรียบเทียบ Network String แบบเดิมจะถือว่าคนละวง แต่ v3 ใช้ `ipaddress.IPv4Interface` ตรวจสอบ Overlap:

```python
net_a = ipaddress.IPv4Interface(f"{ip_a}/{mask_a}").network
net_b = ipaddress.IPv4Interface(f"{ip_b}/{mask_b}").network
if net_a.overlaps(net_b):
    # ตรวจสอบว่าเป็น Point-to-Point (มี 2 ขา) หรือ Multi-Access (มีมากกว่า 2 ขา)
    ...
```

- **Point-to-Point (2 ขา)**: วาดสายตรงเชื่อมระหว่าง `R1 Ethernet0/1 <-> R2 Ethernet0/1`
- **Multi-Access (> 2 ขา)**: สร้าง Node เสมือนประเภท `network` (รูปก้อนเมฆ `Net 192.168.74.0/24`) และลากขา `Ethernet0/0` ของทุกตัวมาเชื่อมต่อกับก้อนเมฆนี้

### 3.3 การรักษา Endpoint Consistency
NetworkX เมื่อแปลงเป็น Edge มักสลับทิศทาง Node อัตโนมัติ (เช่น `(u, v)` กลายเป็น `(v, u)`) ทำให้ Label ขา Interface สลับด้านกัน
- **v3 Fix**: บันทึก `original_from` เอาไว้ และทำการสลับ `from_port` / `to_port` คืนตำแหน่งให้ตรงกับ Node จริงเสมอใน `graph_to_json()`

---

## 4. การบูรณาการ EVE-NG REST API เต็มรูปแบบ

### 4.1 การแก้ปัญหา URL Duplication Bug
- ผู้ใช้ระบุ Host ได้หลากหลายรูปแบบ เช่น `192.168.74.131`, `http://192.168.74.131`, หรือ `http://192.168.74.131/api`
- ใน v2 หากใส่ `/api` มาด้วย ระบบจะต่อ string ซ้ำเป็น `/api/api/auth/login` (404 Not Found)
- **v3 Fix**: เพิ่มตัวตัด Trailing `/api` อัตโนมัติใน `EveNgClient.__init__()`

### 4.2 การดึงข้อมูลอัตโนมัติ (Auto-Enrichment)
เมื่อกด **"EVE-NG Import"**:
1. ล็อกอินผ่าน REST API `/api/auth/login`
2. ดึง Topology Links (`/api/labs/{lab}/topology`) และ Node Data (`/api/labs/{lab}/nodes`)
3. กรอง Bridge Network ภายในที่ตั้งค่า `visibility == '0'` ออก
4. ดึงหมายเลขพอร์ต Telnet Console ของแต่ละ Node (เช่น `32769`, `32770`) จาก Metadata ของ EVE-NG มาใส่ใน Inventory อัตโนมัติ
5. บันทึกเข้า `devices.json` และสั่งเชื่อมต่อเพื่ออ่าน IP ทันที

---

## 5. Interface Configuration Lifecycle & Live Cache Sync

### 5.1 ปัญหา Interface หายไป ("No interface data available")
- ผู้ใช้เปลี่ยน Router ใน Dropdown หน้า Interface แต่ตารางไม่ยอมเปลี่ยนตาม
- เมื่อกด **"Deploy Interface Config"** สำเร็จ หน้าจอไม่ยอมรีเฟรชค่าใหม่
- **v3 Fix ใน `app.js` & `app.py`**:
  1. `onActiveDeviceChange()`: เรียก `refreshInterfaceTable()` ทันทีเมื่อผู้ใช้เปลี่ยน Target Device
  2. `submitInterfaceConfig()`:
     - ปรับปุ่มเป็นสถานะกำลังส่งคำสั่ง (`Deploying...` + Spinner)
     - เมื่อได้รับคำตอบสำเร็จ สั่ง `await refreshInterfaceTable(true)` (ส่ง `?force=1` ดึงค่าสดจาก Router) ทันที
     - สั่ง `runAutoDiscovery()` ให้เส้นใน Topology ปรับเปลี่ยนตามทันทีโดยไม่ต้องรีโหลดหน้าเว็บ
  3. ปุ่ม **Refresh** ในตาราง Step 1: ผูกกับ `refreshInterfaceTable(true)` เพื่อให้ผู้ใช้สามารถบังคับดึงข้อมูลสดจาก Router ได้ทุกเวลา

### 5.2 การรองรับโหมด DHCP Client (`ip address dhcp`)
- ใน Cisco IOS ขา Interface สามารถรับ IP อัตโนมัติจาก DHCP Server ผ่านคำสั่ง `ip address dhcp` (โดยไม่ต้องระบุ Subnet Mask)
- **v3 Implementation & UI UX**:
  - **IP Configuration Mode Toggle**: มีปุ่มสลับโหมดระหว่าง **Static IP** และ **DHCP Client** พร้อมตัวเลือก visual feedback ชัดเจน
  - **Smart Form Adaptation**:
    - เมื่อสลับเป็น DHCP: ช่อง IP Address ถูกกำหนดเป็น `DHCP` (ตัวอักษรสีฟ้าสว่าง `#38bdf8` เด่นชัด) และช่อง Subnet Mask จะถูกปิดการใช้งานอัตโนมัติ (Disabled & Grayed out)
    - เมื่อผู้ใช้พิมพ์คำว่า `dhcp` หรือ `DHCP` ลงในช่อง IP ด้วยตนเอง ระบบจะสลับโหมดและปิดช่อง Subnet Mask ให้อัตโนมัติทันที
    - เมื่อคลิกเลือกแถว Interface ในตาราง Step 1 หากขา Interface นั้นมีค่า IP เป็น DHCP ระบบจะตรวจจับและสลับโหมดมาเป็น DHCP Client ให้อัตโนมัติ
  - **Cisco IOS Command Generation (`command_builder.py`)**:
    - เมื่อ `ip.lower().strip() == 'dhcp'` จะสร้างคำสั่ง:
      ```cisco
      interface <name>
       description <desc>
       ip address dhcp
       no shutdown
      ```
    - ไม่มีการใส่ Subnet Mask ต่อท้าย ซึ่งถูกต้องตาม Cisco IOS Reference Architecture
  - **Backend Validation Bypass (`app.py`)**:
    - ตรวจจับค่า `ip == 'dhcp'` แล้วข้าม Regex Validation ของ IPv4 Address โดยตรง ทำให้ไม่เกิด 400 Bad Request
  - **Verification**:
    - ผ่านการทดสอบโดยอัตโนมัติในชุดทดสอบ Test #27 (`Interface DHCP Configuration`) ครบถ้วน 100%

---

## 6. การปรับปรุง Vis.js Topology UI & Dark Aesthetics

### 6.1 การแก้ปัญหา Node หายตัว (Canvas Rendering Freeze)
- ใน Vis.js หาก Object Node มี Property `margin: undefined` หรือ `shapeProperties: undefined` ตัว Canvas Renderer จะหยุดวาด Node ทันที (ทำให้เหลือแต่เส้น Wire แต่ไม่มีตัว Router)
- **v3 Fix**: ตรวจสอบ Node Type อย่างรัดกุม กำหนด `margin` เฉพาะ Node ก้อนเมฆ (`Net`) เท่านั้น ส่วน Router/Switch ใช้ Icon รูปภาพตามมาตรฐาน

### 6.2 Styling สำหรับ Dark Theme
- **เส้น Edge**: ใช้สี `#38bdf8` (Cyan/Sky) หนา 2.5px พร้อม Highlight เป็น `#60a5fa` เมื่อนำเมาส์ไปชี้
- **Label Wire**: แสดงผลขาและ IP เช่น `e0/1 <-> e0/1` พร้อม Subnet ด้านล่าง
- **Badge Background**: รองพื้นข้อความบนเส้นด้วยสี `#0f172a` ขอบ `#334155` เพื่อไม่ให้เส้น Wire ขีดทับตัวหนังสือ อ่านง่าย สบายตา สไตล์มืออาชีพ

---

## 7. ชุดทดสอบระบบ 27 ฟังก์ชัน (Test Suite Specification)

ระบบมาพร้อมชุดทดสอบอัตโนมัติแบบ End-to-End ในไฟล์ [tests/test_all_features.py](file:///c:/Users/puvad/Documents/RepoGithub/Assignment-2-NetPro/tests/test_all_features.py) ซึ่งผ่านการทดสอบจริงครบถ้วน **27/27 Tests Passed (100%)**:

| # | ชื่อการทดสอบ | Endpoint / Function | สิ่งที่ตรวจสอบ | ผลลัพธ์ |
|---|---|---|---|:---:|
| 1 | Inventory List | `GET /api/inventory` | ดึงรายชื่อ R1, R2, R3 ครบถ้วน | **PASS** |
| 2 | Add/Remove Inventory | `POST/DELETE /api/inventory` | เพิ่มและลบ Switch ทดสอบ | **PASS** |
| 3 | Connect Devices | `POST /api/connect/<id>` | เชื่อมต่อ Telnet R1, R2, R3 บน EVE-NG | **PASS** |
| 4 | Active Connections Pool | `GET /api/connections` | ตรวจสอบ Session Pool ของทั้ง 3 เครื่อง | **PASS** |
| 5 | Interfaces List | `GET /api/devices/<id>/interfaces` | ดึงและ Parse `show ip int brief` | **PASS** |
| 6 | Interface Configure | `POST /api/devices/<id>/interfaces/configure` | ตั้งค่าสถานะ Up/Down บนขา Router จริง | **PASS** |
| 7 | Routing Preview: Static | `POST /api/routing/preview` | ตรวจสอบคำสั่ง `ip route ...` | **PASS** |
| 8 | Routing Preview: OSPF | `POST /api/routing/preview` | ตรวจสอบ `router ospf`, `network ... area` | **PASS** |
| 9 | Routing Preview: RIP | `POST /api/routing/preview` | ตรวจสอบ RIP v2 และ `no auto-summary` | **PASS** |
| 10 | Routing Preview: EIGRP | `POST /api/routing/preview` | ตรวจสอบ `router eigrp <as>`, wildcard | **PASS** |
| 11 | Routing Preview: BGP | `POST /api/routing/preview` | ตรวจสอบ `neighbor ... remote-as`, `network` | **PASS** |
| 12 | Routing Apply (Live Config) | `POST /api/routing/apply` | Push Route ไปยัง R1 จริงและ Rollback | **PASS** |
| 13 | Show Command Execution | `POST /api/show` | รัน `show ip route` รับ Output จริง | **PASS** |
| 14 | CLI Freeform Execution | `POST /api/cli/execute` | รัน `show clock` ผ่าน Virtual Terminal | **PASS** |
| 15 | Topology Auto-Discovery | `GET /api/topology/json` | ตรวจพบ Node และสายเชื่อมต่อ R1-R2 จริง | **PASS** |
| 16 | Front Panel Ports | `GET /api/ports/<id>` | แสดงสถานะไฟ LED และข้อมูลพอร์ต | **PASS** |
| 17 | Command Suggestions | `GET /api/suggestions?q=sh+ip` | แนะนำคำสั่ง Autocomplete อัตโนมัติ | **PASS** |
| 18 | Command Normalization | `POST /api/cli/execute` | แปลง `sh ip int br` -> คำสั่งเต็ม | **PASS** |
| 19 | Virtual PC Config | `POST /api/pc/<id>/config` | บันทึก IP, Mask, Gateway ของ PC | **PASS** |
| 20 | Virtual PC Ping via Proxy | `POST /api/pc/<id>/ping` | ยิง Ping จำลองผ่าน Default Gateway Router | **PASS** |
| 21 | Ping Endpoint | `POST /api/ping` | ตรวจสอบการตอบสนอง ICMP | **PASS** |
| 22 | Interface State Toggle | `POST /api/config/interface/state` | สั่ง Up/Down แยกอิสระพร้อม Verify | **PASS** |
| 23 | Direct Interface Config | `POST /api/config/interface` | ตั้งค่า IP และ Description ผ่าน Endpoint หลัก | **PASS** |
| 24 | Routing Redistribution Preview | `POST /api/routing/preview` | ตรวจสอบ `redistribute` และ `default-originate` | **PASS** |
| 25 | Topology Diagnostic Ifaces | `GET /api/topology/interfaces` | ดึงข้อมูล Interface ทุกตัวที่เชื่อมต่ออยู่ | **PASS** |
| 26 | EVE-NG Direct Import | `POST /api/eveng/import` | ดึงโครงสร้าง Topology จริงจาก EVE-NG Server | **PASS** |
| 27 | Interface DHCP Configuration | `POST /api/config/interface` | ตั้งค่าโหมด DHCP Client (`ip address dhcp`) | **PASS** |

---

## 8. โครงสร้างไฟล์และไดเรกทอรีมาตรฐาน (Project Organization)

เพื่อความเป็นระเบียบเรียบร้อยของโปรเจกต์ โค้ดทั้งหมดถูกจัดหมวดหมู่อย่างชัดเจน:

```text
Assignment-2-NetPro/
├── app.py                                    # Flask Backend Server หลัก
├── command_builder.py                        # ตัวสร้างคำสั่ง Cisco IOS CLI
├── command_normalizer.py                     # ตัวแปลงคำสั่งย่อและ Autocomplete
├── connection_manager.py                     # Netmiko Pool Manager พร้อม Auto-Reconnect
├── topology_builder.py                       # NetworkX MultiGraph & Discovery Engine
├── eve_ng_client.py                          # EVE-NG REST Client
├── devices.json                              # Device Inventory Storage (Persistent)
├── requirements.txt                          # รายการ Python Libraries
│
├── static/                                   # Frontend Assets
│   ├── css/styles.css                        # Modern Dark Glassmorphism Styling
│   ├── js/app.js                             # Logic ควบคุมหน้าบ้านและ Vis.js Canvas
│   └── icons/                                # Custom SVG Network Icons (Router, Switch, PC)
│
├── templates/
│   └── index.html                            # โครงสร้างหน้าเว็บหลัก
│
├── tests/                                    # [โฟลเดอร์สำหรับทดสอบระบบ]
│   ├── test_all_features.py                  # ชุดทดสอบอัตโนมัติครบ 27 ฟังก์ชัน (Test Suite)
│   ├── test_cdp.py                           # สคริปต์ทดสอบ CDP Protocol
│   ├── test_cmd.py                           # สคริปต์ทดสอบ Netmiko Execution
│   ├── test_parse.py                         # สคริปต์ทดสอบ Text Parsing
│   ├── test_parse2.py                        # สคริปต์ทดสอบ Text Parsing เพิ่มเติม
│   └── reconnect.py                          # สคริปต์ Reconnect แล็บด่วน
│
├── legacy/                                   # [โฟลเดอร์โค้ดเก่าที่ปลดระวางแล้ว]
│   └── network_engine.py                     # โมดูลเดิมก่อน Refactor
│
├── README.md                                 # คู่มือการติดตั้งและใช้งานระบบ
├── assignment-2-network-automation-ui-spec.md      # Spec v1 ดั้งเดิม
├── assignment-2-v2-network-automation-ui-spec.md   # Spec v2
└── assignment-2-v3-network-automation-ui-spec.md   # [เอกสารนี้] Spec v3 ล่าสุด
```

---

## สรุปคำแนะนำสำหรับการนำเสนอและการใช้งาน (Demo Checklist)

1. **การเริ่มรันระบบ**:
   ```bash
   python app.py
   ```
2. **การรันชุดทดสอบความถูกต้องทั้งหมด**:
   ```bash
   python tests/test_all_features.py
   ```
3. **การเข้าใช้งาน Web UI**:
   - เปิดเบราว์เซอร์ไปที่ `http://127.0.0.1:5000`
   - ตรวจสอบ Topology: ระบบจะทำการ Auto-Discover ลากสายเชื่อมโยง `e0/1 <-> e0/1` และเชื่อมต่อก้อนเมฆ `Net` ให้อัตโนมัติ
   - หน้า Interface Configuration: เลือกระหว่าง Router R1, R2, R3 ตารางจะอัปเดตสถานะสด และเมื่อกรอก IP/Subnet กด Deploy ข้อมูลจะขึ้นสถานะ `UP/UP` และสะท้อนบน Topology Graph ทันที
