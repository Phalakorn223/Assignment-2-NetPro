# Spec v2 — Network Automation UI: Update, Bug Fix & UX Overhaul

> เอกสารนี้เป็น **ส่วนขยาย/อัปเดต** ของ `network-automation-ui-spec.md` (v1)
> รวบรวม requirement ใหม่, คำถามที่ต้องตัดสินใจ, และ feedback จากการทดสอบระบบจริง (bug + UX)
> ให้ใช้คู่กับไฟล์ v1 เดิม — ส่วนไหนขัดแย้งกับ v1 ให้ยึด v2 นี้เป็นหลัก

---

## ส่วนที่ 1: Requirement เพิ่มเติมด้าน Routing Protocol

### 1.1 RIP ต้องรองรับทั้ง Version 1 และ Version 2

**ปัญหาของ v1**: spec เดิม hardcode `version 2` ไว้ใน `build_rip()` — ต้องแก้ให้เลือกได้

**CLI ที่ต้องรองรับ**
```
router rip
version 1        ! หรือ version 2 (ถ้าไม่ระบุ RIP จะใช้ v1 แบบ classful เป็น default)
network <network-address>
no auto-summary  ! ใช้เฉพาะกรณี v2 เท่านั้น (v1 ไม่รองรับคำสั่งนี้ ไม่ควร generate ให้)
```

**สิ่งที่ต้องแก้ใน `command_builder.py`**
```python
def build_rip(networks: list[str], version: int = 2) -> list[str]:
    """
    version: 1 หรือ 2
    RIP v1 = classful, ไม่รองรับ VLSM/CIDR, ไม่มี no auto-summary
    RIP v2 = classless, รองรับ VLSM, ควรปิด auto-summary เสมอ
    """
    cmds = ["router rip"]
    cmds.append(f"version {version}")
    cmds += [f"network {n}" for n in networks]
    if version == 2:
        cmds.append("no auto-summary")
    return cmds
```

**UI**: เพิ่ม radio button/dropdown "RIP Version: [1] [2]" ในฟอร์ม RIP — ควรมี tooltip อธิบายสั้น ๆ ว่า v1 ไม่รองรับ subnet ที่ไม่ต่อเนื่อง (discontiguous) และไม่รองรับ VLSM เพื่อกันผู้ใช้สับสนตอน routing ไม่ทำงาน

---

### 1.2 Redistribute + Default-Information Originate (สำคัญมาก — ต้องมีทุก protocol)

โจทย์ต้องการให้ routing protocol "คุยกัน" ข้าม protocol ได้ (เช่น OSPF คุยกับ EIGRP, หรือ static route คุยกับ OSPF) ต้องเพิ่ม 2 ความสามารถหลัก:

#### (A) Redistribute — แปลง route จาก protocol/แหล่งหนึ่งเข้าไปประกาศใน protocol อื่น

**Syntax ทั่วไป**: `redistribute <source-protocol> [metric <value>] [subnets] [route-map <name>]`

| ปลายทาง (อยู่ใน `router ...` ของ) | คำสั่ง redistribute ที่ต้องรองรับ |
|---|---|
| **RIP** | `redistribute static`<br>`redistribute connected`<br>`redistribute ospf <process-id> metric <value>`<br>`redistribute eigrp <as> metric <value>` |
| **EIGRP** | `redistribute static`<br>`redistribute connected`<br>`redistribute rip metric <bw> <delay> <reliability> <load> <mtu>`<br>`redistribute ospf <process-id> metric <bw> <delay> <reliability> <load> <mtu>` |
| **OSPF** | `redistribute static subnets`<br>`redistribute connected subnets`<br>`redistribute rip subnets metric <value> metric-type <1|2>`<br>`redistribute eigrp <as> subnets metric <value> metric-type <1|2>` |
| **BGP** | `redistribute static`<br>`redistribute connected`<br>`redistribute ospf <process-id>`<br>`redistribute eigrp <as>` |

> หมายเหตุสำคัญที่ต้องใส่เป็นคำเตือนใน UI:
> - **OSPF ต้องมี `subnets`** ต่อท้ายเกือบทุกครั้ง ไม่งั้นจะ redistribute เฉพาะ classful network เท่านั้น (ผู้ใช้มือใหม่มักลืม)
> - **EIGRP ต้องระบุ metric แบบเต็ม 5 ค่า** (bandwidth, delay, reliability, load, MTU) ไม่งั้น IOS จะถามซ้ำ/error — ค่าที่ใช้กันบ่อยเป็น default: `redistribute rip metric 10000 100 255 1 1500`
> - **RIP redistribute จาก OSPF/EIGRP ต้องระบุ metric** เพราะ RIP ใช้ hop count ไม่รู้จัก metric ของ protocol อื่น (ถ้าไม่ใส่จะ redistribute ไม่ติด)

#### (B) Default-Information Originate — ประกาศ default route เข้า dynamic routing protocol

```
! OSPF
router ospf <process-id>
default-information originate [always]

! EIGRP (ไม่มีคำสั่งนี้ตรง ๆ — ใช้ redistribute static แทนสำหรับ default route หรือใช้ ip default-network)
ip default-network <network>

! RIP
router rip
default-information originate

! BGP
router bgp <as>
network 0.0.0.0 mask 0.0.0.0   ! ต้องมี default route อยู่ใน routing table ก่อน (ผ่าน ip route 0.0.0.0 0.0.0.0 ...)
```

**สิ่งที่ต้องเพิ่มใน `command_builder.py`**
```python
def build_redistribute(protocol: str, source: str, **kwargs) -> list[str]:
    """
    protocol: "rip" | "eigrp" | "ospf" | "bgp"  (protocol ปลายทางที่กำลัง config)
    source:   "static" | "connected" | "rip" | "eigrp" | "ospf" | "bgp"
    kwargs อาจมี: as_number, process_id, metric, metric_bw, metric_delay,
                  metric_reliability, metric_load, metric_mtu, metric_type, subnets(bool)
    """
    line = f"redistribute {source}"

    if source in ("ospf", "eigrp") and source != protocol:
        # ต้องระบุ process-id (ospf) หรือ as-number (eigrp) ของฝั่ง source
        if source == "ospf":
            line += f" {kwargs.get('process_id')}"
        else:
            line += f" {kwargs.get('as_number')}"

    if protocol == "eigrp":
        bw = kwargs.get("metric_bw", 10000)
        delay = kwargs.get("metric_delay", 100)
        rel = kwargs.get("metric_reliability", 255)
        load = kwargs.get("metric_load", 1)
        mtu = kwargs.get("metric_mtu", 1500)
        line += f" metric {bw} {delay} {rel} {load} {mtu}"

    if protocol == "ospf":
        if kwargs.get("subnets", True):
            line += " subnets"
        if kwargs.get("metric"):
            line += f" metric {kwargs['metric']}"
        if kwargs.get("metric_type"):
            line += f" metric-type {kwargs['metric_type']}"

    if protocol == "rip" and kwargs.get("metric"):
        line += f" metric {kwargs['metric']}"

    return [line]


def build_default_information_originate(protocol: str, always: bool = False) -> list[str]:
    if protocol == "ospf":
        return ["default-information originate" + (" always" if always else "")]
    if protocol == "rip":
        return ["default-information originate"]
    if protocol == "eigrp":
        # EIGRP ไม่มี default-information originate ตรง ๆ — แนะนำใน UI ให้ใช้ ip default-network แทน
        raise ValueError("EIGRP ไม่มีคำสั่งนี้โดยตรง ให้ใช้ ip default-network หรือ redistribute static")
    if protocol == "bgp":
        return ["network 0.0.0.0 mask 0.0.0.0"]
    raise ValueError(f"ไม่รู้จัก protocol: {protocol}")
```

**UI**: ในหน้าฟอร์ม Routing ของแต่ละ protocol ต้องมี section เพิ่มเติมชื่อ **"Redistribution"** แยกจากฟอร์มหลัก (network statement) โดย:
- Checkbox/multi-select เลือก source ที่จะ redistribute เข้ามา (Static / Connected / RIP / EIGRP / OSPF / BGP — เอาตัวเองออกจาก list)
- Field กรอก metric ที่ relevant ตาม protocol ปลายทาง (form field เปลี่ยนตาม protocol ที่เลือกแบบ dynamic)
- Checkbox แยก "Originate Default Route" (+ checkbox ย่อย "always" สำหรับ OSPF)
- ปุ่ม Preview command ก่อน Apply เหมือนฟอร์มอื่น ๆ

---

## ส่วนที่ 2: UX Flow ของการกำหนด Interface Up/Down

โจทย์ระบุ flow ชัดเจนว่าต้องทำเป็น 2 ขั้นตอน (ไม่ใช่แค่ toggle เดียวจบ):

```
Step 1: เลือกขาที่ต้องการ (เลือก interface จาก list ของ device นั้น)
        → dropdown หรือ list ของ interface ทั้งหมด พร้อมแสดงสถานะปัจจุบัน (Up/Down + IP ถ้ามี)

Step 2: กดปุ่มให้เป็น Up หรือ Down
        → ปุ่มสองปุ่มแยกกันชัดเจน [Up] [Down] (หรือ toggle switch ที่มี state ชัดเจน)
        → หลังกด ต้องส่งคำสั่งจริงและ refresh สถานะ (re-run `show ip interface brief` เพื่อ confirm)
```

**Backend flow**
```python
@router.post("/devices/{device_id}/interfaces/{interface_name}/state")
def set_interface_state(device_id: str, interface_name: str, state: Literal["up", "down"]):
    commands = build_interface_state_commands(interface_name, up=(state == "up"))
    output = conn_manager.send_config(device_id, commands)
    # verify: ดึงสถานะจริงกลับมาเช็คซ้ำ
    verify = conn_manager.send_command(device_id, f"show interfaces {interface_name}")
    new_status = parse_interface_status(verify)  # "up"/"down"/"administratively down"
    return {"output": output, "current_status": new_status}
```

**UI component**: `InterfaceForm.jsx`
- List/Table ของ interfaces (ดึงจาก `show ip interface brief` แบบ parse ด้วย TextFSM) — คอลัมน์: Interface name, IP Address, Status (badge สีเขียว/แดง), Protocol
- คลิกแถวไหน → เปิด panel ด้านข้าง/modal มีปุ่ม `[⬆ Up]` `[⬇ Down]` และฟอร์มกำหนด IP อยู่ในหน้าเดียวกัน (ลด context switching)

---

## ส่วนที่ 3: Show Command พื้นฐานที่ต้องมีปุ่มลัด (ยืนยันจากโจทย์ล่าสุด)

โจทย์เน้นย้ำ 4 คำสั่งนี้เป็นอย่างน้อย ต้องมีปุ่มลัดเข้าถึงง่ายในหน้า Device Detail (ไม่ต้องพิมพ์เอง):

| ปุ่ม | คำสั่งจริง |
|---|---|
| **IP** | `show ip interface brief` |
| **Running Config** | `show running-config` |
| **Routing Table** | `show ip route` |
| **Interface Brief** | `show ip interface brief` (ซ้ำกับ "IP" ได้ — หรือใช้ `show interfaces status` แทนถ้าต้องการรายละเอียดเพิ่ม เช่น duplex/speed) |

> แนะนำ: ทำเป็นแถบปุ่ม (button bar) ด้านบนของ Terminal panel เสมอ ไม่ต้องเข้าเมนูลึก — คลิกแล้วเห็นผลทันทีในกล่อง terminal ด้านล่าง

---

## ส่วนที่ 4: SSH Setup ต้องมีขั้นตอน Domain Name ก่อน RSA Key Generate

**ปัญหา**: ถ้าไม่ตั้ง `ip domain-name` ก่อน คำสั่ง `crypto key generate rsa` จะ error/ไม่ยอมรัน เพราะ IOS ใช้ domain name ไปประกอบเป็นชื่อ key

**ลำดับคำสั่งที่ถูกต้อง (อ้างอิงสไลด์ Ch6 Network Automation (2))**
```
configure terminal
ip domain-name <domain-name>          ! ต้องมาก่อนเสมอ เช่น thread1.com
crypto key generate rsa               ! ระบบจะถามขนาด key
   ! ให้ตอบ 1024 (หรือมากกว่า ถ้า IOS version ใหม่บังคับขั้นต่ำสูงกว่านี้)
username cisco privilege 15 password cisco
line vty 0 4
login local
transport input ssh
end
```

**สิ่งที่ต้องทำในโปรแกรม**:
1. ทำ **"SSH Setup Wizard"** แยกเป็นฟีเจอร์เฉพาะ (ไม่ใช่แค่ raw command) เพราะ `crypto key generate rsa` เป็นคำสั่ง interactive (ถามขนาด key แบบ prompt) — ต้องจัดการผ่าน netmiko แบบพิเศษ:
   ```python
   def setup_ssh(conn_manager, device_id: str, domain_name: str, key_size: int = 1024,
                  username: str = "cisco", password: str = "cisco"):
       commands = [
           f"ip domain-name {domain_name}",
       ]
       conn_manager.send_config(device_id, commands)

       # crypto key generate rsa เป็นคำสั่ง interactive ต้องใช้ send_command_timing หรือ send_command
       # พร้อม expect_string เพื่อตอบ prompt ขนาด key
       conn = conn_manager.pool[device_id]
       conn.config_mode()
       output = conn.send_command_timing("crypto key generate rsa")
       if "How many bits" in output:
           output += conn.send_command_timing(str(key_size))

       more_commands = [
           f"username {username} privilege 15 password {password}",
           "line vty 0 4",
           "login local",
           "transport input ssh",
       ]
       conn.send_config_set(more_commands)
       conn.exit_config_mode()
       return output
   ```
2. เตือนผู้ใช้ใน UI ว่าต้องรัน "SSH Setup" นี้ก่อนถึงจะเปลี่ยนวิธีเชื่อมต่อจาก Telnet เป็น SSH ได้ (chicken-and-egg: ตอนตั้งค่าครั้งแรกอาจต้องเชื่อมด้วย Telnet หรือ Console/Serial ก่อน แล้วค่อยเปิด SSH ทีหลัง)
3. เพิ่ม field "Domain Name" และ "RSA Key Size" ในฟอร์ม SSH Setup (default 1024, ให้เลือก 1024/2048/4096 ได้)

---

## ส่วนที่ 5: คำถามเปิด (Open Questions) — คำแนะนำในการตัดสินใจ

### 5.1 ต้องมี Virtual PC เป็นอุปกรณ์อีกประเภทหนึ่งไหม (ตอนนี้มี Router, Switch)

**คำแนะนำ: ควรมี** ด้วยเหตุผลดังนี้ (ให้เหมือน Packet Tracer จริง ๆ ต้องมี End Device):

- **บทบาทของ Virtual PC ในระบบนี้**:
  - ใช้ทดสอบ connectivity หลัง config routing เสร็จ (ping จาก PC ไป PC อีกฝั่งผ่าน router)
  - แสดงใน Topology เป็น node ปลายทาง (leaf node) ต่อกับ switch/router
  - ไม่จำเป็นต้องมี CLI Cisco IOS (เพราะไม่ใช่ Cisco device) — แค่ต้องมี "IP config" ง่าย ๆ (IP, subnet mask, default gateway) และปุ่ม "Ping"

- **วิธี implement โดยไม่ต้องพึ่ง physical PC จริง**:
  - **Option A (ง่ายสุด แนะนำสำหรับ scope งานนี้)**: จำลอง PC เป็น "virtual node" ในฐานข้อมูล/topology เท่านั้น ไม่มีการเชื่อมต่อ SSH/Telnet จริง เก็บแค่ IP/Gateway ที่ผู้ใช้กำหนดเอง แล้วให้ backend รัน `ping` จากเครื่องที่รันโปรแกรม (หรือจาก router ที่ต่ออยู่ด้วยคำสั่ง `ping <target-ip>` ผ่าน SSH) เพื่อจำลองว่า "PC ping ได้ไหม"
  - **Option B (ของจริงกว่า)**: ถ้ามี VM หรือ physical PC ต่ออยู่ใน lab จริง (เช่นใน EVE-NG มี Linux/Windows VM) ให้เชื่อมต่อผ่าน SSH เข้า VM นั้นจริง ๆ (netmiko `device_type: 'linux'` หรือใช้ paramiko ตรง ๆ) แล้วรันคำสั่ง `ip addr add`, `ping` จริงบน OS นั้น
  - แนะนำเริ่มจาก **Option A** ก่อนเพราะ scope งานเน้นที่ Router/Switch automation เป็นหลัก ส่วน PC เป็นแค่ตัวช่วย visualize/verify

- **สิ่งที่ต้องเพิ่มในโค้ด**: เพิ่ม `device_type: "pc"` ใน model `Device`, ทำ node icon แยกสำหรับ PC ใน topology, ทำฟอร์ม "Simple IP Config" (ไม่มี CLI เต็มแบบ router/switch)

### 5.2 การเชื่อมต่อผ่าน EVE-NG API (ต้องศึกษาเพิ่ม)

**สรุปสิ่งที่ต้องรู้ (สำหรับนำไป vibe coding ต่อ)**:

- EVE-NG มี **REST API** (community edition ก็มี, เอกสารทางการค่อนข้างน้อยแต่ community มี unofficial wrapper)
- Base URL ทั่วไป: `https://<eve-ng-ip>/api/`
- ต้อง **login ก่อนเพื่อรับ session cookie**:
  ```python
  import requests

  session = requests.Session()
  login_resp = session.post(
      "https://<eve-ng-ip>/api/auth/login",
      json={"username": "admin", "password": "eve", "html5": "-1"},
      verify=False  # EVE-NG มักใช้ self-signed cert
  )
  ```
- หลัง login แล้วสามารถเรียก endpoint อื่น ๆ ได้ เช่น:
  - `GET /api/labs` — list lab ทั้งหมด
  - `GET /api/labs/<path>/nodes` — ดึงรายการ node (router/switch) ใน lab นั้น พร้อมสถานะ (running/stopped), console port ที่ auto-generate
  - `GET /api/labs/<path>/topology` — ดึงข้อมูลการเชื่อมต่อ (link) ระหว่าง node — **ตรงนี้แหละที่ใช้ทำ Auto Discovery ได้แม่นยำกว่า CDP/LLDP เพราะดึงจาก EVE-NG โดยตรง ไม่ต้องพึ่งอุปกรณ์ตอบ CDP**
  - `GET /api/labs/<path>/nodes/<id>` — ดึง console info (telnet port ที่ EVE-NG จะ forward ให้แต่ละ node เช่น `telnet <eve-ng-ip> <auto-port>`)
- **ข้อดีของการต่อผ่าน EVE-NG API แทนต่อ SSH/Telnet ตรงไปที่ router**:
  - ได้ topology จริงจาก EVE-NG โดยไม่ต้องเดา/parse CDP (แม่นยำ 100% ตาม lab ที่วางไว้)
  - รู้ console port อัตโนมัติโดยไม่ต้องให้ผู้ใช้กรอกเอง
- **ข้อควรระวัง**:
  - Unofficial/community library เช่น `eve-ng` บน PyPI อาจไม่ maintain ต่อเนื่อง ควรทดสอบเองก่อนใช้จริง หรือเรียก REST endpoint ตรง ๆ ด้วย `requests` แทนพึ่ง library สำเร็จรูป
  - EVE-NG API เป็น "layer เสริม" สำหรับดึง topology/metadata เท่านั้น — **การส่งคำสั่ง configure ยังต้องเชื่อมเข้า console ของแต่ละ node ผ่าน telnet ไปยัง port ที่ EVE-NG จัดให้ (ไม่ใช่ผ่าน API)** ดังนั้น connection layer (netmiko) เดิมยังต้องใช้อยู่เหมือนเดิม เพียงแต่ได้ IP/port มาจาก API แทนการกรอกเอง

**แนะนำการ implement**:
```python
class EveNgClient:
    def __init__(self, host, username, password):
        self.base_url = f"https://{host}/api"
        self.session = requests.Session()
        self.session.verify = False
        self._login(username, password)

    def _login(self, username, password):
        self.session.post(f"{self.base_url}/auth/login",
                           json={"username": username, "password": password, "html5": "-1"})

    def list_labs(self):
        return self.session.get(f"{self.base_url}/labs").json()

    def get_topology(self, lab_path: str):
        return self.session.get(f"{self.base_url}/labs/{lab_path}/topology").json()

    def get_nodes(self, lab_path: str):
        return self.session.get(f"{self.base_url}/labs/{lab_path}/nodes").json()
```
> เพิ่มเป็นทางเลือกในหน้า Discovery: "Discover via CDP/LLDP" หรือ "Import Topology from EVE-NG" (ให้ผู้ใช้กรอก EVE-NG host + credentials + เลือก lab)

---

## ส่วนที่ 6: Bug ที่พบและวิธีแก้

### 6.1 ลบ Device ที่เป็น default/seed data (3 ตัวแรก) ไม่ได้

**สาเหตุที่เป็นไปได้ (ต้องเช็คทีละข้อในโค้ดจริง)**:
1. 3 device นี้ถูก **hardcode ไว้ใน frontend state** (เช่น initial state ของ React/array ตรง ๆ) แทนที่จะดึงจาก backend/database — กด delete แล้ว update state ฝั่ง frontend ไม่ตรงกับตัวจริงที่ยังอยู่ backend หรือ reload หน้าเว็บแล้วกลับมาใหม่เพราะ mock ไม่ได้เก็บ persist
2. Backend มี logic พิเศษที่ block การลบ device ที่มี `id` ตรงกับ seed data (เช่น `if device.id in ["seed-1","seed-2","seed-3"]: raise HTTPException(...)` ที่ตั้งใจไว้ตอน dev แล้วลืมเอาออก)
3. Database (ถ้าใช้ SQLite/JSON file) เขียนสิทธิ์ไฟล์ผิด (read-only) ทำให้ DELETE query ไม่ commit จริง แต่ frontend คิดว่าสำเร็จ (optimistic UI update ที่ไม่ verify กับ response)
4. Foreign key constraint — ถ้า device 3 ตัวนี้ถูกอ้างอิงจาก topology/connection record อื่นอยู่ การ DELETE ติด constraint แต่ error ถูก silent-catch ไปโดยไม่แจ้ง user

**วิธี debug/แก้**:
```python
# ตรวจสอบใน backend ว่า route DELETE ทำงานถูกจริงไหม
@router.delete("/devices/{device_id}")
def delete_device(device_id: str):
    device = inventory.get(device_id)
    if not device:
        raise HTTPException(404, "Device not found")
    # ต้องไม่มี logic exception พิเศษสำหรับ seed data ตรงนี้!
    inventory.delete(device_id)          # ลบจริงจาก store (DB/JSON file)
    connection_manager.disconnect(device_id)  # เผื่อมี session ค้างอยู่
    return {"status": "deleted", "id": device_id}
```
- เช็คให้แน่ใจว่า **frontend เรียก DELETE endpoint จริงและรอ response ก่อน update UI** (ไม่ใช่แค่ลบออกจาก local state เฉย ๆ)
- เช็คว่า **inventory store เป็น persistent จริง** (ไฟล์ JSON/SQLite ต้องเขียนได้ ไม่ใช่แค่ array ใน memory ที่ reset ทุกครั้งที่ restart server ซึ่งจะทำให้ดูเหมือน "ลบไม่ได้" เพราะ restart แล้ว seed data กลับมาใหม่เสมอ)
- แนะนำเพิ่ม **unit test เฉพาะ**: `test_delete_seed_device()` เพื่อกัน regression ไม่ให้ bug นี้กลับมาอีก

### 6.2 UX/UI ใช้งานยาก อยากคลิก Router/Switch ใน Topology เพื่อ config ได้เลยแบบ Packet Tracer

**Design ใหม่ที่ต้องทำ**:
- เปลี่ยนจาก flow เดิม (เข้าเมนู Device List → เลือก device → ไปหน้า config แยก) เป็น:
  - **หน้า Topology เป็นหน้าหลัก (default landing page)** ไม่ใช่หน้า Device List
  - **Double-click หรือ single-click ที่ node** ใน topology → เปิด **modal/side-drawer แบบเดียวกับ Packet Tracer** ที่มี tab: `Physical (ports)` / `Config (CLI-style form)` / `Terminal (CLI)`
  - Modal นี้ต้องลอยอยู่เหนือ topology (ไม่ใช่เปลี่ยนหน้าไปทั้งหมด) เพื่อให้ผู้ใช้เห็น context ว่ากำลัง config device ตัวไหนอยู่ในภาพรวม topology ตลอดเวลา (เหมือน Packet Tracer ที่ popup หน้าต่างขึ้นมาทับ แต่ยังเห็น topology ด้านหลังลาง ๆ)
  - เพิ่ม **right-click context menu** บน node: "Configure", "Delete", "Show Interfaces", "Ping from here"
- ตัวอย่างโครงสร้าง component (React):
  ```jsx
  <TopologyCanvas onNodeClick={(node) => setActiveDevice(node)} />
  {activeDevice && (
    <DeviceConfigDrawer
      device={activeDevice}
      onClose={() => setActiveDevice(null)}
      tabs={["Physical", "Config", "Routing", "Terminal"]}
    />
  )}
  ```
- ใน tab "Physical" ให้วาดรูปด้านหลัง/ด้านหน้าของอุปกรณ์พร้อม port ทั้งหมด (คล้าย Packet Tracer ที่เห็นรูป physical ports จริง) — ระดับ minimum ทำเป็น list ธรรมดาก่อนได้ ถ้าเวลาไม่พอ

### 6.3 Icon ของ Topology ต้องเป็นรูปจริงตาม Device Type (ไม่ใช่ hexagon generic)

**ปัญหา**: ใช้ default node shape ของ library กราฟ (เช่น hexagon ของ vis-network/react-flow default) แทนไอคอนอุปกรณ์จริง

**วิธีแก้**:
- ใช้ **custom node type** ใน react-flow (หรือ custom node renderer ใน vis-network ผ่าน `shape: "image"`) แทน default shape
- เตรียมไฟล์ icon แยกตาม device type: `router.svg`, `switch.svg`, `pc.svg`, `server.svg` (แนะนำใช้ icon set แบบ network topology ที่มีสไตล์คล้าย Cisco Packet Tracer/Network Topology Icons — เช่น Cisco-style stencils ที่หาได้จาก icon library ฟรีอย่าง `flaticon`, `network-icons`, หรือวาด SVG เองให้เรียบง่ายแต่จำแนกชนิดได้ชัดเจน: Router = ทรงกลม/วงรีมีลูกศรวนสองด้าน, Switch = สี่เหลี่ยมมีลูกศรขึ้นลง, PC = จอคอมพิวเตอร์)
- ตัวอย่าง react-flow custom node:
  ```jsx
  function DeviceNode({ data }) {
    const iconMap = {
      router: "/icons/router.svg",
      switch: "/icons/switch.svg",
      pc: "/icons/pc.svg",
    };
    return (
      <div className="device-node">
        <img src={iconMap[data.type]} alt={data.type} width={48} height={48} />
        <div className="device-label">{data.label}</div>
        <div className={`status-dot ${data.status}`} />
      </div>
    );
  }
  ```
- เพิ่ม status indicator (จุดสีเขียว/แดงเล็ก ๆ มุมบนขวาของ icon) แสดงว่า connected/disconnected — ช่วยให้ UX ดีขึ้นแบบ Packet Tracer ที่เห็นสถานะ link ทันที

### 6.4 สายเชื่อม (edge/link) และ Font อ่านยาก ไม่สบายตา

**ปัญหาที่มักเกิดกับ default styling ของ graph library**: เส้นบางเกินไป, สีเส้นกลืนกับพื้นหลัง, font เริ่มต้นเป็น monospace/system font ที่ดูเป็น debug tool ไม่ใช่ application

**แนวทางแก้ (CSS/config ปรับได้ทันที)**:
- **เส้น (edges)**:
  - เพิ่มความหนาเส้นเป็นอย่างน้อย 2–3px
  - ใช้สีที่ contrast ชัดกับพื้นหลัง (เช่น พื้นขาว/เทาอ่อน → เส้นสีเทาเข้ม `#4a5568` หรือน้ำเงิน `#2b6cb0`)
  - ใช้เส้นแบบ **orthogonal/step line** (มุมฉาก) แทนเส้นตรงทะแยงมุม จะดูเป็นระเบียบแบบ network diagram มืออาชีพมากกว่า (คล้าย Packet Tracer/Visio)
  - เพิ่ม hover state ให้เส้นสว่างขึ้น/หนาขึ้นเมื่อ mouse ชี้ เพื่อบอกว่าคลิกดูรายละเอียด link ได้ (เช่น interface ต้นทาง-ปลายทาง)
  - ตัวอย่าง react-flow edge style:
    ```jsx
    const edgeOptions = {
      type: "smoothstep",   // มุมฉากโค้งมน อ่านง่ายกว่าเส้นตรง
      style: { stroke: "#4a5568", strokeWidth: 2.5 },
      labelStyle: { fontSize: 12, fill: "#2d3748" },
      labelBgStyle: { fill: "#fff", fillOpacity: 0.9 },
    };
    ```
- **Font**:
  - เปลี่ยนจาก default (มักเป็น `-apple-system` หรือ monospace ของ dev tool) เป็น font ที่อ่านง่ายสำหรับ UI ทั่วไป เช่น `"Inter", "Segoe UI", "Roboto", sans-serif` สำหรับ label/UI ทั่วไป
  - **เก็บ monospace font ไว้เฉพาะใน Terminal panel เท่านั้น** (เช่น `"Cascadia Code", "Consolas", monospace`) เพราะ terminal output ต้อง align column ตรงกัน (ตาราง `show ip interface brief` จะเพี้ยนถ้าไม่ใช่ monospace)
  - เพิ่ม font-size ของ label บน node/edge ให้อ่านง่ายขึ้น (อย่างน้อย 12–14px ไม่ใช่ 9–10px แบบ default บาง library)
- สรุป CSS ตัวอย่างระดับ global:
  ```css
  :root {
    --ui-font: "Inter", "Segoe UI", Roboto, sans-serif;
    --terminal-font: "Cascadia Code", "Consolas", "Courier New", monospace;
    --edge-color: #4a5568;
    --edge-color-hover: #2b6cb0;
  }
  body { font-family: var(--ui-font); }
  .terminal-panel { font-family: var(--terminal-font); font-size: 13px; line-height: 1.5; }
  ```

---

## ส่วนที่ 7: สรุป Task ที่ต้องทำเพิ่ม (ผนวกกับ Milestone เดิมใน v1)

| ลำดับ | งาน | หมวด |
|---|---|---|
| 1 | แก้ `build_rip()` ให้เลือก version 1/2 ได้ | Routing |
| 2 | เพิ่ม `build_redistribute()` + `build_default_information_originate()` ทุก protocol | Routing |
| 3 | ทำ UI section "Redistribution" แยกในฟอร์ม routing แต่ละ protocol | Routing UI |
| 4 | ปรับ Interface UI เป็น flow 2 ขั้นตอน (เลือก interface → ปุ่ม Up/Down แยก) พร้อม verify status หลังกด | Interface UX |
| 5 | เพิ่มปุ่มลัด Show command: IP, Running Config, Routing Table, Interface Brief | Show Command |
| 6 | ทำ "SSH Setup Wizard" (domain-name → crypto key generate rsa แบบ interactive → username/line vty) | SSH Setup |
| 7 | เพิ่ม device type "PC" (Option A: virtual node เก็บ IP/Gateway + ปุ่ม ping) | Device Type |
| 8 | ทำ `EveNgClient` (REST API login + ดึง topology/nodes) เป็นทางเลือก import topology | EVE-NG Integration |
| 9 | Fix bug ลบ seed device ไม่ได้ — เช็ค hardcode/persist store/optimistic UI ตาม checklist ข้อ 6.1 | Bug Fix |
| 10 | Redesign หน้า Topology ให้เป็น landing page + คลิก node เปิด config drawer (Physical/Config/Routing/Terminal tabs) | UX Overhaul |
| 11 | เปลี่ยน node icon เป็น SVG ตาม device type จริง (router/switch/pc) + status dot | Visual |
| 12 | ปรับ edge style (สี/ความหนา/orthogonal line) + แยก font UI กับ font terminal | Visual |

---

## ส่วนที่ 8: อ้างอิงเพิ่มเติมสำหรับ vibe coding

- Redistribute/default-information originate syntax: Cisco IOS command reference (`router ospf`, `router eigrp`, `router rip`, `router bgp` sections)
- EVE-NG REST API: ไม่มีเอกสารทางการครบถ้วน แนะนำ inspect ผ่าน browser dev tools ตอน login เข้า EVE-NG web UI เอง (ดู network tab ว่า frontend ของ EVE-NG เรียก endpoint อะไรบ้าง) เพื่อ confirm behavior ก่อนใช้จริง เนื่องจาก API อาจเปลี่ยนตาม version
- react-flow docs: https://reactflow.dev (custom nodes, custom edges, edge types `smoothstep`/`step`)
- vis-network docs (ทางเลือกแทน react-flow): https://visjs.github.io/vis-network/docs/network/
- netmiko `send_command_timing()` / `expect_string`: ใช้จัดการคำสั่ง interactive อย่าง `crypto key generate rsa` ที่ถาม prompt กลางคำสั่ง
