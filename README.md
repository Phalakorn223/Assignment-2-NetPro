# NetConfig Tracer Studio v2
### Network Automation Tool — คล้าย Packet Tracer
**Network Programming — Assignment 2**

---

## ภาพรวม
Web application สำหรับ automation การกำหนดค่าเครือข่าย Cisco IOS ผ่าน UI แบบ Packet Tracer  
รองรับการเชื่อมต่อจริงผ่าน **SSH**, **Telnet**, และ **Serial Console** (EVE-NG / GNS3 / อุปกรณ์จริง)  
และสามารถทำงานในโหมด **Simulation** โดยไม่ต้องมีอุปกรณ์จริงก็ได้

---

## โครงสร้างไฟล์

```
Assignment 2/
├── app.py                    # Flask backend (REST API endpoints)
├── connection_manager.py     # Connection pool (SSH/Telnet/Serial), IP validation, ping check
├── command_builder.py        # Pure functions สร้าง Cisco IOS CLI commands
├── command_normalizer.py     # คำสั่งย่อ → คำสั่งเต็ม + autocomplete suggestions
├── topology_builder.py       # networkx graph, CDP/LLDP discovery, topology JSON
├── network_engine.py         # (Legacy — ไม่ถูกใช้แล้ว)
├── requirements.txt
├── templates/
│   └── index.html            # Web UI (vis-network topology, forms, CLI)
└── static/
    ├── css/styles.css
    └── js/app.js
```

---

## ฟีเจอร์ทั้งหมด

### 1. การเชื่อมต่ออุปกรณ์
- **SSH**: ผ่าน Netmiko (`device_type='cisco_ios'`)
- **Telnet**: ผ่าน Netmiko (`device_type='cisco_ios_telnet'`)
- **Serial/Console**: ผ่าน PySerial (COM port หรือ `/dev/ttyUSBx`)
- **Connection Pool**: เก็บ session ค้างไว้ ไม่ต้อง reconnect ทุกครั้ง
- **Test Ping**: ตรวจ reachability ก่อนเชื่อมต่อจริง
- **IP Validation**: ตรวจ format, loopback (127.x), multicast (224.x+)
- **Device Inventory**: Add/Delete/Connect อุปกรณ์ผ่าน UI

### 2. Interface Configuration
- กำหนด **IP Address + Subnet Mask**
- สั่ง **Up (no shutdown)** / **Down (shutdown)**
- เพิ่ม **Description** ของ interface
- Preview CLI command ก่อน deploy

### 3. Routing Protocols
| Protocol | ฟีเจอร์ |
|---|---|
| **Static Route** | Destination, Mask, Next-Hop |
| **Default Static** | `ip route 0.0.0.0 0.0.0.0 <next-hop>` |
| **RIP v2** | Multiple networks, no auto-summary |
| **EIGRP** | AS Number, Networks + Wildcard mask |
| **OSPF** | Process ID, Router-ID, Networks + Wildcard + Area |
| **BGP** | AS Number, Multiple Neighbors + Remote AS, Networks |

ทุก Protocol มี **CLI Preview** ก่อนกด Deploy

### 4. Show Commands (17 คำสั่ง)
- General: `show ip interface brief`, `show interfaces status`, `show running-config`, `show version`, `show vlan`
- Routing: `show ip route`, `show ip route static`, `show ip protocols`
- RIP: `show ip rip database`
- EIGRP: `show ip eigrp neighbors`, `show ip eigrp topology`
- OSPF: `show ip ospf neighbor`, `show ip ospf database`, `show ip ospf interface brief`
- BGP: `show ip bgp summary`, `show ip bgp neighbors`
- CDP: `show cdp neighbors detail`

### 5. Interactive CLI Terminal
- พิมพ์คำสั่ง Cisco IOS ได้ตรง ๆ
- รองรับ **คำสั่งย่อ** เช่น `sh ip int br`, `sh run`, `conf t`
- **Autocomplete dropdown** ขณะพิมพ์ (กด Tab เพื่อเลือก)
- **Command History**: ใช้ Arrow Up/Down เพื่อเรียกคำสั่งก่อนหน้า
- ส่ง show/config command แยกกันอัตโนมัติ

### 6. Auto-Discovery Topology (Bonus)
- ใช้ `show cdp neighbors detail` + `use_textfsm=True` parse เป็น structured data
- Fallback: subnet-matching ถ้าไม่มี CDP/LLDP
- แสดงผลด้วย **vis-network** (interactive, draggable)
- Double-click node → Port Front Panel
- Single-click node → เปลี่ยน active target device

### 7. Port Front Panel (Bonus)
- แสดง interface ทั้งหมดเป็น port socket พร้อม LED indicator
- ตาราง interface detail (Name, Type, Status, IP, Mask, Speed)

---

## วิธีรัน

```bash
# 1. ติดตั้ง dependencies
pip install -r requirements.txt

# 2. รัน server
python app.py

# 3. เปิด browser
# http://127.0.0.1:5000
```

---

## Error Handling (ตาม Spec)
- **IP Validation**: ตรวจ octet ถูก range, loopback, multicast
- **Ping Check**: ทดสอบ reachability ก่อน connect
- **NetmikoTimeoutException**: แสดง error message ที่อ่านง่าย
- **NetmikoAuthenticationException**: แจ้งว่า username/password ผิด
- **IOS Syntax Error**: ตรวจ `% Invalid input detected at` ใน output ทุกครั้ง

---

## Libraries ที่ใช้
| Library | วัตถุประสงค์ |
|---|---|
| `flask` | Web server / REST API |
| `netmiko` | SSH/Telnet abstraction (Cisco IOS) |
| `paramiko` | SSH transport (ผ่าน netmiko) |
| `pyserial` | Serial console connection |
| `networkx` | Topology graph management |
| `vis-network` (CDN) | Interactive topology visualization |
| `Font Awesome` (CDN) | Icons |
| `Inter/Fira Code` (CDN) | Typography |
