# Spec: Network Automation Tool with UI (คล้าย Packet Tracer)

> เอกสารนี้สรุปและขยายความจากโจทย์อาจารย์ + เนื้อหาสไลด์ Ch5–Ch8 (Network Automation Part I/II)
> เพื่อใช้เป็น "brief" ให้ AI coding assistant (Claude Code / Cursor / Copilot ฯลฯ) เขียนโปรแกรมต่อได้ทันที
> เขียนด้วยแนวคิด vibe coding: อธิบายทุกฟีเจอร์, ทุก edge case, และให้ pseudocode/ตัวอย่างโค้ดอ้างอิงจากสไลด์จริง

---

## 1. โจทย์โดยสรุป (จากอาจารย์)

เขียนโปรแกรมที่มี **UI** (จะทำเป็น Web app หรือ Desktop app ก็ได้ ภาษาอะไรก็ได้) ทำหน้าที่เหมือน "ตัวช่วยจัดการอุปกรณ์เครือข่าย" โดย:

1. **เชื่อมต่ออุปกรณ์ได้หลายวิธี**
   - EVE-NG / GNS3 (virtual lab) และอุปกรณ์จริง (physical device)
   - ผ่าน **Serial (Console cable)**
   - ผ่าน **SSH**
   - ผ่าน **Telnet**
2. **รับคำสั่งจาก UI แล้ว configure ค่าลงอุปกรณ์ได้จริง** โดยรองรับทั้ง
   - คำสั่งเต็ม (full command) เช่น `interface GigabitEthernet0/0`
   - คำสั่งย่อ (abbreviated command) เช่น `int gi0/0`
3. ต้องทำสิ่งเหล่านี้ได้ผ่าน UI:
   - กำหนด **IP Address** บน interface
   - สั่ง **Up/Down (shutdown / no shutdown)** ของ interface
   - ตั้งค่า **Routing**: RIP, EIGRP, OSPF, BGP, Static Route, Default Static Route
   - รัน **show command** พื้นฐานที่เกี่ยวกับ routing และคำสั่งที่จำเป็นอื่น ๆ (เช่น `show ip route`, `show ip interface brief`, `show running-config`, `show vlan`)
4. **โบนัส (3 คะแนน)**: ระบบ **Auto Discovery**
   - สแกน/ค้นหาอุปกรณ์ที่เชื่อมต่อกันอยู่ แล้วสร้าง **Topology** โดยอัตโนมัติ
   - แสดงผลเป็น **รูปภาพ/แผนภาพ** ของ topology ตามการเชื่อมต่อจริง
   - กดที่อุปกรณ์แต่ละตัวใน topology แล้วดู **พอร์ตทั้งหมด** ของอุปกรณ์นั้นได้ (เชื่อมกับฟีเจอร์ข้อ 1–3 ที่เขียนไว้แล้ว)

---

## 2. บริบทจากสไลด์ (สิ่งที่มีอยู่แล้วให้ต่อยอด)

สไลด์ Ch5–Ch8 สอนการเขียน automation ด้วย 3 แนวทางหลัก ให้ใช้เป็นฐานของ "Connection Layer":

### 2.1 Telnet (module: `telnetlib`)
ใช้กับอุปกรณ์ที่เปิด telnet (`transport input all`, `login local`, `username/password`)

```python
import telnetlib

username = 'cisco'
password = 'cisco'
IP = '192.168.1.116'

tn = telnetlib.Telnet(IP)
tn.read_until(b'Username: ')
tn.write(username.encode('ascii') + b'\n')

if password:
    tn.read_until(b"Password: ")
    tn.write(password.encode('ascii') + b"\n")

tn.write(b"conf t \n")
tn.write(b"int lo 10 \n")
tn.write(b"ip add 10.10.10.10 255.255.255.255 \n")
tn.write(b"end \n")
tn.write(b"exit \n")

print(tn.read_all().decode('ascii'))
```

แนวคิดสำคัญที่ใช้ต่อยอดได้:
- Loop สร้างหลาย VLAN (`for n in range(2,10): tn.write(b"vlan " + str(n)...)`)
- Loop ไล่หลาย IP จาก range (`for n in range(117,120): IP = "192.168.1." + str(n)`)
- อ่านรายการอุปกรณ์จากไฟล์ (`myswitches`) แล้ว loop เชื่อมต่อทีละตัว
- อ่านชุดคำสั่งจากไฟล์ (`swconfig`) แล้ว `f.read().splitlines()` ส่งเข้า `send_config_set()`

### 2.2 Paramiko (raw SSH)
ใช้ตอนต้องการ interactive shell ตรง ๆ ผ่าน SSH โดยไม่มี abstraction ของ netmiko

```python
import paramiko, time

HOST = '192.168.1.122'
user = 'cisco'
password = 'cisco'

ssh_client = paramiko.SSHClient()
ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh_client.connect(hostname=HOST, username=user, password=password,
                    allow_agent=False, look_for_keys=False)

remote_connection = ssh_client.invoke_shell()
remote_connection.send("en\n")
remote_connection.send("sh ip int brief\n")
time.sleep(1)

output = remote_connection.recv(65535)
print(output.decode('ascii'))

ssh_client.close()
```

Application ตัวเต็ม (thread1.py ใน Ch6) มีโครงสร้างที่ดีมาก ควรใช้เป็นต้นแบบของ **input validation layer**:
- `ip_is_valid()` — เช็คไฟล์ IP list, validate octet (1–223, ไม่ใช่ 127, ไม่ใช่ loopback/multicast range)
- ping ping reachability check ก่อนต่อจริง (`subprocess.call(["ping","-n","-c","2","-W","1", ip])`)
- `user_is_valid()` — validate ว่าไฟล์ username/password มีจริง (`os.path.isfile()`)
- `cmd_is_valid()` — validate ไฟล์คำสั่งมีจริง
- `open_ssh_conn(ip)` — เปิด SSH, อ่าน user/pass จากไฟล์ (`.split(',')`), ส่งคำสั่งทีละบรรทัดจากไฟล์ cmd, ใช้ `re.search(r"% Invalid input detected at", output)` เพื่อตรวจว่ามี syntax error จาก IOS หรือไม่
- `create_threads()` —ใช้ `threading.Thread(target=open_ssh_conn, args=(ip,))` ยิงหลายอุปกรณ์พร้อมกัน แล้ว `th.join()` รอให้เสร็จทุก thread

### 2.3 Netmiko (SSH abstraction — แนะนำให้เป็นแกนหลักของโปรเจกต์)
Netmiko ห่อ paramiko ให้ใช้ง่ายขึ้นมาก เหมาะเป็น connection layer หลักของโปรแกรมนี้

```python
from netmiko import ConnectHandler

device = {
    'device_type': 'cisco_ios',
    'ip': '192.168.1.120',
    'username': 'cisco',
    'password': 'cisco',
}

net_connect = ConnectHandler(**device)

output = net_connect.send_command('show ip int brief')
print(output)

config_commands = ['int loop 0', 'ip address 1.1.1.1 255.255.255.0']
output = net_connect.send_config_set(config_commands)
print(output)
```

- `send_command()` → ใช้กับ **show command**
- `send_config_set()` → ใช้กับ **configuration command** (เข้า config mode อัตโนมัติ ออกอัตโนมัติ)
- รองรับหลายอุปกรณ์พร้อมกันด้วย list `all_devices = [SW4, SW5]` แล้ว loop
- อ่านชุด config จากไฟล์ทั้งก้อนแล้วส่งเข้า `send_config_set(lines)` ได้เลย (ตัวอย่าง trunk config: `switchport trunk encapsulation dot1q`, `switchport mode trunk`, `switchport trunk allowed vlan 1,2`)

### 2.4 Multithreading (module: `threading` + `queue.Queue`)
ใช้ SSH เข้าอุปกรณ์หลายตัว **พร้อมกัน** (ไม่ใช่ทีละตัวเรียงลำดับแบบเดิม)

```python
import threading
from queue import Queue
from netmiko import ConnectHandler

def ssh_session(router, output_q):
    output_dict = {}
    hostname = router
    device = {'device_type': 'cisco_ios', 'ip': router,
              'username': USER, 'password': PASSWORD, 'verbose': False}
    conn = ConnectHandler(**device)
    output = conn.send_command("show version")
    output_dict[hostname] = output
    output_q.put(output_dict)

output_q = Queue()
for router in routers:
    t = threading.Thread(target=ssh_session, args=(router, output_q))
    t.start()

for t in threading.enumerate():
    if t != threading.currentThread():
        t.join()

while not output_q.empty():
    my_dict = output_q.get()
    for k, v in my_dict.items():
        print(k, v)
```

**สรุป**: โปรเจกต์นี้ควรออกแบบ "Connection Layer" ให้เลือกได้ระหว่าง `telnetlib` / `paramiko` / `netmiko` / (เพิ่มใหม่) `pyserial` โดยแนะนำใช้ **netmiko เป็น driver หลัก** สำหรับ SSH/Telnet เพราะรองรับทั้งสอง protocol ในตัว (`device_type: cisco_ios` ใช้ SSH, `device_type: cisco_ios_telnet` ใช้ telnet) และมี `send_config_set()` / `send_command()` พร้อมใช้

---

## 3. Scope ของฟีเจอร์ทั้งหมด (แปลจากโจทย์เป็น requirement ที่ implement ได้)

### 3.1 Connection Management
- [ ] เพิ่ม/แก้ไข/ลบอุปกรณ์ใน inventory (host, name, connection type, IP หรือ COM port, username, password, enable secret, device_type)
- [ ] เลือกวิธีเชื่อมต่อได้ 3 แบบ:
  - **Serial**: ผ่าน USB-to-Serial/Console cable → ใช้ library `pyserial` (พอร์ต COMx บน Windows หรือ `/dev/ttyUSBx` บน Linux/Mac) — netmiko รองรับ serial ผ่าน `device_type` เช่น `cisco_ios_serial` ด้วย (พารามิเตอร์ `serial_settings`)
  - **SSH**: netmiko `device_type='cisco_ios'` (ต้อง SSH key-gen, username/password ตามสไลด์ Ch6)
  - **Telnet**: netmiko `device_type='cisco_ios_telnet'` (ตามสไลด์ Ch5)
- [ ] Test connection button — เช็คว่า connect ได้จริงก่อนบันทึก
- [ ] เก็บ session ที่ connect ค้างไว้ (connection pool) เพื่อให้กดคำสั่งซ้ำได้เร็วโดยไม่ต้อง reconnect ทุกครั้ง
- [ ] Reconnect / disconnect ต่ออุปกรณ์แต่ละตัวได้อิสระ
- [ ] รองรับหลายอุปกรณ์พร้อมกัน (เก็บ connection เป็น dict `{device_id: net_connect}`)

### 3.2 Command Input (เต็ม + ย่อ)
โจทย์บอกว่าโปรแกรมต้อง "รับคำสั่ง (ทั้งแบบเต็มและคำสั่งย่อ)" — Cisco IOS เองรองรับคำสั่งย่อ (partial command) อยู่แล้วถ้ามันไม่ ambiguous เช่น
`int` = `interface`, `conf t` = `configure terminal`, `sh ip int br` = `show ip interface brief`, `no shut` = `no shutdown`

**สิ่งที่ต้องทำในโปรแกรม:**
- **วิธีที่ง่ายที่สุด (แนะนำ)**: ส่งคำสั่งดิบที่ผู้ใช้พิมพ์ตรง ๆ ไปให้ router ผ่าน `send_command()` / `send_config_set()` — เพราะ IOS แปลคำสั่งย่อเองอยู่แล้ว ไม่ต้อง parse เอง 100%
- **แต่ต้องมี UI-level command builder** สำหรับฟีเจอร์ที่ระบุไว้ชัดเจน (ข้อ 3.3–3.5) เพื่อให้ผู้ใช้ "กดปุ่ม" หรือ "กรอกฟอร์ม" แทนการพิมพ์ CLI ดิบทั้งหมด แล้วโปรแกรม generate คำสั่ง Cisco ให้เอง (นี่คือหัวใจของการทำ "เหมือน Packet Tracer")
- ควรมี normalization layer เล็ก ๆ (mapping table) เผื่อกรณีอยากรองรับ syntax ของผู้ใช้เอง (เช่น พิมพ์ `ip addr` แทน `ip address`) — ตัวอย่าง mapping:

| Full command | คำสั่งย่อที่ควรรองรับ |
|---|---|
| `interface` | `int`, `inte`, `interf` |
| `configure terminal` | `conf t`, `config t`, `conf term` |
| `no shutdown` | `no shut`, `no sh` |
| `shutdown` | `shut`, `sh` (ระวังชนกับ `show`) |
| `ip address` | `ip add`, `ip addr` |
| `show running-config` | `sh run`, `show run` |
| `show ip interface brief` | `sh ip int br`, `show ip int brief` |
| `router ospf` | `router osp` |
| `end` | `en` (ระวังชนกับ `enable`) |

> หมายเหตุ: เนื่องจากอุปกรณ์ปลายทาง (Cisco IOS) เข้าใจคำสั่งย่ออยู่แล้ว วิธีที่ robust ที่สุดคือ **ส่งคำสั่งตรง ๆ ให้ device แปลเอง** แล้วโปรแกรมแค่ตรวจ error message กลับมา (`% Invalid input detected at` ตามที่สไลด์ Ch6 สอนไว้) แทนที่จะพยายาม parse คำสั่งย่อเองทั้งหมด — แต่ยังต้องมี local mapping/autocomplete เพื่อ UX ที่ดีใน UI (เช่น dropdown แนะนำคำสั่ง)

### 3.3 Interface Configuration
ฟีเจอร์ที่ต้องมีใน UI (ฟอร์ม/ปุ่ม):
- เลือก device → เลือก interface (ดึงรายชื่อ interface จาก `show ip interface brief` หรือ `show interfaces status`)
- กำหนด IP Address + Subnet mask → generate:
  ```
  configure terminal
  interface <ชื่อ interface>
  ip address <ip> <mask>
  no shutdown
  end
  ```
- Toggle Up/Down (shutdown / no shutdown):
  ```
  configure terminal
  interface <ชื่อ interface>
  shutdown        (หรือ no shutdown)
  end
  ```
- Description ของ interface (option เสริม, ใช้ตอนแสดง topology ให้อ่านง่าย): `description <text>`

### 3.4 Routing Configuration
ต้องมีฟอร์มสำหรับแต่ละ protocol โดย generate CLI ให้อัตโนมัติ:

**Static Route**
```
ip route <destination-network> <subnet-mask> <next-hop หรือ exit-interface>
```

**Default Static Route**
```
ip route 0.0.0.0 0.0.0.0 <next-hop>
```

**RIP**
```
router rip
version 2
network <network-address>
no auto-summary
```

**EIGRP**
```
router eigrp <AS-number>
network <network-address> [wildcard-mask]
no auto-summary
```

**OSPF**
```
router ospf <process-id>
network <network-address> <wildcard-mask> area <area-id>
```

**BGP**
```
router bgp <AS-number>
neighbor <neighbor-ip> remote-as <remote-AS>
network <network-address> mask <subnet-mask>
```

UI ควรมีฟอร์มแยกตาม protocol (dropdown เลือก protocol → form fields เปลี่ยนตาม) แล้ว preview คำสั่งที่จะส่งก่อนกด "Apply" (เพื่อความปลอดภัยและ debug ง่าย)

### 3.5 Show Commands (จำเป็นสำหรับ routing + ทั่วไป)
ควรมีปุ่ม/dropdown สำเร็จรูปสำหรับคำสั่งที่ใช้บ่อย แล้วโชว์ output แบบ terminal-style ใน UI:

| หมวด | คำสั่ง |
|---|---|
| ทั่วไป | `show running-config`, `show version`, `show ip interface brief`, `show interfaces status`, `show vlan` |
| Routing | `show ip route`, `show ip protocols`, `show ip route static` |
| RIP | `show ip rip database` |
| EIGRP | `show ip eigrp neighbors`, `show ip eigrp topology` |
| OSPF | `show ip ospf neighbor`, `show ip ospf database`, `show ip ospf interface brief` |
| BGP | `show ip bgp summary`, `show ip bgp neighbors` |

รวมถึงมี **Free-form terminal box** ให้พิมพ์คำสั่งอะไรก็ได้ (raw command) ส่งตรงไป device แล้วเห็นผลกลับมาแบบ real console

### 3.6 (โบนัส) Auto Discovery + Topology Visualization
แนวทางที่ทำได้จริงโดยไม่ต้องพึ่ง protocol พิเศษ (CDP/LLDP อาจไม่เปิดใน lab ทุกที่):

**วิธีที่ 1 — ใช้ CDP/LLDP (แม่นยำที่สุดถ้าอุปกรณ์รองรับ)**
```
show cdp neighbors detail
show lldp neighbors detail
```
- Parse output (ใช้ [TextFSM](https://github.com/networktocode/ntc-templates) หรือ netmiko `use_textfsm=True` เพื่อ parse เป็น structured data ทันที — netmiko มี built-in TextFSM templates สำหรับคำสั่งนี้อยู่แล้ว)
- ได้ข้อมูล: local device, local port, remote device, remote port, remote IP
- นำมาสร้าง graph (node = device, edge = การเชื่อมต่อระหว่าง port)

**วิธีที่ 2 — Manual/Config-based discovery (fallback เมื่อไม่มี CDP/LLDP)**
- ดึง IP ของทุกอุปกรณ์ที่ผู้ใช้เพิ่มเข้ามาใน inventory
- Ping sweep + ARP table (`show arp`) เพื่อเดา subnet ที่เชื่อมกัน
- ใช้ interface + subnet matching: ถ้า 2 อุปกรณ์มี interface ที่ IP อยู่ subnet เดียวกัน → ถือว่ามีสาย connect กัน

**การแสดงผล Topology**
- แนะนำ: **Web-based UI** ใช้ library กราฟ interactive เช่น `vis-network`, `cytoscape.js`, หรือ `react-flow` (ฝั่ง frontend) — วาด node เป็นไอคอน router/switch, edge เป็นเส้นเชื่อม
- กด node แต่ละอันแล้ว popup/side panel แสดง:
  - รายชื่อ interface ทั้งหมด + สถานะ (up/down, IP)
  - ปุ่มลัดไปหน้า configuration ของอุปกรณ์นั้น (เชื่อมกลับไปฟีเจอร์ข้อ 3.1–3.5)
- Backend ส่ง JSON graph structure ให้ frontend เช่น:
  ```json
  {
    "nodes": [
      {"id": "R1", "type": "router", "ip": "192.168.1.122"},
      {"id": "SW1", "type": "switch", "ip": "192.168.1.117"}
    ],
    "edges": [
      {"from": "R1", "to": "SW1", "from_port": "Gi0/0", "to_port": "Gi0/1"}
    ]
  }
  ```

---

## 4. สถาปัตยกรรมที่แนะนำ

```
                ┌──────────────────────────┐
                │        Frontend (UI)      │
                │  Web: React/Vue + REST/WS │
                │  หรือ Desktop: Electron/   │
                │  PyQt/Tkinter             │
                └────────────┬───────────────┘
                             │ REST API / WebSocket
                ┌────────────▼───────────────┐
                │        Backend (API)        │
                │  Python: FastAPI / Flask    │
                └────────────┬───────────────┘
                             │
        ┌────────────────────┼─────────────────────┐
        │                    │                      │
┌───────▼───────┐   ┌────────▼────────┐   ┌─────────▼─────────┐
│ Connection Mgr │   │ Command Builder  │   │ Discovery Engine  │
│ (netmiko pool, │   │ (interface, IP,  │   │ (CDP/LLDP parse,  │
│  serial, ssh,  │   │  routing forms → │   │  build graph)     │
│  telnet)       │   │  CLI commands)   │   │                   │
└───────┬───────┘   └────────┬────────┘   └─────────┬─────────┘
        │                    │                       │
        └────────────────────┴───────────────────────┘
                             │
                    ┌────────▼─────────┐
                    │ Network Devices   │
                    │ (EVE-NG / Real)   │
                    │ SSH / Telnet /    │
                    │ Serial            │
                    └───────────────────┘
```

### เทคโนโลยีที่แนะนำ (เลือกอย่างใดอย่างหนึ่งตามความถนัด)

**แนวทาง A: Python full-stack (แนะนำ เพราะสไลด์ทั้งหมดเป็น python)**
- Backend: **FastAPI** (async, มี WebSocket ในตัว, เหมาะกับ real-time terminal output)
- Connection: **netmiko** (SSH/Telnet), **pyserial** (Serial console)
- Discovery: netmiko `use_textfsm=True` + `ntc-templates`, หรือ `networkx` สำหรับสร้าง/จัดการ graph
- Frontend: React + `react-flow` หรือ `vis-network` สำหรับวาด topology, xterm.js สำหรับจำลอง terminal
- Realtime output: WebSocket ระหว่าง backend↔frontend (เพราะ config/show command บางอันใช้เวลา)

**แนวทาง B: Desktop app เดียวจบ (ง่ายกว่าสำหรับ deploy/demo ในห้อง lab)**
- Python + **PyQt5/PySide6** หรือ **Tkinter** (ธรรมดากว่า) เป็น GUI
- netmiko + pyserial เหมือนเดิม
- Topology วาดด้วย `networkx` + `matplotlib` (แสดงเป็นรูปภาพ static) หรือฝัง `Graphviz`
- ข้อเสีย: การทำ interactive click-to-view-port จะยากกว่าเว็บเล็กน้อย แต่ทำได้ด้วย PyQt event

---

## 5. โครงสร้างโปรเจกต์ที่แนะนำ (แนวทาง A: Python + FastAPI + React)

```
network-automation-ui/
├── backend/
│   ├── main.py                  # FastAPI app entrypoint
│   ├── devices/
│   │   ├── inventory.py         # CRUD ของ device list (JSON/SQLite)
│   │   └── models.py            # Pydantic models: Device, Interface, RouteConfig
│   ├── connection/
│   │   ├── connection_manager.py # pool ของ netmiko session ที่เปิดค้างไว้
│   │   ├── ssh_driver.py
│   │   ├── telnet_driver.py
│   │   └── serial_driver.py
│   ├── commands/
│   │   ├── command_builder.py    # generate CLI จาก form data
│   │   └── command_normalizer.py # mapping คำสั่งย่อ <-> เต็ม (สำหรับ UI autocomplete)
│   ├── discovery/
│   │   ├── cdp_lldp_parser.py
│   │   └── topology_builder.py   # ใช้ networkx สร้าง graph → export JSON
│   └── api/
│       ├── routes_devices.py
│       ├── routes_commands.py
│       ├── routes_routing.py
│       └── routes_topology.py
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── DeviceList.jsx
│   │   │   ├── TerminalPanel.jsx     # ใช้ xterm.js
│   │   │   ├── InterfaceForm.jsx
│   │   │   ├── RoutingForm.jsx
│   │   │   └── TopologyView.jsx      # ใช้ react-flow / vis-network
│   │   └── App.jsx
├── requirements.txt
└── README.md
```

---

## 6. รายละเอียด Implementation ที่สำคัญ (ทีละโมดูล)

### 6.1 `connection_manager.py` — จัดการ session
```python
from netmiko import ConnectHandler

class ConnectionManager:
    def __init__(self):
        self.pool = {}  # device_id -> netmiko connection object

    def connect(self, device_id: str, device_params: dict):
        """
        device_params ตัวอย่าง:
        {
            'device_type': 'cisco_ios',        # หรือ 'cisco_ios_telnet'
            'ip': '192.168.1.120',
            'username': 'cisco',
            'password': 'cisco',
            'secret': 'cisco',                 # enable secret
        }
        """
        if device_id in self.pool:
            return self.pool[device_id]
        conn = ConnectHandler(**device_params)
        conn.enable()
        self.pool[device_id] = conn
        return conn

    def send_command(self, device_id: str, command: str):
        conn = self.pool[device_id]
        return conn.send_command(command, use_textfsm=True)

    def send_config(self, device_id: str, commands: list[str]):
        conn = self.pool[device_id]
        return conn.send_config_set(commands)

    def disconnect(self, device_id: str):
        if device_id in self.pool:
            self.pool[device_id].disconnect()
            del self.pool[device_id]
```

> สำหรับ Serial: netmiko รองรับผ่าน `device_type: 'cisco_ios_serial'` และต้องส่ง `serial_settings={'port': 'COM3', 'baudrate': 9600}` แทน `ip` — หรือถ้าอยากคุมเองเต็มที่ใช้ `pyserial` ตรง ๆ (`serial.Serial(port, baudrate=9600, timeout=1)`) แล้วเขียน read/write loop คล้ายแบบ telnetlib ในสไลด์

### 6.2 `command_builder.py` — แปลง form → CLI
```python
def build_ip_address_commands(interface: str, ip: str, mask: str) -> list[str]:
    return [
        f"interface {interface}",
        f"ip address {ip} {mask}",
        "no shutdown",
    ]

def build_interface_state_commands(interface: str, up: bool) -> list[str]:
    return [
        f"interface {interface}",
        "no shutdown" if up else "shutdown",
    ]

def build_static_route(dest_network: str, mask: str, next_hop: str) -> list[str]:
    return [f"ip route {dest_network} {mask} {next_hop}"]

def build_default_route(next_hop: str) -> list[str]:
    return [f"ip route 0.0.0.0 0.0.0.0 {next_hop}"]

def build_rip(networks: list[str]) -> list[str]:
    cmds = ["router rip", "version 2"]
    cmds += [f"network {n}" for n in networks]
    cmds.append("no auto-summary")
    return cmds

def build_eigrp(as_number: int, networks: list[str]) -> list[str]:
    cmds = [f"router eigrp {as_number}"]
    cmds += [f"network {n}" for n in networks]
    cmds.append("no auto-summary")
    return cmds

def build_ospf(process_id: int, network_area_pairs: list[tuple]) -> list[str]:
    cmds = [f"router ospf {process_id}"]
    for network, wildcard, area in network_area_pairs:
        cmds.append(f"network {network} {wildcard} area {area}")
    return cmds

def build_bgp(as_number: int, neighbors: list[tuple], networks: list[tuple]) -> list[str]:
    cmds = [f"router bgp {as_number}"]
    for neighbor_ip, remote_as in neighbors:
        cmds.append(f"neighbor {neighbor_ip} remote-as {remote_as}")
    for network, mask in networks:
        cmds.append(f"network {network} mask {mask}")
    return cmds
```

### 6.3 `command_normalizer.py` — รองรับคำสั่งย่อฝั่ง UI (เสริม UX)
```python
COMMAND_ALIASES = {
    "int": "interface",
    "conf t": "configure terminal",
    "conf term": "configure terminal",
    "no shut": "no shutdown",
    "sh run": "show running-config",
    "sh ip int br": "show ip interface brief",
    "sh ip route": "show ip route",
    "router osp": "router ospf",
}

def normalize(raw_command: str) -> str:
    key = raw_command.strip().lower()
    return COMMAND_ALIASES.get(key, raw_command)
```
> ใช้เฉพาะตอน "auto-complete/suggestion" ใน UI เท่านั้น เวลาส่งจริงให้ส่งคำสั่งดิบที่ผู้ใช้ยืนยันแล้วไปตรง ๆ เพราะ IOS parse คำสั่งย่อได้เองอยู่แล้ว (กันความเสี่ยง mapping ผิดพลาดเอง)

### 6.4 `cdp_lldp_parser.py` + `topology_builder.py`
```python
import networkx as nx

def discover_neighbors(conn_manager, device_id):
    """ใช้ netmiko use_textfsm=True เพื่อ parse show cdp neighbors detail เป็น list of dict"""
    result = conn_manager.send_command(device_id, "show cdp neighbors detail")
    # result เป็น list of dict เช่น
    # [{'destination_host': 'SW1', 'local_port': 'Gi0/0', 'remote_port': 'Gi0/1', ...}]
    return result

def build_topology_graph(devices: list[str], conn_manager) -> nx.Graph:
    G = nx.Graph()
    for device_id in devices:
        G.add_node(device_id)
        neighbors = discover_neighbors(conn_manager, device_id)
        for n in neighbors:
            remote = n.get('destination_host')
            if remote:
                G.add_edge(device_id, remote,
                           local_port=n.get('local_port'),
                           remote_port=n.get('remote_port'))
    return G

def graph_to_json(G: nx.Graph) -> dict:
    nodes = [{"id": n} for n in G.nodes()]
    edges = [
        {"from": u, "to": v, "from_port": d.get("local_port"), "to_port": d.get("remote_port")}
        for u, v, d in G.edges(data=True)
    ]
    return {"nodes": nodes, "edges": edges}
```

---

## 7. Flow การทำงานของ UI (User Journey)

1. ผู้ใช้เปิดโปรแกรม → หน้า **Device Inventory** → กด "Add Device" กรอก IP/Serial port, เลือก connection type (SSH/Telnet/Serial), username/password
2. กด "Connect" → backend เรียก `ConnectionManager.connect()` → แสดงสถานะ Connected/Failed
3. เข้าหน้า **Device Detail**:
   - Tab "Interface" → ฟอร์มตั้ง IP + Up/Down (ปุ่ม toggle)
   - Tab "Routing" → เลือก protocol (RIP/EIGRP/OSPF/BGP/Static) → กรอกฟอร์ม → preview คำสั่งก่อนกด Apply
   - Tab "Show Commands" → ปุ่มลัด + free-form terminal (แสดงผลแบบ real-time ผ่าน WebSocket)
4. (โบนัส) เข้าหน้า **Topology** → กดปุ่ม "Discover" → backend รัน CDP/LLDP scan ทุกอุปกรณ์ที่ connect ไว้ → วาด graph ขึ้นจอ → คลิก node ดู port ทั้งหมด → ลิงก์กลับไปหน้า Device Detail ของอุปกรณ์นั้น

---

## 8. Error Handling ที่ต้องมี (อ้างอิงแนวคิดจากสไลด์ Ch6 thread1.py)

- ตรวจ **IP format** ก่อนเชื่อมต่อ (octet 0–255, ไม่ใช่ 127.x, ไม่ใช่ multicast)
- ตรวจ **reachability** ด้วย ping ก่อน SSH/Telnet จริง (`subprocess` หรือ platform-native ping)
- จับ `NetmikoTimeoutException`, `NetmikoAuthenticationException` แล้วแสดง error message ที่อ่านง่ายใน UI
- หลังส่งคำสั่ง configure ทุกครั้ง ตรวจ output ว่ามี `% Invalid input detected at` หรือไม่ (ตามสไลด์ Ch6) แล้วแจ้งเตือนผู้ใช้ทันทีว่าอาจพิมพ์คำสั่งผิด/version IOS ไม่รองรับ
- SSH key generation: เตือนผู้ใช้ว่าต้อง config `ip domain-name`, `crypto key generate rsa` (1024 bit) บน router ก่อนถึงจะ SSH ได้ (ตามสไลด์ Ch6/Ch5 ข้อ 20)

---

## 9. แผนการพัฒนา (Task Breakdown แนะนำ ทำเป็นขั้น ๆ)

1. **Milestone 1 — Core connection**: ต่อ SSH/Telnet ผ่าน netmiko ได้ 1 อุปกรณ์, ส่ง `show ip int brief` แล้วโชว์ผลบน UI ธรรมดา (ยังไม่ต้องสวย)
2. **Milestone 2 — Multi-device + Serial**: เพิ่ม inventory หลายอุปกรณ์, เพิ่ม serial driver, ทำ connection pool
3. **Milestone 3 — Interface & Routing forms**: ทำฟอร์ม IP/Up-Down + Static/RIP/EIGRP/OSPF/BGP ตาม command_builder ด้านบน พร้อม preview ก่อนส่ง
4. **Milestone 4 — Terminal UI**: ทำ terminal panel (xterm.js) รองรับ raw command + คำสั่งย่อ, WebSocket real-time
5. **Milestone 5 (โบนัส) — Discovery + Topology**: ทำ CDP/LLDP parser, สร้าง graph, วาด topology แบบคลิกได้

---

## 10. Reference

- สไลด์ต้นฉบับ: Ch5 Network Automation Part I, Ch6 Network Automation Part II (telnetlib, paramiko, netmiko, threading)
- Netmiko docs: https://pynet.twb-tech.com/blog/automation/netmiko.html (อ้างอิงในสไลด์ Ch6)
- Netmiko GitHub: `ktbyers/netmiko`
- ntc-templates (TextFSM สำหรับ parse show command): `networktocode/ntc-templates`
- NetworkX (จัดการ graph/topology): `networkx.org`
