# 📋 แผนการทดสอบระบบแบบแยกฟังก์ชัน (System Test Cases Checklist)
### NetConfig Tracer Studio v3 — Network Automation & CLI Platform

เอกสารนี้รวบรวม **Test Cases ทุกฟังก์ชันของระบบ** เพื่อให้คุณสามารถทดสอบตรวจสอบการทำงานด้วยตัวเองทีละขั้นตอน (Step-by-Step) ทั้งอุปกรณ์ Cisco (Router, Switch) และ Linux PC (Ubuntu Desktop)

---

## 📌 สรุปรายการชุดการทดสอบ (Test Suites Overview)

| หมวดหมู่ | รหัสทดสอบ | จำนวนเคส | เป้าหมายการทดสอบ |
| :--- | :--- | :---: | :--- |
| **1. การจัดการอุปกรณ์ & การเชื่อมต่อ** | `TC-CONN-xx` | 7 Cases | เพิ่ม/แก้/ลบ, SSH Cisco, Telnet EVE-NG, SSH Linux PC, Test Ping, SSH Wizard |
| **2. ผังเครือข่าย & Topology** | `TC-TOPO-xx` | 4 Cases | Interactive Canvas, Refresh, Import EVE-NG Lab, Auto-Discovery |
| **3. การตั้งค่า Interface** | `TC-IF-xx` | 7 Cases | ดึงตาราง (Cisco & Linux), Up/Down, Static IP, DHCP, No IP, Add IF, Front Panel |
| **4. ระบบ Routing Protocol Wizard** | `TC-RT-xx` | 6 Cases | Static Route, Default Route, RIPv2, OSPF, EIGRP, BGP & Redistribution |
| **5. เมนูรันคำสั่งตรวจสอบ (Show Commands)**| `TC-SHOW-xx` | 4 Cases | Cisco General, Routing/CDP, Linux/PC Status, Copy Output |
| **6. หน้าต่าง Interactive CLI Terminal** | `TC-CLI-xx` | 8 Cases | Prompt, Inline Help `?`, Tab Auto-complete, History Up/Down, Linux Bash, Sudo Masking, Ctrl+C, Reconnect |
| **7. การจัดการไฟล์คอนฟิก (Config Lifecycle)**| `TC-CFG-xx` | 4 Cases | Export Running, Export Startup, Write Memory, Merge Config |
| **8. เมนูด้านข้าง (Device Drawer & Virtual PC)**| `TC-DRW-xx` | 2 Cases | Packet Tracer Drawer (Physical/Terminal), Drawer PC IP & Ping |
| **9. การเข้าถึงระยะไกล (Cloudflare Tunnel)** | `TC-REMOTE-xx`| 1 Case | ตรวจสอบการเปิดเข้าเว็บจากภายนอกผ่าน Cloudflare Tunnel |

---

## 🧪 หมวดที่ 1: การจัดการอุปกรณ์ & การเชื่อมต่อ (Device Connection Manager)

### [TC-CONN-01] การเพิ่มอุปกรณ์ใหม่ลงใน Inventory (Add Device)
* **เป้าหมาย:** ตรวจสอบว่าระบบสามารถบันทึกอุปกรณ์ใหม่ทั้งประเภท Router, Switch และ PC ได้ถูกต้อง
* **ขั้นตอนการทดสอบ (Steps):**
  1. กดปุ่ม `+ Add Device` ที่แถบ Device Inventory ด้านซ้าย
  2. กรอกข้อมูล:
     - **Device Name:** `Test-R1`
     - **Device Type:** เลือก `Router`
     - **Connection Protocol:** เลือก `SSH`
     - **IP Address:** `192.168.80.138`, **Port:** `22`
     - **Username:** `admin`, **Password:** `cisco`
  3. กดปุ่ม `Save Device`
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] โมดัลปิดลง และมีรายการ `Test-R1` ปรากฏในแถบ Inventory ด้านซ้าย
  - [ ] ในกล่อง Target Device Dropdown มีชื่อ `Test-R1` ให้เลือก

---

### [TC-CONN-02] การแก้ไขและการลบอุปกรณ์ (Edit & Delete Device)
* **เป้าหมาย:** ตรวจสอบว่าสามารถลบหรือแก้ไขข้อมูลอุปกรณ์ในระบบได้
* **ขั้นตอนการทดสอบ (Steps):**
  1. ที่แถบ Inventory ด้านซ้าย ชี้ไปที่อุปกรณ์ที่สร้างไว้
  2. กดปุ่มลบ (รูปถังขยะ) หรือปุ่มแก้ไข
  3. ยืนยันการลบ
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] อุปกรณ์ถูกลบออกจากแถบ Inventory และ Dropdown ทันที

---

### [TC-CONN-03] การเชื่อมต่อ Cisco ผ่าน Telnet (EVE-NG Console / Port 23)
* **เป้าหมาย:** ตรวจสอบการเชื่อมต่อ Cisco Router / Switch ผ่าน Telnet
* **ข้อมูลตัวอย่าง:** อุปกรณ์ `R4` (IP: `192.168.80.134`, Port: `23`, Password: `cisco`) หรือ `SW2` (Port: `23`)
* **ขั้นตอนการทดสอบ (Steps):**
  1. ไปที่แท็บ **Connect** (แท็บที่ 5)
  2. เลือก Device: `R4` หรือ `SW2`
  3. เลือก Protocol: `TELNET`
  4. ใส่ Port `23` หรือ Port EVE-NG Console (เช่น `32769`) และ Password: `cisco`
  5. กดปุ่ม **Connect**
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] กล่องสถานะขึ้นสีเขียว: `Connected to R4 (TELNET)`
  - [ ] ไฟสถานะอุปกรณ์ใน Inventory และ Topology เปลี่ยนเป็นสีเขียว (Online)
  - [ ] หน้าต่าง CLI ปรับ Prompt เป็น `R4#` หรือ `SW2#`

---

### [TC-CONN-04] การเชื่อมต่อ Cisco ผ่าน SSH (Port 22)
* **เป้าหมาย:** ตรวจสอบการเชื่อมต่ออุปกรณ์ Cisco ด้วยโปรโตคอล SSH และ Netmiko Driver
* **ข้อมูลตัวอย่าง:** `R1` (IP: `192.168.80.138`, Port: `22`, User: `admin`, Pass: `cisco`) หรือ `R2`
* **ขั้นตอนการทดสอบ (Steps):**
  1. ไปที่แท็บ **Connect**
  2. เลือก Device: `R1`
  3. เลือก Protocol: `SSH`
  4. กรอก Username: `admin`, Password: `cisco`, Port: `22`
  5. กดปุ่ม **Connect**
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] ขึ้นข้อความ `Connected to R1 (SSH)` สีเขียว
  - [ ] ในแท็บ CLI แสดงข้อความพร้อมรับคำสั่ง `R1#`

---

### [TC-CONN-05] การเชื่อมต่อ Ubuntu Linux PC ผ่าน SSH (ฟังก์ชันใหม่ล่าสุด ⭐)
* **เป้าหมาย:** ตรวจสอบว่าระบบสามารถเชื่อมต่อ Linux Node (Ubuntu Desktop 21.04) โดยไม่ติดปัญหา Cisco command error
* **ข้อมูลตัวอย่าง:** `PC1` (IP: `192.168.80.139`, Port: `22`, User: `user`, Pass: `Test123`)
* **ขั้นตอนการทดสอบ (Steps):**
  1. ไปที่แท็บ **Connect**
  2. เลือก Device: `PC1`
  3. สังเกตการตั้งค่า: Protocol: `SSH`, Port: `22`, User: `user`, Pass: `Test123`
  4. กดปุ่ม **Connect**
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] ระบบเรียกใช้ Netmiko `linux` driver โดยอัตโนมัติ
  - [ ] ขึ้นข้อความ `Connected to PC1 (SSH)` สีเขียว
  - [ ] หน้าต่าง CLI สลับ Prompt เป็นรูปแบบ Linux Bash เช่น `user@user1:~$ `

---

### [TC-CONN-06] การทดสอบยิง Ping ไปยังอุปกรณ์ (Test Ping)
* **เป้าหมาย:** ทดสอบความสามารถในการตรวจสอบการเชื่อมต่อไปยัง IP ปลายทาง
* **ขั้นตอนการทดสอบ (Steps):**
  1. ไปที่แท็บ **Connect**
  2. ใส่ IP Address เช่น `192.168.80.139` (หรือ IP ที่เปิดอยู่)
  3. กดปุ่ม **Test Ping**
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] กล่องผลลัพธ์แสดงสถานะ `Host is reachable` พร้อมค่า RTT (ms)

---

### [TC-CONN-07] การใช้งาน SSH Setup Wizard อัตโนมัติบน Cisco
* **เป้าหมาย:** ทดสอบการสร้าง RSA Key และเปิด SSH บน Cisco Node จากหน้าเว็บ
* **ขั้นตอนการทดสอบ (Steps):**
  1. เชื่อมต่ออุปกรณ์ Cisco ผ่าน Telnet ก่อน
  2. เลื่อนลงมาที่หัวข้อ **SSH Setup Wizard** ในแท็บ Connect
  3. ใส่ Domain Name: `lab.local`, RSA Key Size: `2048`
  4. กดปุ่ม **Run SSH Setup on Target Device**
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] อุปกรณ์ส่งคำสั่ง `ip domain-name`, `crypto key generate rsa` และเปิด `transport input ssh` สำเร็จ
  - [ ] มีผลลัพธ์แจ้งยืนยันว่า SSH พร้อมใช้งาน

---

## 🗺️ หมวดที่ 2: ผังเครือข่าย & Topology

### [TC-TOPO-01] การแสดงผลและโต้ตอบบน Interactive Topology Canvas
* **เป้าหมาย:** ตรวจสอบว่า vis-network แสดง Node และ Link ได้ถูกต้อง
* **ขั้นตอนการทดสอบ (Steps):**
  1. มองที่กรอบซ้ายบน **Network Topology**
  2. ใช้เมาส์คลิกลาก Node ต่างๆ (เช่น R1, R2, SW1, PC1)
  3. เลื่อนล้อเมาส์ (Scroll Wheel) เพื่อซูมเข้า/ออก
  4. คลิกที่ตัว Node ของอุปกรณ์
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] Node เคลื่อนไหวตามเมาส์ได้อย่างลื่นไหล
  - [ ] เมื่อคลิกที่ Node ใด ช่อง **Target Device** จะเปลี่ยนไปเลือกอุปกรณ์นั้นโดยอัตโนมัติ

---

### [TC-TOPO-02] การกดปุ่ม Refresh Topology
* **เป้าหมาย:** ตรวจสอบการดึงข้อมูลสถานะและอุปกรณ์ล่าสุดมาเรนเดอร์ใหม่
* **ขั้นตอนการทดสอบ (Steps):**
  1. กดปุ่ม **Refresh** เล็กๆ ด้านบนขวาของการ์ด Network Topology
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] ขึ้นไอคอนหมุนโหลดสั้นๆ และผัง Topology อัปเดตแสดงสถานะปัจจุบัน

---

### [TC-TOPO-03] การนำเข้าผังจาก EVE-NG (EVE-NG Lab Import)
* **เป้าหมาย:** ตรวจสอบการดึง Nodes & Links จาก EVE-NG Server ผ่าน REST API
* **ขั้นตอนการทดสอบ (Steps):**
  1. กดปุ่ม **EVE-NG** บนแถบ Navbar ด้านบน
  2. ใส่ EVE-NG Host (เช่น `192.168.74.131`), User: `admin`, Pass: `eve`
  3. กดปุ่ม **ค้นหา Lab**
  4. เลือกไฟล์ Lab ที่ต้องการ (หรือระบุ `Test.unl`)
  5. กดปุ่ม **Import Topology**
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] ระบบดึงรายชื่อ Node, รุ่นอุปกรณ์, หมายเลข Port Telnet Console มาลงในระบบ
  - [ ] ผัง Topology อัปเดตแสดงโครงสร้างตามแล็บใน EVE-NG

---

### [TC-TOPO-04] การตรวจหาโครงสร้างอัตโนมัติ (Auto-Discovery)
* **เป้าหมาย:** ตรวจสอบการส่งคำสั่ง CDP / ARP เพื่อค้นหาอุปกรณ์ข้างเคียง
* **ขั้นตอนการทดสอบ (Steps):**
  1. เลือก Target Device เป็น Router/Switch ที่เชื่อมต่ออยู่
  2. กดปุ่ม **Auto-Discover** บน Navbar ด้านบน
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] ระบบส่งคำสั่งตรวจหา CDP Neighbor และอัปเดตเส้น Link ระหว่างอุปกรณ์

---

## 🔌 หมวดที่ 3: การตั้งค่า Interface (Tab 1)

### [TC-IF-01] การดึงตาราง Interface ของ Cisco (show ip int brief)
* **เป้าหมาย:** ตรวจสอบว่าระบบสามารถอ่านพอร์ตและสถานะ Up/Down ของ Cisco ได้ครบถ้วน
* **ขั้นตอนการทดสอบ (Steps):**
  1. เลือก Target Device: `R1` (เชื่อมต่อแล้ว)
  2. สลับไปที่ **Tab 1: Interface**
  3. กดปุ่ม **Refresh** เหนือตาราง Interface
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] ตารางแสดงรายชื่อ Interface (เช่น `GigabitEthernet0/0/0`, `Loopback0`)
  - [ ] แสดง IP Address, สถานะ Status (`up` หรือ `administratively down`), และ Protocol (`up`/`down`)
  - [ ] Dropdown ในฟอร์มด้านล่างมีรายชื่อพอร์ตเหล่านี้ให้เลือกตรงกัน

---

### [TC-IF-02] การดึงตาราง Interface ของ Linux PC (ฟังก์ชันใหม่ล่าสุด ⭐)
* **เป้าหมาย:** ตรวจสอบว่าระบบสามารถอ่านพอร์ตจริงของ Ubuntu (`ens3`, `lo`) ผ่าน `ip -br addr` ได้
* **ขั้นตอนการทดสอบ (Steps):**
  1. เลือก Target Device: `PC1` (เชื่อมต่อแล้ว)
  2. สลับไปที่ **Tab 1: Interface**
  3. กดปุ่ม **Refresh**
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] ไม่แสดงข้อความ error ของ Cisco
  - [ ] ตารางแสดงอินเทอร์เฟซจริง เช่น `ens3` (IP: `192.168.80.139/24`, Status: `UP`) และ `lo` (IP: `127.0.0.1/8`)

---

### [TC-IF-03] การสั่งเปิด/ปิด Interface (Quick Up / Down)
* **เป้าหมาย:** ตรวจสอบการสั่ง `shutdown` และ `no shutdown` จากปุ่มด่วน Step 2
* **ขั้นตอนการทดสอบ (Steps):**
  1. เลือกแถว Interface เช่น `Loopback0` ในตาราง
  2. กดปุ่มสีแดง **Down**
  3. สังเกตข้อความยืนยันและกดปุ่ม Refresh เพื่อดูสถานะ
  4. กดปุ่มสีเขียว **Up**
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] เมื่อกด Down: สถานะพอร์ตเปลี่ยนเป็น `administratively down`
  - [ ] เมื่อกด Up: สถานะพอร์ตเปลี่ยนกลับมาเป็น `up` พร้อมข้อความแจ้งเตือนสีเขียว

---

### [TC-IF-04] การกำหนด Static IP Address และดู Live Cisco Preview
* **เป้าหมาย:** ตรวจสอบการสร้างคำสั่งและคอนฟิก IP Address แบบ Static
* **ขั้นตอนการทดสอบ (Steps):**
  1. เลือกพอร์ตเป้าหมาย เช่น `GigabitEthernet0/0/2`
  2. เลือกโหมด: `Static IP`
  3. กรอก IP Address: `10.10.10.1`, Subnet Mask: `255.255.255.0`
  4. กรอก Description: `Connection-to-Branch`
  5. เลือก Interface State: `UP`
  6. สังเกตในกล่อง **Cisco IOS Preview** ด้านล่าง
  7. กดปุ่ม **Deploy Interface Config**
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] ในกล่อง Preview ขึ้นคำสั่ง:
    ```cisco
    interface GigabitEthernet0/0/2
     description Connection-to-Branch
     ip address 10.10.10.1 255.255.255.0
     no shutdown
    ```
  - [ ] ส่งคำสั่งไปยังอุปกรณ์สำเร็จ และตาราง Interface อัปเดต IP ใหม่ทันที

---

### [TC-IF-05] การกำหนด DHCP Client และ No IP
* **เป้าหมาย:** ตรวจสอบการสั่งให้พอร์ตรับ IP จาก DHCP หรือลบ IP
* **ขั้นตอนการทดสอบ (Steps):**
  1. เลือกโหมด `DHCP Client` สังเกต Preview กลายเป็น `ip address dhcp`
  2. เลือกโหมด `No IP` สังเกต Preview กลายเป็น `no ip address`
  3. ทดสอบส่งคำสั่งไปยังพอร์ตที่ไม่ใช้งาน
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] ส่งคำสั่งไปยังอุปกรณ์ได้ถูกต้องตาม Preview

---

### [TC-IF-06] การเพิ่ม Interface ใหม่ (Add Loopback / VLAN)
* **เป้าหมาย:** ตรวจสอบโมดัลเพิ่ม Interface เสมือน
* **ขั้นตอนการทดสอบ (Steps):**
  1. กดเปิดปุ่ม/เมนู Add Interface
  2. เลือกชนิด: `Loopback`, ระบุหมายเลข: `99`
  3. กดยืนยัน
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] ระบบสร้าง Interface `Loopback99` บนอุปกรณ์ และปรากฏในตาราง

---

### [TC-IF-07] การเปิดดูหน้าต่าง Front Panel (Chassis & Port LEDs)
* **เป้าหมาย:** ตรวจสอบหน้าต่างแสดงพอร์ตฮาร์ดแวร์เสมือนจริง
* **ขั้นตอนการทดสอบ (Steps):**
  1. กดปุ่ม **Front Panel** ที่อยู่ข้างล่างแผง Topology
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] โมดัลเปิดขึ้นมา แสดงแผงหน้ากากอุปกรณ์ Cisco พร้อมไฟสถานะ SYS, ACT, PWR สีเขียว
  - [ ] แสดงช่องพอร์ตตามโมเดล และตารางรายละเอียดพอร์ต Speed / Status / IP

---

## 🔀 หมวดที่ 4: ระบบการตั้งค่า Routing Protocol (Tab 2)

### [TC-RT-01] การตั้งค่า Static Route
* **เป้าหมาย:** ตรวจสอบการคอนฟิกเส้นทางแบบระบุปลายทางเอง
* **ขั้นตอนการทดสอบ (Steps):**
  1. สลับไปที่ **Tab 2: Routing**
  2. เลือกประเภท: **Static**
  3. กรอก Destination Network: `172.16.1.0`, Subnet Mask: `255.255.255.0`
  4. กรอก Next-Hop: `10.1.1.2`
  5. สังเกต Preview: `ip route 172.16.1.0 255.255.255.0 10.1.1.2`
  6. กดปุ่ม **Deploy Routing Config**
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] ระบบส่งคำสั่งสำเร็จ เมื่อไปดู `show ip route static` ในแท็บ Show จะพบเส้นทางนี้

---

### [TC-RT-02] การตั้งค่า Default Route
* **เป้าหมาย:** ตรวจสอบการสร้างเส้นทาง Default Gateway
* **ขั้นตอนการทดสอบ (Steps):**
  1. เลือกประเภท: **Default**
  2. กรอก Next-Hop IP: `192.168.1.1`
  3. สังเกต Preview: `ip route 0.0.0.0 0.0.0.0 192.168.1.1`
  4. กดปุ่ม **Deploy Routing Config**
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] คอนฟิกสำเร็จ และพบ `Gateway of last resort` ในตาราง Routing

---

### [TC-RT-03] การตั้งค่า RIP Version 2
* **เป้าหมาย:** ตรวจสอบการคอนฟิก Dynamic Routing RIPv2
* **ขั้นตอนการทดสอบ (Steps):**
  1. เลือกประเภท: **RIP**
  2. เลือก RIP Version: `Version 2 (classless + VLSM)`
  3. กดปุ่ม `+ Add Network` แล้วระบุ: `192.168.1.0` และ `10.0.0.0`
  4. สังเกต Preview:
     ```cisco
     router rip
      version 2
      no auto-summary
      network 192.168.1.0
      network 10.0.0.0
     ```
  5. กดปุ่ม **Deploy Routing Config**
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] ระบบส่งคำสั่งเข้า Router สำเร็จ

---

### [TC-RT-04] การตั้งค่า OSPF (Single & Multi Area)
* **เป้าหมาย:** ตรวจสอบการเปิดใช้งาน OSPF พร้อม Process ID และ Router ID
* **ขั้นตอนการทดสอบ (Steps):**
  1. เลือกประเภท: **OSPF**
  2. กำหนด Process ID: `1`, Router-ID: `1.1.1.1`
  3. กด `+ Add Network`:
     - Network: `192.168.1.0`, Wildcard: `0.0.0.255`, Area: `0`
  4. สังเกต Preview:
     ```cisco
     router ospf 1
      router-id 1.1.1.1
      network 192.168.1.0 0.0.0.255 area 0
     ```
  5. กดปุ่ม **Deploy Routing Config**
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] คอนฟิก OSPF เข้าอุปกรณ์สำเร็จ และตรวจสอบได้ใน `show ip ospf neighbor`

---

### [TC-RT-05] การตั้งค่า EIGRP
* **เป้าหมาย:** ตรวจสอบการคอนฟิก EIGRP ด้วย Autonomous System (AS)
* **ขั้นตอนการทดสอบ (Steps):**
  1. เลือกประเภท: **EIGRP**
  2. กำหนด AS Number: `100`
  3. กด `+ Add Network`: `10.0.0.0`, Wildcard: `0.0.255.255`
  4. สังเกต Preview แสดง `router eigrp 100` และ `no auto-summary`
  5. กดปุ่ม **Deploy Routing Config**
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] คอนฟิกสำเร็จ

---

### [TC-RT-06] การตั้งค่า BGP และ Route Redistribution
* **เป้าหมาย:** ตรวจสอบการคอนฟิก BGP Neighbor และการแจกจ่าย Default Route
* **ขั้นตอนการทดสอบ (Steps):**
  1. เลือกประเภท: **BGP**
  2. ใส่ Local AS: `65001`, ใส่ Neighbor IP: `10.1.1.2`, Remote AS: `65002`
  3. ทดสอบติ๊กเลือก `Originate Default Route (default-information originate)`
  4. ตรวจสอบ Preview และกดส่ง
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] โค้ดคำสั่งถูกสร้างอย่างถูกต้องและส่งเข้าอุปกรณ์ได้

---

## 👁️ หมวดที่ 5: รวมคำสั่งตรวจสอบ (Tab 3: Show Commands)

### [TC-SHOW-01] การรันคำสั่ง Cisco General Show
* **เป้าหมาย:** ทดสอบการคลิกปุ่มคำสั่งพื้นฐานบน Cisco Router/Switch
* **ขั้นตอนการทดสอบ (Steps):**
  1. เลือก Target Device เป็น Cisco Node (เช่น `R1`, `R2`, `SW1`)
  2. สลับไปที่ **Tab 3: Show**
  3. ทดสอบคลิกปุ่มต่อไปนี้ทีละปุ่ม:
     - `ip int brief`
     - `int status`
     - `running-config`
     - `version`
     - `vlan` (สำหรับ Switch)
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] ช่อง Output สีดำด้านล่างแสดงผลลัพธ์ที่ถูกต้องจากอุปกรณ์จริง ไม่ค้าง และไม่ออกมาเป็นค่าว่าง

---

### [TC-SHOW-02] การรันคำสั่ง Cisco Routing & Protocols
* **เป้าหมาย:** ทดสอบคำสั่งตรวจสอบเส้นทางและสถานะโปรโตคอล
* **ขั้นตอนการทดสอบ (Steps):**
  1. ในหน้า Tab 3 กดปุ่ม:
     - `ip route`
     - `ip protocols`
     - `ospf neighbor`
     - `cdp neighbors`
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] ผลลัพธ์ Routing Table และเพื่อนบ้านแสดงครบถ้วน

---

### [TC-SHOW-03] การรันคำสั่ง Linux / PC Status (ฟังก์ชันใหม่ล่าสุด ⭐)
* **เป้าหมาย:** ตรวจสอบว่าปุ่มในหมวด Linux / PC แสดงผลลัพธ์ของ Ubuntu ได้อย่างสมบูรณ์
* **ขั้นตอนการทดสอบ (Steps):**
  1. เลือก Target Device: `PC1` (เชื่อมต่อแล้ว)
  2. สลับไปที่ **Tab 3: Show**
  3. ทดสอบกดปุ่มในส่วน **Linux / PC Status Commands**:
     - `ip -br addr (IPs)`: ตรวจสอบ IP ทุก Interface
     - `ifconfig`: ตรวจสอบสถานะการ์ดเครือข่าย
     - `ip route`: ตรวจสอบ Routing Table บน Linux
     - `uname -a`: ตรวจสอบ Kernel และสถาปัตยกรรมระบบ
     - `os-release`: ตรวจสอบเวอร์ชัน Ubuntu (21.04)
     - `ssh status`: ตรวจสอบสถานะ daemon `sshd`
     - `df -h (Disk)`: ตรวจสอบพื้นที่ดิสก์
     - `free -m (RAM)`: ตรวจสอบปริมาณหน่วยความจำ
     - `open ports (ss)`: ตรวจสอบพอร์ตที่เปิดรับการเชื่อมต่อ
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] ทุกปุ่มส่งคำสั่งไปยัง Linux และได้ผลลัพธ์กลับมาแสดงในหน้าต่าง Output อย่างรวดเร็ว ถูกต้อง ชัดเจน

---

### [TC-SHOW-04] การคัดลอกผลลัพธ์ Output (Copy)
* **เป้าหมาย:** ตรวจสอบปุ่ม Copy บนหน้าต่าง Output
* **ขั้นตอนการทดสอบ (Steps):**
  1. รันคำสั่งใดๆ ให้มีผลลัพธ์ขึ้นในกล่อง
  2. กดปุ่มรูปกระดาษ (Copy) บนมุมขวาของกล่อง Output
  3. ไปเปิด Notepad แล้วกด `Ctrl + V`
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] ข้อความในกล่อง Output ถูกคัดลอกลง Clipboard ครบทุกบรรทัด

---

## 💻 หมวดที่ 6: หน้าต่าง Interactive CLI Terminal (Tab 4)

### [TC-CLI-01] การส่งคำสั่ง Cisco CLI พื้นฐาน
* **เป้าหมาย:** ตรวจสอบความถูกต้องและลื่นไหลของการพิมพ์คำสั่งสไตล์ PuTTY / TeraTerm
* **ขั้นตอนการทดสอบ (Steps):**
  1. เลือก Target Device: `R1`
  2. สลับไปที่ **Tab 4: CLI**
  3. พิมพ์ `show ip interface brief` แล้วกด `Enter`
  4. พิมพ์ `configure terminal` แล้วกด `Enter`
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] ตัวหนังสือพิมพ์ลื่นไหล ไม่มีสะดุด
  - [ ] Prompt ปรับเปลี่ยนตามโหมด เช่น `R1#` กลายเป็น `R1(config)#`
  - [ ] บรรทัดพิมพ์เลื่อนลงล่างสุดอัตโนมัติ (Auto-scroll)

---

### [TC-CLI-02] การใช้งานปุ่ม `?` เพื่อดู Inline Help
* **เป้าหมาย:** ตรวจสอบฟังก์ชันแนะนำคำสั่งบริบท (Context-sensitive Help)
* **ขั้นตอนการทดสอบ (Steps):**
  1. ขณะอยู่ที่ Prompt `R1#` พิมพ์ `show ?` (หรือกดปุ่ม `?`)
  2. ทดสอบพิมพ์ `clock ?` หรือ `ip ?`
  3. สลับไปที่อุปกรณ์ Linux `PC1` แล้วกด `?`
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] บน Cisco: แสดงรายการคำสั่งย่อยที่เป็นไปได้ทั้งหมด พร้อมคำอธิบายสไตล์ Cisco IOS
  - [ ] บน Linux: แสดงหมวดคำสั่ง Linux Help (Networking, System, Monitoring, Package Manager)

---

### [TC-CLI-03] การใช้งานปุ่ม `Tab` เพื่อเติมคำสั่งอัตโนมัติ (Auto-completion)
* **เป้าหมาย:** ตรวจสอบการเติมคำสั่งเต็มเมื่อพิมพ์เพียงตัวย่อ
* **ขั้นตอนการทดสอบ (Steps):**
  1. ที่ Cisco Prompt พิมพ์ `sh` แล้วกดปุ่ม `Tab`
  2. พิมพ์ `conf t` แล้วกด `Tab`
  3. ที่ Linux Prompt พิมพ์ `ifcon` แล้วกด `Tab`
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] `sh` ขยายเป็น `show`
  - [ ] `conf t` ขยายเป็น `configure terminal`
  - [ ] `ifcon` บน Linux ขยายเป็น `ifconfig`

---

### [TC-CLI-04] การเรียกดูประวัติคำสั่งด้วยลูกศรขึ้น/ลง (`Up` / `Down` Arrow)
* **เป้าหมาย:** ตรวจสอบระบบ Command History Navigation
* **ขั้นตอนการทดสอบ (Steps):**
  1. พิมพ์คำสั่ง 3 คำสั่ง: `show version`, `show clock`, `show users`
  2. กดปุ่มลูกศรขึ้น `↑` ซ้ำๆ
  3. กดปุ่มลูกศรลง `↓`
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] ข้อความในช่องพิมพ์หมุนเวียนเรียกคำสั่งเก่าที่เคยพิมพ์กลับมาตามลำดับ

---

### [TC-CLI-05] การรันคำสั่ง Linux Bash ทั่วไปบน PC1
* **เป้าหมาย:** ตรวจสอบการโต้ตอบคำสั่ง Linux ทั่วไป
* **ขั้นตอนการทดสอบ (Steps):**
  1. เลือกอุปกรณ์ `PC1`
  2. ในหน้า CLI พิมพ์:
     - `uname -a`
     - `whoami`
     - `cat /etc/os-release`
     - `ip addr`
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] ผลลัพธ์แสดงบรรทัดตามจริงของ Linux Ubuntu โดยไม่ถูกครอบด้วยคำสั่ง Cisco

---

### [TC-CLI-06] การรันคำสั่ง `sudo` และการซ่อนรหัสผ่าน (Password Masking ⭐)
* **เป้าหมาย:** ตรวจสอบว่าเมื่อรันคำสั่งที่ต้องการสิทธิ์ root ระบบจะซ่อนรหัสผ่าน ไม่หลุดตัวอักษร และส่งรหัสผ่านให้ sudo สำเร็จ
* **ขั้นตอนการทดสอบ (Steps):**
  1. เลือกอุปกรณ์ `PC1`
  2. พิมพ์คำสั่ง `sudo ip addr show` แล้วกด `Enter`
  3. สังเกตบรรทัดที่ระบบตอบกลับ: `[sudo] password for user:`
  4. พิมพ์รหัสผ่าน `Test123` แล้วกด `Enter`
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] ขณะพิมพ์รหัสผ่าน ตัวอักษรจะถูกซ่อนเป็นจุดหรือเว้นว่าง (ไม่ขึ้นเป็นตัวหนังสือ `Test123` ในหน้าจอ)
  - [ ] ระบบส่งรหัสผ่านเข้า sudo ได้สำเร็จ และแสดงผลลัพธ์คำสั่ง root โดยไม่โดน abort หรือ password incorrect

---

### [TC-CLI-07] การใช้งานปุ่ม Ctrl+C (Break), Clear และ Copy ในแถบ Titlebar
* **เป้าหมาย:** ตรวจสอบปุ่มควบคุมหน้าต่างเทอร์มินัล
* **ขั้นตอนการทดสอบ (Steps):**
  1. ทดสอบกดปุ่ม **Ctrl+C** บน Titlebar
  2. พิมพ์คำสั่งให้หน้าจอเต็ม แล้วกดปุ่ม **Clear**
  3. พิมพ์คำสั่งใหม่ แล้วกดปุ่ม **Copy** แล้วนำไปวางใน Notepad
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] ปุ่ม Ctrl+C ส่งสัญญาณยกเลิกไปยังอุปกรณ์ได้จริง
  - [ ] ปุ่ม Clear ล้างหน้าจอหน้าต่างเทอร์มินัลให้ว่างสะอาด
  - [ ] ปุ่ม Copy สามารถคัดลอกข้อความในเทอร์มินัลได้ครบถ้วน

---

### [TC-CLI-08] การกดปุ่ม Reconnect Session
* **เป้าหมาย:** ตรวจสอบการรีเซ็ตและเชื่อมต่อเซสชัน CLI ใหม่เมื่อเกิดปัญหาหลุด
* **ขั้นตอนการทดสอบ (Steps):**
  1. กดปุ่ม **Reconnect** บน Titlebar ของ CLI
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] ระบบทำการตัดการเชื่อมต่อเดิมและสถาปนาเซสชันใหม่กลับมาพร้อมใช้งาน

---

## 💾 หมวดที่ 7: การจัดการไฟล์คอนฟิก (Tab 6: Config Lifecycle)

### [TC-CFG-01] การ Export Running Config เป็นไฟล์ .txt
* **เป้าหมาย:** ตรวจสอบการสำรองข้อมูลคอนฟิกปัจจุบันลงเครื่องคอมพิวเตอร์
* **ขั้นตอนการทดสอบ (Steps):**
  1. เลือก Target Device: `R1` (เชื่อมต่อแล้ว)
  2. ไปที่ **Tab 6: Config**
  3. กดปุ่ม **Export Running** ในการ์ด Export Running Config
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] เบราว์เซอร์ดาวน์โหลดไฟล์ชื่อประมาณ `R1_running_config_....txt`
  - [ ] เมื่อเปิดดูในไฟล์ มีเนื้อหา running-config ของอุปกรณ์ครบถ้วน

---

### [TC-CFG-02] การ Export Startup Config เป็นไฟล์ .txt
* **เป้าหมาย:** ตรวจสอบการดาวน์โหลด startup-config
* **ขั้นตอนการทดสอบ (Steps):**
  1. กดปุ่ม **Export Startup**
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] เบราว์เซอร์ดาวน์โหลดไฟล์ `R1_startup_config_....txt` สำเร็จ

---

### [TC-CFG-03] การสั่งบันทึกคอนฟิก (Write Memory)
* **เป้าหมาย:** ตรวจสอบการบันทึก running-config ไปยัง startup-config (NVRAM)
* **ขั้นตอนการทดสอบ (Steps):**
  1. กดปุ่ม **Write Memory**
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] กล่อง Config Output ด้านล่างแสดงผลลัพธ์ `[OK]` หรือ `Building configuration... [OK]`

---

### [TC-CFG-04] การ Merge Config (ส่งสคริปต์คอนฟิกพร้อมข้ามบรรทัด `!`)
* **เป้าหมาย:** ตรวจสอบการนำชุดคำสั่งหลายบรรทัดมาอัดเข้าอุปกรณ์
* **ขั้นตอนการทดสอบ (Steps):**
  1. ในช่องข้อความ Merge Config วางโค้ดทดสอบ:
     ```cisco
     ! Test merge configuration
     interface Loopback101
      description Created-by-Merge-Test
      ip address 10.101.1.1 255.255.255.0
      no shutdown
     !
     end
     ```
  2. กดปุ่ม **Merge to Device**
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] ระบบส่งคำสั่งเข้าอุปกรณ์โดยข้ามบรรทัดคอมเมนต์ `!`
  - [ ] ตรวจสอบพบ Interface `Loopback101` บนอุปกรณ์

---

## 🗂️ หมวดที่ 8: เมนูด้านข้าง (Device Drawer & Virtual PC)

### [TC-DRW-01] การเปิดแผง Drawer และสลับแท็บ Physical / Terminal
* **เป้าหมาย:** ตรวจสอบ Packet Tracer style Drawer
* **ขั้นตอนการทดสอบ (Steps):**
  1. ดับเบิ้ลคลิกที่อุปกรณ์บน Topology หรือคลิกเลือกเพื่อเปิด Drawer
  2. สลับแท็บไปที่ **Physical**: สังเกตภาพจำลองเครื่อง
  3. สลับแท็บไปที่ **Terminal**: ทดสอบพิมพ์คำสั่งด่วน
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] Drawer เลื่อนออกมาอย่างนุ่มนวล และสลับแท็บดูข้อมูลได้ถูกต้อง

---

### [TC-DRW-02] การตั้งค่า Virtual PC และทดสอบยิง Ping จาก Drawer
* **เป้าหมาย:** ตรวจสอบการบันทึก IP/Gateway ของ PC และการทดสอบ Ping
* **ขั้นตอนการทดสอบ (Steps):**
  1. เลือกอุปกรณ์ประเภท PC
  2. สลับไปที่แท็บ **PC** ใน Drawer
  3. กำหนด IP: `192.168.80.139`, Mask: `255.255.255.0`, Gateway: `192.168.80.1`
  4. กดปุ่ม **Save PC Config**
  5. ในช่อง Target พิมพ์ `8.8.8.8` หรือ IP ในแล็บ แล้วกดปุ่ม **Ping**
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] กล่องผลลัพธ์แสดงผลการ Ping สำเร็จ

---

## 🌐 หมวดที่ 9: การเข้าถึงระยะไกล (Cloudflare Tunnel)

### [TC-REMOTE-01] การเปิดเข้าเว็บผ่าน Public HTTPS Tunnel
* **เป้าหมาย:** ตรวจสอบการเข้าถึง Web Application จากเครื่องอื่นภายนอกเครือข่าย
* **ข้อมูลตัวอย่าง:** `https://die-genes-prevent-seal.trycloudflare.com` (หรือ URL ที่กำลังรันอยู่)
* **ขั้นตอนการทดสอบ (Steps):**
  1. เปิดเบราว์เซอร์จากคอมพิวเตอร์เครื่องอื่น หรือบนสมาร์ตโฟน (ใช้ 4G/5G)
  2. เข้า URL ของ Cloudflare Tunnel
  3. ทดสอบเข้าดูหน้าเว็บ ผัง Topology และแท็บต่างๆ
* **ผลลัพธ์ที่คาดหวัง (Expected Result):**
  - [ ] หน้าเว็บโหลดขึ้นมาอย่างสมบูรณ์ รองรับ HTTPS โดยไม่ต้อง Forward Port ที่เราเตอร์จริง

---

## 📝 ตารางสรุปผลการทดสอบ (Test Execution Record Sheet)

| รหัสเคส | ชื่อฟังก์ชันที่ทดสอบ | วันที่ทดสอบ | ผลการทดสอบ (Pass/Fail) | หมายเหตุ |
| :--- | :--- | :---: | :---: | :--- |
| `TC-CONN-01` | เพิ่มอุปกรณ์ใหม่ (Add Device) | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-CONN-02` | แก้ไข/ลบอุปกรณ์ (Edit/Delete) | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-CONN-03` | เชื่อมต่อ Cisco Telnet | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-CONN-04` | เชื่อมต่อ Cisco SSH | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-CONN-05` | เชื่อมต่อ Ubuntu Linux PC SSH | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-CONN-06` | ทดสอบยิง Ping (Test Ping) | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-CONN-07` | SSH Setup Wizard อัตโนมัติ | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-TOPO-01` | โต้ตอบผังเครือข่าย Interactive | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-TOPO-02` | ปุ่ม Refresh Topology | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-TOPO-03` | Import Lab จาก EVE-NG | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-TOPO-04` | Auto-Discovery ค้นหาเพื่อนบ้าน | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-IF-01` | ดึงตาราง Interface Cisco | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-IF-02` | ดึงตาราง Interface Linux PC | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-IF-03` | ปรับสถานะพอร์ตด่วน Up/Down | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-IF-04` | กำหนด Static IP + Live Preview | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-IF-05` | กำหนด DHCP Client / No IP | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-IF-06` | เพิ่ม Interface เสมือน (Loopback) | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-IF-07` | แผงหน้าปัด Front Panel & LEDs | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-RT-01` | ตั้งค่า Static Route | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-RT-02` | ตั้งค่า Default Route | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-RT-03` | ตั้งค่า RIPv2 Dynamic Routing | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-RT-04` | ตั้งค่า OSPF Routing | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-RT-05` | ตั้งค่า EIGRP Routing | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-RT-06` | ตั้งค่า BGP & Redistribution | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-SHOW-01` | Cisco General Show Commands | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-SHOW-02` | Cisco Routing & CDP Show | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-SHOW-03` | Linux / PC Status Commands | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-SHOW-04` | คัดลอกผลลัพธ์ Output | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-CLI-01` | ส่งคำสั่ง Cisco CLI & Prompt | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-CLI-02` | ฟังก์ชัน Inline Help `?` | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-CLI-03` | ฟังก์ชัน Auto-complete `Tab` | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-CLI-04` | เลื่อนประวัติคำสั่ง `Up/Down` | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-CLI-05` | ส่งคำสั่ง Linux Bash ทั่วไป | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-CLI-06` | รัน `sudo` + Password Masking | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-CLI-07` | ควบคุม Ctrl+C / Clear / Copy | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-CLI-08` | กด Reconnect Session | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-CFG-01` | Export Running Config (.txt) | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-CFG-02` | Export Startup Config (.txt) | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-CFG-03` | สั่งบันทึก Write Memory | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-CFG-04` | นำเข้าคอนฟิก Merge Config | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-DRW-01` | เปิดดู Device Drawer | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-DRW-02` | กำหนด IP & Ping จาก Drawer PC | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
| `TC-REMOTE-01`| เข้าใช้งานผ่าน Cloudflare Tunnel | `____/__/__` | `[ ] PASS / [ ] FAIL` | |
