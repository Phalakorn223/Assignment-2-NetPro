# NetConfig Tracer Studio v2
### Network Automation Tool — คล้าย Packet Tracer
**Network Programming — Assignment 2**

---

## ภาพรวม
Web application สำหรับ automation การกำหนดค่าเครือข่าย Cisco IOS ผ่าน UI แบบ Packet Tracer  
รองรับการเชื่อมต่อจริงผ่าน **SSH**, **Telnet**, และ **Serial Console** (EVE-NG / GNS3 / อุปกรณ์จริง)  
และสามารถทำงานในโหมด **Simulation** โดยไม่ต้องมีอุปกรณ์จริงก็ได้

---

## สิ่งที่ต้องมีก่อนรัน (Prerequisites)

### Python
- **Python 3.8** ขึ้นไป (แนะนำ Python 3.10+)
- ตรวจสอบเวอร์ชัน: `python --version`
- ดาวน์โหลดได้ที่: https://www.python.org/downloads/

### pip (Python Package Manager)
- มาพร้อมกับ Python อยู่แล้ว
- ตรวจสอบ: `pip --version`

### อินเทอร์เน็ต
- ต้องเชื่อมต่ออินเทอร์เน็ตในครั้งแรกเพื่อโหลด CDN (vis-network, Font Awesome, Google Fonts)

---

## Libraries / Modules ที่ต้องติดตั้ง

### Python Libraries (ติดตั้งผ่าน pip)

| # | Library | เวอร์ชันขั้นต่ำ | วัตถุประสงค์ | จำเป็น? |
|---|---------|---------------|-------------|---------|
| 1 | `flask` | ≥ 2.3.0 | Web server / REST API backend | ✅ **จำเป็น** |
| 2 | `netmiko` | ≥ 4.2.0 | เชื่อมต่ออุปกรณ์ Cisco IOS ผ่าน SSH / Telnet | ✅ **จำเป็น** |
| 3 | `paramiko` | ≥ 3.0.0 | SSH transport layer (dependency ของ netmiko) | ✅ **จำเป็น** |
| 4 | `pyserial` | ≥ 3.5 | เชื่อมต่อผ่าน Serial Console (COM port) | ✅ **จำเป็น** |
| 5 | `networkx` | ≥ 3.0 | สร้าง topology graph สำหรับ auto-discovery | ✅ **จำเป็น** |

### รายละเอียด Library แต่ละตัว

#### 1. Flask (`flask`)
- **ทำหน้าที่**: เป็น web framework สำหรับสร้าง REST API backend ทั้งหมด
- **ใช้ในไฟล์**: `app.py`
- **ถ้าไม่ติดตั้ง**: ❌ โปรเจกต์จะรันไม่ได้เลย (เป็น web server หลัก)

#### 2. Netmiko (`netmiko`)
- **ทำหน้าที่**: จัดการ SSH/Telnet connection ไปยังอุปกรณ์ Cisco IOS ส่ง show/config command
- **ใช้ในไฟล์**: `connection_manager.py`, `network_engine.py`
- **ถ้าไม่ติดตั้ง**: ⚠️ โปรเจกต์จะรันได้แต่เชื่อมต่ออุปกรณ์จริงไม่ได้ (ใช้ได้เฉพาะ Simulation mode)

#### 3. Paramiko (`paramiko`)
- **ทำหน้าที่**: เป็น SSH transport layer ที่ netmiko ใช้เบื้องหลัง
- **ใช้ในไฟล์**: ถูกเรียกผ่าน netmiko โดยอัตโนมัติ
- **ถ้าไม่ติดตั้ง**: ❌ SSH connection จะทำงานไม่ได้ (ปกติจะติดตั้งมาพร้อมกับ netmiko)

#### 4. PySerial (`pyserial`)
- **ทำหน้าที่**: เชื่อมต่ออุปกรณ์ผ่าน Serial Console (COM port / `/dev/ttyUSB`)
- **ใช้ในไฟล์**: `connection_manager.py`, `network_engine.py`
- **ถ้าไม่ติดตั้ง**: ⚠️ ใช้ Serial connection ไม่ได้ (SSH/Telnet ยังใช้ได้ปกติ)
- **หมายเหตุ**: ชื่อ package บน pip คือ `pyserial` แต่ import ในโค้ดคือ `import serial`

#### 5. NetworkX (`networkx`)
- **ทำหน้าที่**: สร้างและจัดการ topology graph สำหรับ auto-discovery (CDP/LLDP)
- **ใช้ในไฟล์**: `topology_builder.py`
- **ถ้าไม่ติดตั้ง**: ⚠️ ฟีเจอร์ auto-discovery topology จะไม่ทำงาน (แสดง demo topology แทน)

### Python Standard Libraries (ไม่ต้องติดตั้งเพิ่ม — มากับ Python)

| Library | ใช้ทำอะไร | ใช้ในไฟล์ |
|---------|----------|----------|
| `os` | จัดการ file path | `connection_manager.py` |
| `re` | Regular expression matching | `connection_manager.py`, `topology_builder.py`, `network_engine.py` |
| `json` | อ่าน/เขียน JSON (device inventory) | `connection_manager.py`, `topology_builder.py` |
| `subprocess` | รัน ping command | `connection_manager.py` |
| `socket` | Network socket operations | `connection_manager.py` |
| `time` | Delay/sleep สำหรับ serial communication | `connection_manager.py`, `network_engine.py` |
| `threading` | Multi-threading support | `network_engine.py` |
| `platform` | ตรวจสอบ OS (Windows/Linux) สำหรับ ping | `connection_manager.py` |
| `typing` | Type hints (Dict, List, Any, Optional) | ทุกไฟล์ |

### Frontend Libraries (โหลดผ่าน CDN — ไม่ต้องติดตั้ง)

| Library | เวอร์ชัน | วัตถุประสงค์ |
|---------|---------|-------------|
| `vis-network` | 9.1.2 | Interactive topology visualization (ลาก/ซูมได้) |
| `Font Awesome` | 6.4.0 | ไอคอน (router, switch, network icons) |
| `Google Fonts` (Inter) | — | ฟอนต์หลักของ UI |
| `Google Fonts` (Fira Code) | — | ฟอนต์ monospace สำหรับ CLI terminal |

> **หมายเหตุ**: Frontend libraries โหลดจาก CDN อัตโนมัติผ่านอินเทอร์เน็ต ไม่ต้องติดตั้งเพิ่มเติม

---

## วิธีติดตั้งและรัน

### ขั้นตอนที่ 1: Clone หรือดาวน์โหลดโปรเจกต์

```bash
git clone https://github.com/Phalakorn223/Assignment-2-NetPro.git
cd Assignment-2-NetPro
```

### ขั้นตอนที่ 2: ติดตั้ง Dependencies ทั้งหมด (วิธีง่ายสุด)

```bash
pip install -r requirements.txt
```

คำสั่งนี้จะติดตั้ง library ทั้ง 5 ตัวให้อัตโนมัติ:
- `flask>=2.3.0`
- `netmiko>=4.2.0`
- `paramiko>=3.0.0`
- `pyserial>=3.5`
- `networkx>=3.0`

### หรือติดตั้งทีละตัว (ถ้าต้องการ)

```bash
pip install flask
pip install netmiko
pip install paramiko
pip install pyserial
pip install networkx
```

### ขั้นตอนที่ 3: รัน Server

```bash
python app.py
```

### ขั้นตอนที่ 4: เปิด Browser

```
http://127.0.0.1:5000
```

---

## การตรวจสอบว่าติดตั้งครบแล้ว

รันคำสั่งนี้ใน Python เพื่อตรวจสอบ:

```python
python -c "
import flask; print(f'Flask: {flask.__version__}')
import netmiko; print(f'Netmiko: {netmiko.__version__}')
import paramiko; print(f'Paramiko: {paramiko.__version__}')
import serial; print(f'PySerial: {serial.__version__}')
import networkx; print(f'NetworkX: {networkx.__version__}')
print('All libraries installed successfully!')
"
```

ถ้าขึ้น error `ModuleNotFoundError` แสดงว่ายังติดตั้ง library นั้นไม่ครบ

---

## โครงสร้างไฟล์

```
Assignment-2-NetPro/
├── app.py                    # Flask backend (REST API endpoints)
├── connection_manager.py     # Connection pool (SSH/Telnet/Serial), IP validation, ping check
├── command_builder.py        # Pure functions สร้าง Cisco IOS CLI commands
├── command_normalizer.py     # คำสั่งย่อ → คำสั่งเต็ม + autocomplete suggestions
├── topology_builder.py       # networkx graph, CDP/LLDP discovery, topology JSON
├── network_engine.py         # (Legacy — ไม่ถูกใช้แล้ว)
├── devices.json              # ไฟล์เก็บ device inventory
├── requirements.txt          # รายการ dependencies
├── README.md                 # เอกสารนี้
├── .gitignore
├── templates/
│   └── index.html            # Web UI (vis-network topology, forms, CLI)
└── static/
    ├── css/styles.css         # Stylesheet
    └── js/app.js              # Frontend JavaScript
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

## Error Handling (ตาม Spec)
- **IP Validation**: ตรวจ octet ถูก range, loopback, multicast
- **Ping Check**: ทดสอบ reachability ก่อน connect
- **NetmikoTimeoutException**: แสดง error message ที่อ่านง่าย
- **NetmikoAuthenticationException**: แจ้งว่า username/password ผิด
- **IOS Syntax Error**: ตรวจ `% Invalid input detected at` ใน output ทุกครั้ง

---

## Troubleshooting

| ปัญหา | สาเหตุ | วิธีแก้ |
|-------|--------|--------|
| `ModuleNotFoundError: No module named 'flask'` | ยังไม่ได้ติดตั้ง Flask | `pip install flask` |
| `ModuleNotFoundError: No module named 'netmiko'` | ยังไม่ได้ติดตั้ง Netmiko | `pip install netmiko` |
| `ModuleNotFoundError: No module named 'serial'` | ยังไม่ได้ติดตั้ง PySerial | `pip install pyserial` (ไม่ใช่ `pip install serial`) |
| `ModuleNotFoundError: No module named 'networkx'` | ยังไม่ได้ติดตั้ง NetworkX | `pip install networkx` |
| หน้าเว็บ topology ไม่แสดง | ไม่มีอินเทอร์เน็ต (CDN โหลดไม่ได้) | เชื่อมต่ออินเทอร์เน็ตแล้วรีเฟรช |
| SSH connection timeout | อุปกรณ์ offline หรือ IP ผิด | ตรวจสอบ IP และ ping ก่อน |
| Authentication failed | username/password ไม่ถูกต้อง | ตรวจสอบ credentials ที่ใช้เชื่อมต่อ |
| Serial port ไม่เปิด | COM port ไม่ถูกต้องหรือถูกใช้งานอยู่ | ตรวจสอบ COM port ใน Device Manager |
