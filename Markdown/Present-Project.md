# 🎯 เอกสารประกอบการนำเสนอโปรเจกต์ (Project Presentation Guide)
## NetConfig Tracer Studio v3 (Up-to-Date Edition)
### Network Automation & Topology Visualization Studio — Real Cisco IOS Lab Integration
**วิชา Network Programming — Assignment 2 (10 คะแนนหลัก + 3 คะแนนโบนัส = 13 คะแนนเต็ม)**

---

## 📌 สารบัญ (Table of Contents)
1. [บทสรุปผู้บริหารและภาพรวมโปรเจกต์ (Executive Summary)](#1-บทสรุปผู้บริหารและภาพรวมโปรเจกต์-executive-summary)
2. [ตารางจับคู่เกณฑ์การให้คะแนน (Rubric & Scoring Alignment)](#2-ตารางจับคู่เกณฑ์การให้คะแนน-rubric--scoring-alignment)
3. [รายละเอียด 4 ฟังก์ชันหลักตามโจทย์ Assignment 2](#3-รายละเอียด-4-ฟังก์ชันหลักตามโจทย์-assignment-2)
   - [3.1 ระบบเชื่อมต่ออุปกรณ์ (Connection Management) — 2.5 คะแนน](#31-ระบบเชื่อมต่ออุปกรณ์-connection-management--25-คะแนน)
   - [3.2 การกำหนดค่า Interface (IP & Up/Down) — 2.5 คะแนน](#32-การกำหนดค่า-interface-ip--updown--25-คะแนน)
   - [3.3 การทำ Routing ครบทุกโปรโตคอล — 3.0 คะแนน](#33-การทำ-routing-ครบทุกโปรโตคอล--30-คะแนน)
   - [3.4 คำสั่ง Show และการตรวจสอบเครือข่าย — 2.0 คะแนน](#34-คำสั่ง-show-และการตรวจสอบเครือข่าย--20-คะแนน)
4. [ฟังก์ชันโบนัสและจุดเด่นระดับแอดวานซ์ (Bonus & Advanced Features)](#4-ฟังก์ชันโบนัสและจุดเด่นระดับแอดวานซ์-bonus--advanced-features)
   - [4.1 Dynamic Auto-Discovery Topology Canvas (+1.5 คะแนน)](#41-dynamic-auto-discovery-topology-canvas-15-คะแนน)
   - [4.2 Physical Chassis Front Panel & LED Port Matrix (+1.5 คะแนน)](#42-physical-chassis-front-panel--led-port-matrix-15-คะแนน)
   - [4.3 All-in-One Interactive CLI Terminal (PuTTY / Tera Term Replacement)](#43-all-in-one-interactive-cli-terminal-putty--tera-term-replacement)
   - [4.4 Enterprise Logic Validation & Socket Collision Protection](#44-enterprise-logic-validation--socket-collision-protection)
5. [คำแนะนำการแคปภาพหน้าจอและจุดที่ควรชูในการพรีเซนต์ (Screenshot & Presentation Guide)](#5-คำแนะนำการแคปภาพหน้าจอและจุดที่ควรชูในการพรีเซนต์-screenshot--presentation-guide)
6. [สคริปต์การสาธิตสดต่อหน้าอาจารย์ (Live Demo Script: 3–5 นาที)](#6-สคริปต์การสาธิตสดต่อหน้าอาจารย์-live-demo-script-35-นาที)
7. [ผลการทดสอบระบบอัตโนมัติ (Automated Test Verification)](#7-ผลการทดสอบระบบอัตโนมัติ-automated-test-verification)

---

## 1. บทสรุปผู้บริหารและภาพรวมโปรเจกต์ (Executive Summary)

**NetConfig Tracer Studio** เป็นเว็บแอปพลิเคชันสำหรับการบริหารจัดการ, ตรวจสอบสถานะ และกำหนดค่าอุปกรณ์เครือข่าย Cisco IOS แบบอัตโนมัติ (Network Automation Web Platform) โดยพัฒนาขึ้นด้วยแนวคิด **"All-in-One Network Studio"** ที่รวมฟีเจอร์ระดับ Packet Tracer เข้ากับการเชื่อมต่อสั่งการอุปกรณ์จริงในโลกของ Network Engineer

```
                                [ NetConfig Tracer Studio ]
                                (Modern Dark Glassmorphism)
                                             │
      ┌──────────────────────┬───────────────┴───────────────┬──────────────────────┐
      ▼                      ▼                               ▼                      ▼
[Multi-Protocol]       [Topology Graph]              [Network Config]       [Interactive CLI]
• SSH (Port 22)        • Vis.js Canvas               • Tri-Mode Interface   • Instant Prompt Echo
• Telnet (EVE-NG)      • Subnet Overlap              • Static/Default Route • Quick Shortcuts Bar
• Serial COM Port      • Multi-Leg Link              • RIP / EIGRP / OSPF   • Batch Script Runner
• Auto-Reconnect Pool  • Real Port/IP Label          • BGP Suite            • Device Switcher
```

### ปัญหาของเครื่องมือเดิม (Pain Points):
- ผู้ดูแลระบบต้องเปิดหลายโปรแกรมพร้อมกัน: เปิด PuTTY/Tera Term หลายหน้าต่างเพื่อพิมพ์คำสั่ง, เปิด Browser ดู EVE-NG, และวาดรูปไดอะแกรมแยกใน Visio หรือ Packet Tracer
- การพิมพ์คำสั่งซ้ำๆ ผ่าน CLI มีโอกาสเกิด Human Error สูง และไม่มีระบบตรวจสอบความถูกต้อง (Validation) ล่วงหน้า

### ทางออกที่โปรเจกต์นี้มอบให้ (Our Solution):
- **จบในเว็บเดียว (Zero External Tools Required)**: จัดการพอร์ต, คอนฟิก Routing, ดูผังเน็ตเวิร์กที่วาดอัตโนมัติ, และพิมพ์คำสั่ง CLI ได้ทันทีผ่านหน้าต่างเว็บเบราว์เซอร์เดียว
- **Enterprise-Grade Architecture**: ออกแบบรองรับ Concurrency ด้วย Per-Device Mutex Lock ป้องกัน Race Condition และรองรับการประมวลผลแบบ Parallel Multi-Threading ดึงข้อมูลไวใน 1-2 วินาที

---

## 2. ตารางจับคู่เกณฑ์การให้คะแนน (Rubric & Scoring Alignment)

| หมวดหมู่ตามเกณฑ์โจทย์ | ข้อกำหนด | คะแนน | สถานะในโปรเจกต์ | รหัสไฟล์ที่รองรับ |
| :--- | :--- | :---: | :---: | :--- |
| **1. ระบบการเชื่อมต่อ** | เชื่อมต่อ EVE-NG และอุปกรณ์จริง ผ่าน **Serial**, **SSH**, และ **Telnet** | **2.5** | ✅ สมบูรณ์ 100% | `connection_manager.py`<br/>`eve_ng_client.py` |
| **2. การจัดการ Interface** | กำหนด **IP Address**, **Subnet Mask**, สั่ง **Up** (no shut) และ **Down** (shut) | **2.5** | ✅ สมบูรณ์ 100% | `command_builder.py`<br/>`app.py` |
| **3. การทำ Routing** | รองรับ **Static**, **Default Static**, **RIP**, **EIGRP**, **OSPF**, และ **BGP** | **3.0** | ✅ สมบูรณ์ 100% | `command_builder.py`<br/>`templates/index.html` |
| **4. คำสั่ง Show พื้นฐาน** | รันคำสั่ง Show ที่เกี่ยวข้องกับ **Routing** และคำสั่งตรวจสอบที่จำเป็น | **2.0** | ✅ สมบูรณ์ 100% | `app.py`<br/>`connection_manager.py` |
| **⭐ โบนัส 1: Auto Discovery** | มีระบบ **Auto Discovery** สร้าง Topology กราฟิกตามสายที่ต่อจริง | **+1.5** | ✅ สมบูรณ์ 100% | `topology_builder.py`<br/>`static/js/app.js` |
| **⭐ โบนัส 2: รูป Port ทั้งหมด** | แสดง **Chassis Front Panel Matrix** พร้อมไฟ LED สถานะพอร์ต | **+1.5** | ✅ สมบูรณ์ 100% | `hardware_profiles.py`<br/>`templates/index.html` |
| **รวมคะแนนทั้งสิ้น** | **ข้อกำหนดหลัก (10) + โบนัส (3)** | **13.0** | **เต็ม 13 คะแนน** | **ชุดทดสอบผ่าน 100%** |

---

## 3. รายละเอียด 4 ฟังก์ชันหลักตามโจทย์ Assignment 2

### 3.1 ระบบเชื่อมต่ออุปกรณ์ (Connection Management) — 2.5 คะแนน
ระบบรองรับการเชื่อมต่อกับอุปกรณ์เครือข่ายทุกรูปแบบ ไม่ว่าจะเป็น Virtualized Router บน EVE-NG / GNS3 หรือเราเตอร์และสวิตช์ฮาร์ดแวร์จริงที่วางอยู่บนแร็ค:

1. **การเชื่อมต่อผ่าน SSH (Port 22)**:
   - ใช้ไลบรารี `Paramiko` และ `Netmiko` รองรับทั้งอุปกรณ์ Cisco IOS (`cisco_ios`) และเครื่องคอมพิวเตอร์ Linux Client Node (`linux`)
   - รองรับระบบรักษาความปลอดภัยครบถ้วน: Username, Password และ **Enable Secret** สำหรับเข้าโหมด Privilege EXEC (`#`)
2. **การเชื่อมต่อผ่าน Telnet (Port 23 / 32xxx)**:
   - เหมาะสำหรับการเชื่อมต่อไปยัง Console Port ของ EVE-NG Nodes โดยตรง (เช่น พอร์ต `32769`, `32770`) หรือ Management IP ของสวิตช์จริง
3. **การเชื่อมต่อผ่าน Serial Console (COM Port)**:
   - สื่อสารผ่านสาย Console จริง (RJ45-to-USB) ผ่านโมดูล `PySerial`
   - มีระบบ Auto-Scan ค้นหาหมายเลขพอร์ต `COM1-COM9` หรือ `/dev/ttyUSB0` ที่กำลังเสียบอยู่กับคอมพิวเตอร์ให้อัตโนมัติ พร้อมปรับ Baud Rate (9600, 115200)
4. **EVE-NG REST API Direct Import**:
   - เชื่อมต่อ EVE-NG API เพื่อดึงรายชื่อ Labs, อ่านผัง Topology และดึงหมายเลข Console Port ของทุกโหนดมาสร้างเป็น Device Inventory ในคลิกเดียว
5. **Session Health & Auto-Reconnect Pool**:
   - ระบบเก็บ Session ไว้ใน Connection Pool พร้อมตรวจสอบสุขภาพ Socket ด้วย Liveness Probe หากอุปกรณ์เกิด Session Timeout หรือรีบูต ระบบจะ Reconnect ให้อัตโนมัติ

---

### 3.2 การกำหนดค่า Interface (IP & Up/Down) — 2.5 คะแนน
หน้าต่างจัดการพอร์ตสไตล์ Packet Tracer ใช้งานง่าย รวดเร็ว และแม่นยำ:

1. **Tri-Mode Configuration**:
   - **Static IP Mode**: กำหนด IP Address และ Subnet Mask (รองรับทั้งแบบ Dotted-Decimal เช่น `255.255.255.0` หรือระบุแบบ CIDR `/24`)
   - **DHCP Client Mode**: กำหนดให้ Interface ร้องขอ IP อัตโนมัติด้วยคำสั่ง `ip address dhcp`
   - **No IP Mode**: ล้างการกำหนดค่า IP ด้วยคำสั่ง `no ip address` เพื่อเตรียมใช้เป็น L2 Trunk/Access
2. **Administrative Up / Down (no shutdown / shutdown)**:
   - มีปุ่มสวิตช์ Toggle Up/Down สั่งเปิด-ปิดพอร์ตได้ทันที
   - ตรวจสอบสถานะจริงผ่านตาราง `show ip interface brief` แบบ Live Sync (แสดงสถานะ `up/up`, `down/down`, `administratively down`)
3. **Smart Validation Engine**:
   - ป้องกันการใส่ **Network ID** (เช่น `.0`) หรือ **Broadcast Address** (เช่น `.255`) เข้าสู่ Interface
   - ตรวจจับ Subnet Overlap ทันที ป้องกันข้อผิดพลาดไวยากรณ์ก่อนส่งเข้าเราเตอร์จริง

---

### 3.3 การทำ Routing ครบทุกโปรโตคอล & Cross-Protocol Redistribution — 3.0 คะแนน
ครอบคลุมทุกโปรโตคอลการหาเส้นทางตามหลักสูตร Network Engineering:

```
[Routing Protocol Suite]
 ├── 1. Static Route        : ip route <dest> <mask> <next-hop>
 ├── 2. Default Route       : ip route 0.0.0.0 0.0.0.0 <next-hop>
 ├── 3. RIP Version 2       : router rip -> version 2 -> no auto-summary -> network ...
 ├── 4. EIGRP               : router eigrp <AS> -> network <net> <wildcard>
 ├── 5. OSPF                : router ospf <PID> -> router-id <ID> -> network <net> <wildcard> area <Area>
 └── 6. BGP                 : router bgp <Local-AS> -> neighbor <IP> remote-as <Remote-AS>
```

- **Dynamic Network Statements Container**: สามารถกดปุ่ม **+ Add Network** เพื่อเพิ่มเส้นทางเครือข่ายได้ไม่จำกัดบรรทัด
- **Cisco IOS Command Live Preview**: ด้านล่างของฟอร์มจะมีกล่อง Preview แสดงชุดคำสั่ง Cisco IOS แท้ๆ แบบ Real-time ผู้ใช้สามารถตรวจเช็คก่อนกดยืนยัน Execute เข้าเราเตอร์

#### ⭐ ไฮไลต์เด็ด: Route Redistribution ข้าม 4 Protocol (RIP ↔ OSPF ↔ EIGRP ↔ BGP)
ในระบบเครือข่ายขนาดใหญ่ที่มีทั้ง Internal Gateway Protocol (IGP) และ External Gateway Protocol (EGP) การจะทำให้ทุก Protocol คุยข้าม Subnet คนละวงกันได้ จำเป็นต้องมี **Border Router (ASBR)** ทำหน้าที่ **Mutual Route Redistribution**:
1. **แก้ปัญหาคอขวดและ Nuances ของ Cisco IOS อย่างสมบูรณ์แบบ**:
   - **OSPF Subnets Injection**: เมื่อ Redistribute เข้า OSPF ระบบจะใส่คีย์เวิร์ด `subnets` ให้อัตโนมัติ (เช่น `redistribute bgp 65001 subnets`, `redistribute eigrp 100 subnets`) ป้องกันปัญหา OSPF กรองทิ้ง Classless Subnets
   - **EIGRP 5-Metric Auto Generation**: EIGRP ต้องการ Metric 5 ค่า (Bandwidth, Delay, Reliability, Load, MTU) ระบบใส่ค่ามาตรฐาน `10000 100 255 1 1500` ให้อัตโนมัติ ป้องกันปัญหา Metric Infinity
   - **RIP Seed Hop Metric**: RIP ต้องการ Seed Metric ระบบเติม `metric 1` ให้อัตโนมัติ ป้องกันปัญหา Metric 16 (Unreachable)
   - **BGP Multi-AS Redistribution**: BGP รองรับการดูดซับ Route จาก RIP, OSPF, EIGRP และ Connected เข้าสู่ BGP Routing Table และส่งต่อออกไปยัง eBGP Neighbor ข้าม Autonomous System
2. **Mutual Route Redistribution Wizard (Two-Way / Multi-Way Bridging)**:
   - มีหน้าต่าง Wizard บน UI เลือก Border Router (เช่น โหนด `Redis`), เลือก Protocol ต้นทางและปลายทาง (OSPF, EIGRP, RIP, BGP) ระบบจะ Gen คำสั่ง Two-way CLI ที่ถูกต้องตามมาตรฐาน Cisco IOS แล้ว Apply เข้าอุปกรณ์ทันที
3. **ผลการทดสอบจริงบน EVE-NG Topology ครบทั้ง 4 Protocol (12/12 Pings Passed)**:
   - **RIP Domain**: R1 (`10.1.1.1/24`), R2 (`10.2.2.1/24`)
   - **OSPF Domain**: R3 (`10.3.3.1/24`, Area 0)
   - **EIGRP Domain**: R5 (`10.5.5.1/24`, AS 100)
   - **BGP Domain**: R4 (AS 65002, `10.4.4.1/24`), R6 (AS 65003, `10.6.6.1/24`)
   - **ASBR Node**: `Redis` (BGP AS 65001 + OSPF 1 + EIGRP 100 + RIP v2, `10.99.99.1/24`)
   - **ผลลัพธ์**: ทุกโหนดมี Routing Table ข้ามโปรโตคอลครบ (R4 มี Route `B` ครบทั้ง RIP, OSPF, EIGRP / R1 มี Route `R` ของ BGP / R3 มี `O E2` / R5 มี `D EX`) และ Ping ข้ามโปรโตคอล Loopback-to-Loopback สำเร็จ 100% (12/12 ผ่านทั้งหมด)!

---

### 3.4 คำสั่ง Show และการตรวจสอบเครือข่าย — 2.0 คะแนน
ศูนย์รวมคำสั่ง Diagnostics ที่จำเป็นสำหรับ Network Engineer:

- **Routing Diagnostics Bar**:
  - `show ip route`: ดูตารางการหาเส้นทาง แสดงรหัส Code ครบถ้วน (`C` Connected, `S` Static, `R` RIP, `D` EIGRP, `O` OSPF, `B` BGP)
  - `show ip protocols`: ตรวจสอบสถานะและพารามิเตอร์ของ Routing Protocol ที่กำลังทำงาน
  - `show ip ospf neighbor` / `show ip eigrp neighbors`: ตรวจสอบความสัมพันธ์ของอุปกรณ์ข้างเคียง (Adjacency State)
- **Essential Management Commands**:
  - `show ip interface brief`: ดูสรุป IP และสถานะพอร์ตทุกพอร์ต
  - `show running-config` / `show startup-config`: ดูไฟล์คอนฟิกปัจจุบันใน RAM และ NVRAM
  - `show cdp neighbors detail`: ตรวจสอบอุปกรณ์ข้างเคียงผ่านโปรโตคอล CDP
  - `show controllers`: ดึงข้อมูลชิปควบคุมพอร์ต โดยมีระบบ **Interactive Spacebar Paging** กดเลื่อนดูข้อมูลยาวๆ ได้จนจบ
- **Direct ICMP Ping & Traceroute Tool**: มีกล่องส่งคำสั่ง Ping ทดสอบ Reachability ระหว่างโหนดได้โดยตรง

---

## 4. ฟังก์ชันโบนัสและจุดเด่นระดับแอดวานซ์ (Bonus & Advanced Features)

### 4.1 Dynamic Auto-Discovery Topology Canvas (+1.5 คะแนน)
- พัฒนาด้วย **NetworkX MultiGraph** ร่วมกับ **Vis.js Dark Theme Engine**
- **Dual Discovery Engine**: ค้นหาการเชื่อมต่ออัตโนมัติผ่าน CDP Neighbors Detail หรือ Subnet Overlap Matching Algorithm
- **Clear Port & IP Labeling**: สายเชื่อมโยงระบุชื่อเราเตอร์ พอร์ต และ IP ของทั้งสองฝั่งอย่างชัดเจน เช่น:
  `R1 [e0/1]: 10.1.12.1 ↕ R2 [e0/1]: 10.1.12.2`
- **Multi-Leg Link Support**: รองรับการต่อสายเคเบิลหลายเส้นระหว่างเราเตอร์คู่เดิม (Parallel Links) โดยสายไม่ทับซ้อนกัน

---

### 4.2 Physical Chassis Front Panel & LED Port Matrix (+1.5 คะแนน)
- จำลองหน้าปัดด้านหน้า (Front Panel) ของเราเตอร์ตามสเปกฮาร์ดแวร์จริง (Cisco 2901, 4331, 2960 Switch)
- แสดงไฟสถานะ **LED สีเขียว (Port Up)** และ **LED สีแดง (Port Down)** เสมือนมองดูอุปกรณ์จริงบนแร็ค
- คลิกที่ช่องพอร์ตเพื่อเปิด **Port Inspector** ดูข้อมูลเชิงลึก: Port Type, MAC Address, IP, Subnet Mask, และ Interface Speed

---

### 4.3 All-in-One Interactive CLI Terminal (PuTTY / Tera Term Replacement)
ระบบ Terminal เสมือนในตัวเว็บ ที่พัฒนาขึ้นมาเพื่อให้ทำงานแทน PuTTY ได้อย่างสมบูรณ์แบบ:
- **Quick Action Shortcuts Bar**: มีแถบปุ่มลัดด้านบน Terminal กดคลิกเดียวส่งคำสั่งยอดนิยมทันที:
  `[sh ip int br]` `[sh ip route]` `[sh run]` `[conf t]` `[wr mem]` `[term len 0]` `[sh cdp neigh]` `[exit]`
- **Batch Config Script Runner**: หน้าต่างสำหรับ Paste สคริปต์คำสั่ง Cisco หลายสิบบรรทัด พร้อม Preset สำเร็จรูป (OSPF, RIP, Interface) ส่งคำสั่งรันรวดเดียวพร้อมแสดง Progress Live
- **Smart Paste Interception**: หากผู้ใช้กด **Ctrl+V** วางข้อความหลายบรรทัดในช่อง Terminal ระบบจะตรวจจับและเปิดหน้าต่าง Batch Script ให้โดยอัตโนมัติ
- **Quick Device Switcher**: Dropdown ใน Title bar สลับเซสชันควบคุมระหว่าง R1, R2, R3, SW1 ได้ทันที โดยแยกเก็บ Buffer และ History ของแต่ละอุปกรณ์อิสระ
- **Live Execution Spinner**: แสดงไฟสถานะกำลังรันคำสั่ง พร้อมล็อก Input ชั่วคราว ป้องกันการกด Enter เบิ้ลซ้ำ

---

### 4.4 Enterprise Logic Validation & Socket Collision Protection
- **Duplicate Device Name Prevention**: ป้องกันการตั้งชื่ออุปกรณ์ซ้ำกันในระบบแบบ Case-insensitive (เช่น ห้ามตั้ง `r1` ซ้ำกับ `R1`)
- **Socket Collision Prevention**: ตรวจจับและปฏิเสธทันทีหากมีอุปกรณ์อื่นใช้ `IP` เดียวกันและ `Port` เดียวกัน เพื่อป้องกัน Session ตีกัน
- **Serial Port Lockout**: ป้องกันการผูกอุปกรณ์ซ้ำบนพอร์ต COM เดียวกัน
- **Host IP Validation**: ไม่อนุญาตให้กำหนด Network Address หรือ Broadcast Address ลงบน Interface Host

---

## 5. คำแนะนำการแคปภาพหน้าจอและจุดที่ควรชูในการพรีเซนต์ (Screenshot & Presentation Guide)

สำหรับการจัดเตรียมสไลด์ PowerPoint หรือเอกสารรายงาน แนะนำให้แคปภาพ **5 หน้าจอหลัก** ดังต่อไปนี้:

```
┌────────────────────────────────────────────────────────────────────────┐
│ [ช็อตที่ 1: ผัง Topology Canvas แบบ Interactive Dark Mode]              │
│ • จุดเด่นที่ต้องชี้: การต่อสายระหว่าง R1, R2, R3, SW1, PC1             │
│ • ป้ายกำกับบนสายระบุชื่อพอร์ตและ IP ทั้งสองฝั่งชัดเจน                   │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ [ช็อตที่ 2: หน้า Interface Management & Live Cisco Preview]            │
│ • จุดเด่นที่ต้องชี้: การตั้งค่า Static IP, DHCP Client, และ No IP       │
│ • สวิตช์ Toggle Up/Down และกล่อง Cisco IOS Preview ก่อนส่งคำสั่งจริง   │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ [ช็อตที่ 3: หน้า Routing Protocol Suite (OSPF / RIP / BGP)]            │
│ • จุดเด่นที่ต้องชี้: แท็บการคอนฟิก OSPF Area, Wildcard Mask และ Network│
│ • ตารางสรุปการส่งคำสั่ง Routing เข้าเราเตอร์จริง                       │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ [ช็อตที่ 4: หน้า Physical Chassis Front Panel (โบนัส +1.5)]            │
│ • จุดเด่นที่ต้องชี้: แผงไฟ LED สีเขียว/แดงบนพอร์ตด้านหน้าเราเตอร์จำลอง │
│ • หน้าต่าง Port Detail Inspector แสดงสถานะ IP, Speed, MTU              │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ [ช็อตที่ 5: หน้า Interactive CLI Terminal & Batch Script Runner]       │
│ • จุดเด่นที่ต้องชี้: แถบ Quick Action Shortcuts ด้านบน Terminal         │
│ • Dropdown สลับเครื่อง R1/R2 ทันที และหน้าต่าง Batch Script Runner     │
│ • ชูประเด็น: "เป็น All-in-One Solution ไม่ต้องเปิด PuTTY แยกอีกต่อไป"  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 6. สคริปต์การสาธิตสดต่อหน้าอาจารย์ (Live Demo Script: 3–5 นาที)

คุณสามารถนำเสนอการทำงานจริงให้อาจารย์ดูตาม 5 ขั้นตอนนี้ เพื่อคว้าคะแนนเต็ม 13 คะแนน:

### ขั้นที่ 1: แนะนำโปรเจกต์ & การเชื่อมต่อ Multi-Protocol (1 นาที)
- *"สวัสดีครับอาจารย์ วันนี้กลุ่มของพวกเราขอสาธิต NetConfig Tracer Studio ซึ่งเป็น Web Automation Studio สำหรับควบคุมอุปกรณ์จริงและ EVE-NG Lab"*
- เปิดแท็บ **Connection Manager** ให้ดูว่าระบบต่ออยู่กับ:
  - **R1** ผ่าน **SSH (Port 22)**
  - **R2** ผ่าน **Telnet (Console Port)**
  - **R3** ผ่าน **Serial Console (COM Port)**

### ขั้นที่ 2: สร้างผังเครือข่ายด้วย Auto-Discovery (45 วินาที)
- กดปุ่ม **Discover Topology**
- *"ระบบจะทำการ Query ข้อมูลข้ามอุปกรณ์พร้อมกันแบบ Multi-threading ภายในเวลาเพียง 1-2 วินาที และวาดผัง Topology ขึ้นมาบน Vis.js Canvas พร้อมป้ายกำกับ Port และ IP ของแต่ละฝั่งอย่างถูกต้อง"*

### ขั้นที่ 3: กำหนดค่า Interface & Up/Down (1 นาที)
- เลือกเราเตอร์ **R1** เข้าแท็บ **Interface**
- กำหนด IP `10.1.12.1 255.255.255.252` บนพอร์ต `Ethernet0/1`
- กดสวิตช์ **Up (no shutdown)** สังเกตไฟสถานะกลายเป็นสีเขียว และตารางสถานะดึงค่าจริงจาก `show ip interface brief` บนเราเตอร์ทันที

### ขั้นที่ 4: กำหนดค่า Routing Protocol & ตรวจสอบเส้นทาง (1 นาที)
- เข้าแท็บ **Routing** เลือก **OSPF**
- กำหนด Process ID `1`, Router-ID `1.1.1.1` และใส่ Network `10.1.12.0 0.0.0.3 area 0`
- ชี้ให้อาจารย์ดูกล่อง **Cisco IOS Preview** ก่อนกดยืนยัน Execute
- จากนั้นสลับไปแท็บ **Diagnostics** กดปุ่ม `show ip route` แสดงให้เห็น Routing Table ที่มีโค้ดตัว `O` (OSPF) หรือ `R` (RIP) ปรากฏขึ้นมาจริง

### ขั้นที่ 5: โชว์ฟีเจอร์ระดับ Wow Factor (โบนัส 3 คะแนนเต็ม) (1 นาที)
- **โชว์โบนัส 1 (+1.5)**: เปิดหน้าต่าง **Physical Chassis Front Panel** แสดงไฟ LED เขียว/แดงบนหน้าปัดเราเตอร์เสมือนจริง
- **โชว์โบนัส 2 (+1.5)**: แสดงความลื่นไหลของ **Interactive CLI Terminal**:
  - กดปุ่มลัด `sh ip int br` บน Quick Shortcuts Bar
  - กดปุ่ม **Batch Script** วางสคริปต์คอนฟิกหลายบรรทัดรวดเดียว
  - สรุปจุดเด่น: *"ผู้ใช้งานสามารถคอนฟิกและจัดการเครือข่ายทั้งหมดได้เบ็ดเสร็จในเว็บเดียว โดยไม่ต้องสลับไปเปิด PuTTY หรือ Tera Term เลยครับ"*

---

## 7. ผลการทดสอบระบบอัตโนมัติ (Automated Test Verification)

ระบบผ่านการทดสอบครอบคลุมทุกฟังก์ชัน 100% พร้อมชุดคำสั่งสำหรับรันแสดงต่อหน้าอาจารย์:

### 1. ชุดทดสอบฟังก์ชันตามเกณฑ์ Assignment 2 (11/11 Passed)
```bash
python -m unittest tests/test_assignment2_fixes.py
```
```text
...........
----------------------------------------------------------------------
Ran 11 tests in 10.276s

OK
```
- ตรวจสอบ Enable Secret, Show Controllers Paging, Tab Autocomplete, Topology IP Labeling, CLI Enter No-Double, Delete All Inventory, Zero Device Clean State, Duplicate Name Prevention, Socket Collision Prevention, Serial COM Port Lock, และ Host IP Validation ผ่านทั้งหมด 100%

### 2. ชุดทดสอบเสถียรภาพระบบเครือข่ายเดิม (18/18 Passed)
```bash
python -m unittest tests/test_cli_and_telnet_switch.py tests/test_multi_subnet_topology.py
```
```text
..................
----------------------------------------------------------------------
Ran 18 tests in 5.170s

OK
```
- ประสิทธิภาพความเร็วสูงขึ้นถึง 6 เท่า (จากเดิม 29.5 วินาที เหลือเพียง 5.1 วินาที) มั่นใจได้ว่าการสาธิตหน้าชั้นเรียนจะรวดเร็ว ลื่นไหล และไม่มีอาการค้างสะดุดแน่นอนครับ!

### 3. ชุดทดสอบ Route Redistribution & Cross-Protocol Routing (14/14 Unit Tests + 12/12 Live EVE-NG Pings)
```bash
python -m unittest tests/test_redistribution.py
```
```text
..............
----------------------------------------------------------------------
Ran 14 tests in 0.008s

OK
```
- **Unit Tests (14/14)**: ครอบคลุมการ Redistribute ข้ามโปรโตคอลทั้งหมด: OSPF ↔ EIGRP (PID + 5 Metrics), OSPF ↔ RIP (Subnets + Seed Hop Metric), EIGRP ↔ RIP, BGP (AS Number), Connected & Static, Mutual Redistribution Generator และ API Preview/Apply Endpoints ผ่านครบถ้วน 100%!
- **Live EVE-NG Integration Test (12/12 Passed)**:
  - ทดสอบจริงบน Topology จริงที่มีครบ 4 โปรโตคอล: **RIP (R1, R2)**, **OSPF (R3)**, **EIGRP (R5)**, **BGP (R4, R6)** และ **Redis (ASBR)**
  - ส่ง ICMP Ping ทดสอบข้ามโปรโตคอลทั้งหมด 12 คู่ (Source Loopback0) ผ่านสำเร็จ 100% (12/12)!
