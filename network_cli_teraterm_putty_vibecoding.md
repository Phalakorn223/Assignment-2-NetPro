# Tera Term / PuTTY และการดึง CLI จาก Router / Switch
## Technical Explanation + Specification สำหรับนำไป Vibe Coding

เอกสารนี้อธิบายเชิงเทคนิคว่า Tera Term และ PuTTY ทำงานอย่างไรเมื่อเชื่อมต่อ Router / Switch ผ่าน Serial, Telnet หรือ SSH และทำไมจึงสามารถ "เก็บ CLI", "เก็บ command + output", "ดึง running-config" หรือทำ automation เพื่อเก็บข้อมูลจากอุปกรณ์ Network ได้

จุดสำคัญที่สุด:

> Tera Term / PuTTY ไม่ได้มีฐานข้อมูล command ของ Router/Switch อยู่ในโปรแกรม และไม่ได้อ่าน command ทั้งหมดจาก firmware โดยตรง
>
> โปรแกรมทำหน้าที่เป็น Terminal Emulator + Transport Client โดยรับ byte/character stream จากอุปกรณ์ แล้วแสดงผลบน Terminal หรือบันทึกลง log
>
> ส่วน command ที่รองรับ, output, configuration และ prompt ถูกสร้าง/ส่งมาจาก CLI ของ Router/Switch เอง

---

# 1. Mental Model ที่ถูกต้อง

ให้คิดว่า Router/Switch เป็น "Server ที่มี CLI" และ Tera Term/PuTTY เป็น "หน้าจอ + keyboard + connection"

```text
┌──────────────────────────────┐
│ PC                           │
│                              │
│ Tera Term / PuTTY            │
│                              │
│  Terminal Emulator           │
│  SSH / Telnet / Serial       │
└──────────────┬───────────────┘
               │
               │ bytes / characters
               │
               ▼
┌──────────────────────────────┐
│ Router / Switch              │
│                              │
│ Network OS / CLI              │
│                              │
│ command parser                │
│ command execution             │
│ configuration database        │
└──────────────────────────────┘
```

ตัวอย่าง:

ผู้ใช้พิมพ์:

```text
show ip interface brief
```

โปรแกรม Terminal ไม่จำเป็นต้องรู้ว่า command นี้คืออะไร

มันเพียงส่งข้อความ:

```text
s h o w   i p   i n t e r f a c e   b r i e f
```

ไปยัง Router

Router จึงเป็นผู้:

1. รับ input
2. parse command
3. ตรวจสอบว่า command ถูกต้องหรือไม่
4. execute command
5. สร้าง output
6. ส่ง output กลับมา

Tera Term/PuTTY จึงรับ output:

```text
Interface              IP-Address      OK? Method Status
GigabitEthernet0/1     192.168.1.1     YES manual up
GigabitEthernet0/2     unassigned      YES unset  down
```

แล้วแสดงบนหน้าจอ

---

# 2. Transport Layer ที่ Terminal สามารถใช้ได้

Terminal Emulator สามารถเชื่อมต่อกับอุปกรณ์ได้หลายวิธี

## 2.1 Serial Console

ตัวอย่าง:

```text
PC
 │
 │ USB → Serial
 │
 ▼
Console Port
 │
 ▼
Router
```

ข้อมูลเป็น byte stream ผ่าน serial port

ค่าที่พบบ่อย เช่น:

```text
Baud Rate : 9600
Data      : 8 bit
Parity    : None
Stop Bits : 1
Flow Ctrl : None
```

หรืออาจเป็น baud rate อื่นตามอุปกรณ์

ในกรณีนี้ไม่มี TCP/IP จำเป็นสำหรับการเข้าสู่ CLI เพราะเป็น local console connection

---

# 3. Telnet

Telnet ใช้ TCP

โดยทั่วไป:

```text
PC
 │
 │ TCP
 │
 │ destination port 23
 ▼
Router
 │
 ▼
CLI
```

Terminal ส่ง/รับ byte ผ่าน TCP connection

ตัวอย่าง:

```text
Client → Server

username
password
show version
```

Server ส่งกลับ:

```text
Username:
Password:
Router#
Router# show version
...
```

ข้อเสียสำคัญคือ Telnet ไม่มี encryption

ดังนั้น production network โดยทั่วไปควรใช้ SSH เมื่อเป็นไปได้

---

# 4. SSH

SSH ก็เป็น byte stream เช่นเดียวกันในมุมของ Terminal Application แต่มี secure transport อยู่ด้านล่าง

```text
┌─────────────────────────────┐
│ Tera Term / PuTTY           │
│                             │
│ Terminal                    │
└──────────────┬──────────────┘
               │
               ▼
        SSH Client
               │
        encrypted channel
               │
               ▼
        SSH Server
               │
               ▼
             CLI
```

โดยทั่วไปใช้ TCP port 22

สิ่งสำคัญ:

Tera Term/PuTTY ไม่ได้ส่ง "object ที่ชื่อ command" ไปยัง Router

มันส่งข้อมูลใน channel เช่น:

```text
show version\r
```

Router จึงอ่านข้อความจาก SSH session

---

# 5. Terminal Emulator จริง ๆ ทำอะไร?

Terminal Emulator มีหน้าที่หลัก เช่น:

- รับ keyboard input
- แปลง keyboard input เป็น character/byte
- ส่งข้อมูลไป connection
- รับ byte จาก connection
- แปล control characters
- จัดการ cursor
- แสดง text
- รองรับ ANSI/VT escape sequences
- จัดการ backspace
- จัดการ newline/carriage return
- แสดงสี/formatting บางประเภท
- scrollback
- copy/paste
- logging

ดังนั้นถ้า Router ส่ง:

```text
\x1b[32mRouter#\x1b[0m
```

Terminal อาจตีความ ANSI escape sequence แล้วแสดง:

```text
Router#
```

ด้วยสีที่กำหนด

---

# 6. Byte Stream คือหัวใจของระบบ

ในระดับโปรแกรม สิ่งที่ได้รับอาจเป็น stream เช่น:

```text
52 6f 75 74 65 72 23 20
```

ASCII:

```text
Router# 
```

เมื่อส่ง command:

```text
show version
```

อาจถูกส่งเป็น:

```text
73 68 6f 77 20 76 65 72 73 69 6f 6e 0d
```

โดย `0d` คือ carriage return (`\r`) ในตัวอย่างนี้

จึงไม่ควรคิดว่า:

```text
sendCommand("show version")
```

เป็น protocol-level object ที่ Router เข้าใจ

ในระดับ transport มันเป็น text/bytes

---

# 7. Command Line Interface อยู่ใน Router/Switch

Router/Switch มี Network OS เช่น Cisco IOS/IOS XE, NX-OS, Junos, ArubaOS, FortiOS ฯลฯ

CLI ของแต่ละ OS มี parser ของตัวเอง

ตัวอย่างแนวคิด:

```text
input:
show ip route

        ↓

CLI Parser

        ↓

ตรวจสอบ:
- command มีอยู่หรือไม่
- syntax ถูกหรือไม่
- privilege เพียงพอหรือไม่
- mode ปัจจุบันคืออะไร

        ↓

Command Handler

        ↓

Generate Output

        ↓

SSH/Telnet/Serial Session

        ↓

Tera Term / PuTTY
```

---

# 8. ทำไม `?` ถึงสามารถแสดง command ได้?

เพราะ `?` เป็น feature ของ CLI

ตัวอย่าง:

```text
Router# ?
```

Router อาจตอบ:

```text
Exec commands:
  clear
  configure
  copy
  debug
  disable
  enable
  exit
  ping
  reload
  show
  traceroute
```

Terminal Emulator ไม่ได้สร้างรายการนี้เอง

Router เป็นผู้ส่งรายการกลับมา

เช่น:

```text
User:
?

Router:
clear
configure
copy
debug
...
```

---

# 9. Context-sensitive CLI

CLI ของ Network OS มักขึ้นกับ mode

ตัวอย่าง:

```text
Router#
```

คือ EXEC mode

เมื่อ:

```text
configure terminal
```

จะกลายเป็น:

```text
Router(config)#
```

ถ้า:

```text
interface GigabitEthernet0/1
```

จะกลายเป็น:

```text
Router(config-if)#
```

ดังนั้น command ที่รองรับในแต่ละจุดจะแตกต่างกัน

ตัวอย่าง:

```text
Router# ?
```

อาจได้:

```text
show
configure
copy
reload
...
```

แต่:

```text
Router(config)# ?
```

อาจได้:

```text
hostname
interface
ip
router
line
...
```

และ:

```text
Router(config-if)# ?
```

อาจได้:

```text
description
ip
shutdown
no
switchport
...
```

ดังนั้นการ "ดึง command ทั้งหมด" ไม่ใช่แค่ส่ง `?` ครั้งเดียว

ถ้าต้องการ command tree ต้องสำรวจหลาย context

---

# 10. Command Tree

สามารถมอง CLI เป็น tree ได้

ตัวอย่างแนวคิด:

```text
?
├── show
│   ├── version
│   ├── interfaces
│   ├── ip
│   │   ├── interface
│   │   ├── route
│   │   └── arp
│   ├── running-config
│   └── startup-config
│
├── configure
│   └── terminal
│
└── copy
```

เมื่อพิมพ์:

```text
show ?
```

Router จะคืน child nodes ของ `show`

เมื่อพิมพ์:

```text
show ip ?
```

Router จะคืน child nodes ของ `show ip`

ดังนั้นโปรแกรม automation สามารถ conceptually สำรวจ:

```text
?
 ↓
show ?
 ↓
show ip ?
 ↓
show ip interface ?
...
```

แต่การทำจริงมีข้อจำกัดและความเสี่ยง ซึ่งอธิบายภายหลัง

---

# 11. "ดึง Command ทั้งหมด" มีหลายความหมาย

ก่อนออกแบบโปรแกรมต้องแยกคำว่า "ทั้งหมด"

## แบบที่ 1: Commands ที่ผู้ใช้พิมพ์

ตัวอย่าง:

```text
enable
show version
show ip interface brief
show running-config
```

วิธีเก็บ:

```text
input logging
```

---

## แบบที่ 2: Output ที่ Router ส่งกลับมา

เช่น:

```text
Cisco IOS XE Software...
Version ...
...
```

วิธีเก็บ:

```text
session logging
```

---

## แบบที่ 3: Configuration ปัจจุบัน

เช่น:

```text
hostname Router01

interface GigabitEthernet0/1
 ip address 192.168.1.1 255.255.255.0
 no shutdown
```

มักใช้:

```text
show running-config
```

---

## แบบที่ 4: Startup configuration

เช่น:

```text
show startup-config
```

เป็น configuration ที่เก็บไว้สำหรับ startup

---

## แบบที่ 5: Command ที่ CLI รองรับ

ต้องใช้ CLI help/discovery เช่น:

```text
?
show ?
show ip ?
configure terminal
?
```

และต้องสำรวจหลาย mode

---

# 12. Tera Term Logging

Tera Term สามารถเปิด log file แล้วบันทึกข้อมูลที่ผ่าน terminal session

Concept:

```text
┌───────────────┐
│ Router        │
└───────┬───────┘
        │
        │ bytes
        ▼
┌───────────────┐
│ Tera Term     │
│               │
│ receive data  │
│ display       │
│ logging       │
└───────┬───────┘
        │
        ▼
router-session.txt
```

Log อาจประกอบด้วย:

```text
Router# show version

Cisco IOS XE Software...
...
Router# show ip interface brief

Interface ...
...
```

ข้อควรระวัง:

Log ไม่ได้แปลว่า parser รู้ว่า:

```text
show version
```

คือ command

และ:

```text
Cisco IOS XE Software...
```

คือ output

โดยพื้นฐานมันสามารถเป็นเพียง transcript ของ terminal session

---

# 13. PuTTY Logging

PuTTY ก็ใช้แนวคิดเดียวกัน

```text
PuTTY
  │
  ├── Keyboard input
  │
  ├── SSH/Telnet/Serial
  │
  ├── Received terminal data
  │
  └── Session logging
```

ถ้าเปิด logging แล้ว session จะถูกบันทึกลงไฟล์

แต่เช่นเดียวกัน:

> PuTTY ไม่ได้รู้ semantic meaning ของ command โดยอัตโนมัติ

มันเก็บ terminal data

---

# 14. ปัญหาสำคัญ: Paging

ถ้า command output ยาว Router อาจไม่ส่งทั้งหมดรวดเดียวในลักษณะที่ผู้ใช้เห็นได้ทันที

ตัวอย่าง:

```text
Router# show running-config

...
--More--
```

นี่คือ pagination

ถ้า automation ทำ:

```text
send("show running-config")
```

แล้วรอ prompt:

```text
Router#
```

อาจค้าง เพราะ Router กำลังรอ:

```text
Space
```

เพื่อแสดงหน้าถัดไป

ดังนั้น automation ต้องจัดการ paging

---

# 15. Disable Paging

อุปกรณ์หลายยี่ห้อมี command สำหรับปิด paging

Cisco IOS ตัวอย่าง:

```text
terminal length 0
```

ทำให้ output ไม่หยุดที่:

```text
--More--
```

แต่ command แตกต่างกันตาม vendor/OS

ดังนั้น software ไม่ควร hard-code ว่า device ทุกตัวใช้:

```text
terminal length 0
```

ควรมี profile เช่น:

```json
{
  "vendor": "cisco",
  "os": "ios",
  "paging_command": "terminal length 0"
}
```

ตัวอย่าง Junos อาจใช้แนวทางอื่น

ดังนั้น architecture ควรแยก vendor adapter

---

# 16. Prompt Detection

Automation ต้องรู้ว่า command จบแล้วเมื่อไร

ตัวอย่าง:

```text
Router# show version
...
Router#
```

โปรแกรมสามารถ detect:

```text
Router#
```

แล้วถือว่า command เสร็จ

แต่ห้ามสมมติว่า prompt ต้องเป็น:

```text
Router#
```

เพราะอาจเป็น:

```text
Switch#
Core-SW#
R1#
R1(config)#
R1(config-if)#
```

หรือ hostname อาจเปลี่ยนได้

---

# 17. Prompt เป็น Dynamic State

ควรเก็บ state:

```text
mode = exec
prompt = Router#
```

หลัง:

```text
configure terminal
```

กลายเป็น:

```text
mode = config
prompt = Router(config)#
```

หลัง:

```text
interface g0/1
```

กลายเป็น:

```text
mode = interface
prompt = Router(config-if)#
```

ดังนั้น command runner ควรมี:

```text
Connection State
├── transport
├── authenticated
├── privilege
├── mode
├── prompt
└── paging state
```

---

# 18. Enable / Privilege Mode

Cisco-style devices อาจมี:

```text
Router>
```

และ:

```text
Router#
```

โดยทั่วไป:

```text
>
```

คือ user EXEC

และ:

```text
#
```

คือ privileged EXEC

ถ้า automation ต้องการ:

```text
show running-config
```

หรือ configuration commands บางอย่าง อาจต้อง:

```text
enable
```

แล้วจัดการ enable password/secret

ระบบ automation ควรแยก:

```text
login
enable
command execution
```

ออกจากกัน

ไม่ควรเอารหัสผ่านไปใส่ใน log

---

# 19. Authentication

SSH อาจใช้:

```text
username
password
```

หรือ:

```text
SSH key
```

หรือวิธีอื่นตามระบบ

Automation ต้องสามารถ detect:

```text
Username:
Password:
Router>
Router#
```

แต่ prompt เหล่านี้ไม่ควรถูก hard-code เป็นวิธีเดียว

---

# 20. ANSI Escape Sequences

Terminal output อาจมี control sequence

ตัวอย่าง:

```text
ESC [ 2 K
ESC [ 1 G
ESC [ 32 m
ESC [ 0 m
```

ถ้าจะสร้าง software ที่ "เก็บ raw output" และ "เก็บ clean output" ควรแยกสองแบบ:

```text
raw_stream.log
clean_output.txt
```

### Raw

เก็บ byte/control sequence ตามที่ได้รับ

เหมาะสำหรับ debugging

### Clean

ลบ terminal control sequence แล้วเหลือ text

เหมาะสำหรับ parser/search

---

# 21. CR และ LF

Terminal protocol มีเรื่อง newline ที่ต้องระวัง

เช่น:

```text
\r
\n
\r\n
```

บางอุปกรณ์ส่ง:

```text
\r\n
```

บาง input ต้องการ:

```text
\r
```

ดังนั้น command runner ควรมี configurable line ending:

```text
CR
LF
CRLF
```

อย่าสมมติทุก device เหมือนกัน

---

# 22. Echo

เวลาส่ง:

```text
show version
```

Router อาจ echo command กลับ:

```text
Router# show version
```

ดังนั้น transcript:

```text
TX:
show version\r

RX:
show version
Cisco IOS...
...
Router#
```

โปรแกรมสามารถใช้ข้อมูลนี้เพื่อแยก command และ output ได้ดีขึ้น แต่ไม่ควร assume ว่า echo จะเหมือนกันทุก device

---

# 23. วิธีแยก Command กับ Output

มีหลายระดับ

## ระดับ 1: Transcript

เก็บทั้งหมด:

```text
Router# show version
...
Router#
```

ง่ายที่สุดและน่าเชื่อถือ

---

## ระดับ 2: Command-aware runner

โปรแกรมเป็นผู้ส่ง command เอง:

```text
send("show version")
```

จึงรู้ว่า command คือ:

```text
show version
```

จากนั้นรอ prompt

จึงสร้าง object:

```json
{
  "command": "show version",
  "output": "Cisco IOS XE Software...",
  "prompt_before": "Router#",
  "prompt_after": "Router#",
  "timestamp": "..."
}
```

วิธีนี้เหมาะกับ automation มากกว่า session logging ธรรมดา

---

# 24. Command Execution Model

แนะนำ architecture:

```text
execute(command)

1. validate connection
2. detect current prompt
3. send command + line ending
4. read incoming bytes
5. decode terminal data
6. detect paging
7. if paging:
       send space / configured key
       continue reading
8. detect command completion
9. return output
10. save structured log
```

Pseudo-code:

```python
def execute(command):
    send(command + "\r")

    buffer = ""

    while True:
        data = read()
        buffer += decode(data)

        if detect_paging(buffer):
            send(" ")

        if detect_prompt(buffer):
            break

    return clean_output(buffer)
```

---

# 25. ห้ามใช้ Sleep อย่างเดียว

วิธีที่ไม่ดี:

```python
send("show running-config")
sleep(5)
read()
```

เพราะ:

- output อาจสั้นกว่านั้น
- output อาจยาวกว่านั้น
- network latency เปลี่ยน
- CPU ของ device เปลี่ยน
- command บางตัวใช้เวลานาน
- paging อาจหยุด

วิธีที่ดีกว่า:

```text
send command
      ↓
read continuously
      ↓
detect paging
      ↓
detect prompt
      ↓
command complete
```

Sleep ใช้เป็น timeout/polling ได้ แต่ไม่ควรเป็น completion mechanism หลัก

---

# 26. Timeout

ควรมีอย่างน้อย:

```text
connect_timeout
login_timeout
command_timeout
read_timeout
idle_timeout
```

ตัวอย่าง:

```json
{
  "connect_timeout": 10,
  "login_timeout": 20,
  "command_timeout": 60,
  "read_timeout": 1
}
```

---

# 27. Long-running Commands

บาง command อาจใช้เวลานาน:

```text
show tech-support
```

หรือ command ที่ generate output จำนวนมาก

ดังนั้น:

```text
command_timeout = 60 sec
```

อาจไม่พอ

ควร support:

```text
per-command timeout
```

ตัวอย่าง:

```json
{
  "command": "show tech-support",
  "timeout": 300
}
```

---

# 28. การดึง Running Config

ถ้าจุดประสงค์คือ backup config ไม่จำเป็นต้อง "ค้น command tree"

สามารถใช้ command ที่เหมาะสมของ vendor โดยตรง

ตัวอย่าง Cisco:

```text
show running-config
```

แล้ว capture output

แต่ต้องจัดการ:

- paging
- prompt
- timeout
- terminal width
- ANSI
- privilege
- output size

---

# 29. Terminal Width

บาง device อาจ wrap output ถ้า terminal width แคบ

เช่น:

```text
description This is a very long interface descripti
on...
```

ทำให้ parser ยาก

ดังนั้น automation บางประเภทควรตั้ง terminal width ตาม vendor/OS ถ้ารองรับ

เช่น conceptually:

```text
terminal width 0
```

แต่ command จริงต้องเป็น vendor-specific

---

# 30. Configuration Backup ที่ดี

ไม่ควรเก็บแค่:

```text
router.txt
```

อย่างเดียว

แนะนำ metadata:

```json
{
  "device": "Router01",
  "host": "192.168.1.1",
  "vendor": "Cisco",
  "os": "IOS XE",
  "timestamp": "2026-09-25T20:00:00+07:00",
  "commands": [
    "show version",
    "show ip interface brief",
    "show running-config"
  ]
}
```

และแยก:

```text
backups/
└── Router01/
    ├── metadata.json
    ├── session.log
    ├── show-version.txt
    ├── show-ip-interface-brief.txt
    └── running-config.txt
```

---

# 31. ทำไมไม่ควรใช้ Log File อย่างเดียว

Session log มีข้อดี:

```text
Router# show version
...
Router# show ip interface brief
...
```

แต่ parser ต้องเดาว่าแต่ละ output เริ่ม/จบตรงไหน

ถ้า application เป็นผู้ส่ง command เอง สามารถสร้าง structured result ได้:

```json
{
  "command": "show version",
  "success": true,
  "output": "...",
  "duration_ms": 420,
  "prompt": "Router#"
}
```

จึงเหมาะกับ application มากกว่า

---

# 32. Command Discovery

ถ้าต้องการทำโปรแกรมที่ "ค้น command ที่ device รองรับ" สามารถออกแบบเป็น crawler

แนวคิด:

```text
Root:
?

        ↓

show ?

        ↓

show ip ?

        ↓

show ip interface ?

        ↓

...
```

แล้วสร้าง tree:

```json
{
  "show": {
    "version": {},
    "interfaces": {},
    "ip": {
      "interface": {},
      "route": {},
      "arp": {}
    }
  }
}
```

แต่ต้องระวังอย่างมาก

---

# 33. ทำไม Command Discovery แบบ Recursive ถึงยาก

CLI จริงไม่ได้เป็น tree ที่สมบูรณ์และง่ายเสมอไป

อาจมี:

- dynamic commands
- privilege restrictions
- hidden commands
- aliases
- abbreviations
- context dependency
- interactive commands
- destructive commands
- commands ที่ต้อง argument
- commands ที่ trigger another prompt
- commands ที่มี side effects

ดังนั้น:

```text
?
```

ไม่ได้หมายความว่า:

```text
"นี่คือ command ทั้งหมดที่สามารถ execute ได้"
```

มันคือ help information สำหรับ context ปัจจุบัน

---

# 34. ห้าม Automation Execute ทุก Command ที่พบ

นี่เป็นข้อสำคัญมาก

ถ้า crawler พบ:

```text
reload
write
erase
delete
clear
debug
shutdown
```

ไม่ควร execute อัตโนมัติ

เพราะบาง command มี side effect

ตัวอย่าง:

```text
reload
```

อาจ reboot device

หรือ:

```text
erase startup-config
```

อาจลบ configuration

ดังนั้น discovery system ควรเป็น:

```text
DISCOVER
  ↓
PARSE
  ↓
STORE
```

ไม่ใช่:

```text
DISCOVER
  ↓
EXECUTE EVERYTHING
```

---

# 35. Read-only Command Policy

ถ้าสร้าง tool สำหรับเก็บข้อมูล ควรมี policy:

```json
{
  "mode": "read_only",
  "allow_commands": [
    "show version",
    "show interfaces",
    "show ip interface brief",
    "show ip route",
    "show running-config"
  ]
}
```

และ deny:

```text
configure
reload
erase
delete
write
shutdown
clear
debug
copy
```

ตามความเหมาะสมของ platform

---

# 36. Vendor Adapter

อย่าเขียน architecture แบบ:

```python
if vendor == "cisco":
    ...
elif vendor == "juniper":
    ...
elif vendor == "aruba":
    ...
```

กระจายเต็มทั้ง codebase

ควรมี abstraction:

```text
NetworkDeviceDriver
```

เช่น:

```python
class NetworkDeviceDriver:
    def login(self):
        pass

    def get_prompt(self):
        pass

    def disable_paging(self):
        pass

    def get_version(self):
        pass

    def get_running_config(self):
        pass

    def normalize_output(self, text):
        pass
```

แล้ว implement:

```text
CiscoIOSDriver
CiscoNXOSDriver
JunosDriver
ArubaOSDriver
FortiOSDriver
```

---

# 37. Transport Abstraction

ควรแยก transport ออกจาก device OS

```text
             Network Device Driver
                      │
          ┌───────────┴───────────┐
          │                       │
      SSH Transport          Serial Transport
          │                       │
          ▼                       ▼
       TCP/22                  COM Port
```

ในอนาคตอาจเพิ่ม:

```text
TelnetTransport
```

โดยไม่ต้องเขียน CLI logic ใหม่ทั้งหมด

---

# 38. Proposed Architecture

```text
┌─────────────────────────────────────────┐
│                UI / CLI                 │
└────────────────────┬────────────────────┘
                     │
┌────────────────────▼────────────────────┐
│             Session Manager             │
│                                         │
│ login / reconnect / timeout / state     │
└────────────────────┬────────────────────┘
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
┌──────────────────┐   ┌──────────────────┐
│ Device Driver    │   │ Transport Layer  │
│                  │   │                  │
│ Cisco IOS        │   │ SSH              │
│ Junos            │   │ Telnet           │
│ Aruba            │   │ Serial           │
└────────┬─────────┘   └────────┬─────────┘
         │                      │
         └──────────┬───────────┘
                    ▼
             Command Runner
                    │
                    ▼
             Terminal Parser
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
      Prompt      Pager       ANSI
      Parser      Handler      Parser
        │           │           │
        └───────────┼───────────┘
                    ▼
             Structured Output
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
      JSON / DB             Text Log
```

---

# 39. Session State Machine

แนะนำให้ application มี state machine

```text
DISCONNECTED
     │
     ▼
CONNECTING
     │
     ▼
CONNECTED
     │
     ▼
AUTHENTICATING
     │
     ▼
AUTHENTICATED
     │
     ▼
DETECTING_PROMPT
     │
     ▼
READY
     │
     ├── EXECUTING_COMMAND
     │          │
     │          ▼
     │       PAGING
     │          │
     │          ▼
     │       WAIT_PROMPT
     │          │
     │          ▼
     │         READY
     │
     ▼
DISCONNECTING
     │
     ▼
DISCONNECTED
```

---

# 40. Important: Prompt Detection ไม่ควรใช้แค่ Regex เดียว

ตัวอย่างง่าย:

```regex
^[A-Za-z0-9._-]+[>#]\s*$
```

อาจใช้ได้กับบางกรณี

แต่ production-grade parser ต้องรองรับ:

```text
Router#
Router>
Router(config)#
Router(config-if)#
Router(config-line)#
Switch-01#
```

รวมถึง hostname ที่มี character พิเศษตาม platform

วิธีที่ดีกว่าคือ:

1. อ่าน initial prompt
2. เก็บ prompt ที่พบ
3. ใช้ prompt เป็น session state
4. update เมื่อเข้า/ออก mode
5. ใช้ command response เพื่อ validate

---

# 41. Prompt Discovery

หลัง login:

```text
read until idle
```

อาจได้:

```text
Router#
```

เก็บ:

```json
{
  "prompt": "Router#",
  "privilege": "privileged_exec"
}
```

ถ้าสั่ง:

```text
configure terminal
```

คาดหวัง:

```text
Router(config)#
```

ถ้าได้:

```text
Router(config)#
```

update state

---

# 42. Login Flow ที่ Robust

ตัวอย่าง:

```text
CONNECT
  ↓
READ
  ↓
detect Username?
  ├── yes → send username
  └── no
  ↓
detect Password?
  ├── yes → send password
  └── no
  ↓
detect prompt
  ↓
READY
```

แต่ไม่ควร assume ลำดับตายตัว เพราะ SSH บางระบบใช้ public key และบางระบบไม่มี username/password prompt แบบ terminal

---

# 43. Raw Log + Structured Log

แนะนำเก็บสองประเภท

## Raw session

```text
session.raw.log
```

เอาไว้ debug

## Structured command results

```json
[
  {
    "command": "show version",
    "started_at": "...",
    "ended_at": "...",
    "duration_ms": 420,
    "output": "...",
    "success": true
  }
]
```

เอาไว้ application

---

# 44. Security

ห้าม log:

```text
password
enable secret
private key
session token
```

เช่นถ้า session มี:

```text
Password: MySecret123
```

log ควร redact:

```text
Password: ********
```

หรือไม่บันทึก password prompt/input เลย

---

# 45. Credential Storage

ไม่ควร:

```json
{
  "username": "admin",
  "password": "admin123"
}
```

ใน source code

หรือ:

```python
PASSWORD = "admin123"
```

ควรใช้:

```text
OS credential store
environment secret
encrypted secret store
SSH key
interactive prompt
```

ตาม architecture ของ application

---

# 46. Concurrency

ถ้าต้อง backup 100 devices:

```text
Router01
Router02
Router03
...
Router100
```

ไม่ควรเปิด thread จำนวนมากโดยไม่มี limit

ควรมี:

```text
worker pool
max_concurrency
retry policy
per-device timeout
```

เช่น:

```json
{
  "max_concurrency": 10,
  "connect_timeout": 10,
  "command_timeout": 60,
  "retries": 2
}
```

---

# 47. Retry

ควร retry เฉพาะ error ที่ retry ได้ เช่น:

```text
connection timeout
temporary network failure
connection reset
```

ไม่ควร retry แบบไม่มีเงื่อนไขเมื่อ:

```text
authentication failed
authorization denied
invalid command
```

เพราะ retry จะไม่แก้ปัญหา

---

# 48. Idempotency

ถ้า application เป็น read-only backup tool:

```text
show ...
```

โดยทั่วไปมีผลข้างเคียงต่ำ

แต่ถ้าเป็น configuration automation:

```text
configure terminal
...
```

ต้องคิดเรื่อง idempotency อย่างจริงจัง

เพราะ command บางตัวมีผลต่อ device state

---

# 49. CLI Scraping vs Network Automation API

ถ้าจุดประสงค์เป็น:

> "ทำโปรแกรมเหมือน Tera Term ที่เชื่อมต่อ device และอ่านข้อความ CLI"

ใช้:

```text
SSH / Telnet / Serial
```

เหมาะสม

แต่ถ้าจุดประสงค์คือ:

> "ระบบจัดการ network device จำนวนมาก"

ควรพิจารณา API/automation protocol ที่อุปกรณ์รองรับ เช่น:

```text
NETCONF
RESTCONF
SNMP
vendor API
Ansible modules
```

ไม่จำเป็นต้อง scrape CLI ทุกอย่าง

---

# 50. CLI Automation เหมาะกับกรณีใด

เหมาะเมื่อ:

- device รุ่นเก่า
- มีเฉพาะ CLI
- ต้อง backup config
- ต้อง run diagnostic commands
- ต้อง automate legacy equipment
- ต้องทำงานผ่าน console
- ต้องรองรับ vendor หลายรุ่นที่ไม่มี API เดียวกัน

---

# 51. CLI Automation ไม่เหมาะเมื่อ

ถ้ามี structured API ที่เชื่อถือได้และต้องจัดการ device จำนวนมาก:

```text
CLI scraping
```

อาจเปราะบางกว่า API

เพราะ output อาจเปลี่ยน:

```text
IOS version A
IOS version B
```

format ไม่เหมือนกัน

ดังนั้น parser ต้อง version-aware ในบางกรณี

---

# 52. Vibe Coding Specification

ถ้าต้องการให้ AI coding agent สร้างโปรแกรมประเภทนี้ ควรให้ requirement แบบชัดเจน

ตัวอย่าง:

```text
Build a network terminal automation application.

Requirements:

1. Support SSH and Serial initially.
2. Provide a terminal UI.
3. Show live RX/TX data.
4. Support session logging.
5. Support structured command execution.
6. Detect login prompts.
7. Detect shell/CLI prompt.
8. Support command timeout.
9. Support paging detection.
10. Support vendor-specific drivers.
11. Never log passwords.
12. Store raw session logs separately from parsed output.
13. Allow user-defined command lists.
14. Support read-only mode.
15. Allow per-device configuration.
16. Provide reconnect functionality.
17. Provide clear error states.
18. Do not execute discovered commands automatically.
```

---

# 53. Suggested Data Model

## Device

```json
{
  "id": "router-01",
  "name": "Router01",
  "host": "192.168.1.1",
  "transport": "ssh",
  "port": 22,
  "vendor": "cisco",
  "os": "ios"
}
```

## Session

```json
{
  "device_id": "router-01",
  "session_id": "uuid",
  "connected_at": "...",
  "transport": "ssh",
  "state": "ready",
  "prompt": "Router#"
}
```

## Command Result

```json
{
  "session_id": "uuid",
  "command": "show version",
  "output": "...",
  "success": true,
  "duration_ms": 421
}
```

---

# 54. Suggested Project Structure

ตัวอย่าง:

```text
network-cli-tool/
│
├── app/
│   ├── main
│   ├── ui
│   ├── session
│   ├── terminal
│   ├── parser
│   ├── logging
│   ├── security
│   │
│   ├── transport/
│   │   ├── ssh
│   │   ├── serial
│   │   └── telnet
│   │
│   └── drivers/
│       ├── cisco_ios
│       ├── cisco_nxos
│       ├── junos
│       └── generic
│
├── configs/
├── logs/
├── backups/
└── tests/
```

---

# 55. Terminal Core API

แนะนำ API ประมาณนี้:

```python
class TerminalTransport:
    def connect(self):
        ...

    def disconnect(self):
        ...

    def write(self, data: bytes):
        ...

    def read(self, timeout=None) -> bytes:
        ...

    def is_connected(self) -> bool:
        ...
```

จากนั้น:

```python
class TerminalSession:
    def login(self):
        ...

    def detect_prompt(self):
        ...

    def execute(self, command, timeout=None):
        ...

    def close(self):
        ...
```

และ:

```python
class DeviceDriver:
    def prepare_session(self):
        ...

    def get_version(self):
        ...

    def get_running_config(self):
        ...
```

---

# 56. Event-driven Architecture

Terminal UI ไม่ควร block ขณะที่ command กำลังทำงาน

ใช้ event:

```text
DATA_RECEIVED
PROMPT_DETECTED
PAGER_DETECTED
COMMAND_STARTED
COMMAND_COMPLETED
LOGIN_PROMPT
AUTH_FAILED
CONNECTION_LOST
```

ตัวอย่าง:

```json
{
  "event": "DATA_RECEIVED",
  "timestamp": "...",
  "data": "Router# show version..."
}
```

---

# 57. Reader Loop

แนวคิด:

```python
while connected:
    data = transport.read(timeout=0.5)

    if data:
        raw_logger.write(data)

        terminal_parser.feed(data)

        events = terminal_parser.process()

        for event in events:
            event_bus.emit(event)
```

ข้อดีคือ:

- UI realtime
- logging realtime
- parser ทำงานต่อเนื่อง
- command runner ใช้ event ได้

---

# 58. อย่าให้ UI เป็นตัวควบคุม protocol โดยตรง

ไม่ควร:

```text
Button → SSH write()
```

โดยตรง

ควร:

```text
UI
 ↓
Session Manager
 ↓
Command Runner
 ↓
Transport
```

เพราะจะทำให้ test ยากและขยายระบบยาก

---

# 59. Testing

ควรมี mock transport

ตัวอย่าง:

```python
MockTransport(
    incoming=[
        "Username:",
        "Password:",
        "Router#",
        "Router# show version\r\n",
        "Cisco IOS...\r\n",
        "Router#"
    ]
)
```

แล้วทดสอบ:

```text
login
prompt detection
command execution
paging
timeout
disconnect
```

โดยไม่ต้องมี Router จริง

---

# 60. Golden Transcript Testing

เก็บ session ตัวอย่าง:

```text
fixtures/
├── cisco_login.txt
├── cisco_show_version.txt
├── cisco_paging.txt
├── cisco_config_mode.txt
└── cisco_ansi.txt
```

จากนั้น parser ต้องให้ผลเหมือนเดิมเมื่อ input เหมือนเดิม

เหมาะมากกับ CLI parser

---

# 61. Acceptance Criteria

ตัวอย่าง acceptance criteria:

```text
[ ] Connect ผ่าน SSH ได้
[ ] Connect ผ่าน Serial ได้
[ ] Detect login prompt
[ ] Detect initial CLI prompt
[ ] Send command
[ ] Receive output
[ ] Detect command completion
[ ] Handle pagination
[ ] Save raw log
[ ] Save structured output
[ ] Redact credentials
[ ] Timeout ได้
[ ] Reconnect ได้
[ ] Vendor profile แยกได้
[ ] Read-only mode
[ ] UI ไม่ค้างระหว่าง command
```

---

# 62. สิ่งที่โปรแกรม "ไม่ควรทำ"

ไม่ควร:

```text
อ่าน firmware เพื่อหา command
```

เพียงเพราะต้องการ command list

ไม่ควร:

```text
execute ทุกอย่างจาก `?`
```

ไม่ควร:

```text
ใช้ sleep(5) แล้วคิดว่า command จบ
```

ไม่ควร:

```text
ใช้ prompt "Router#" แบบ hard-code
```

ไม่ควร:

```text
เก็บ password ลง log
```

ไม่ควร:

```text
สมมติว่า output ทุก vendor เหมือน Cisco
```

---

# 63. ความแตกต่างระหว่าง "Terminal Emulator" กับ "Network Automation"

## Terminal Emulator

หน้าที่:

```text
keyboard
   ↓
terminal
   ↓
device
   ↓
output
   ↓
screen
```

เช่น Tera Term / PuTTY

## Network Automation

หน้าที่:

```text
device inventory
       ↓
connection manager
       ↓
device driver
       ↓
command runner
       ↓
parser
       ↓
structured data
       ↓
database / backup / dashboard
```

Automation จึงอยู่เหนือ Terminal Emulator อีกชั้นหนึ่ง

---

# 64. หากต้องการสร้าง "Tera Term + Network Automation" ในโปรแกรมเดียว

Architecture ที่เหมาะ:

```text
                    ┌─────────────────┐
                    │       UI        │
                    └────────┬────────┘
                             │
             ┌───────────────┴───────────────┐
             │                               │
             ▼                               ▼
      Interactive Terminal            Automation Engine
             │                               │
             └───────────────┬───────────────┘
                             ▼
                       Session Manager
                             │
                  ┌──────────┴──────────┐
                  ▼                     ▼
             Device Driver          Transport
                  │                     │
                  └──────────┬──────────┘
                             ▼
                        Router/Switch
```

Interactive Terminal:

```text
User types command manually
```

Automation Engine:

```text
Application sends predefined commands
```

แต่ทั้งสองใช้:

```text
Session Manager
Transport
Terminal Parser
```

ร่วมกัน

---

# 65. ตัวอย่าง End-to-End

สมมติ:

```text
Device:
Cisco Router

IP:
192.168.1.1

Protocol:
SSH
```

Application:

```text
1. TCP connect 192.168.1.1:22
2. SSH handshake
3. Authenticate
4. Read initial prompt
5. Detect:
      Router>
6. Send:
      enable
7. Detect:
      Password:
8. Send enable secret
9. Detect:
      Router#
10. Send:
      terminal length 0
11. Detect:
      Router#
12. Send:
      show version
13. Read bytes
14. Detect:
      Router#
15. Store command result
16. Send:
      show ip interface brief
17. Read
18. Detect prompt
19. Store result
20. Send:
      show running-config
21. Handle large output
22. Detect prompt
23. Save backup
24. Disconnect
```

---

# 66. ผลลัพธ์ที่ควรได้

```text
output/
└── Router01/
    ├── session.raw.log
    ├── metadata.json
    ├── show-version.txt
    ├── show-ip-interface-brief.txt
    └── running-config.txt
```

และ:

```json
{
  "device": "Router01",
  "status": "success",
  "commands_executed": 4,
  "duration_ms": 3820
}
```

---

# 67. สรุปแบบจำง่ายที่สุด

Tera Term / PuTTY:

```text
Keyboard
   ↓
Terminal Emulator
   ↓
SSH / Telnet / Serial
   ↓
Router/Switch CLI
   ↓
Command Parser
   ↓
Command Execution
   ↓
Output
   ↓
SSH / Telnet / Serial
   ↓
Terminal Emulator
   ↓
Screen / Log
```

ดังนั้น:

```text
Tera Term ≠ Database ของ Cisco Commands
PuTTY    ≠ Database ของ Cisco Commands
```

แต่:

```text
Tera Term / PuTTY
=
Terminal + Transport + Display + Logging
```

ส่วน:

```text
Router/Switch
=
CLI + Command Parser + Command Execution + Configuration
```

และถ้าจะสร้างโปรแกรมแบบ Tera Term ที่ "ดึงข้อมูล CLI อัตโนมัติ":

```text
Transport
   +
Session Manager
   +
Prompt Detector
   +
Pager Handler
   +
Command Runner
   +
Terminal Parser
   +
Device Driver
   +
Logger
   +
Security
```

คือส่วนประกอบหลัก

---

# 68. Prompt สำหรับ Vibe Coding Agent

สามารถนำส่วนนี้ไปใช้กับ AI Coding Agent ได้โดยตรง:

```text
Create a production-oriented network CLI automation application.

Goal:
Build a terminal/automation tool similar in concept to Tera Term/PuTTY, but designed specifically for network device management.

Core principle:
The application must NOT assume that it owns the device CLI command database.
The router/switch owns the CLI parser and command set.
The application communicates through SSH, Serial, or Telnet and processes the byte/character stream returned by the device.

Architecture:
- UI
- Session Manager
- Transport abstraction
- SSH transport
- Serial transport
- Optional Telnet transport
- Terminal parser
- ANSI/control-sequence parser
- Prompt detector
- Paging handler
- Command runner
- Device-driver abstraction
- Raw session logger
- Structured command logger
- Credential/security layer

Functional requirements:
1. SSH connection.
2. Serial console connection.
3. Interactive terminal.
4. Session recording.
5. Structured command execution.
6. Dynamic prompt detection.
7. Login prompt detection.
8. Privilege/enable handling.
9. Paging handling.
10. Command timeout.
11. Connection timeout.
12. Reconnect.
13. Raw byte/session logging.
14. Clean output extraction.
15. Per-command structured results.
16. Vendor-specific device profiles.
17. Read-only mode.
18. Credential redaction.
19. Mock transport for testing.
20. Golden transcript parser tests.

Do not:
- hard-code one prompt such as Router#
- assume all devices are Cisco
- assume all devices use CRLF
- use fixed sleep as the only command-completion mechanism
- execute every command discovered through `?`
- store passwords in logs
- store passwords in source code
- assume `?` returns every possible executable command
- mix UI code directly with SSH/Serial protocol code

Command execution flow:

send(command)
→ read byte stream
→ decode terminal data
→ append raw log
→ detect paging
→ handle paging
→ detect prompt
→ determine completion
→ clean output
→ return structured result

Example result:

{
  "command": "show version",
  "success": true,
  "output": "...",
  "prompt_before": "Router#",
  "prompt_after": "Router#",
  "duration_ms": 420
}

Implement the system so that the same command runner can work with SSH and Serial without changing device CLI logic.

Use vendor adapters for device-specific behavior such as:
- login flow
- prompt patterns
- paging disable command
- terminal width
- privilege escalation
- configuration retrieval
- output normalization

Start with a generic driver and a Cisco IOS/IOS XE driver.

Prioritize correctness, robust stream handling, security, testability, and clean separation of concerns.
```

---

# 69. Final Concept

ถ้าจะจำเพียงประโยคเดียว:

> **Tera Term/PuTTY ไม่ได้ "ดึง command จาก Router" แต่เปิดช่องทางสื่อสารกับ CLI ของ Router แล้วส่ง/รับ byte stream; ถ้าต้องการดึงข้อมูล เราต้องสั่ง command ให้ Router ประมวลผล แล้ว capture output ที่ Router ส่งกลับมา**

และถ้าจะทำโปรแกรมให้เหนือกว่า Tera Term/PuTTY:

```text
Terminal Emulator
        +
Command Runner
        +
Prompt/Pager Parser
        +
Device Driver
        +
Structured Data
        +
Automation
        +
Security
```

นี่คือแกนหลักของระบบที่ควรนำไป Vibe Coding
